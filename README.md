# Federated Learning Feature-Parity Runtime

This runtime keeps the current Flower-based architecture while using Docker-safe startup commands that launch long-running Flower processes.

Implemented capabilities:
- Server-side central differential privacy over aggregated client updates
- Flower SecAgg+ support during fit rounds
- Event-driven, hash-based round triggering
- Optional client personalization
- Docker/local launch paths aligned with `flower-superlink`, `flower-server-app`, and `flower-supernode`
- Redis-backed server state hooks for training status, model registry, and used-hash tracking
- FastAPI control API for health, training state, logs, and model metadata

## Runtime startup

- Server container/local process starts a Flower SuperLink and then attaches `server.server_app:app`
- Client container/local process starts a Flower SuperNode and attaches `client.client_app:app`
- Default fleet address is `SERVER_ADDRESS` / `CLIENT_SERVER_ADDRESS` on port `45678`
- Default internal driver address for the server app is `SERVER_DRIVER_ADDRESS=127.0.0.1:9091`

## Local run

Run all four local processes in separate terminals:

```bash
python main.py
```

## Docker run

Build images:

```bash
docker build -f Dockerfile.server -t fl-server .
docker build -f Dockerfile.client -t fl-client .
docker build -f Dockerfile.control-api -t fl-control-api .
docker build -f Dockerfile.inference-api -t fl-inference-api .
```

Run the server:

```bash
docker run --rm -p 45678:45678 --env-file server.env fl-server
```

Run a client:

```bash
docker run --rm --env-file examples/client1.env.example fl-client
```

Run the control API:

```bash
docker run --rm -p 8000:8000 --env-file server.env fl-control-api
```

Run the inference API:

```bash
docker run --rm -p 8001:8001 --env-file server.env fl-inference-api
```

Local control API run:

```bash
python -m uvicorn server.control_api.app:app --host 0.0.0.0 --port 8000
```

Example control API calls:

```bash
curl http://127.0.0.1:8000/health
curl http://127.0.0.1:8000/training/status
curl -X POST http://127.0.0.1:8000/training/stop
curl http://127.0.0.1:8000/models/latest
curl http://127.0.0.1:8000/logs
```

Redis notes:

- Set `REDIS_ENABLED=true` and provide `REDIS_HOST`/`REDIS_PORT` or `REDIS_URL` in `server.env`
- When Redis is enabled, the server owns `used_hashes`, training state, and model metadata in Redis
- If Redis is disabled or unavailable, the training runtime falls back to in-memory state for local development

Version compatibility notes:

- `flwr` is pinned to the `1.10.x` line because the current runtime wrappers and workflow integration target that CLI/runtime shape
- `FastAPI`, `uvicorn`, `redis`, and `streamlit` are installed alongside the training runtime for control-plane and dashboard services

## Dashboard

Install dependencies, then run:

```bash
streamlit run dashboard/app.py
```

Docker image:

```bash
docker build -f Dockerfile.dashboard -t fl-dashboard .
docker run --rm -p 8501:8501 --env-file server.env fl-dashboard
```

## Docker Compose

Bring up Redis, server runtime, control API, dashboard, and one client:

```bash
docker compose up --build
```

Bring up all three clients as well:

```bash
docker compose --profile multi-client up --build
```

Compose services:

- `redis` stores server-owned training state, used hashes, and model metadata
- `server` runs Flower training/orchestration
- `control-api` exposes health, status, logs, and model registry endpoints on `:8000`
- `inference-api` serves prediction and model-info endpoints on `:8001`
- `dashboard` serves the Streamlit UI on `:8501` and reads runtime status/logs from `CONTROL_API_URL` plus prediction/insight data from `INFERENCE_API_URL`
- `client1` starts by default; `client2` and `client3` are available via the `multi-client` profile

Dashboard/control API wiring:

- Local default: `CONTROL_API_URL=http://127.0.0.1:8000`
- Compose default: `CONTROL_API_URL=http://control-api:8000`
- Local default: `INFERENCE_API_URL=http://127.0.0.1:8001`
- Compose default: `INFERENCE_API_URL=http://inference-api:8001`
- The dashboard uses the control API for runtime status, model registry, and log viewing, and uses the inference API for prediction and clinical insights

Key config lives in `.env`, `server.env`, and `common/config.py`.
