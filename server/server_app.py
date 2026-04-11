import os

from dotenv import load_dotenv
from flwr.common import Context, ndarrays_to_parameters
from flwr.server import LegacyContext, ServerApp, ServerConfig
from flwr.server.workflow import SecAggPlusWorkflow

from common.config import (
    ARTIFACT_DIR,
    TRAINING_LOG_PATH,
    MIN_CLIENTS,
    ORCHESTRATION_IDLE_SLEEP_SECONDS,
    SECAGG_ENABLED,
    SECAGGPLUS_CLIPPING_RANGE,
    SECAGGPLUS_MAX_WEIGHT,
    SECAGGPLUS_MODULUS_RANGE,
    SECAGGPLUS_NUM_SHARES,
    SECAGGPLUS_QUANTIZATION_RANGE,
    SECAGGPLUS_RECONSTRUCTION_THRESHOLD,
    SECAGGPLUS_TIMEOUT_SECONDS,
    TRAINING_SESSION_ROUNDS,
    get_input_dim,
)
from common.network import NeuralNetworkAlgo
from .logging_utils import configure_logging
from .state import get_state_store
from .custom_strategy import FeatureParityFedAvg
from .evaluator import get_evaluate_fn
from .event_driven_workflow import EventDrivenWorkflow
from .client_manager import StatefulClientManager

load_dotenv(os.path.join(os.path.dirname(__file__), "../.env"))
configure_logging(TRAINING_LOG_PATH, "server.training")

GLOBAL_TEST = os.getenv("GLOBAL_TESTING_SET")
app = ServerApp()


def _build_legacy_context(context: Context, strategy: FeatureParityFedAvg) -> LegacyContext:
    kwargs = {
        "context": context,
        "config": ServerConfig(num_rounds=TRAINING_SESSION_ROUNDS),
        "strategy": strategy,
    }
    client_manager = StatefulClientManager()
    try:
        return LegacyContext(client_manager=client_manager, **kwargs)
    except TypeError:
        legacy_context = LegacyContext(**kwargs)
        if not hasattr(legacy_context, "client_manager"):
            legacy_context.client_manager = client_manager
        return legacy_context


@app.main()
def main(grid, context: Context) -> None:
    state_store = get_state_store()
    state_store.set_desired_training_status("running")
    model = NeuralNetworkAlgo(input_dim=get_input_dim())
    initial_parameters = ndarrays_to_parameters(model.get_weights())

    strategy = FeatureParityFedAvg(
        fraction_fit=1.0,
        fraction_evaluate=1.0,
        min_fit_clients=MIN_CLIENTS,
        min_available_clients=MIN_CLIENTS,
        min_evaluate_clients=MIN_CLIENTS,
        evaluate_fn=get_evaluate_fn(GLOBAL_TEST),
        initial_parameters=initial_parameters,
        artifact_dir=ARTIFACT_DIR,
        reference_data_path=GLOBAL_TEST,
    )

    legacy_context = _build_legacy_context(context, strategy)
    fit_workflow = None
    if SECAGG_ENABLED:
        fit_workflow = SecAggPlusWorkflow(
            num_shares=SECAGGPLUS_NUM_SHARES,
            reconstruction_threshold=SECAGGPLUS_RECONSTRUCTION_THRESHOLD,
            max_weight=SECAGGPLUS_MAX_WEIGHT,
            clipping_range=SECAGGPLUS_CLIPPING_RANGE,
            quantization_range=SECAGGPLUS_QUANTIZATION_RANGE,
            modulus_range=SECAGGPLUS_MODULUS_RANGE,
            timeout=SECAGGPLUS_TIMEOUT_SECONDS,
        )
    workflow = EventDrivenWorkflow(
        fit_workflow=fit_workflow,
        idle_sleep=ORCHESTRATION_IDLE_SLEEP_SECONDS,
    )
    workflow(grid, legacy_context)
