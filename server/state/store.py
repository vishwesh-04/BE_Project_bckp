from __future__ import annotations

import json
import logging
import threading
from abc import ABC, abstractmethod
from datetime import datetime, timezone
from typing import Any

from common.config import (
    REDIS_DB,
    REDIS_ENABLED,
    REDIS_HOST,
    REDIS_PASSWORD,
    REDIS_PORT,
    REDIS_SSL,
    REDIS_URL,
    REDIS_USERNAME,
)

LOGGER = logging.getLogger(__name__)


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


class StateStore(ABC):
    @abstractmethod
    def is_available(self) -> bool:
        raise NotImplementedError

    @abstractmethod
    def get_training_state(self) -> dict[str, Any]:
        raise NotImplementedError

    @abstractmethod
    def set_training_status(self, status: str) -> None:
        raise NotImplementedError

    @abstractmethod
    def set_training_round(self, round_number: int) -> None:
        raise NotImplementedError

    @abstractmethod
    def set_training_started_at(self, started_at: str | None = None) -> None:
        raise NotImplementedError

    @abstractmethod
    def get_desired_training_status(self) -> str:
        raise NotImplementedError

    @abstractmethod
    def set_desired_training_status(self, status: str) -> None:
        raise NotImplementedError

    @abstractmethod
    def is_hash_used(self, data_hash: str) -> bool:
        raise NotImplementedError

    @abstractmethod
    def mark_hash_used(self, data_hash: str) -> None:
        raise NotImplementedError

    @abstractmethod
    def remove_used_hash(self, data_hash: str) -> None:
        raise NotImplementedError

    @abstractmethod
    def clear_client_hash(self, client_id: str) -> None:
        raise NotImplementedError

    @abstractmethod
    def get_active_session_hashes(self) -> set[str]:
        raise NotImplementedError

    @abstractmethod
    def set_active_session_hashes(self, hashes: set[str]) -> None:
        raise NotImplementedError

    @abstractmethod
    def clear_active_session_hashes(self) -> None:
        raise NotImplementedError

    @abstractmethod
    def finalize_active_session_hashes(self) -> set[str]:
        raise NotImplementedError

    @abstractmethod
    def update_client_metadata(self, client_id: str, data_hash: str) -> None:
        raise NotImplementedError

    @abstractmethod
    def mark_client_done(self, client_id: str, data_hash: str) -> None:
        raise NotImplementedError

    @abstractmethod
    def get_pending_clients_count(self) -> int:
        raise NotImplementedError

    @abstractmethod
    def get_pending_clients(self) -> list[dict[str, str]]:
        raise NotImplementedError

    @abstractmethod
    def register_model(self, version: str, metadata: dict[str, Any]) -> None:
        raise NotImplementedError

    @abstractmethod
    def get_latest_model(self) -> dict[str, Any] | None:
        raise NotImplementedError

    @abstractmethod
    def get_model(self, version: str) -> dict[str, Any] | None:
        raise NotImplementedError

    @abstractmethod
    def list_models(self) -> list[dict[str, Any]]:
        raise NotImplementedError


class InMemoryStateStore(StateStore):
    def __init__(self) -> None:
        self.training_state = {
            "training:status": "idle",
            "training:round": "0",
            "training:started_at": _utc_now(),
            "training:desired_status": "running",
        }
        self.used_hashes: set[str] = set()
        self.client_metadata: dict[str, dict[str, str]] = {}
        self.models: dict[str, dict[str, Any]] = {}
        self.latest_version: str | None = None

    def is_available(self) -> bool:
        return True

    def get_training_state(self) -> dict[str, Any]:
        return {
            "status": self.training_state["training:status"],
            "round": int(self.training_state["training:round"]),
            "started_at": self.training_state["training:started_at"],
            "desired_status": self.training_state["training:desired_status"],
        }

    def set_training_status(self, status: str) -> None:
        self.training_state["training:status"] = status

    def set_training_round(self, round_number: int) -> None:
        self.training_state["training:round"] = str(round_number)

    def set_training_started_at(self, started_at: str | None = None) -> None:
        self.training_state["training:started_at"] = started_at or _utc_now()

    def get_desired_training_status(self) -> str:
        return self.training_state["training:desired_status"]

    def set_desired_training_status(self, status: str) -> None:
        self.training_state["training:desired_status"] = status

    def is_hash_used(self, data_hash: str) -> bool:
        return data_hash in self.used_hashes

    def mark_hash_used(self, data_hash: str) -> None:
        self.used_hashes.add(data_hash)

    def remove_used_hash(self, data_hash: str) -> None:
        self.used_hashes.discard(data_hash)

    def clear_client_hash(self, client_id: str) -> None:
        metadata = self.client_metadata.get(client_id)
        if metadata:
            last = metadata.get("last_trained_hash")
            if last:
                self.used_hashes.discard(last)

    def get_active_session_hashes(self) -> set[str]:
        active = self.training_state.get("training:active_hashes", "")
        if not active:
            return set()
        return {item for item in active.split(",") if item}

    def set_active_session_hashes(self, hashes: set[str]) -> None:
        self.training_state["training:active_hashes"] = ",".join(sorted(hashes))

    def clear_active_session_hashes(self) -> None:
        self.training_state["training:active_hashes"] = ""

    def finalize_active_session_hashes(self) -> set[str]:
        hashes = self.get_active_session_hashes()
        self.used_hashes.update(hashes)
        self.clear_active_session_hashes()
        return hashes

    def update_client_metadata(self, client_id: str, data_hash: str) -> None:
        if client_id not in self.client_metadata:
            self.client_metadata[client_id] = {"current_hash": "", "last_trained_hash": ""}
        self.client_metadata[client_id]["current_hash"] = data_hash

    def mark_client_done(self, client_id: str, data_hash: str) -> None:
        if client_id not in self.client_metadata:
            self.client_metadata[client_id] = {"current_hash": data_hash, "last_trained_hash": data_hash}
        else:
            self.client_metadata[client_id]["last_trained_hash"] = data_hash
        self.mark_hash_used(data_hash)

    def get_pending_clients_count(self) -> int:
        return sum(
            1
            for metadata in self.client_metadata.values()
            if (curr := metadata.get("current_hash", "")) and not self.is_hash_used(curr)
        )

    def get_pending_clients(self) -> list[dict[str, str]]:
        return [
            {"client_id": client_id, "data_hash": curr}
            for client_id, metadata in self.client_metadata.items()
            if (curr := metadata.get("current_hash", "")) and not self.is_hash_used(curr)
        ]

    def register_model(self, version: str, metadata: dict[str, Any]) -> None:
        payload = dict(metadata)
        payload["version"] = version
        self.models[version] = payload
        self.latest_version = version

    def get_latest_model(self) -> dict[str, Any] | None:
        if self.latest_version is None:
            return None
        return self.models.get(self.latest_version)

    def get_model(self, version: str) -> dict[str, Any] | None:
        return self.models.get(version)

    def list_models(self) -> list[dict[str, Any]]:
        return [self.models[key] for key in sorted(self.models.keys())]


class RedisStateStore(StateStore):
    TRAINING_HASH = "training:state"
    USED_HASHES_KEY = "used_hashes"
    ACTIVE_SESSION_HASHES_KEY = "session:active_hashes"
    MODEL_LATEST_KEY = "model:latest"
    MODEL_INDEX_KEY = "model:versions"
    CLIENT_METADATA_PREFIX = "client:metadata"

    def __init__(self) -> None:
        import redis

        if REDIS_URL:
            self.client = redis.Redis.from_url(REDIS_URL, decode_responses=True)
        else:
            self.client = redis.Redis(
                host=REDIS_HOST,
                port=REDIS_PORT,
                db=REDIS_DB,
                username=REDIS_USERNAME,
                password=REDIS_PASSWORD,
                ssl=REDIS_SSL,
                decode_responses=True,
            )

    def is_available(self) -> bool:
        try:
            return bool(self.client.ping())
        except Exception as exc:
            LOGGER.warning("Redis ping failed: %s", exc)
            return False

    def get_training_state(self) -> dict[str, Any]:
        payload = self.client.hgetall(self.TRAINING_HASH)
        return {
            "status": payload.get("training:status", "idle"),
            "round": int(payload.get("training:round", 0)),
            "started_at": payload.get("training:started_at"),
            "desired_status": payload.get("training:desired_status", "running"),
        }

    def set_training_status(self, status: str) -> None:
        self.client.hset(self.TRAINING_HASH, "training:status", status)

    def set_training_round(self, round_number: int) -> None:
        self.client.hset(self.TRAINING_HASH, "training:round", round_number)

    def set_training_started_at(self, started_at: str | None = None) -> None:
        self.client.hset(self.TRAINING_HASH, "training:started_at", started_at or _utc_now())

    def get_desired_training_status(self) -> str:
        value = self.client.hget(self.TRAINING_HASH, "training:desired_status")
        return value or "running"

    def set_desired_training_status(self, status: str) -> None:
        self.client.hset(self.TRAINING_HASH, "training:desired_status", status)

    def is_hash_used(self, data_hash: str) -> bool:
        return bool(self.client.sismember(self.USED_HASHES_KEY, data_hash))

    def mark_hash_used(self, data_hash: str) -> None:
        self.client.sadd(self.USED_HASHES_KEY, data_hash)

    def remove_used_hash(self, data_hash: str) -> None:
        self.client.srem(self.USED_HASHES_KEY, data_hash)

    def clear_client_hash(self, client_id: str) -> None:
        key = f"{self.CLIENT_METADATA_PREFIX}:{client_id}"
        last = self.client.hget(key, "last_trained_hash")
        if last:
            self.client.srem(self.USED_HASHES_KEY, last)

    def get_active_session_hashes(self) -> set[str]:
        return {str(item) for item in self.client.smembers(self.ACTIVE_SESSION_HASHES_KEY)}

    def set_active_session_hashes(self, hashes: set[str]) -> None:
        pipeline = self.client.pipeline()
        pipeline.delete(self.ACTIVE_SESSION_HASHES_KEY)
        if hashes:
            pipeline.sadd(self.ACTIVE_SESSION_HASHES_KEY, *sorted(hashes))
        pipeline.execute()

    def clear_active_session_hashes(self) -> None:
        self.client.delete(self.ACTIVE_SESSION_HASHES_KEY)

    def finalize_active_session_hashes(self) -> set[str]:
        hashes = self.get_active_session_hashes()
        pipeline = self.client.pipeline()
        if hashes:
            pipeline.sadd(self.USED_HASHES_KEY, *sorted(hashes))
        pipeline.delete(self.ACTIVE_SESSION_HASHES_KEY)
        pipeline.execute()
        return hashes

    def update_client_metadata(self, client_id: str, data_hash: str) -> None:
        key = f"{self.CLIENT_METADATA_PREFIX}:{client_id}"
        self.client.hset(key, "current_hash", data_hash)

    def mark_client_done(self, client_id: str, data_hash: str) -> None:
        key = f"{self.CLIENT_METADATA_PREFIX}:{client_id}"
        self.client.hset(key, "last_trained_hash", data_hash)
        self.mark_hash_used(data_hash)

    def _scan_client_keys(self) -> list[str]:
        """Return all client metadata keys via SCAN (cursor-safe, no KEYS)."""
        keys: list[str] = []
        cursor = 0
        while True:
            cursor, batch = self.client.scan(cursor, match=f"{self.CLIENT_METADATA_PREFIX}:*", count=100)
            keys.extend(batch)
            if cursor == 0:
                break
        return keys

    def get_pending_clients_count(self) -> int:
        """Return the number of clients whose current hash is not yet in used_hashes.

        Uses a single Redis pipeline to batch all HGET + SISMEMBER calls instead of
        issuing one round-trip per client (O(N) → 2 round-trips regardless of N).
        """
        keys = self._scan_client_keys()
        if not keys:
            return 0

        # Batch 1: fetch current_hash for all clients
        pipe = self.client.pipeline(transaction=False)
        for key in keys:
            pipe.hget(key, "current_hash")
        current_hashes: list[str | None] = pipe.execute()

        # Batch 2: check SISMEMBER for all non-empty hashes
        nonempty = [(key, h) for key, h in zip(keys, current_hashes) if h]
        if not nonempty:
            return 0

        pipe = self.client.pipeline(transaction=False)
        for _, h in nonempty:
            pipe.sismember(self.USED_HASHES_KEY, h)
        used_flags: list[bool] = pipe.execute()

        return sum(1 for used in used_flags if not used)

    def get_pending_clients(self) -> list[dict[str, str]]:
        """Return list of pending client dicts using batched pipeline calls."""
        keys = self._scan_client_keys()
        if not keys:
            return []

        pipe = self.client.pipeline(transaction=False)
        for key in keys:
            pipe.hget(key, "current_hash")
        current_hashes: list[str | None] = pipe.execute()

        nonempty = [
            (key.split(f"{self.CLIENT_METADATA_PREFIX}:")[-1], h)
            for key, h in zip(keys, current_hashes)
            if h
        ]
        if not nonempty:
            return []

        pipe = self.client.pipeline(transaction=False)
        for _, h in nonempty:
            pipe.sismember(self.USED_HASHES_KEY, h)
        used_flags: list[bool] = pipe.execute()

        return [
            {"client_id": client_id, "data_hash": h}
            for (client_id, h), used in zip(nonempty, used_flags)
            if not used
        ]

    def register_model(self, version: str, metadata: dict[str, Any]) -> None:
        payload = json.dumps({**metadata, "version": version}, sort_keys=True)
        self.client.set(f"model:{version}", payload)
        self.client.set(self.MODEL_LATEST_KEY, payload)
        self.client.zadd(self.MODEL_INDEX_KEY, {version: float(metadata.get("round", 0))})

    def get_latest_model(self) -> dict[str, Any] | None:
        payload = self.client.get(self.MODEL_LATEST_KEY)
        return json.loads(payload) if payload else None

    def get_model(self, version: str) -> dict[str, Any] | None:
        payload = self.client.get(f"model:{version}")
        return json.loads(payload) if payload else None

    def list_models(self) -> list[dict[str, Any]]:
        versions = self.client.zrange(self.MODEL_INDEX_KEY, 0, -1)
        items: list[dict[str, Any]] = []
        for version in versions:
            model = self.get_model(version)
            if model is not None:
                items.append(model)
        return items


# ---------------------------------------------------------------------------
# Singleton factory — thread-safe double-checked locking
# ---------------------------------------------------------------------------

_STORE: StateStore | None = None
_STORE_LOCK = threading.Lock()


def get_state_store() -> StateStore:
    global _STORE
    # Fast path: no lock needed once initialized
    if _STORE is not None:
        return _STORE

    with _STORE_LOCK:
        # Re-check inside the lock to handle concurrent callers racing on startup
        if _STORE is not None:
            return _STORE

        if REDIS_ENABLED:
            try:
                store = RedisStateStore()
                if store.is_available():
                    _STORE = store
                    LOGGER.info("Using Redis state store (%s:%s db=%s)", REDIS_HOST, REDIS_PORT, REDIS_DB)
                    return _STORE
            except Exception as exc:
                LOGGER.warning("Redis unavailable, falling back to in-memory state store: %s", exc)

        LOGGER.warning(
            "Using InMemoryStateStore. NOTE: multiple processes (server, control-api) "
            "will have independent stores and will diverge. Enable Redis for production."
        )
        _STORE = InMemoryStateStore()
        return _STORE
