import logging
import traceback
from typing import Any, Mapping, Optional

from PySide6.QtCore import QObject, Signal, Slot
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

class FLWorker(QObject):
    """
    Worker running on a background QThread to perform blocking ML tasks.
    It wraps both Federated Learning execution and Inference.
    """
    # Signals for Inference
    prediction_result = Signal(object)  # Emits a PredictionResult or Exception
    
    # Signals for FL Training
    training_started = Signal()
    training_ended = Signal(bool)
    fl_client_started = Signal()
    fl_client_stopped = Signal(bool, str) # success, message
    
    # Generic logging channel
    log_message = Signal(str)
    
    def __init__(self):
        super().__init__()
        # Retrieve paths and inputs early
        self.train_path, self.test_path = get_client_dataset_paths(CLIENT_ID)
        self.input_dim = get_input_dim()
        self.client_id = CLIENT_ID
        
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
        
    def _create_client(self) -> FLClientRuntime:
        """Helper to create FLClientRuntime with GUI signals bound."""
        client = FLClientRuntime(
            client_id=str(self.client_id),
            train_path=self.train_path,
            test_path=self.test_path,
            algo=NeuralNetworkAlgo(input_dim=self.input_dim),
            use_personalization=False,
            # Bind the callbacks to our Qt Signals
            on_training_start=self._on_training_start_callback,
            on_training_end=self._on_training_end_callback,
        )
        return client

    def _on_training_start_callback(self):
        # We must emit signals from the background thread so PySide properly routes to GUI thread
        self.training_started.emit()
        
    def _on_training_end_callback(self, success: bool):
        self.training_ended.emit(success)

    @Slot(str)
    def start_fl_client(self, server_address: str):
        """Starts the Flower client syncing loop in this thread."""
        LOGGER.info(f"Connecting FL Client to {server_address}")
        self.fl_client_started.emit()
        
        import signal
        original_signal = signal.signal
        try:
            # Mock signal handler to prevent ValueError from main thread requirement
            signal.signal = lambda *args, **kwargs: None
            
            if not self.fl_client:
                self.fl_client = self._create_client()
            
            # Start client - blocks until disconnected
            fl.client.start_client(
                server_address=server_address,
                client=self.fl_client.to_client(),
                transport="grpc-rere"
            )
            self.fl_client_stopped.emit(True, "Disconnected normally.")
        except Exception as e:
            err_msg = f"Failed to start FL client: {str(e)}\n{traceback.format_exc()}"
            LOGGER.error(err_msg)
            self.fl_client_stopped.emit(False, str(e))
        finally:
            # Restore original signal to not disrupt other thread operations permanently
            signal.signal = original_signal
            
    @Slot(dict)
    def run_prediction(self, inputs: Mapping[str, float]):
        """Runs the prediction using the inference engine."""
        try:
            result: PredictionResult = predict_from_inputs(inputs)
            self.prediction_result.emit(result)
        except Exception as e:
            err_msg = f"Inference engine failed: {str(e)}"
            LOGGER.error(err_msg)
            self.prediction_result.emit(e)
