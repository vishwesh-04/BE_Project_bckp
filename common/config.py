import os
from typing import Optional


def _get_env(name: str, default: str) -> str:
    return os.getenv(name, default)


def get_bool(name: str, default: bool) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def get_int(name: str, default: int) -> int:
    return int(_get_env(name, str(default)))


def get_float(name: str, default: float) -> float:
    return float(_get_env(name, str(default)))


def get_int_or_float(name: str, default: int | float) -> int | float:
    value = _get_env(name, str(default)).strip()
    try:
        parsed = float(value)
    except ValueError as exc:
        raise ValueError(f"Environment variable {name} must be numeric, got {value!r}") from exc
    return int(parsed) if parsed.is_integer() else parsed


# Paths
COLUMNS_PATH = _get_env("COLUMNS_PATH", "./preprocessing/columns.txt")
SCALER_PATH = _get_env("SCALER_PATH", "./preprocessing/scaler.pkl")
MODEL_DIR = _get_env("MODEL_DIR", "./models")
ARTIFACT_DIR = _get_env("ARTIFACT_DIR", MODEL_DIR)
LOG_DIR = _get_env("LOG_DIR", "./logs")
TRAINING_LOG_PATH = _get_env("TRAINING_LOG_PATH", os.path.join(LOG_DIR, "server-training.log"))
CONTROL_API_LOG_PATH = _get_env("CONTROL_API_LOG_PATH", os.path.join(LOG_DIR, "server-control-api.log"))
INFERENCE_API_LOG_PATH = _get_env("INFERENCE_API_LOG_PATH", os.path.join(LOG_DIR, "server-inference-api.log"))

# Federated learning params
NUM_CLIENTS = get_int("NUM_CLIENTS", 3)
LOCAL_EPOCHS = get_int("LOCAL_EPOCHS", 5)
BATCH_SIZE = get_int("BATCH_SIZE", 32)
LEARNING_RATE = get_float("LEARNING_RATE", 0.001)

# Model / dataset selection surface
MODEL_NAME = _get_env("MODEL_NAME", "neural_network")
DATASET_NAME = _get_env("DATASET_NAME", "cardio")
DASHBOARD_FEATURE_KEYS = ["age", "gender", "height", "weight"]
DASHBOARD_FEATURE_LABELS = ["Age", "Gender", "Height", "Weight"]

# Client-side DP-SGD (kept for parity, can be disabled)
CLIENT_DP_ENABLED = get_bool("CLIENT_DP_ENABLED", False)
L2_NORM_CLIP = get_float("L2_NORM_CLIP", 1.5)
NOISE_MULTIPLIER = get_float("NOISE_MULTIPLIER", 1.1)
NUM_MICROBATCHES = get_int("NUM_MICROBATCHES", 1)

# Server-side central DP
CENTRAL_DP_ENABLED = get_bool("CENTRAL_DP_ENABLED", True)
DP_MAX_NORM = get_float("DP_MAX_NORM", 1.0)
DP_NOISE_MULTIPLIER = get_float("DP_NOISE_MULTIPLIER", 0.25)
DP_NOISE_SEED = get_int("DP_NOISE_SEED", 2026)

# Flower SecAgg+
SECAGG_ENABLED = get_bool("SECAGG_ENABLED", True)
SECAGGPLUS_NUM_SHARES = get_int_or_float("SECAGGPLUS_NUM_SHARES", 1.0)
SECAGGPLUS_RECONSTRUCTION_THRESHOLD = get_int_or_float("SECAGGPLUS_RECONSTRUCTION_THRESHOLD", 0.75)
SECAGGPLUS_MAX_WEIGHT = get_float("SECAGGPLUS_MAX_WEIGHT", 1000.0)
SECAGGPLUS_CLIPPING_RANGE = get_float("SECAGGPLUS_CLIPPING_RANGE", 8.0)
SECAGGPLUS_QUANTIZATION_RANGE = get_int("SECAGGPLUS_QUANTIZATION_RANGE", 2**22)
SECAGGPLUS_MODULUS_RANGE = get_int("SECAGGPLUS_MODULUS_RANGE", 2**32)
SECAGGPLUS_TIMEOUT_SECONDS = float(os.getenv("SECAGGPLUS_TIMEOUT_SECONDS", "30.0"))

# Event-driven orchestration
MIN_CLIENTS = get_int("MIN_CLIENTS", NUM_CLIENTS)
READINESS_POLL_TIMEOUT_SECONDS = get_float("READINESS_POLL_TIMEOUT_SECONDS", 5.0)
ORCHESTRATION_IDLE_SLEEP_SECONDS = get_float("ORCHESTRATION_IDLE_SLEEP_SECONDS", 1.0)
TRAINING_SESSION_ROUNDS = get_int("TRAINING_SESSION_ROUNDS", 4)
QUORUM_WAIT_TIMEOUT = get_float("QUORUM_WAIT_TIMEOUT", 30.0)
SESSION_COOLDOWN_SECONDS = get_float("SESSION_COOLDOWN_SECONDS", 300.0)
SESSION_STALL_TIMEOUT_SECONDS = get_float("SESSION_STALL_TIMEOUT_SECONDS", 60.0)
MAX_CLIENTS = get_int("MAX_CLIENTS", 100)
CLIENT_ID = os.getenv("CLIENT_ID")
CLIENT_PERSONALIZE = get_bool("CLIENT_PERSONALIZE", False)

# Transport
SERVER_ADDRESS = _get_env("SERVER_ADDRESS", "0.0.0.0:45678")
CLIENT_SERVER_ADDRESS = _get_env("CLIENT_SERVER_ADDRESS", "127.0.0.1:45678")
TLS_ENABLED = get_bool("TLS_ENABLED", False)
TLS_CA_CERT = os.getenv("TLS_CA_CERT")
TLS_SERVER_CERT = os.getenv("TLS_SERVER_CERT")
TLS_SERVER_KEY = os.getenv("TLS_SERVER_KEY")
TLS_CLIENT_CERT = os.getenv("TLS_CLIENT_CERT")
TLS_CLIENT_KEY = os.getenv("TLS_CLIENT_KEY")
AUTH_TOKEN = os.getenv("AUTH_TOKEN")

# Control API
CONTROL_API_HOST = _get_env("CONTROL_API_HOST", "0.0.0.0")
CONTROL_API_PORT = get_int("CONTROL_API_PORT", 8000)
CONTROL_API_URL = _get_env("CONTROL_API_URL", f"http://127.0.0.1:{CONTROL_API_PORT}")

# Inference API
INFERENCE_API_HOST = _get_env("INFERENCE_API_HOST", "0.0.0.0")
INFERENCE_API_PORT = get_int("INFERENCE_API_PORT", 8001)
INFERENCE_API_URL = _get_env("INFERENCE_API_URL", f"http://127.0.0.1:{INFERENCE_API_PORT}")

# Redis
REDIS_ENABLED = get_bool("REDIS_ENABLED", False)
REDIS_HOST = _get_env("REDIS_HOST", "127.0.0.1")
REDIS_PORT = get_int("REDIS_PORT", 6379)
REDIS_DB = get_int("REDIS_DB", 0)
REDIS_USERNAME = os.getenv("REDIS_USERNAME")
REDIS_PASSWORD = os.getenv("REDIS_PASSWORD")
REDIS_SSL = get_bool("REDIS_SSL", False)
REDIS_URL = os.getenv("REDIS_URL")


def get_input_dim() -> int:
    if not os.path.exists(COLUMNS_PATH):
        return 12
    with open(COLUMNS_PATH, "r", encoding="utf-8") as file:
        return len([line.strip() for line in file.readlines() if line.strip()])


def get_client_dataset_paths(client_id: str) -> tuple[Optional[str], Optional[str]]:
    train_key = f"CLIENT_{client_id}_TRAINING_SET"
    test_key = f"CLIENT_{client_id}_TESTING_SET"
    return os.getenv(train_key), os.getenv(test_key)
