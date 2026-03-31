from __future__ import annotations

import time
import timeit
import logging
from logging import INFO
from typing import Any

from flwr.common import ConfigsRecord, Context
from flwr.common.logger import log
from flwr.server import LegacyContext
from flwr.server.compat.app_utils import start_update_client_manager_thread
from flwr.server.driver import Driver
from flwr.server.workflow.constant import MAIN_CONFIGS_RECORD, Key as WorkflowKey
from flwr.server.workflow.default_workflows import (
    default_centralized_evaluation_workflow,
    default_evaluate_workflow,
    default_fit_workflow,
    default_init_params_workflow,
)

from common.config import QUORUM_WAIT_TIMEOUT, SESSION_COOLDOWN_SECONDS, SESSION_STALL_TIMEOUT_SECONDS
from .state import get_state_store

LOGGER = logging.getLogger(__name__)


class EventDrivenWorkflow:
    def __init__(
        self,
        fit_workflow: Any | None = None,
        evaluate_workflow: Any | None = None,
        idle_sleep: float = 1.0,
    ) -> None:
        self.fit_workflow = fit_workflow or default_fit_workflow
        self.evaluate_workflow = evaluate_workflow or default_evaluate_workflow
        self.idle_sleep = idle_sleep
        self.state_store = get_state_store()

    def __call__(self, driver: Driver, context: Context) -> None:
        if not isinstance(context, LegacyContext):
            raise TypeError(f"Expect a LegacyContext, but get {type(context).__name__}.")

        thread, f_stop = start_update_client_manager_thread(driver, context.client_manager)

        try:
            self.state_store.set_training_started_at()
            self.state_store.set_training_status("initializing")
            log(INFO, "[INIT]")
            default_init_params_workflow(driver, context)
            self.state_store.set_training_status("idle")

            cfg = ConfigsRecord()
            cfg[WorkflowKey.START_TIME] = timeit.default_timer()
            context.state.configs_records[MAIN_CONFIGS_RECORD] = cfg

            current_round = 0
            idle_time = 0.0
            last_session_end_time = 0.0
            # Track whether the current session start is a cold start (vs. a restart
            # after abort). We only run the quorum accumulation window on cold starts
            # so that restart sessions don't incur unnecessary latency.
            _is_cold_start = True
            target_rounds = int(getattr(getattr(context, "config", None), "num_rounds", 1))

            while True:
                desired_status = self.state_store.get_desired_training_status()
                if desired_status != "running":
                    self.state_store.set_training_status(desired_status)
                    LOGGER.info("Training loop waiting because desired status is %s", desired_status)
                    time.sleep(self.idle_sleep)
                    idle_time = 0.0
                    continue

                # Session Cooldown Gate
                if current_round == 0 and last_session_end_time > 0.0:
                    elapsed_since_end = timeit.default_timer() - last_session_end_time
                    if elapsed_since_end < SESSION_COOLDOWN_SECONDS:
                        self.state_store.set_training_status("cooldown")
                        time.sleep(self.idle_sleep)
                        continue

                next_round = current_round + 1
                if hasattr(context.strategy, "has_pending_round"):
                    should_start = context.strategy.has_pending_round(next_round, context.client_manager)
                else:
                    should_start = context.client_manager.num_available() > 0

                if not should_start:
                    if current_round > 0:
                        idle_time += self.idle_sleep
                        if idle_time >= SESSION_STALL_TIMEOUT_SECONDS:
                            LOGGER.warning(
                                "Session stalling due to missing clients (>%.0fs). Aborting session.",
                                SESSION_STALL_TIMEOUT_SECONDS,
                            )
                            if hasattr(context.strategy, "abort_training_session"):
                                context.strategy.abort_training_session()
                            current_round = 0
                            _is_cold_start = False  # restart — skip quorum window
                            self.state_store.set_training_round(0)
                            idle_time = 0.0
                            self.state_store.set_training_status("idle")
                            continue
                    else:
                        idle_time += self.idle_sleep
                        if int(idle_time) > 0 and int(idle_time) % 30 == 0 and int(idle_time - self.idle_sleep) % 30 != 0:
                            num_avail = context.client_manager.num_available()
                            LOGGER.info("Waiting for more clients to begin session... (%s connected)", num_avail)

                    self.state_store.set_training_status("idle")
                    time.sleep(self.idle_sleep)
                    continue
                else:
                    # Quorum Accumulation Window — only on cold starts, not restarts.
                    # On a restart, reconnecting clients are already known, so waiting
                    # for late joiners only adds unnecessary delay.
                    if current_round == 0 and _is_cold_start:
                        LOGGER.info("Quorum threshold met. Waiting %ss for late joiners...", QUORUM_WAIT_TIMEOUT)
                        wait_start = timeit.default_timer()
                        while timeit.default_timer() - wait_start < QUORUM_WAIT_TIMEOUT:
                            time.sleep(self.idle_sleep)
                            context.strategy.poll_ready_updates(1, context.client_manager)

                    idle_time = 0.0

                current_round = next_round
                cfg[WorkflowKey.CURRENT_ROUND] = current_round
                self.state_store.set_training_round(current_round)
                self.state_store.set_training_status("running")
                log(INFO, "")
                log(INFO, "[ROUND %s]", current_round)

                round_success = False
                try:
                    self.fit_workflow(driver, context)
                    default_centralized_evaluation_workflow(driver, context)
                    self.evaluate_workflow(driver, context)
                    round_success = True
                except Exception as exc:
                    LOGGER.error("Round %s failed due to error: %s", current_round, exc)
                    LOGGER.info(
                        "Client dropout or error detected. Session aborted. "
                        "A new %s-round session will begin from the latest checkpoint.",
                        target_rounds,
                    )
                    self.state_store.set_training_status("idle")
                    current_round = 0
                    _is_cold_start = False  # restart — skip quorum window
                    self.state_store.set_training_round(0)
                    if hasattr(context.strategy, "abort_training_session"):
                        context.strategy.abort_training_session()
                    time.sleep(self.idle_sleep)
                    continue

                if round_success and current_round >= target_rounds:
                    if hasattr(context.strategy, "complete_training_session"):
                        completed_hashes = context.strategy.complete_training_session()
                        LOGGER.info(
                            "Completed training session after %s rounds; finalized %s dataset hashes",
                            target_rounds,
                            len(completed_hashes),
                        )
                    current_round = 0
                    _is_cold_start = True   # next session is a fresh cold start
                    last_session_end_time = timeit.default_timer()
                    self.state_store.set_training_started_at()
                    self.state_store.set_training_round(0)
                self.state_store.set_training_status("idle")
        finally:
            self.state_store.set_training_status("stopped")
            f_stop.set()
            thread.join()
