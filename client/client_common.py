from __future__ import annotations

import hashlib
import logging
import os
import threading
from enum import Enum
from typing import Any, Callable, Optional

import numpy as np
import torch
import torch.nn as nn
from flwr.client import NumPyClient
from torch.utils.data import DataLoader, TensorDataset

from common.config import (
    CLIENT_DP_ENABLED,
    L2_NORM_CLIP,
    NOISE_MULTIPLIER,
)
from common.data_loader import load_local_data
from common.network import NeuralNetworkAlgo

LOGGER = logging.getLogger(__name__)


class ClientReadyState(str, Enum):
    """
    Authoritative states a client can be in.

    READY       — idle, data present, not muted; participates in rounds.
    BUSY        — currently executing fit() or evaluate(); cannot be muted.
    MUTED       — user has voluntarily opted out; rounds are skipped.
    MISSING_DATA — train-data file absent; client cannot participate.
    """
    READY = "ready"
    BUSY = "busy"
    MUTED = "muted"
    MISSING_DATA = "missing_data"


class FLClientRuntime(NumPyClient):
    def __init__(
        self,
        client_id: str,
        train_path: str,
        test_path: str,
        algo: NeuralNetworkAlgo,
        use_personalization: bool = False,
        local_epochs: int = 3,
        batch_size: int = 32,
        learning_rate: float = 0.001,
        # ------------------------------------------------------------------
        # Optional UI callback hooks — call notification to the Client UI.
        # on_training_start(): called when fit() begins a local training run.
        # on_training_end(success: bool): called when fit() completes/fails.
        # Both default to None; headless usage is completely unaffected.
        # ------------------------------------------------------------------
        on_training_start: Optional[Callable[[int], None]] = None,
        on_training_end: Optional[Callable[[bool], None]] = None,
        on_evaluate: Optional[Callable[[float, float], None]] = None,
    ):
        self.client_id = str(client_id)
        self.train_path = train_path
        self.test_path = test_path
        self.algo = algo
        self.device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
        self.use_personalization = use_personalization
        self.local_epochs = local_epochs
        self.batch_size = batch_size
        self.learning_rate = learning_rate
        self._on_training_start = on_training_start
        self._on_training_end = on_training_end
        self._on_evaluate = on_evaluate

        # ------------------------------------------------------------------
        # Thread-safe state:
        #   _busy_lock  — RLock held while fit/evaluate is running; mute()
        #                  attempts to acquire it (non-blocking) to detect BUSY.
        #   _muted      — Event whose *cleared* state means muted:
        #                  set   → NOT muted (normal operation)
        #                  clear → muted (skip rounds)
        # Using an Event lets the gRPC thread (which owns the lock) never
        # race with the UI thread (which calls mute/unmute).
        # ------------------------------------------------------------------
        self._busy_lock = threading.RLock()
        self._muted = threading.Event()
        self._muted.set()   # start: NOT muted

    # ------------------------------------------------------------------
    # Public mute / unmute API (safe to call from any thread)
    # ------------------------------------------------------------------

    def mute(self) -> bool:
        """
        Request the client to opt out of future rounds.

        Returns True if the state changed to MUTED.
        Returns False if the client is currently BUSY (mid-training) — the
        caller should re-try or notify the user that they must wait.

        Deliberately NOT cached permanently: calling unmute() reverses it.
        """
        if not self._busy_lock.acquire(blocking=False):
            LOGGER.warning("mute() rejected: client is currently busy in a training round.")
            return False
        try:
            self._muted.clear()
            LOGGER.info("Client %s: state changed to MUTED.", self.client_id)
            return True
        finally:
            self._busy_lock.release()

    def unmute(self) -> None:
        """
        Re-enable participation in future rounds.
        Always succeeds (even if currently BUSY — unmute is always safe).
        """
        self._muted.set()
        LOGGER.info("Client %s: state changed to READY.", self.client_id)

    @property
    def is_muted(self) -> bool:
        return not self._muted.is_set()

    # ------------------------------------------------------------------
    # Legacy shim: allow controller code that previously set
    # `client.stop_requested = True/False` to still work, by routing
    # through mute() / unmute(). Non-blocking — mute may silently fail
    # if BUSY, which is the correct safe behaviour.
    # ------------------------------------------------------------------

    @property
    def stop_requested(self) -> bool:
        return self.is_muted

    @stop_requested.setter
    def stop_requested(self, value: bool) -> None:
        if value:
            self.mute()
        else:
            self.unmute()

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _data_hash(self) -> str:
        if not self.train_path or not os.path.exists(self.train_path):
            return ""
        digest = hashlib.sha256()
        with open(self.train_path, "rb") as file:
            for chunk in iter(lambda: file.read(1024 * 1024), b""):
                digest.update(chunk)
        return digest.hexdigest()

    def _ready_state(self) -> tuple[bool, ClientReadyState]:
        """
        Evaluate the client's current readiness without side-effects.

        Priority:
          1. MISSING_DATA  — hard gate, always checked first.
          2. MUTED         — in-process mute toggle (_muted Event).
          3. BUSY          — currently in a training call (reentrancy guard).
          4. READY         — all clear.
        """
        if not self.train_path or not os.path.exists(self.train_path):
            LOGGER.warning(
                "Client %s: training data not found at '%s' — status=MISSING_DATA. "
                "Ensure CLIENT_ID and CLIENT_{id}_TRAINING_SET are set correctly.",
                self.client_id, self.train_path,
            )
            return False, ClientReadyState.MISSING_DATA

        # Single source of truth: the in-process _muted Event.
        # (The sidecar file was removed to eliminate the dual-truth race condition.)
        if self.is_muted:
            return False, ClientReadyState.MUTED

        # Use non-blocking acquire to detect BUSY without risking deadlock.
        # If we can acquire the lock the client is idle (READY).
        acquired = self._busy_lock.acquire(blocking=False)
        if not acquired:
            return False, ClientReadyState.BUSY
        self._busy_lock.release()

        return True, ClientReadyState.READY

    def get_properties(self, config: dict[str, Any]) -> dict[str, Any]:
        ready, state = self._ready_state()
        return {
            "client_id": self.client_id,
            "data_hash": self._data_hash(),
            "ready": ready,
            "status": state.value,
        }

    def get_parameters(self, config: dict[str, Any]):
        return self.algo.get_weights()

    def _make_private_loader(self, dataset: TensorDataset, seed: int | None = None):
        train_loader = DataLoader(dataset, batch_size=self.batch_size, shuffle=True)
        optimizer = torch.optim.Adam(self.algo.model.parameters(), lr=self.learning_rate)
        if not CLIENT_DP_ENABLED:
            return self.algo.model, optimizer, train_loader

        try:
            from opacus import PrivacyEngine
        except Exception:
            return self.algo.model, optimizer, train_loader

        privacy_engine = PrivacyEngine()
        model, optimizer, private_loader = privacy_engine.make_private(
            module=self.algo.model,
            optimizer=optimizer,
            data_loader=train_loader,
            noise_multiplier=NOISE_MULTIPLIER,
            max_grad_norm=L2_NORM_CLIP,
            seed=seed,
        )
        return model, optimizer, private_loader

    def _train_model(self, train_path: str, data_hash: str | None = None):
        """Train local model and return (x_data, y_data)."""
        x_data, y_data = load_local_data(train_path)
        x_tensor = torch.from_numpy(x_data).float()
        y_tensor = torch.from_numpy(y_data).float().reshape(-1, 1)
        dataset = TensorDataset(x_tensor, y_tensor)

        dp_seed = int(data_hash[:8], 16) if data_hash else None
        model, optimizer, train_loader = self._make_private_loader(dataset, seed=dp_seed)

        model.train()
        criterion = nn.BCELoss()
        for _ in range(self.local_epochs):
            if self.is_muted:
                # Mid-training mute request: finish epoch gracefully then stop
                LOGGER.info("Client %s: mute requested mid-training; stopping after current epoch.", self.client_id)
                break
            for batch_x, batch_y in train_loader:
                batch_x = batch_x.to(self.device)
                batch_y = batch_y.to(self.device)
                optimizer.zero_grad()
                outputs = model(batch_x)
                loss = criterion(outputs, batch_y)
                loss.backward()
                optimizer.step()

        if self.use_personalization and not self.is_muted:
            self._personalize_head(dataset)

        return x_data, y_data

    def _personalize_head(self, dataset: TensorDataset) -> None:
        named_params = list(self.algo.model.named_parameters())
        trainable_from = max(0, len(named_params) - 2)
        for idx, (_, param) in enumerate(named_params):
            param.requires_grad = idx >= trainable_from

        optimizer = torch.optim.Adam(
            filter(lambda param: param.requires_grad, self.algo.model.parameters()),
            lr=self.learning_rate,
        )
        loader = DataLoader(dataset, batch_size=self.batch_size, shuffle=True)
        criterion = nn.BCELoss()
        self.algo.model.train()
        for batch_x, batch_y in loader:
            batch_x = batch_x.to(self.device)
            batch_y = batch_y.to(self.device)
            optimizer.zero_grad()
            outputs = self.algo.model(batch_x)
            loss = criterion(outputs, batch_y)
            loss.backward()
            optimizer.step()

        for _, param in self.algo.model.named_parameters():
            param.requires_grad = True

    def fit(self, parameters, config: dict[str, Any]):
        ready, state = self._ready_state()
        if not ready:
            LOGGER.info(
                "Client %s: skipping fit — state=%s",
                self.client_id, state.value,
            )
            return self.algo.get_weights(), 0, {
                "skipped": True,
                "not_ready": 1,
                "status": state.value,
            }

        data_hash = self._data_hash()

        # Acquire the busy lock for the duration of training.
        # This blocks mute() from succeeding mid-training, enforcing
        # the "can't mute while training" guarantee.
        with self._busy_lock:
            server_round = config.get("server_round", 0)
            if self._on_training_start is not None:
                try:
                    self._on_training_start(int(server_round))
                except Exception as exc:
                    LOGGER.debug("on_training_start callback error: %s", exc)
            try:
                base_weights = [np.asarray(layer, dtype=np.float32) for layer in parameters]
                self.algo.set_weights(base_weights)
                x_data, _ = self._train_model(self.train_path, data_hash=data_hash)
                trained_weights = self.algo.get_weights()
                if self._on_training_end is not None:
                    try:
                        self._on_training_end(True)
                    except Exception as exc:
                        LOGGER.debug("on_training_end callback error: %s", exc)
                return trained_weights, len(x_data), {
                    "skipped": False,
                    "not_ready": 0,
                    "status": ClientReadyState.READY.value,
                    "data_hash": data_hash,
                }
            except Exception:
                if self._on_training_end is not None:
                    try:
                        self._on_training_end(False)
                    except Exception as exc:
                        LOGGER.debug("on_training_end callback error: %s", exc)
                raise

    def evaluate(self, parameters, config: dict[str, Any]):
        ready, state = self._ready_state()
        if not ready:
            LOGGER.info(
                "Client %s: skipping evaluate — state=%s",
                self.client_id, state.value,
            )
            return 0.0, 0, {
                "accuracy": 0.0,
                "skipped": True,
                "not_ready": 1,
                "status": state.value,
            }

        self.algo.set_weights(parameters)
        loss, acc = self.algo.test(self.test_path)
        _, y_data = load_local_data(self.test_path)
        
        if self._on_evaluate is not None:
            try:
                self._on_evaluate(float(loss), float(acc))
            except Exception as exc:
                LOGGER.debug("on_evaluate callback error: %s", exc)
                
        return float(loss), len(y_data), {
            "accuracy": float(acc),
            "skipped": False,
            "not_ready": 0,
            "status": ClientReadyState.READY.value,
        }
