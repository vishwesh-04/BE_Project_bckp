from __future__ import annotations

import logging
from logging import WARNING
from typing import Any, Callable, Optional

from flwr.common import (
    FitIns,
    GetPropertiesIns,
    NDArrays,
    Parameters,
    Scalar,
    ndarrays_to_parameters,
    parameters_to_ndarrays,
)
from flwr.common.logger import log
from flwr.server.client_manager import ClientManager
from flwr.server.client_proxy import ClientProxy
from flwr.server.strategy import FedAvg
from flwr.server.strategy.aggregate import aggregate as fedavg_aggregate

from common.artifacts import load_feature_reference_means, save_global_artifact
from common.config import (
    ARTIFACT_DIR,
    CENTRAL_DP_ENABLED,
    DP_MAX_NORM,
    DP_NOISE_MULTIPLIER,
    DP_NOISE_SEED,
    DASHBOARD_FEATURE_KEYS,
    MIN_CLIENTS,
    MAX_CLIENTS,
    READINESS_POLL_TIMEOUT_SECONDS,
    SECAGG_ENABLED,
)
from privacy.dp_aggregation import apply_dp_to_aggregate
from .state import get_state_store

LOGGER = logging.getLogger(__name__)


class FeatureParityFedAvg(FedAvg):
    def __init__(
        self,
        *args: Any,
        artifact_dir: str = ARTIFACT_DIR,
        reference_data_path: str | None = None,
        dashboard_feature_keys: list[str] | None = None,
        # ------------------------------------------------------------------
        # Optional UI callback — called after each model artifact is saved.
        # Signature: on_model_updated(version: str, metrics_json: str)
        # Defaults to None; headless usage is unaffected.
        # ------------------------------------------------------------------
        on_model_updated: Optional[Callable[[str, str], None]] = None,
        **kwargs: Any,
    ) -> None:
        super().__init__(*args, **kwargs)
        self.latest_parameters: NDArrays | None = None
        self.last_known_hash: dict[str, str] = {}
        self.round_candidates: dict[int, dict[str, str]] = {}
        self._prepared_clients: dict[int, list[ClientProxy]] = {}
        self.artifact_dir = artifact_dir
        self.reference_data_path = reference_data_path
        self.dashboard_feature_keys = dashboard_feature_keys or list(DASHBOARD_FEATURE_KEYS)
        self.state_store = get_state_store()
        self._session_hashes = set(self.state_store.get_active_session_hashes())
        self.reference_feature_means = load_feature_reference_means(
            self.reference_data_path,
            self.dashboard_feature_keys,
        )
        self._on_model_updated = on_model_updated

    def _get_client_id(self, client: ClientProxy, fallback: str = "unknown") -> str:
        return str(getattr(client, "cid", getattr(client, "node_id", fallback)))

    def _activate_session_hashes(self, hashes: set[str]) -> None:
        self._session_hashes = set(hashes)
        self.state_store.set_active_session_hashes(self._session_hashes)

    def complete_training_session(self) -> set[str]:
        finalized_hashes = self.state_store.finalize_active_session_hashes()
        self._session_hashes = set()
        self.round_candidates.clear()
        self._prepared_clients.clear()
        return finalized_hashes

    def abort_training_session(self) -> None:
        self.state_store.set_active_session_hashes(set())
        self._session_hashes = set()
        self.round_candidates.clear()
        self._prepared_clients.clear()

    def _persist_global_artifact(self, server_round: int, metrics: dict[str, Any], source: str) -> None:
        if self.latest_parameters is None:
            return
        metadata = {
            "version": f"v{server_round}",
            "round": server_round,
            "source": source,
            "reference_data_path": self.reference_data_path,
            "feature_names": self.dashboard_feature_keys,
            "feature_reference_means": self.reference_feature_means,
            "metrics": metrics,
            "model_parameter_count": len(self.latest_parameters),
        }
        save_global_artifact(self.latest_parameters, metadata, artifact_dir=self.artifact_dir)
        version = f"v{server_round}"
        self.state_store.register_model(version, metadata)
        # Fire UI callback if registered
        if self._on_model_updated is not None:
            try:
                import json
                self._on_model_updated(version, json.dumps({k: v for k, v in metrics.items() if isinstance(v, (int, float, str, bool))}))
            except Exception as exc:
                LOGGER.debug("on_model_updated callback error: %s", exc)

    def initialize_parameters(self, client_manager: ClientManager) -> Parameters | None:
        parameters = super().initialize_parameters(client_manager)
        if parameters is not None:
            self.latest_parameters = parameters_to_ndarrays(parameters)
            self._persist_global_artifact(0, {"initial_parameters": True}, source="initial")
        return parameters

    def _request_properties(self, client: ClientProxy, server_round: int) -> dict[str, Scalar]:
        ins = GetPropertiesIns({"server_round": server_round})
        timeout = READINESS_POLL_TIMEOUT_SECONDS
        try:
            response = client.get_properties(ins, timeout=timeout, group_id=server_round)
        except TypeError:
            try:
                response = client.get_properties(ins, timeout=timeout)
            except TypeError:
                response = client.get_properties(ins)
        return dict(response.properties)

    def _current_parameters(self) -> Parameters | None:
        if self.latest_parameters is not None:
            return ndarrays_to_parameters(self.latest_parameters)
        if self.initial_parameters is not None:
            return self.initial_parameters
        return None

    def poll_ready_updates(self, server_round: int, client_manager: ClientManager) -> int:
        available_clients = list(client_manager.all().values())
        ready_session_clients: list[ClientProxy] = []
        ready_new_clients: list[ClientProxy] = []
        current_hashes: dict[str, str] = {}
        session_hashes = set(self.state_store.get_active_session_hashes()) or set(self._session_hashes)
        self._session_hashes = session_hashes

        for client in available_clients:
            client_id = self._get_client_id(client)
            try:
                properties = self._request_properties(client, server_round)
            except Exception as exc:
                log(WARNING, "Failed to fetch readiness from client %s: %s", client_id, exc)
                continue

            data_hash = str(properties.get("data_hash", ""))
            is_ready = bool(properties.get("ready", False))
            if not data_hash:
                continue

            if data_hash in session_hashes:
                current_hashes[client_id] = data_hash
                if is_ready:
                    ready_session_clients.append(client)
                continue

            if self.state_store.is_hash_used(data_hash):
                LOGGER.info("Skipping client %s because hash %s already participated", client_id, data_hash)
                continue

            current_hashes[client_id] = data_hash
            if is_ready:
                ready_new_clients.append(client)

        combined_clients = ready_session_clients
        if server_round == 1:
            combined_clients += ready_new_clients

        if len(combined_clients) < MIN_CLIENTS:
            self._prepared_clients.pop(server_round, None)
            self.round_candidates[server_round] = {}
            return len(combined_clients)

        sample_size, min_num_clients = self.num_fit_clients(len(combined_clients))
        selected_count = max(min_num_clients, min(sample_size, len(combined_clients), MAX_CLIENTS))
        selected_clients = combined_clients[:selected_count]

        selected_hashes = {
            current_hashes[self._get_client_id(client, str(idx))]
            for idx, client in enumerate(selected_clients)
            if self._get_client_id(client, str(idx)) in current_hashes
        }
        
        new_hashes = session_hashes.union(selected_hashes)
        if new_hashes != session_hashes:
            self._activate_session_hashes(new_hashes)
            session_hashes = new_hashes

        selected_ids = [
            self._get_client_id(client, str(idx))
            for idx, client in enumerate(selected_clients)
        ]
        self._prepared_clients[server_round] = selected_clients
        self.round_candidates[server_round] = {
            client_id: current_hashes[client_id]
            for client_id in selected_ids
            if client_id in current_hashes
        }
        return len(selected_clients)

    def has_pending_round(self, server_round: int, client_manager: ClientManager) -> bool:
        return self.poll_ready_updates(server_round, client_manager) >= MIN_CLIENTS

    def configure_fit(self, server_round: int, parameters: Parameters, client_manager: ClientManager):
        selected_clients = self._prepared_clients.pop(server_round, None)
        if selected_clients is None:
            if self.poll_ready_updates(server_round, client_manager) < MIN_CLIENTS:
                return []
            selected_clients = self._prepared_clients.pop(server_round, [])
        if not selected_clients:
            return []

        config: dict[str, Scalar] = {}
        if self.on_fit_config_fn is not None:
            config.update(self.on_fit_config_fn(server_round))
        config["server_round"] = server_round
        config["secagg_enabled"] = bool(SECAGG_ENABLED)

        fit_ins = FitIns(parameters, config)
        return [(client, fit_ins) for client in selected_clients]

    def aggregate_fit(self, server_round: int, results, failures):
        if not results:
            log(WARNING, "Round %s produced no fit results; keeping previous global model", server_round)
            self._prepared_clients.pop(server_round, None)
            return self._current_parameters(), {"round_failed": True}

        if len(results) < MIN_CLIENTS:
            log(
                WARNING,
                "Round %s below minimum result threshold (%s < %s); keeping previous model",
                server_round,
                len(results),
                MIN_CLIENTS,
            )
            self._prepared_clients.pop(server_round, None)
            return self._current_parameters(), {
                "round_failed": True,
                "reason": "below_min_clients",
            }

        if self.latest_parameters is None:
            if self.initial_parameters is None:
                return None, {"round_failed": True, "reason": "missing_initial_parameters"}
            self.latest_parameters = parameters_to_ndarrays(self.initial_parameters)
        current_weights = self.latest_parameters

        # Proper weighted FedAvg — average all clients' updates weighted by num_examples.
        # Previously this incorrectly used only results[0], discarding every other client.
        weights_results = [
            (parameters_to_ndarrays(fit_res.parameters), fit_res.num_examples)
            for _, fit_res in results
        ]
        aggregated_parameters = fedavg_aggregate(weights_results)

        if CENTRAL_DP_ENABLED:
            aggregated_update = [new - cur for new, cur in zip(aggregated_parameters, current_weights)]
            aggregated_update = apply_dp_to_aggregate(
                aggregated_update,
                max_norm=DP_MAX_NORM,
                noise_multiplier=DP_NOISE_MULTIPLIER,
                seed=DP_NOISE_SEED + server_round,
            )
            new_weights = [layer + delta for layer, delta in zip(current_weights, aggregated_update)]
        else:
            new_weights = aggregated_parameters

        round_hashes = self.round_candidates.pop(server_round, {})
        self._prepared_clients.pop(server_round, None)
        for client_proxy, _ in results:
            client_id = self._get_client_id(client_proxy)
            if client_id in round_hashes:
                self.last_known_hash[client_id] = round_hashes[client_id]

        self.latest_parameters = new_weights
        metrics = {}
        if self.fit_metrics_aggregation_fn is not None:
            metrics = self.fit_metrics_aggregation_fn(
                [(fit_res.num_examples, fit_res.metrics) for _, fit_res in results]
            )
        metrics["participants"] = len(results)
        metrics["secagg_protected"] = bool(SECAGG_ENABLED)
        metrics["central_dp_enabled"] = bool(CENTRAL_DP_ENABLED)
        metrics["active_session_hashes"] = len(self._session_hashes)
        self._persist_global_artifact(server_round, metrics, source="aggregation")
        return ndarrays_to_parameters(new_weights), metrics
