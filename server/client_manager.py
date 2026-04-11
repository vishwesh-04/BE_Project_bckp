from __future__ import annotations

import logging
import threading
from typing import Dict, Set

from flwr.server.client_manager import SimpleClientManager
from flwr.server.client_proxy import ClientProxy

LOGGER = logging.getLogger(__name__)


class StatefulClientManager(SimpleClientManager):
    """
    Custom ClientManager that tracks extended client states (IDLE, READY, WAITING, ACTIVE)
    and robustly handles disconnects/reconnects to prevent stale state bugs.
    """

    def __init__(self) -> None:
        super().__init__()
        self.active_clients: Set[str] = set()
        self.cycle_clients: Set[str] = set()
        self.waiting_pool: Set[str] = set()
        self.round_mappings: Dict[int, Set[str]] = {}
        self.client_state: Dict[str, str] = {}
        
        # We need a lock to protect our custom state dictionary updates
        self._state_lock = threading.RLock()

    def register(self, client: ClientProxy) -> bool:
        """Register client and (re)initialize its state to IDLE.

        Flower calls this on *every* connection — including reconnects.  We
        intentionally reset to IDLE on every call so that:
        - stale READY/ACTIVE state from a previous session is never preserved
        - the state dict always has an entry for any connected client

        The client is promoted to READY on the next poll_ready_updates() cycle
        once get_properties() confirms it is ready.
        """
        is_new = super().register(client)
        with self._state_lock:
            cid = client.cid
            prev_state = self.client_state.get(cid)
            # Clean stale round/pool state before writing new IDLE.
            self._clean_stale_state(cid)
            self.client_state[cid] = "IDLE"
            if prev_state is not None and prev_state != "IDLE":
                # Client re-registered while it had non-IDLE state — this is a
                # reconnect after an unexpected disconnect (e.g. network blip).
                LOGGER.info(
                    "Client %s reconnected (was %s) — state reset to IDLE. "
                    "Will be re-promoted to READY on next readiness poll.",
                    cid, prev_state,
                )
            else:
                LOGGER.info("Client %s registered — state initialized to IDLE.", cid)
        return is_new

    def unregister(self, client: ClientProxy) -> None:
        """Unregister client and aggressively clean up all its state mappings."""
        with self._state_lock:
            cid = client.cid
            self._clean_stale_state(cid)
            self.client_state.pop(cid, None)
            LOGGER.info("Client %s unregistered and all active states purged.", cid)

        super().unregister(client)

    def _ensure_state_entry(self, client_id: str) -> None:
        """Guarantee a state dict entry exists for the given client_id.

        Called as a safety-net before any state-mutating operation.  If the
        entry is missing (can happen in edge-case races between register() and
        the first poll cycle) we default to IDLE rather than leaving the dict
        in an inconsistent state.
        """
        if client_id not in self.client_state:
            LOGGER.debug(
                "_ensure_state_entry: client %s had no state entry; defaulting to IDLE.",
                client_id,
            )
            self.client_state[client_id] = "IDLE"

    def _clean_stale_state(self, cid: str) -> None:
        """Internal helper to remove a client from all tracking structures."""
        self.active_clients.discard(cid)
        self.cycle_clients.discard(cid)
        self.waiting_pool.discard(cid)
        
        for round_num, clients_in_round in list(self.round_mappings.items()):
            if cid in clients_in_round:
                clients_in_round.discard(cid)
                if not clients_in_round:
                    del self.round_mappings[round_num]

    def set_ready(self, client_id: str) -> bool:
        """
        Mark a client as READY to participate in rounds.

        Requirements met:
        - Idempotent: returns True if already READY or WAITING
        - Independence: does not depend on old round/session state
        - Guarded: client must not be in any active round
        - Reconnect-safe: works even if state dict entry was briefly absent
        """
        with self._state_lock:
            # Guard: client must actually be connected (in Flower's live registry).
            # We deliberately check self.clients (the live proxy dict maintained by
            # SimpleClientManager) rather than self.client_state because after a
            # reconnect there is a brief window where self.clients is updated but
            # self.client_state may not yet have been written (e.g. if register()
            # lost the race).  _ensure_state_entry() closes that gap.
            if client_id not in self.clients and client_id not in self.client_state:
                LOGGER.warning(
                    "set_ready: client %s is not connected — cannot mark ready.",
                    client_id,
                )
                return False

            # Ensure a state dict entry always exists before we read it.
            self._ensure_state_entry(client_id)
            current_state = self.client_state[client_id]

            # Idempotent success
            if current_state in ["READY", "WAITING"]:
                LOGGER.debug(
                    "set_ready idempotent success for %s (already %s)",
                    client_id, current_state,
                )
                return True

            # Guard: must not be locked in an active round (SecAgg safety).
            for round_num, clients_in_round in self.round_mappings.items():
                if client_id in clients_in_round:
                    LOGGER.warning(
                        "set_ready failed: client %s is locked in active round %s.",
                        client_id, round_num,
                    )
                    return False

            # Transition to READY.
            self.client_state[client_id] = "READY"
            self.waiting_pool.add(client_id)
            LOGGER.info("Client %s: %s → READY.", client_id, current_state)
            return True

    def assign_to_round(self, client_id: str, round_num: int) -> bool:
        """Helper to safely transition a ready client into an active round."""
        with self._state_lock:
            if self.client_state.get(client_id) not in ["READY", "WAITING"]:
                return False

            self.waiting_pool.discard(client_id)
            self.active_clients.add(client_id)
            self.cycle_clients.add(client_id)

            if round_num not in self.round_mappings:
                self.round_mappings[round_num] = set()
            self.round_mappings[round_num].add(client_id)

            self.client_state[client_id] = "ACTIVE"
            LOGGER.debug("Client %s assigned to round %s (state: ACTIVE).", client_id, round_num)
            return True

    def complete_round(self, client_id: str, round_num: int) -> None:
        """
        Transition a client from ACTIVE → READY after successfully completing a round.
        Called by aggregate_fit() for each client whose results were used.
        """
        with self._state_lock:
            if self.client_state.get(client_id) != "ACTIVE":
                return

            # Remove from round tracking
            if round_num in self.round_mappings:
                self.round_mappings[round_num].discard(client_id)
                if not self.round_mappings[round_num]:
                    del self.round_mappings[round_num]

            self.active_clients.discard(client_id)
            self.cycle_clients.discard(client_id)
            self.waiting_pool.add(client_id)
            self.client_state[client_id] = "READY"
            LOGGER.debug("Client %s completed round %s (state: READY).", client_id, round_num)

    def mark_not_ready(self, client_id: str) -> None:
        """
        Transition a client to IDLE regardless of current state.
        Called when:
          - get_properties() returns ready=False (client muted / missing-data)
          - get_properties() raises an exception (client unreachable)
          - aggregate_fit() receives a skipped (not_ready=1) result

        This does NOT disconnect the client — it only resets the scheduling
        state so the server stops selecting it for rounds until it reports
        ready=True again on the next poll cycle.
        """
        with self._state_lock:
            if client_id not in self.client_state:
                return

            # Only log if we're actually changing state (avoid spam on every poll)
            current = self.client_state.get(client_id)
            if current != "IDLE":
                LOGGER.info("Client %s: %s → IDLE (not-ready).", client_id, current)

            # Clear from active round tracking
            self._clean_stale_state(client_id)
            self.client_state[client_id] = "IDLE"
