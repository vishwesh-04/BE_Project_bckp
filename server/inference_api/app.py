from __future__ import annotations

from typing import Any

from dotenv import load_dotenv
from fastapi import FastAPI
from pydantic import BaseModel

from common.config import INFERENCE_API_LOG_PATH
from common.inference_service import get_model_info, predict_from_inputs
from server.logging_utils import configure_logging

load_dotenv()
LOGGER = configure_logging(INFERENCE_API_LOG_PATH, "server.inference_api")

app = FastAPI(title="FL Inference API", version="1.0.0")


class PredictRequest(BaseModel):
    inputs: dict[str, float]


@app.get("/health")
def health() -> dict[str, Any]:
    LOGGER.info("Inference health check requested")
    return {"ok": True, "model": get_model_info()}


@app.get("/model-info")
def model_info() -> dict[str, Any]:
    LOGGER.info("Inference model info requested")
    return get_model_info()


@app.post("/predict")
def predict(payload: PredictRequest) -> dict[str, Any]:
    LOGGER.info("Prediction requested for %s features", len(payload.inputs))
    return predict_from_inputs(payload.inputs).to_dict()
