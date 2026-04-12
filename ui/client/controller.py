import os
import traceback
from PySide6.QtCore import QObject, Signal, Slot, QThread
import flwr as fl

# ── Dynamic imports based on your client logic ──
from common.config import get_client_dataset_paths, get_input_dim
from common.network import NeuralNetworkAlgo
from client.client_common import FLClientRuntime
from client.inference_engine import predict_from_inputs, PredictionResult
from client.shap_engine import get_local_explainer, get_global_explainer


class FLSystemWorker(QObject):
    """
    Background worker that executes the blocking Flower network connection.
    Prevents PySide6 Main Thread (UI) from freezing.
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

        # Resolve client ID and paths natively
        client_id = os.getenv("CLIENT_ID", "1")
        train_path, test_path = get_client_dataset_paths(client_id)

        if not train_path or not test_path:
            self.log_signal.emit(f"[WARNING] Data paths for Client {client_id} not found!")

        algo = NeuralNetworkAlgo(input_dim=get_input_dim())

        # Instantiate your custom Flower client with UI hooks attached
        self.fl_client = FLClientRuntime(
            client_id=client_id,
            train_path=train_path,
            test_path=test_path,
            algo=algo,
            use_personalization=True,
            local_epochs=self.epochs,
            batch_size=self.batch_size,
            learning_rate=self.lr,
            on_training_start=lambda rnd: self.training_started_sig.emit(rnd),
            on_training_end=lambda success: self.training_ended_sig.emit(success),
            on_evaluate=lambda loss, acc: self.evaluation_completed_sig.emit(
                {"loss": loss, "accuracy": acc}
            )
        )

    @Slot()
    def run(self):
        self.log_signal.emit(f"[SYSTEM] Connecting to SuperLink at {self.server_address}...")
        self.started.emit()
        try:
            # Flower 1.28.0 Wrapper
            client_wrapper = self.fl_client.to_client()

            # Blocking call
            fl.client.start_client(
                server_address=self.server_address,
                client=client_wrapper,
                insecure=True
            )
            self.log_signal.emit("[SYSTEM] FL Client disconnected gracefully.")
        except Exception as e:
            self.log_signal.emit(f"[ERROR] FL connection error: {e}")
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
        if self.fl_system_worker and hasattr(self.fl_system_worker.fl_client, 'unmute'):
            self.fl_system_worker.fl_client.unmute()
            self.log_message.emit("[SYSTEM] Node resumed active participation.")

    @Slot()
    def stop_fl_client(self):
        if self.fl_thread and self.fl_thread.isRunning():
            if self.fl_system_worker and hasattr(self.fl_system_worker.fl_client, 'mute'):
                # Try to mute. If it returns False, the client is currently training!
                success = self.fl_system_worker.fl_client.mute()
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
            # Route to your inference_engine.py function
            result: PredictionResult = predict_from_inputs(val_map)
            self.prediction_result.emit(result)
        except Exception as e:
            self.log_message.emit(f"[ERROR] Inference failed: {str(e)}")
            self.prediction_result.emit(e)

    @Slot(object, dict)
    def run_shap_local(self, background_data, val_map: dict):
        try:
            self.log_message.emit("[SHAP] Generating model explanation waterfall...")
            # Route to your shap_engine.py function
            fig = get_local_explainer(background_data, val_map)
            self.shap_local_result.emit(fig)
        except Exception as e:
            self.log_message.emit(f"[ERROR] SHAP calculation failed: {str(e)}")
            self.shap_local_result.emit(e)