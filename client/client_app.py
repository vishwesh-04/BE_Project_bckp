from __future__ import annotations

import argparse
import logging
import sys

from dotenv import load_dotenv
from flwr.client import ClientApp
from flwr.client.mod import secaggplus_mod
from flwr.common import Context

from common.config import CLIENT_ID, CLIENT_PERSONALIZE, CLIENT_SERVER_ADDRESS, get_client_dataset_paths, get_input_dim
from common.network import NeuralNetworkAlgo
from .client_common import FLClientRuntime
from .supernode_runner import build_node_config, run_supernode_blocking

load_dotenv()

LOGGER = logging.getLogger(__name__)


def _context_lookup(context: Context, *keys: str) -> str | None:
    for attr in ("node_config", "run_config"):
        payload = getattr(context, attr, None)
        if isinstance(payload, dict):
            for key in keys:
                value = payload.get(key)
                if value is not None:
                    return str(value)
    return None


def _context_bool(context: Context, *keys: str) -> bool | None:
    value = _context_lookup(context, *keys)
    if value is None:
        return None
    return value.strip().lower() in {"1", "true", "yes", "on"}


def _resolve_client_id(context: Context) -> str:
    client_id = _context_lookup(context, "client_id", "partition-id", "partition_id") or CLIENT_ID
    if not client_id:
        raise ValueError("Client ID is required via Context config or CLIENT_ID environment variable")
    return client_id


def _resolve_personalize(context: Context) -> bool:
    value = _context_bool(context, "personalize", "client_personalize")
    return CLIENT_PERSONALIZE if value is None else value


def _resolve_int(context: Context, key: str, default: int) -> int:
    val = _context_lookup(context, key)
    return int(val) if val is not None else default


def _resolve_float(context: Context, key: str, default: float) -> float:
    val = _context_lookup(context, key)
    return float(val) if val is not None else default


# app = ClientApp(client_fn=client_fn, mods=[secaggplus_mod])

# ------------------------------------------------------------------
# UI callback injection mechanism
# ------------------------------------------------------------------
UI_CALLBACKS = {
    "on_training_start": None,
    "on_training_end": None,
    "on_evaluate": None,
    "instance": None,
}

def update_ui_callbacks(on_training_start=None, on_training_end=None, on_evaluate=None):
    if on_training_start: UI_CALLBACKS["on_training_start"] = on_training_start
    if on_training_end: UI_CALLBACKS["on_training_end"] = on_training_end
    if on_evaluate: UI_CALLBACKS["on_evaluate"] = on_evaluate

def get_client_instance():
    return UI_CALLBACKS["instance"]

def client_fn(context: Context):
    client_id = _resolve_client_id(context)
    personalize = _resolve_personalize(context)
    train_set, test_set = get_client_dataset_paths(client_id)
    if not train_set or not test_set:
        raise ValueError(f"Paths for client {client_id} not found in environment")

    # Resolve training hyperparams (from user input in UI, passed via Context)
    epochs = _resolve_int(context, "local_epochs", 3)
    batch_size = _resolve_int(context, "batch_size", 32)
    lr = _resolve_float(context, "learning_rate", 0.001)

    client_instance = FLClientRuntime(
        client_id=client_id,
        train_path=train_set,
        test_path=test_set,
        algo=NeuralNetworkAlgo(input_dim=get_input_dim()),
        use_personalization=personalize,
        local_epochs=epochs,
        batch_size=batch_size,
        learning_rate=lr,
        on_training_start=UI_CALLBACKS["on_training_start"],
        on_training_end=UI_CALLBACKS["on_training_end"],
        on_evaluate=UI_CALLBACKS["on_evaluate"],
    )
    UI_CALLBACKS["instance"] = client_instance
    return client_instance.to_client()


app = ClientApp(client_fn=client_fn, mods=[secaggplus_mod])


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------

def _build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python -m client",
        description=(
            "Launch this node as a Flower SuperNode (standalone CLI mode). \n"
            "Connects to a running SuperLink fleet API and participates in \n"
            "federated learning rounds.  All flags are optional; unset values \n"
            "fall back to the .env file / environment variables."
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--superlink",
        metavar="HOST:PORT",
        default=None,
        help=(
            "SuperLink fleet API address to connect to. "
            f"Defaults to CLIENT_SERVER_ADDRESS from .env ({CLIENT_SERVER_ADDRESS})."
        ),
    )
    parser.add_argument(
        "--client-id",
        metavar="ID",
        default=None,
        help=(
            "Client identifier (partition ID). "
            "Defaults to CLIENT_ID from .env."
        ),
    )
    parser.add_argument(
        "--epochs",
        metavar="N",
        type=int,
        default=None,
        help="Number of local training epochs per round (default: LOCAL_EPOCHS from .env or 3).",
    )
    parser.add_argument(
        "--batch-size",
        metavar="N",
        type=int,
        default=None,
        help="Training batch size (default: BATCH_SIZE from .env or 32).",
    )
    parser.add_argument(
        "--lr",
        metavar="FLOAT",
        type=float,
        default=None,
        help="Learning rate (default: LEARNING_RATE from .env or 0.001).",
    )
    parser.add_argument(
        "--secure",
        action="store_true",
        default=False,
        help="Enable TLS (omit --insecure flag). Default: insecure mode.",
    )
    parser.add_argument(
        "--log-level",
        metavar="LEVEL",
        default="INFO",
        choices=["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"],
        help="Python logging level (default: INFO).",
    )
    return parser


def main(argv: list[str] | None = None) -> None:
    """CLI entry point: parse args and launch ``flower-supernode`` in the foreground.

    Blocks until the supernode exits or the user presses Ctrl+C.
    Exit code mirrors the supernode exit code.
    """
    parser = _build_arg_parser()
    args = parser.parse_args(argv)

    logging.basicConfig(
        level=getattr(logging, args.log_level),
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%H:%M:%S",
    )

    superlink = args.superlink or CLIENT_SERVER_ADDRESS
    node_config = build_node_config(
        client_id=args.client_id,
        epochs=args.epochs,
        batch_size=args.batch_size,
        lr=args.lr,
    )

    print(f"[CLIENT] Connecting to SuperLink at {superlink}")
    if node_config:
        print(f"[CLIENT] Node config: {node_config}")

    try:
        exit_code = run_supernode_blocking(
            superlink=superlink,
            node_config=node_config,
            insecure=not args.secure,
            log_fn=print,
        )
    except FileNotFoundError:
        sys.exit(1)
    except KeyboardInterrupt:
        print("\n[CLIENT] Interrupted — shutting down.")
        sys.exit(0)
    else:
        sys.exit(exit_code)


if __name__ == "__main__":
    main()
