import json
import logging
import os
import urllib.request
from fastapi import FastAPI, HTTPException

app = FastAPI(title="FL Client Sidecar API")
LOGGER = logging.getLogger("client.sidecar")

READY_FILE_PATH = os.getenv("READY_FILE_PATH", "/tmp/client_ready.json")
CLIENT_ID = os.getenv("CLIENT_ID", "unknown_client")
SERVER_CONTROL_URL = os.getenv("SERVER_CONTROL_URL", "http://control-api:8000")

def _read_ready_state() -> bool:
    if os.path.exists(READY_FILE_PATH):
        try:
            with open(READY_FILE_PATH, "r") as f:
                data = json.load(f)
                return data.get("ready", True)
        except Exception:
            return True
    return True

def _write_ready_state(ready: bool):
    os.makedirs(os.path.dirname(READY_FILE_PATH), exist_ok=True)
    with open(READY_FILE_PATH, "w") as f:
        json.dump({"ready": ready}, f)

@app.get("/status")
def get_status():
    return {
        "client_id": CLIENT_ID,
        "ready": _read_ready_state()
    }

@app.post("/ready")
def set_ready(data: dict):
    ready_val = data.get("ready")
    if ready_val is None:
        raise HTTPException(status_code=400, detail="Missing 'ready' boolean in payload")
    _write_ready_state(bool(ready_val))
    return {"message": f"Client {CLIENT_ID} readiness set to {ready_val}"}

@app.post("/request-retrain")
def request_retrain():
    try:
        url = f"{SERVER_CONTROL_URL}/config/clear-client-lock"
        payload = json.dumps({"client_id": CLIENT_ID}).encode('utf-8')
        req = urllib.request.Request(
            url, 
            data=payload, 
            headers={'Content-Type': 'application/json'}
        )
        with urllib.request.urlopen(req, timeout=5.0) as response:
            res_body = response.read()
            return {
                "message": "Retrain requested successfully",
                "server_response": json.loads(res_body)
            }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to request retrain from server: {e}")
