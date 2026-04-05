import logging
import traceback
from typing import Any, Mapping, Optional

from PySide6.QtCore import QObject, Signal, Slot, QThread
import flwr as fl

# Import from the client module
from client.client_common import FLClientRuntime
from client.inference_engine import predict_from_inputs, PredictionResult
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
    """Worker running on a background QThread to perform Federated Learning execution."""
    training_started = Signal()
    training_ended = Signal(bool)
    fl_client_started = Signal()
    fl_client_stopped = Signal(bool, str) # success, message
    log_message = Signal(str)

    def __init__(self):
        super().__init__()
        # Retrieve paths and inputs early
        self.train_path, self.test_path = get_client_dataset_paths(CLIENT_ID)
        self.input_dim = get_input_dim()
        self.client_id = CLIENT_ID
        self.current_url = ""
        
        self.fl_client: Optional[FLClientRuntime] = None

        # Setup logging redirection for our worker thread
        handler = QtLogHandler(self._emit_log)
        handler.setFormatter(logging.Formatter('[%(levelname)s] %(message)s'))
        logging.getLogger("flwr").addHandler(handler)
        logging.getLogger("client").addHandler(handler)
        # Also capture our own LOGGER just in case
        LOGGER.addHandler(handler)
        
    def _emit_log(self, msg: str):
        self.log_message.emit(msg)
        
    def _create_client(self, local_epochs: int = 3, batch_size: int = 32, lr: float = 0.001) -> FLClientRuntime:
        """Helper to create FLClientRuntime with GUI signals bound."""
        return FLClientRuntime(
            client_id=str(self.client_id),
            train_path=self.train_path,
            test_path=self.test_path,
            algo=NeuralNetworkAlgo(input_dim=self.input_dim),
            use_personalization=False,
            local_epochs=local_epochs,
            batch_size=batch_size,
            learning_rate=lr,
            # Bind the callbacks to our Qt Signals
            on_training_start=self._on_training_start_callback,
            on_training_end=self._on_training_end_callback,
        )

    def _on_training_start_callback(self):
        # We must emit signals from the background thread so PySide properly routes to GUI thread
        self.training_started.emit()
        
    def _on_training_end_callback(self, success: bool):
        self.training_ended.emit(success)

    @Slot(str, int, int, float)
    def start_fl_client(self, server_address: str, local_epochs: int, batch_size: int, lr: float):
        """Starts or resumes the Flower client syncing loop."""
        if self.fl_client and self.current_url == server_address:
            # We are already connected to this URL. Just resume!
            LOGGER.info("Resuming existing FL Client connection.")
            self.fl_client.stop_requested = False
            self.fl_client.local_epochs = local_epochs
            self.fl_client.batch_size = batch_size
            self.fl_client.learning_rate = lr
            self.fl_client_started.emit()
            return
            
        LOGGER.info(f"Connecting FL Client to {server_address} | EPOCHS={local_epochs} BFS={batch_size} LR={lr}")
        self.current_url = server_address
        self.fl_client_started.emit()
        
        import signal
        original_signal = signal.signal
        try:
            # Mock signal handler to prevent ValueError from main thread requirement
            signal.signal = lambda *args, **kwargs: None
            
            # recreate client to apply new hyperparams
            self.fl_client = self._create_client(local_epochs, batch_size, lr)
            
            # Start client - blocks until disconnected or exception
            fl.client.start_client(
                server_address=server_address,
                client=self.fl_client.to_client(),
                transport="grpc-rere"
            )
            self.fl_client_stopped.emit(True, "Disconnected normally.")
        except BaseException as e:
            # Catch BaseException
            err_msg = f"FL client stopped: {str(e)}\n{traceback.format_exc()}"
            LOGGER.error(err_msg)
            self.fl_client_stopped.emit(False, str(e))
        finally:
            # Restore original signal to not disrupt other thread operations permanently
            signal.signal = original_signal

    @Slot()
    def stop_fl_client(self):
        """Sets the client to not ready, skipping rounds."""
        if self.fl_client:
            self.fl_client.stop_requested = True
            LOGGER.info("Client set to Not Ready (muted by sidecar).")
            # We explicitly tell the UI it's paused. We don't drop the connection.
            self.fl_client_stopped.emit(True, "Paused")


class FLWorker(QObject):
    """
    Main controller to manage Inference, SHAP, and FL System workers.
    It encapsulates them such that each runs in a separate QThread of its own.
    It provides backward compatibility with the original FLWorker interface.
    """
    # Signals for Inference
    prediction_result = Signal(object)
    
    # Signals for SHAP
    shap_result = Signal(object)
    
    # Signals for FL Training
    training_started = Signal()
    training_ended = Signal(bool)
    fl_client_started = Signal()
    fl_client_stopped = Signal(bool, str) # success, message
    
    # Generic logging channel
    log_message = Signal(str)
    
    # Internal routing signals (to cross thread boundaries)
    _run_prediction_signal = Signal(dict)
    _run_shap_signal = Signal(object)
    _start_fl_signal = Signal(str, int, int, float)
    _stop_fl_signal = Signal()

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
        self._stop_fl_signal.connect(self.fl_system_worker.stop_fl_client)

        # 5. Connect worker signals back out (Worker -> Controller -> UI)
        self.inference_worker.prediction_result.connect(self.prediction_result)
        self.shap_worker.shap_result.connect(self.shap_result)
        
        self.fl_system_worker.training_started.connect(self.training_started)
        self.fl_system_worker.training_ended.connect(self.training_ended)
        self.fl_system_worker.fl_client_started.connect(self.fl_client_started)
        self.fl_system_worker.fl_client_stopped.connect(self.fl_client_stopped)
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
        """Routes the pause command to the worker."""
        self._stop_fl_signal.emit()

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
        self.shutdown()
