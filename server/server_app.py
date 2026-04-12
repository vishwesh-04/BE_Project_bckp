from __future__ import annotations

import argparse
import logging
import os
import sys

from dotenv import load_dotenv
from flwr.common import Context, ndarrays_to_parameters
from flwr.server import Grid, LegacyContext, ServerApp, ServerConfig
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
from .superlink_runner import run_server_blocking

load_dotenv(os.path.join(os.path.dirname(__file__), "../.env"))
configure_logging(TRAINING_LOG_PATH, "server.training")

CLI_LOGGER = logging.getLogger(__name__)

GLOBAL_TEST = os.getenv("GLOBAL_TESTING_SET")
app = ServerApp()


def _build_legacy_context(context: Context, strategy: FeatureParityFedAvg) -> LegacyContext:
    return LegacyContext(
        context=context,
        config=ServerConfig(num_rounds=TRAINING_SESSION_ROUNDS),
        strategy=strategy,
        client_manager=StatefulClientManager(),
    )


@app.main()
def main(grid: Grid, context: Context) -> None:
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


# ---------------------------------------------------------------------------
# CLI entry point  (python -m server  /  server-starter.sh)
# ---------------------------------------------------------------------------

_DEFAULT_FLEET_ADDRESS = os.getenv("SERVER_ADDRESS", "0.0.0.0:45678")
_DEFAULT_APPIO_ADDRESS = os.getenv("SERVER_APPIO_ADDRESS", "127.0.0.1:9091")


def _build_cli_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python -m server",
        description=(
            "Launch the Flower server infrastructure (SuperLink + SuperExec).\n"
            "All flags are optional; unset values fall back to .env / environment variables."
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--fleet-api-address",
        metavar="HOST:PORT",
        default=None,
        help=(
            "Fleet API address clients connect to. "
            f"Defaults to SERVER_ADDRESS from .env ({_DEFAULT_FLEET_ADDRESS})."
        ),
    )
    parser.add_argument(
        "--appio-address",
        metavar="HOST:PORT",
        default=None,
        help=(
            "Internal ServerApp I/O address. "
            f"Defaults to SERVER_APPIO_ADDRESS from .env ({_DEFAULT_APPIO_ADDRESS})."
        ),
    )
    parser.add_argument(
        "--startup-delay",
        metavar="SECONDS",
        type=float,
        default=2.0,
        help="Seconds to wait after SuperLink starts before launching SuperExec (default: 2).",
    )
    parser.add_argument(
        "--secure",
        action="store_true",
        default=False,
        help="Enable TLS. Default: insecure mode.",
    )
    parser.add_argument(
        "--no-free-port",
        action="store_true",
        default=False,
        help="Skip killing any process on the appio port before starting.",
    )
    parser.add_argument(
        "--log-level",
        metavar="LEVEL",
        default="INFO",
        choices=["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"],
        help="Python logging level (default: INFO).",
    )
    return parser


def main_cli(argv: list[str] | None = None) -> None:
    """CLI entry point: parse args and launch SuperLink + SuperExec in the foreground.

    Blocks until both processes exit or the user presses Ctrl+C.
    Exit code mirrors the SuperExec exit code.
    """
    parser = _build_cli_parser()
    args = parser.parse_args(argv)

    logging.basicConfig(
        level=getattr(logging, args.log_level),
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%H:%M:%S",
    )

    fleet_address = args.fleet_api_address or _DEFAULT_FLEET_ADDRESS
    appio_address = args.appio_address or _DEFAULT_APPIO_ADDRESS

    print(f"[SERVER] Fleet API address : {fleet_address}")
    print(f"[SERVER] ServerApp I/O addr: {appio_address}")

    try:
        exit_code = run_server_blocking(
            fleet_api_address=fleet_address,
            serverappio_api_address=appio_address,
            insecure=not args.secure,
            superlink_startup_delay=args.startup_delay,
            free_port_before_start=not args.no_free_port,
            log_fn=print,
        )
    except FileNotFoundError:
        sys.exit(1)
    except KeyboardInterrupt:
        print("\n[SERVER] Interrupted — shutting down.")
        sys.exit(0)
    else:
        sys.exit(exit_code)


if __name__ == "__main__":
    main_cli()
