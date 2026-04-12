import logging
import traceback
from typing import Any, Mapping, Optional

from PySide6.QtCore import QObject, Signal, Slot, QThread
import grpc

# Import from the client module
from client.client_common import FLClientRuntime
from client.inference_engine import predict_from_inputs, PredictionResult, get_model_info
from common.config import CLIENT_ID, get_client_dataset_paths, get_input_dim
from common.network import NeuralNetworkAlgo


class QtLogHandler(logging.Handler):
    def __init__(self, emit_func):
        super().__init__()
        self.emit_func = emit_func

    def emit(self, record):
        msg = self.format(record)
        self.emit_func(msg)

LOGGER = logging.getLogger(__name__)


class InferenceWorker(QObject):
    """Worker running on a background QThread to perform Inference tasks."""
    prediction_result = Signal(object)

    @Slot(dict)
    def run_prediction(self, inputs: Mapping[str, float]):
        try:
            model_info = get_model_info()
            if not model_info.get("available", False):
                raise FileNotFoundError(
                    "No federated model artifact found yet. Run at least one successful training round first."
                )
            result: PredictionResult = predict_from_inputs(inputs)
            self.prediction_result.emit(result)
        except Exception as e:
            err_msg = f"Inference engine failed: {str(e)}"
            LOGGER.error(err_msg)
            self.prediction_result.emit(e)


class ShapWorker(QObject):
    """Worker running on a background QThread to perform SHAP tasks."""
    shap_result = Signal(object)

    @Slot(object)
    def run_shap(self, data: Any):
        # Placeholder for SHAP logic integration
        try:
            # result = compute_shap(data)
            self.shap_result.emit({"status": "success", "data": "SHAP analysis complete"})
        except Exception as e:
            err_msg = f"SHAP engine failed: {str(e)}"
            LOGGER.error(err_msg)
            self.shap_result.emit(e)


class FLSystemWorker(QObject):
    """
    Worker running on a background QThread to perform Federated Learning execution.

    Reconnection handling:
    Each call to start_fl_client() issues a fresh gRPC connection.
    If the client was previously running (even on the same URL), the old
    state is discarded and a new session is established.  This ensures a
    clean slate after service restarts or network interruptions without
    requiring an explicit disconnect step.
    """
    training_started = Signal()
    training_ended = Signal(bool)
    fl_client_started = Signal()
    fl_client_stopped = Signal(bool, str)  # success, message
    mute_rejected = Signal()              # emitted when mute() fails (client is mid-training)
    log_message = Signal(str)

    def __init__(self):
        super().__init__()
        self.train_path, self.test_path = get_client_dataset_paths(CLIENT_ID)
        self.input_dim = get_input_dim()
        self.client_id = CLIENT_ID

        self.fl_client: Optional[FLClientRuntime] = None

        # Setup logging redirection for our worker thread
        handler = QtLogHandler(self._emit_log)
        handler.setFormatter(logging.Formatter('[%(levelname)s] %(message)s'))
        logging.getLogger("flwr").addHandler(handler)
        logging.getLogger("client").addHandler(handler)
        LOGGER.addHandler(handler)

    def _emit_log(self, msg: str):
        self.log_message.emit(msg)

    def _create_client(self, local_epochs: int = 3, batch_size: int = 32, lr: float = 0.001) -> FLClientRuntime:
        """Helper to create FLClientRuntime with GUI signals bound."""
        return FLClientRuntime(
            client_id=str(self.client_id),
            train_path=str(self.train_path),
            test_path=str(self.test_path),
            algo=NeuralNetworkAlgo(input_dim=self.input_dim),
            use_personalization=False,
            local_epochs=local_epochs,
            batch_size=batch_size,
            learning_rate=lr,
            on_training_start=self._on_training_start_callback,
            on_training_end=self._on_training_end_callback,
        )

    def _on_training_start_callback(self):
        self.training_started.emit()

    def _on_training_end_callback(self, success: bool):
        self.training_ended.emit(success)

    @Slot(str, int, int, float)
    def start_fl_client(self, server_address: str, local_epochs: int, batch_size: int, lr: float):
        """
        Starts the Flower client, always issuing a fresh gRPC connection.

        A new FLClientRuntime is created on every call so that:
          1. Reconnections after a service restart get a clean state.
          2. Updated hyperparameters (epochs, batch-size, lr) are applied.
          3. Any mute state from a previous session is cleared.

        The previous client is cleanly unmuted first so its _busy_lock is
        released before we discard it (avoids holding a lock on a zombie obj).
        """
        # Tear down any previous client cleanly so its lock is released.
        if self.fl_client is not None:
            try:
                self.fl_client.unmute()  # ensure no lingering mute flag
            except Exception:
                pass
            self.fl_client = None

        LOGGER.info(
            "Connecting FL Client to %s | EPOCHS=%d BFS=%d LR=%.4f",
            server_address, local_epochs, batch_size, lr,
        )
        self.fl_client = self._create_client(local_epochs, batch_size, lr)
        self.fl_client_started.emit()

        import signal as _signal
        original_signal = _signal.signal
        try:
            # Mock signal handler to prevent ValueError from main-thread requirement
            _signal.signal = lambda *a, **kw: None

            # ------------------------------------------------------------------
            # Use _start_client_internal with a load_client_app_fn so the
            # real ClientApp (with secaggplus_mod) is used for every message.
            # Flower's internal _start_client_internal wraps everything in the
            # lazy-loaded ClientApp; our factory below captures fl_client so
            # the per-invocation FLClientRuntime instance is used.
            # ------------------------------------------------------------------
            from flwr.client.app import _start_client_internal
            from flwr.client import ClientApp
            from flwr.client.mod import secaggplus_mod
            from common.config import SECAGG_ENABLED

            fl_client_ref = self.fl_client  # local snapshot for the closure

            def _load_client_app(_fab_id: str, _fab_version: str) -> ClientApp:
                """
                Factory called by Flower each time it needs a ClientApp.
                We return the same app instance but ensure the client_fn
                closure always routes to the current fl_client instance.
                """
                def _client_fn(context):  # noqa: ANN001
                    return fl_client_ref.to_client()

                mods = [secaggplus_mod] if SECAGG_ENABLED else []
                return ClientApp(client_fn=_client_fn, mods=mods)

            if self.fl_client is not None:
                try:
                    # In newer flwr versions, start_client transport defaults to 'grpc-bidi'
                    # which is compatible with older versions of start_server
                    _start_client_internal(
                        server_address=server_address,
                        node_config={},
                        load_client_app_fn=_load_client_app,
                        insecure=True,
                        transport="grpc-bidi",
                        # Allow unlimited reconnect retries so the client survives
                        # transient server restarts without terminating the UI.
                        max_retries=None,
                        max_wait_time=None,
                    )
                    self.fl_client_stopped.emit(True, "Disconnected normally.")
                except Exception as e:
                    # Flower often raises a custom Exception or MultiThreadedRendezvous inside start_client
                    err_str = str(e)
                    
                    if "StatusCode.UNAVAILABLE" in err_str:
                        err_msg = f"Failed to connect to FL Server at {server_address}. The server might be offline or starting up."
                        LOGGER.error(err_msg)
                        self.fl_client_stopped.emit(False, "Server Offline")
                    elif "StatusCode.UNIMPLEMENTED" in err_str or "Method not found" in err_str:
                        # FALLBACK to grpc-bidi if Server version mismatch occurs
                        err_msg = f"Version mismatch or incorrect endpoint on FL Server at {server_address}. Method not found. (Using grpc-bidi transport)"
                        LOGGER.error(err_msg)
                        self.fl_client_stopped.emit(False, "Server Version/Endpoint Mismatch")
                    else:
                        raise e # Not a known grpc connection error, escalate
        except Exception as e:
             err_msg = f"FL client stopped: {str(e)}\n{traceback.format_exc()}"
             LOGGER.error(err_msg)
             self.fl_client_stopped.emit(False, str(e))
        finally:
            _signal.signal = original_signal

    @Slot()
    def stop_fl_client(self):
        """
        Mute the client — it will skip future rounds but remain connected.

        mute() is thread-safe and will refuse to mute while a training call
        is in progress (returns False). In that case we emit mute_rejected so
        the UI can snap the toggle back to its previous (Ready) state instead
        of silently leaving it unchecked while the client is still READY.
        """
        if self.fl_client is None:
            LOGGER.warning("stop_fl_client called but no active FL client.")
            return

        success = self.fl_client.mute()
        if success:
            LOGGER.info("Client set to Not Ready (muted). Future rounds will be skipped.")
            self.fl_client_stopped.emit(True, "Paused — skipping rounds.")
        else:
            # Mid-training: mute rejected — tell the UI to snap the toggle back.
            LOGGER.warning(
                "Mute rejected: client is currently in a training round. "
                "Wait for the round to complete before muting."
            )
            self.mute_rejected.emit()

    @Slot()
    def resume_fl_client(self):
        """
        Unmute the client — it will resume participation in future rounds.
        Always safe to call (even mid-training: unmute is instant & lock-free).
        """
        if self.fl_client is None:
            LOGGER.warning("resume_fl_client called but no active FL client.")
            return
        self.fl_client.unmute()
        LOGGER.info("Client resumed (unmuted). Will participate in the next round.")

    def get_client_status(self) -> str:
        """Returns the current ClientReadyState as a string (useful for UI status bars)."""
        if self.fl_client is None:
            return "disconnected"
        _, state = self.fl_client._ready_state()
        return state.value


class FLWorker(QObject):
    """
    Main controller to manage Inference, SHAP, and FL System workers.
    Each sub-worker runs in its own dedicated QThread.
    Provides backward-compatible interface with the original FLWorker.
    """
    # Signals for Inference
    prediction_result = Signal(object)

    # Signals for SHAP
    shap_result = Signal(object)

    # Signals for FL Training
    training_started = Signal()
    training_ended = Signal(bool)
    fl_client_started = Signal()
    fl_client_stopped = Signal(bool, str)  # success, message
    mute_rejected = Signal()              # emitted when mute() is rejected (mid-training)

    # Generic logging channel
    log_message = Signal(str)

    # Internal routing signals (cross thread boundaries)
    _run_prediction_signal = Signal(dict)
    _run_shap_signal = Signal(object)
    _start_fl_signal = Signal(str, int, int, float)
    _stop_fl_signal = Signal()
    _resume_fl_signal = Signal()

    def __init__(self):
        super().__init__()

        self.batch_size = 32
        self.learning_rate = 0.001

        # 1. Initialize Threads
        self.inference_thread = QThread()
        self.shap_thread = QThread()
        self.fl_thread = QThread()

        # 2. Initialize Workers
        self.inference_worker = InferenceWorker()
        self.shap_worker = ShapWorker()
        self.fl_system_worker = FLSystemWorker()

        # 3. Move Workers to their respective threads
        self.inference_worker.moveToThread(self.inference_thread)
        self.shap_worker.moveToThread(self.shap_thread)
        self.fl_system_worker.moveToThread(self.fl_thread)

        # 4. Connect routing signals (Controller -> Worker)
        self._run_prediction_signal.connect(self.inference_worker.run_prediction)
        self._run_shap_signal.connect(self.shap_worker.run_shap)
        self._start_fl_signal.connect(self.fl_system_worker.start_fl_client)
        # NOTE: _stop_fl_signal and _resume_fl_signal are intentionally NOT
        # connected to FLSystemWorker slots here. The fl_thread is permanently
        # blocked inside start_client() (gRPC loop), so its Qt event
        # loop never processes queued signals. mute()/unmute() are
        # threading.Event operations safe to call directly from any thread.

        # 5. Connect worker signals back out (Worker -> Controller -> UI)
        self.inference_worker.prediction_result.connect(self.prediction_result)
        self.shap_worker.shap_result.connect(self.shap_result)

        self.fl_system_worker.training_started.connect(self.training_started)
        self.fl_system_worker.training_ended.connect(self.training_ended)
        self.fl_system_worker.fl_client_started.connect(self.fl_client_started)
        self.fl_system_worker.fl_client_stopped.connect(self.fl_client_stopped)
        self.fl_system_worker.mute_rejected.connect(self.mute_rejected)
        self.fl_system_worker.log_message.connect(self.log_message)

        # 6. Start Threads
        self.inference_thread.start()
        self.shap_thread.start()
        self.fl_thread.start()

    @Slot(str, int, int, float)
    def start_fl_client(self, server_address: str, local_epochs: int, batch_size: int, lr: float):
        """Routes start FL client command to FL system worker."""
        self._start_fl_signal.emit(server_address, local_epochs, batch_size, lr)

    @Slot()
    def stop_fl_client(self):
        """
        Mute the client — it will skip rounds but stay connected.

        CRITICAL: We call fl_system_worker.fl_client.mute() DIRECTLY here,
        bypassing the Qt signal/slot queue.  The fl_thread is permanently
        blocked inside start_client() (the Flower gRPC loop), so
        its event loop never processes queued signals — emitting _stop_fl_signal
        would silently do nothing and the client would keep replying ready=True.

        mute() only touches a threading.Event and RLock, so it is explicitly
        designed to be called from any thread at any time.
        """
        worker = self.fl_system_worker
        if worker.fl_client is None:
            LOGGER.warning("stop_fl_client: no active FL client to mute.")
            return

        success = worker.fl_client.mute()
        if success:
            LOGGER.info("[UI] Client muted directly — will skip future rounds.")
            # Emit fl_client_stopped so the config tab card updates.
            # Use a Qt-safe emit from this (main) thread — the signal is
            # connected to the main-thread config tab widget.
            worker.fl_client_stopped.emit(True, "Paused — skipping rounds.")
        else:
            # Mid-training rejection — signal the UI to snap the checkbox back.
            LOGGER.warning(
                "[UI] Mute rejected: client is in a training round. "
                "Try again after the round completes."
            )
            worker.mute_rejected.emit()

    @Slot()
    def resume_fl_client(self):
        """
        Unmute the client — it will participate in rounds again.

        Same reasoning as stop_fl_client: we call unmute() directly on the
        FLClientRuntime rather than routing through the blocked fl_thread's
        event queue.  unmute() is always safe and lock-free.
        """
        worker = self.fl_system_worker
        if worker.fl_client is None:
            LOGGER.warning("resume_fl_client: no active FL client to unmute.")
            return
        worker.fl_client.unmute()
        LOGGER.info("[UI] Client unmuted directly — will participate in next round.")

    @Slot(dict)
    def run_prediction(self, inputs: Mapping[str, float]):
        """Routes prediction command to inference worker."""
        self._run_prediction_signal.emit(inputs)

    @Slot(object)
    def run_shap(self, data: Any):
        """Routes SHAP command to shap worker."""
        self._run_shap_signal.emit(data)

    def shutdown(self):
        """Gracefully stop background threads, force killing FL thread if still blocked."""
        self.inference_thread.quit()
        self.shap_thread.quit()

        if self.fl_thread.isRunning():
            self.fl_thread.terminate()
            self.fl_thread.wait()

        self.inference_thread.wait()
        self.shap_thread.wait()

    def __del__(self):
        try:
            self.shutdown()
        except Exception:
            pass  # Qt C++ objects may already be deleted by GC time
