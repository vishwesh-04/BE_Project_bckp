from __future__ import annotations

import os
from typing import Any

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from fastapi.responses import JSONResponse

from common.artifacts import list_saved_models, load_global_artifact
from common.config import ARTIFACT_DIR, MODEL_API_LOG_PATH
from server.logging_utils import configure_logging
from server.state import get_state_store

load_dotenv()
LOGGER = configure_logging(MODEL_API_LOG_PATH, "server.model_api")

app = FastAPI(title="FL Model API", version="1.0.0")
state_store = get_state_store()


@app.get("/health")
def health() -> dict[str, Any]:
    return {"ok": True, "redis_available": state_store.is_available()}


@app.get("/models")
def models() -> dict[str, Any]:
    cached = state_store.list_models()
    return {"models": cached or list_saved_models(ARTIFACT_DIR)}


@app.get("/models/latest")
def latest_model() -> dict[str, Any]:
    model = state_store.get_latest_model()
    if model is None:
        saved = list_saved_models(ARTIFACT_DIR)
        if not saved:
            raise HTTPException(status_code=404, detail="No model metadata available")
        model = saved[-1]
    return model


@app.get("/models/{version}")
def model_version(version: str) -> dict[str, Any]:
    model = state_store.get_model(version)
    if model is not None:
        return model

    artifact = load_global_artifact(ARTIFACT_DIR, version=version)
    if artifact is None:
        raise HTTPException(status_code=404, detail=f"Model version {version} not found")
    _, metadata = artifact
    return metadata
