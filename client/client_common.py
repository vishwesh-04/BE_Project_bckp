from __future__ import annotations

import hashlib
import logging
import os
from typing import Any, Callable, Optional

import numpy as np
import torch
import torch.nn as nn
from flwr.client import NumPyClient
from torch.utils.data import DataLoader, TensorDataset

from common.config import (
    BATCH_SIZE,
    CLIENT_DP_ENABLED,
    L2_NORM_CLIP,
    LEARNING_RATE,
    LOCAL_EPOCHS,
    NOISE_MULTIPLIER,
)
from common.data_loader import load_local_data  # moved to common/
from common.network import NeuralNetworkAlgo

LOGGER = logging.getLogger(__name__)


class FLClientRuntime(NumPyClient):
    def __init__(
        self,
        client_id: str,
        train_path: str,
        test_path: str,
        algo: NeuralNetworkAlgo,
        use_personalization: bool = False,
        # ------------------------------------------------------------------
        # Optional UI callback hooks — call notification to the Client UI.
        # on_training_start(): called when fit() begins a local training run.
        # on_training_end(success: bool): called when fit() completes/fails.
        # Both default to None; headless usage is completely unaffected.
        # ------------------------------------------------------------------
        on_training_start: Optional[Callable[[], None]] = None,
        on_training_end: Optional[Callable[[bool], None]] = None,
    ):
        self.client_id = str(client_id)
        self.train_path = train_path
        self.test_path = test_path
        self.algo = algo
        self.device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
        self.use_personalization = use_personalization
        self.is_training = False
        self._on_training_start = on_training_start
        self._on_training_end = on_training_end

    def _data_hash(self) -> str:
        if not self.train_path or not os.path.exists(self.train_path):
            return ""
        digest = hashlib.sha256()
        with open(self.train_path, "rb") as file:
            for chunk in iter(lambda: file.read(1024 * 1024), b""):
                digest.update(chunk)
        return digest.hexdigest()

    def _ready_state(self) -> tuple[bool, str]:
        ready_file = os.getenv("READY_FILE_PATH", "/tmp/client_ready.json")
        if os.path.exists(ready_file):
            try:
                import json
                with open(ready_file, "r") as f:
                    data = json.load(f)
                    if not data.get("ready", True):
                        return False, "muted_by_sidecar"
            except Exception as exc:
                # Malformed ready-file — log and treat as ready to avoid getting stuck
                LOGGER.warning("Could not parse ready-file %s: %s — treating client as ready", ready_file, exc)

        if self.is_training:
            return False, "busy"
        if not self.train_path or not os.path.exists(self.train_path):
            return False, "missing_data"
        return True, "idle"

    def get_properties(self, config: dict[str, Any]) -> dict[str, Any]:
        ready, status = self._ready_state()
        return {
            "client_id": self.client_id,
            "data_hash": self._data_hash(),
            "ready": ready,
            "status": status,
        }

    def get_parameters(self, config: dict[str, Any]):
        return self.algo.get_weights()

    def _make_private_loader(self, dataset: TensorDataset, seed: int | None = None):
        train_loader = DataLoader(dataset, batch_size=BATCH_SIZE, shuffle=True)
        optimizer = torch.optim.Adam(self.algo.model.parameters(), lr=LEARNING_RATE)
        if not CLIENT_DP_ENABLED:
            return self.algo.model, optimizer, train_loader

        try:
            from opacus import PrivacyEngine
        except Exception:
            return self.algo.model, optimizer, train_loader

        privacy_engine = PrivacyEngine()
        model, optimizer, private_loader = privacy_engine.make_private(
            module=self.algo.model,
            optimizer=optimizer,
            data_loader=train_loader,
            noise_multiplier=NOISE_MULTIPLIER,
            max_grad_norm=L2_NORM_CLIP,
            seed=seed,
        )
        return model, optimizer, private_loader

    def _train_model(self, train_path: str, data_hash: str | None = None):
        """Train local model and return (x_data, y_data)."""
        x_data, y_data = load_local_data(train_path)
        x_tensor = torch.from_numpy(x_data).float()
        y_tensor = torch.from_numpy(y_data).float().reshape(-1, 1)
        dataset = TensorDataset(x_tensor, y_tensor)

        # Use the pre-computed hash for DP seeding so the seed is stable for this dataset
        dp_seed = int(data_hash[:8], 16) if data_hash else None
        model, optimizer, train_loader = self._make_private_loader(dataset, seed=dp_seed)

        model.train()
        criterion = nn.BCELoss()
        for _ in range(LOCAL_EPOCHS):
            for batch_x, batch_y in train_loader:
                batch_x = batch_x.to(self.device)
                batch_y = batch_y.to(self.device)
                optimizer.zero_grad()
                outputs = model(batch_x)
                loss = criterion(outputs, batch_y)
                loss.backward()
                optimizer.step()

        if self.use_personalization:
            self._personalize_head(dataset)

        return x_data, y_data

    def _personalize_head(self, dataset: TensorDataset) -> None:
        named_params = list(self.algo.model.named_parameters())
        trainable_from = max(0, len(named_params) - 2)
        for idx, (_, param) in enumerate(named_params):
            param.requires_grad = idx >= trainable_from

        optimizer = torch.optim.Adam(
            filter(lambda param: param.requires_grad, self.algo.model.parameters()),
            lr=LEARNING_RATE,
        )
        loader = DataLoader(dataset, batch_size=BATCH_SIZE, shuffle=True)
        criterion = nn.BCELoss()
        self.algo.model.train()
        for batch_x, batch_y in loader:
            batch_x = batch_x.to(self.device)
            batch_y = batch_y.to(self.device)
            optimizer.zero_grad()
            outputs = self.algo.model(batch_x)
            loss = criterion(outputs, batch_y)
            loss.backward()
            optimizer.step()

        for _, param in self.algo.model.named_parameters():
            param.requires_grad = True

    def fit(self, parameters, config: dict[str, Any]):
        ready, status = self._ready_state()
        if not ready:
            return self.algo.get_weights(), 0, {"skipped": True, "status": status}

        # Compute the hash exactly once — used for DP seeding AND returned in metrics.
        # Computing it twice would double the file I/O and risk an inconsistent value if
        # the dataset file changes between reads.
        data_hash = self._data_hash()

        self.is_training = True
        if self._on_training_start is not None:
            try:
                self._on_training_start()
            except Exception as exc:
                LOGGER.debug("on_training_start callback error: %s", exc)
        try:
            base_weights = [np.asarray(layer, dtype=np.float32) for layer in parameters]
            self.algo.set_weights(base_weights)
            x_data, _ = self._train_model(self.train_path, data_hash=data_hash)
            trained_weights = self.algo.get_weights()
            if self._on_training_end is not None:
                try:
                    self._on_training_end(True)
                except Exception as exc:
                    LOGGER.debug("on_training_end callback error: %s", exc)
            return trained_weights, len(x_data), {
                "skipped": False,
                "status": "trained",
                "data_hash": data_hash,
            }
        except Exception:
            if self._on_training_end is not None:
                try:
                    self._on_training_end(False)
                except Exception as exc:
                    LOGGER.debug("on_training_end callback error: %s", exc)
            raise
        finally:
            self.is_training = False

    def evaluate(self, parameters, config: dict[str, Any]):
        self.algo.set_weights(parameters)
        loss, acc = self.algo.test(self.test_path)
        _, y_data = load_local_data(self.test_path)
        return float(loss), len(y_data), {"accuracy": float(acc)}
