from dotenv import load_dotenv
from flwr.client import ClientApp
from flwr.client.mod import secaggplus_mod
from flwr.common import Context

from common.config import CLIENT_ID, CLIENT_PERSONALIZE, get_client_dataset_paths, get_input_dim
from common.network import NeuralNetworkAlgo
from .client_common import FLClientRuntime

load_dotenv()


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


def client_fn(context: Context):
    client_id = _resolve_client_id(context)
    personalize = _resolve_personalize(context)
    train_set, test_set = get_client_dataset_paths(client_id)
    if not train_set or not test_set:
        raise ValueError(f"Paths for client {client_id} not found in environment")

    client_instance = FLClientRuntime(
        client_id=client_id,
        train_path=train_set,
        test_path=test_set,
        algo=NeuralNetworkAlgo(input_dim=get_input_dim()),
        use_personalization=personalize,
    )
    return client_instance.to_client()


# app = ClientApp(client_fn=client_fn, mods=[secaggplus_mod])
