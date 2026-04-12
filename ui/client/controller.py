import os
import sys
import traceback
from PySide6.QtCore import QObject, Signal, Slot, QThread

from client.client_app import get_client_instance
from client.inference_engine import predict_from_inputs
from client.shap_engine import get_local_explainer
from client.supernode_runner import build_node_config, run_supernode_blocking


class FLSystemWorker(QObject):
    """
    Background worker that executes the blocking Flower network connection.
    Prevents PySide6 Main Thread (UI) from freezing.

    Uses the modern `flower-supernode` CLI subprocess (flwr >= 1.13) to connect
    to the SuperLink fleet API. The legacy `fl.client.start_client()` function
    was deprecated in 1.13 and is incompatible with the SuperLink architecture.
    """
    finished = Signal()
    log_signal = Signal(str)
    started = Signal()
    stopped = Signal()

    # Pass-through signals for FLClientRuntime callbacks
    training_started_sig = Signal(int)
    training_ended_sig = Signal(bool)
    evaluation_completed_sig = Signal(dict)

    def __init__(self, server_address: str, epochs: int, batch_size: int, lr: float):
        super().__init__()
        self.server_address = server_address
        self.epochs = epochs
        self.batch_size = batch_size
        self.lr = lr

    @Slot()
    def run(self):
        """
        Launch a ``flower-supernode`` subprocess to connect to the SuperLink
        fleet API.  Delegates to :func:`client.supernode_runner.run_supernode_blocking`
        so subprocess-launch logic lives in exactly one place.

        Why subprocess instead of fl.client.start_client()?
        - fl.client.start_client() was deprecated in flwr 1.13 and does NOT work
          with the modern SuperLink fleet API (--fleet-api-address).  It only
          connected to the legacy gRPC 8080-style endpoint.
        - The recommended pattern since flwr 1.13 is the ``flower-supernode`` CLI.
        - UI hyperparams (epochs, batch_size, lr) are injected via --node-config,
          which client_app.py reads from context.node_config.
        """
        self.log_signal.emit(
            f"[SYSTEM] Connecting to SuperLink fleet API at {self.server_address}..."
        )
        self.started.emit()

        node_config = build_node_config(
            epochs=self.epochs,
            batch_size=self.batch_size,
            lr=self.lr,
        )

        try:
            run_supernode_blocking(
                superlink=self.server_address,
                node_config=node_config,
                insecure=True,
                log_fn=self.log_signal.emit,
            )
        except FileNotFoundError:
            pass  # error already emitted by run_supernode_blocking via log_fn
        except Exception as exc:
            self.log_signal.emit(f"[ERROR] FL connection error: {exc}")
            self.log_signal.emit(traceback.format_exc())
        finally:
            self.stopped.emit()
            self.finished.emit()


class FLWorker(QObject):
    """
    Primary Controller: Handles signals to and from the UI, orchestrating
    Federated Learning, Inference, and Explainability tasks.
    """
    # ── UI Signals (Must match connections in main.py) ──
    training_started = Signal(int)
    training_ended = Signal()
    evaluation_completed = Signal(dict)
    fl_client_started = Signal()
    fl_client_stopped = Signal()
    mute_rejected = Signal()
    log_message = Signal(str)

    prediction_result = Signal(object)
    shap_local_result = Signal(object)
    shap_global_result = Signal(object)

    def __init__(self):
        super().__init__()
        self.fl_thread = None
        self.fl_system_worker = None

    # ──────────────────────────────────────────────────────────────────────
    #  Federated Learning Controls
    # ──────────────────────────────────────────────────────────────────────
    @Slot(str, int, int, float)
    def start_fl_client(self, server_address: str, local_epochs: int, batch_size: int, lr: float):
        self.stop_fl_client()  # Prevent overlapping threads

        self.log_message.emit("[SYSTEM] Initializing FL node thread...")

        self.fl_thread = QThread()
        self.fl_system_worker = FLSystemWorker(server_address, local_epochs, batch_size, lr)
        self.fl_system_worker.moveToThread(self.fl_thread)

        # Thread lifecycle signals
        self.fl_thread.started.connect(self.fl_system_worker.run)
        self.fl_system_worker.finished.connect(self.fl_thread.quit)
        self.fl_system_worker.finished.connect(self.fl_system_worker.deleteLater)
        self.fl_thread.finished.connect(self.fl_thread.deleteLater)

        # Map worker signals to UI signals
        self.fl_system_worker.log_signal.connect(self.log_message.emit)
        self.fl_system_worker.started.connect(self.fl_client_started.emit)
        self.fl_system_worker.stopped.connect(self.fl_client_stopped.emit)

        self.fl_system_worker.training_started_sig.connect(self.training_started.emit)
        self.fl_system_worker.training_ended_sig.connect(lambda _: self.training_ended.emit())
        self.fl_system_worker.evaluation_completed_sig.connect(self.evaluation_completed.emit)

        self.fl_thread.start()

    @Slot()
    def resume_fl_client(self):
        client = get_client_instance()
        if client and hasattr(client, 'unmute'):
            client.unmute()
            self.log_message.emit("[SYSTEM] Node resumed active participation.")

    @Slot()
    def stop_fl_client(self):
        client = get_client_instance()
        if client and hasattr(client, 'mute'):
            # Try to mute. If it returns False, the client is currently training!
            success = client.mute()
            if success:
                self.log_message.emit("[SYSTEM] Node paused participation (muted).")
            else:
                self.mute_rejected.emit()

    @Slot()
    def shutdown(self):
        """Hard exit for application closing."""
        if self.fl_thread and self.fl_thread.isRunning():
            self.fl_thread.quit()
            self.fl_thread.wait()

    # ──────────────────────────────────────────────────────────────────────
    #  Inference & Explainability Controls
    # ──────────────────────────────────────────────────────────────────────
    @Slot(dict)
    def run_prediction(self, val_map: dict):
        try:
            self.log_message.emit(f"[INFERENCE] Running ad-hoc prediction...")
            result = predict_from_inputs(val_map)
            self.prediction_result.emit(result)
        except Exception as e:
            self.log_message.emit(f"[ERROR] Inference failed: {str(e)}")
            self.prediction_result.emit(e)

    @Slot(object, dict)
    def run_shap_local(self, background_data, val_map: dict):
        try:
            self.log_message.emit("[SHAP] Generating model explanation waterfall...")
            fig = get_local_explainer(background_data, val_map)
            self.shap_local_result.emit(fig)
        except Exception as e:
            self.log_message.emit(f"[ERROR] SHAP calculation failed: {str(e)}")
            self.shap_local_result.emit(e)