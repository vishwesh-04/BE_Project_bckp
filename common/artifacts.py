from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable

import numpy as np
import pandas as pd

from .config import ARTIFACT_DIR


LATEST_MODEL_FILENAME = "latest_global_model.npz"
LATEST_METADATA_FILENAME = "latest_global_metadata.json"


def _versioned_model_filename(version: str) -> str:
    return f"global_model_{version}.npz"


def _versioned_metadata_filename(version: str) -> str:
    return f"global_model_{version}.json"


def get_artifact_dir(artifact_dir: str | os.PathLike[str] | None = None) -> Path:
    return Path(artifact_dir or ARTIFACT_DIR)


def _json_ready(value):
    if isinstance(value, (np.floating, np.integer)):
        return value.item()
    if isinstance(value, np.ndarray):
        return value.tolist()
    if isinstance(value, dict):
        return {str(key): _json_ready(val) for key, val in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json_ready(item) for item in value]
    return value


def load_feature_reference_means(
    data_path: str | os.PathLike[str] | None,
    feature_keys: Iterable[str],
) -> dict[str, float] | None:
    if not data_path:
        return None

    path = Path(data_path)
    if not path.exists():
        return None

    try:
        frame = pd.read_csv(path)
    except Exception:
        return None

    means: dict[str, float] = {}
    for key in feature_keys:
        if key in frame.columns:
            means[str(key)] = float(frame[key].mean())

    return means or None


def save_global_artifact(
    weights,
    metadata: dict,
    artifact_dir: str | os.PathLike[str] | None = None,
) -> tuple[Path, Path]:
    directory = get_artifact_dir(artifact_dir)
    directory.mkdir(parents=True, exist_ok=True)

    version = str(metadata.get("version", f"v{metadata.get('round', 0)}"))
    model_path = directory / LATEST_MODEL_FILENAME
    metadata_path = directory / LATEST_METADATA_FILENAME
    versioned_model_path = directory / _versioned_model_filename(version)
    versioned_metadata_path = directory / _versioned_metadata_filename(version)

    arrays = {f"w{i}": np.asarray(weight) for i, weight in enumerate(weights)}
    np.savez_compressed(model_path, **arrays)
    np.savez_compressed(versioned_model_path, **arrays)

    payload = {
        "updated_at": datetime.now(timezone.utc).isoformat(),
        **_json_ready(metadata),
    }
    with metadata_path.open("w", encoding="utf-8") as file:
        json.dump(payload, file, indent=2, sort_keys=True)

    with versioned_metadata_path.open("w", encoding="utf-8") as file:
        json.dump(payload, file, indent=2, sort_keys=True)

    return model_path, metadata_path


def load_global_artifact(
    artifact_dir: str | os.PathLike[str] | None = None,
    version: str | None = None,
) -> tuple[list[np.ndarray], dict] | None:
    directory = get_artifact_dir(artifact_dir)
    if version is None:
        model_path = directory / LATEST_MODEL_FILENAME
        metadata_path = directory / LATEST_METADATA_FILENAME
    else:
        model_path = directory / _versioned_model_filename(version)
        metadata_path = directory / _versioned_metadata_filename(version)

    if not model_path.exists() or not metadata_path.exists():
        return None

    with np.load(model_path, allow_pickle=False) as data:
        weights = [data[key] for key in sorted(data.files, key=lambda name: int(name[1:]))]

    with metadata_path.open("r", encoding="utf-8") as file:
        metadata = json.load(file)

    return weights, metadata


def get_latest_metadata(artifact_dir: str | os.PathLike[str] | None = None) -> dict | None:
    directory = get_artifact_dir(artifact_dir)
    metadata_path = directory / LATEST_METADATA_FILENAME
    
    if not metadata_path.exists():
        return None
        
    try:
        with metadata_path.open("r", encoding="utf-8") as file:
            return json.load(file)
    except Exception:
        return None



def list_saved_models(artifact_dir: str | os.PathLike[str] | None = None) -> list[dict]:
    directory = get_artifact_dir(artifact_dir)
    if not directory.exists():
        return []

    records: list[dict] = []
    for metadata_path in sorted(directory.glob("global_model_v*.json")):
        try:
            with metadata_path.open("r", encoding="utf-8") as file:
                records.append(json.load(file))
        except Exception:
            continue
    return records
