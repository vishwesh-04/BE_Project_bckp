from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any, Mapping
import pickle

import numpy as np
import pandas as pd
import torch

from common.artifacts import load_global_artifact, get_latest_metadata
from common.config import ARTIFACT_DIR, COLUMNS_PATH, DASHBOARD_FEATURE_KEYS, SCALER_PATH, get_input_dim
from common.network import NeuralNetworkAlgo


@dataclass
class FeatureInsight:
    key: str
    label: str
    value: float
    reference: float | None
    delta: float | None
    delta_percent: float | None
    contribution: float
    comparison_text: str


@dataclass
class PredictionResult:
    probability: float
    risk_label: str
    summary: str
    insights: list[FeatureInsight]
    model_loaded: bool
    metadata: dict[str, Any]
    reference_note: str

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        return payload


def _load_columns() -> list[str]:
    with open(COLUMNS_PATH, "r", encoding="utf-8") as file:
        return [line.strip() for line in file.readlines() if line.strip()]


def _load_scaler():
    with open(SCALER_PATH, "rb") as file:
        return pickle.load(file)


def _fallback_reference_values(columns: list[str], reference_means: dict[str, float] | None) -> dict[str, float]:
    values = {column: 0.0 for column in columns}
    if reference_means:
        for key, value in reference_means.items():
            if key in values:
                values[key] = float(value)
    return values


def _risk_label(probability: float) -> str:
    if probability < 0.30:
        return "Low"
    if probability <= 0.70:
        return "Medium"
    return "High"


def _summary_from_driver(insights: list[FeatureInsight], reference_note: str) -> str:
    if not insights:
        return "No driver data available yet."
    strongest = max(insights, key=lambda item: abs(item.contribution))
    direction = "increases" if strongest.contribution >= 0 else "reduces"
    if strongest.delta_percent is not None:
        comparison = f"It is {abs(strongest.delta_percent):.1f}% {'above' if strongest.delta_percent >= 0 else 'below'} the federated norm."
    else:
        comparison = ""
    return f"{reference_note} {strongest.label} is the strongest driver and {direction} the model risk signal. {comparison}".strip()


def _build_model() -> NeuralNetworkAlgo:
    return NeuralNetworkAlgo(input_dim=get_input_dim())


def _predict_probability(model: NeuralNetworkAlgo, raw_vector: np.ndarray, scaler, columns: list[str]) -> float:
    scaled = scaler.transform(pd.DataFrame([raw_vector], columns=columns)).astype(np.float32)
    tensor = torch.from_numpy(scaled).float().to(model.device)
    model.model.eval()
    with torch.no_grad():
        output = model.model(tensor)
    return float(output.item())


_cache: dict[str, Any] = {
    "columns": None,
    "scaler": None,
    "model": None,
    "metadata": None,
    "version": None,
}

def _get_cached_assets():
    if _cache["columns"] is None:
        _cache["columns"] = _load_columns()
    if _cache["scaler"] is None:
        _cache["scaler"] = _load_scaler()

    # Fast polling: only read the JSON metadata first
    latest_metadata = get_latest_metadata(ARTIFACT_DIR)
    
    if latest_metadata is None:
        if _cache["model"] is None:
            model = _build_model()
            _cache["model"] = model
            _cache["metadata"] = {"feature_reference_means": None, "round": None, "source": "default"}
            _cache["version"] = "default"
    else:
        version = latest_metadata.get("version", latest_metadata.get("updated_at", "unknown"))
        if _cache["version"] != version:
            # Version changed — perform the heavy disk I/O to load weights
            artifact = load_global_artifact(ARTIFACT_DIR)
            if artifact is not None:
                weights, full_metadata = artifact
                model = _build_model()
                model.set_weights(weights)
                _cache["model"] = model
                _cache["metadata"] = full_metadata
                _cache["version"] = version
            else:
                # Artifact file not yet flushed to disk (race between writer and reader).
                # Log a warning but intentionally do NOT update _cache["version"] so that
                # the next request retries the reload instead of permanently serving stale weights.
                import logging as _logging
                _logging.getLogger(__name__).warning(
                    "Model version %s detected in metadata but artifact not yet readable — "
                    "serving previous version until reload succeeds.",
                    version,
                )

    return _cache["columns"], _cache["model"], _cache["scaler"], _cache["metadata"]

def get_model_info() -> dict[str, Any]:
    _, _, _, metadata = _get_cached_assets()
    if metadata.get("source") == "default":
        return {"available": False, "metadata": None}
    return {"available": True, "metadata": metadata}

def predict_from_inputs(inputs: Mapping[str, float]) -> PredictionResult:
    columns, model, scaler, metadata = _get_cached_assets()

    reference_means = metadata.get("feature_reference_means") if isinstance(metadata, dict) else None
    reference_round = metadata.get("round") if isinstance(metadata, dict) else None
    reference_source = metadata.get("source") if isinstance(metadata, dict) else None
    raw_values = _fallback_reference_values(columns, reference_means)
    for key, value in inputs.items():
        if key in raw_values:
            raw_values[key] = float(value)

    ordered_raw = np.array([raw_values[column] for column in columns], dtype=np.float32)
    probability = _predict_probability(model, ordered_raw, scaler, columns)

    insights: list[FeatureInsight] = []
    for key in DASHBOARD_FEATURE_KEYS:
        if key not in raw_values:
            continue
        reference = reference_means.get(key) if isinstance(reference_means, dict) else None
        value = raw_values[key]
        delta = None if reference is None else value - reference
        use_percent = reference is not None and abs(reference) >= 1.0
        delta_percent = (delta / reference) * 100.0 if use_percent else None

        step = max(abs(value) * 0.05, 1.0)
        adjusted = ordered_raw.copy()
        adjusted[columns.index(key)] = value + step
        perturbed_probability = _predict_probability(model, adjusted, scaler, columns)
        contribution = (perturbed_probability - probability) / step

        if delta is None:
            comparison_text = "No federated norm available"
        elif delta_percent is None:
            comparison_text = f"{abs(delta):.2f} {'above' if delta >= 0 else 'below'} federated norm"
        else:
            comparison_text = f"{abs(delta_percent):.1f}% {'above' if delta_percent >= 0 else 'below'} federated norm"

        insights.append(
            FeatureInsight(
                key=key,
                label=key.replace("_", " ").title(),
                value=float(value),
                reference=None if reference is None else float(reference),
                delta=None if delta is None else float(delta),
                delta_percent=None if delta_percent is None else float(delta_percent),
                contribution=float(contribution),
                comparison_text=comparison_text,
            )
        )

    reference_note = (
        f"Compared with federated round {reference_round} ({reference_source or 'latest'}),"
        if reference_round is not None
        else "Compared with the current federated norm,"
    )
    summary = _summary_from_driver(insights, reference_note)
    return PredictionResult(
        probability=probability,
        risk_label=_risk_label(probability),
        summary=summary,
        insights=insights,
        model_loaded=True,
        metadata=metadata,
        reference_note=reference_note,
    )
