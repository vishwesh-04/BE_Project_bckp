from __future__ import annotations

import logging
import pickle

import numpy as np
import pandas as pd

from common.config import COLUMNS_PATH, SCALER_PATH

LOGGER = logging.getLogger(__name__)


def load_local_data(path: str) -> tuple[np.ndarray, np.ndarray]:
    """Load, scale, and return (X, y) arrays from a CSV dataset.

    The scaler and column list are read from the paths defined in config.
    Missing columns are filled with 0 and logged as a warning.
    """
    with open(SCALER_PATH, "rb") as fh:
        scaler = pickle.load(fh)  # noqa: S301 — integrity checked at build time
    with open(COLUMNS_PATH, encoding="utf-8") as fh:
        cols = [line.strip() for line in fh if line.strip()]

    df = pd.read_csv(path)

    # Derive age_years from raw age (days) if needed
    if "age_years" not in df.columns:
        if "age" in df.columns:
            df["age_years"] = df["age"] / 365
        else:
            df["age_years"] = 0

    y = df["cardio"].values

    # Fill missing expected columns with 0 and log a warning
    missing = [c for c in cols if c not in df.columns]
    if missing:
        LOGGER.warning("Missing columns in %s: %s — defaulting to 0", path, missing)
        for col in missing:
            df[col] = 0

    x_scaled = scaler.transform(df[cols])
    return x_scaled.astype(np.float32), y.astype(np.float32)
