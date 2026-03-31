from __future__ import annotations

import collections
import logging
import os
from pathlib import Path
from typing import Annotated

from dotenv import load_dotenv
from fastapi import Depends, FastAPI, HTTPException, Query
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from common.artifacts import list_saved_models, load_global_artifact
from common.config import ARTIFACT_DIR, AUTH_TOKEN, CONTROL_API_LOG_PATH, TRAINING_LOG_PATH
from server.evaluator import get_evaluate_fn
from server.logging_utils import configure_logging
from server.state import get_state_store

load_dotenv()
LOGGER = configure_logging(CONTROL_API_LOG_PATH, "server.control_api")

app = FastAPI(title="FL Control API", version="1.0.0")
state_store = get_state_store()

# ---------------------------------------------------------------------------
# Auth
# ---------------------------------------------------------------------------

_bearer_scheme = HTTPBearer(auto_error=False)

if not AUTH_TOKEN:
    LOGGER.warning(
        "AUTH_TOKEN is not set — all Control API mutating endpoints are UNPROTECTED. "
        "Set AUTH_TOKEN in your environment for production deployments."
    )


def _verify_token(
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(_bearer_scheme)],
) -> None:
    """Raise 403 if AUTH_TOKEN is configured and the request doesn't supply it."""
    if not AUTH_TOKEN:
        # No token configured — skip auth (dev/local mode; warning already logged at startup)
        return
    if credentials is None or credentials.credentials != AUTH_TOKEN:
        raise HTTPException(status_code=403, detail="Invalid or missing auth token")


# Shorthand dependency alias used by mutating routes
_require_auth = Depends(_verify_token)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _tail_log(path: str, max_lines: int) -> list[str]:
    """Return the last `max_lines` lines of a log file without loading it all into memory."""
    file_path = Path(path)
    if not file_path.exists():
        return []
    with file_path.open("r", encoding="utf-8") as fh:
        tail = collections.deque(fh, maxlen=max_lines)
    return [line.rstrip("\n") for line in tail]


# ---------------------------------------------------------------------------
# Routes — read-only (no auth required)
# ---------------------------------------------------------------------------

@app.get("/health")
def health() -> dict:
    return {
        "ok": True,
        "redis_available": state_store.is_available(),
    }


@app.get("/status")
def status() -> dict:
    return {
        "health": health(),
        "training": state_store.get_training_state(),
        "latest_model": state_store.get_latest_model(),
    }


@app.get("/training/status")
def training_status() -> dict:
    return state_store.get_training_state()


@app.get("/quorum")
def quorum() -> dict:
    return {
        "pending_clients_count": state_store.get_pending_clients_count(),
        "pending_clients": state_store.get_pending_clients(),
    }


@app.get("/logs")
def logs(lines: int = Query(default=200, ge=1, le=2000)) -> dict:
    return {
        "path": TRAINING_LOG_PATH,
        "lines": _tail_log(TRAINING_LOG_PATH, lines),
    }


@app.get("/models")
def models() -> dict:
    cached = state_store.list_models()
    return {"models": cached or list_saved_models(ARTIFACT_DIR)}


@app.get("/models/latest")
def latest_model() -> dict:
    model = state_store.get_latest_model()
    if model is None:
        saved = list_saved_models(ARTIFACT_DIR)
        if not saved:
            raise HTTPException(status_code=404, detail="No model metadata available")
        model = saved[-1]
    return model


@app.get("/models/{version}")
def model_version(version: str) -> dict:
    model = state_store.get_model(version)
    if model is not None:
        return model

    artifact = load_global_artifact(ARTIFACT_DIR, version=version)
    if artifact is None:
        raise HTTPException(status_code=404, detail=f"Model version {version} not found")
    _, metadata = artifact
    return metadata


# ---------------------------------------------------------------------------
# Routes — mutating (auth required)
# ---------------------------------------------------------------------------

@app.post("/training/start", dependencies=[_require_auth])
def start_training() -> dict:
    state_store.set_desired_training_status("running")
    state_store.set_training_status("idle")
    LOGGER.info("Training start requested via control API")
    return {"message": "Training marked as running", "training": state_store.get_training_state()}


@app.post("/training/stop", dependencies=[_require_auth])
def stop_training() -> dict:
    state_store.set_desired_training_status("stopped")
    state_store.set_training_status("stopped")
    LOGGER.info("Training stop requested via control API")
    return {"message": "Training marked as stopped", "training": state_store.get_training_state()}


@app.post("/client/register", dependencies=[_require_auth])
def register_client(data: dict) -> dict:
    client_id = data.get("client_id")
    data_hash = data.get("data_hash")
    if not client_id or not data_hash:
        raise HTTPException(status_code=400, detail="client_id and data_hash are required")
    state_store.update_client_metadata(client_id, data_hash)
    return {"message": "Client metadata updated"}


@app.post("/config/clear-hash-lock", dependencies=[_require_auth])
def clear_hash_lock(data: dict) -> dict:
    data_hash = data.get("data_hash")
    if not data_hash:
        raise HTTPException(status_code=400, detail="data_hash is required")
    state_store.remove_used_hash(data_hash)
    LOGGER.info("Manually cleared hash lock for %s", data_hash)
    return {"message": f"Hash {data_hash} removed from used pool"}


@app.post("/config/clear-client-lock", dependencies=[_require_auth])
def clear_client_lock(data: dict) -> dict:
    client_id = data.get("client_id")
    if not client_id:
        raise HTTPException(status_code=400, detail="client_id is required")
    state_store.clear_client_hash(client_id)
    LOGGER.info("Manually cleared hash lock for client %s", client_id)
    return {"message": f"Hash lock for {client_id} removed"}


@app.post("/models/{version}/evaluate", dependencies=[_require_auth])
def evaluate_model(version: str) -> dict:
    artifact = load_global_artifact(ARTIFACT_DIR, version=version)
    if artifact is None:
        raise HTTPException(status_code=404, detail=f"Model version {version} not found")

    weights, metadata = artifact
    global_test_path = os.getenv("GLOBAL_TESTING_SET") or metadata.get("reference_data_path")
    if not global_test_path:
        raise HTTPException(status_code=400, detail="Global evaluation dataset is not configured")
    loss, metrics = get_evaluate_fn(global_test_path)(int(metadata.get("round", 0)), weights, {})
    return {"version": version, "loss": loss, "metrics": metrics}
