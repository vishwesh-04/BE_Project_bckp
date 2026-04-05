# PLAN 1 — Foundation: Callback Bus + Process Management + Skeleton UIs

> **Scope**: Lay the architectural groundwork so every subsequent plan can build on a stable base.
> No complex features yet — just wiring and scaffolding.

---

## Background

The existing system runs as three separate Flower processes (superlink, flower-server-app, flower-supernode × N)
launched via `main.py` using `subprocess.Popen` into system terminals.
State is managed via `InMemoryStateStore` (or Redis), and two FastAPI apps (`control_api`, `inference_api`)
expose the FL system over HTTP.

The goal of this plan is to **replace the terminal-spawning approach** with a proper desktop app
that embeds process management directly inside PyQt6 and introduces a **callback/event bus**
so all UI components can react to FL system events without polling HTTP APIs.

---

## Key Architectural Decisions

> [!IMPORTANT]
> **No Docker.** Processes are launched via `subprocess.Popen` managed by the PyQt6 app.
>
> **No API polling.** UI <-> FL system integration uses a Python callback/signal bus (pubsub pattern).
> The existing FastAPI control and inference APIs remain available but are optional (external tools, curl, etc.).
>
> **Separate apps.** `server_ui/main.py` and `client_ui/main.py` are two independent executables.
> Running multiple clients on one machine means launching `client_ui/main.py` once per client with a different `CLIENT_ID` env var.

---

## New Directory Layout (additions only)

```
My-refractored/
├── ui/                             [NEW]
│   ├── __init__.py
│   ├── core/
│   │   ├── __init__.py
│   │   ├── event_bus.py            <- thread-safe Qt signal bridge
│   │   ├── process_runner.py       <- manages subprocesses, captures stdout/stderr
│   │   └── log_tail.py             <- file watcher for log files
│   ├── server_ui/
│   │   ├── __init__.py
│   │   ├── main.py                 <- entry point for Server desktop app
│   │   └── windows/
│   │       ├── __init__.py
│   │       └── main_window.py      <- QMainWindow skeleton with tab placeholders
│   └── client_ui/
│       ├── __init__.py
│       ├── main.py                 <- entry point for Client desktop app
│       └── windows/
│           ├── __init__.py
│           └── main_window.py      <- QMainWindow skeleton with tab placeholders
├── ui-requirements.txt             [NEW]
├── launch_server.py                [NEW]  <- entry point for server desktop app
└── launch_client.py                [NEW]  <- entry point for client desktop app
```

---

## Proposed Changes

---

### Component 1 — Event Bus (`ui/core/event_bus.py`)

#### [NEW] event_bus.py

A lightweight **publish-subscribe event bus** bridging background threads (FL processes, log watchers)
to the Qt main thread. All signals use `Qt.ConnectionType.QueuedConnection` automatically when
emitted from a non-GUI thread, making this thread-safe by design.

**Events to define (as typed dataclasses):**

| Event | Payload | Producer |
|---|---|---|
| `TrainingStatusChanged` | `status: str, round: int` | `ProcessRunner` parsing stdout |
| `LogLine` | `source: str, text: str` | `LogTailer` / `ProcessRunner` |
| `ClientReadyChanged` | `client_id: str, ready: bool` | `ProcessRunner` stdout parse |
| `ModelUpdated` | `version: str, metrics: dict` | artifact file watcher |
| `ProcessExited` | `name: str, exit_code: int` | `ProcessRunner` |
| `ETLStatusChanged` | `status: str` | client ETL watcher |

**Implementation sketch:**
```python
from PyQt6.QtCore import QObject, pyqtSignal

class EventBus(QObject):
    log_line = pyqtSignal(str, str)             # source, text
    training_status_changed = pyqtSignal(str, int)  # status, round
    client_ready_changed = pyqtSignal(str, bool)    # client_id, ready
    model_updated = pyqtSignal(str, dict)           # version, metrics
    process_exited = pyqtSignal(str, int)           # name, exit_code
    etl_status_changed = pyqtSignal(str)            # status

_bus: EventBus | None = None
def get_event_bus() -> EventBus: ...  # singleton accessor
```

---

### Component 2 — Process Runner (`ui/core/process_runner.py`)

#### [NEW] process_runner.py

Replaces `main.py`'s terminal-spawning approach.

**Responsibilities:**
- Launch/stop individual named processes (superlink, flower-server-app, flower-supernode).
- Capture `stdout` + `stderr` in dedicated reader threads.
- Parse known log patterns (round updates, status changes) and fire `EventBus` signals.
- Provide `is_running()`, `restart()`, `stop()` per-process methods.
- Graceful shutdown: `SIGTERM` -> wait 3s -> `SIGKILL`.

**Key design:**
```python
class ManagedProcess:
    name: str
    command: list[str]
    env: dict[str, str]
    _proc: subprocess.Popen | None
    _reader_thread: threading.Thread

    def start(self) -> None: ...
    def stop(self) -> None: ...
    def is_running(self) -> bool: ...

class ProcessManager:
    _processes: dict[str, ManagedProcess]
    def register(self, proc: ManagedProcess) -> None: ...
    def start_all(self) -> None: ...
    def stop_all(self) -> None: ...
    def get_status(self) -> dict[str, bool]: ...
```

**Log parsing patterns (regex):**
```
[ROUND N] -> emit training_status_changed("running", N)
"Training marked as stopped" -> emit training_status_changed("stopped", 0)
"Model saved" -> emit model_updated(...)
```

---

### Component 3 — Log File Tailer (`ui/core/log_tail.py`)

#### [NEW] log_tail.py

Watches the training log file on disk (already written by `configure_logging`).

- `threading.Thread` polling every 250ms: `file.seek(end)` then `file.read()`.
- Fires `log_line` events via the EventBus.
- Graceful: if log file doesn't exist yet, retries until it appears.
- Supports `stop()` for clean thread shutdown.

---

### Component 4 — Server UI Skeleton

#### [NEW] `ui/server_ui/windows/main_window.py`

`QMainWindow` with:
- **`QTabWidget`** containing 4 placeholder tabs:
  1. Overview / Status
  2. Training Logs
  3. Client Monitor
  4. Training Controls
- **Status bar** with live training status label (updated via `training_status_changed` signal).
- **Toolbar** with: "Start Server", "Stop Server", "Start All", "Stop All" buttons.
- `closeEvent` override: calls `process_manager.stop_all()`.

#### [NEW] `ui/server_ui/main.py`

```python
def main():
    load_dotenv()
    app = QApplication(sys.argv)
    bus = get_event_bus()
    pm = ProcessManager()
    # register: superlink, flower-server-app
    # optionally: control-api, inference-api via uvicorn subprocess
    window = ServerMainWindow(process_manager=pm, event_bus=bus)
    window.show()
    sys.exit(app.exec())
```

---

### Component 5 — Client UI Skeleton

#### [NEW] `ui/client_ui/windows/main_window.py`

`QMainWindow` with 5 placeholder tabs:
1. Overview / Status
2. Training Logs
3. ETL Pipeline Status
4. Inference
5. Insights Dashboard

Status bar shows client readiness.

#### [NEW] `ui/client_ui/main.py`

```python
def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--client-id", required=True)
    args = parser.parse_args()
    os.environ["CLIENT_ID"] = args.client_id
    load_dotenv()
    app = QApplication(sys.argv)
    bus = get_event_bus()
    pm = ProcessManager()
    # register: flower-supernode for this CLIENT_ID
    # optionally: client sidecar API
    window = ClientMainWindow(process_manager=pm, event_bus=bus, client_id=args.client_id)
    window.show()
    sys.exit(app.exec())
```

---

### Component 6 — Launch Scripts

#### [NEW] `launch_server.py`
Thin wrapper: `from ui.server_ui.main import main; main()`

#### [NEW] `launch_client.py`
Thin wrapper: `from ui.client_ui.main import main; main()`

#### [MODIFY] `main.py`
Add `--ui` CLI flag. When present, import and call the relevant UI main. When absent, existing `run_simulation()` runs unchanged (headless fallback).

---

### Component 7 — Dependencies

#### [NEW] `ui-requirements.txt`
```
PyQt6>=6.6,<7
PyQt6-Charts>=6.6,<7
pyqtgraph>=0.13,<1
```

---

## Integration with Existing Code

| Existing Module | Change | Reason |
|---|---|---|
| `server/state/store.py` | None | UI can read store in-process (server side) |
| `server/control_api/app.py` | None | Kept for external use; optionally launched as subprocess |
| `client/control_api/app.py` | None | Same |
| `server/event_driven_workflow.py` | Minor: optional callback arg | Fire EventBus signals at round boundaries |
| `server/custom_strategy.py` | Minor: optional callback arg | Fire EventBus on model update / session complete |
| `main.py` | Minor: add `--ui` flag | Non-destructive |

> [!NOTE]
> Callback injection is purely optional. The FL core passes a `callback: Callable | None = None`
> argument. The UI injects a lambda that calls `event_bus.signal.emit(...)`.
> Without a UI, callback is None and nothing changes.

---

## Verification Plan

### Manual Steps
1. `python launch_server.py` -> Server UI window opens with 4 tabs, no crash.
2. `python launch_client.py --client-id 1` -> Client UI window opens with 5 tabs.
3. Click "Start Server" button -> superlink and flower-server-app processes start.
4. Click "Stop All" -> all processes terminate cleanly.
5. Close the window -> `closeEvent` stops all processes; no zombie processes.

### Automated Tests (new `tests/ui/` dir)
- `test_event_bus.py`: emit signal from background thread, assert slot receives it on main thread.
- `test_managed_process.py`: start `echo hello` process, assert stdout is captured, exit callback fires.
- `test_log_tail.py`: write to a temp log file, assert `LogLine` events fire within 500ms.

---

## Open Questions

> [!IMPORTANT]
> **Q1 — Deployment topology**: Will client and server UIs run on the same machine (demo mode)
> or on separate machines (distributed hospital setup)? This affects how `ProcessManager` is
> configured in each launcher.
>
> **Q2 — Redis**: Current default is `REDIS_ENABLED=false`. For a desktop app (single machine),
> pure in-memory is sufficient. Should Redis support be dropped from the UI launcher, or kept
> as an optional env-var toggle?
>
> **Q3 — Control/Inference API subprocesses**: Should the control API and inference API
> be launched as subprocesses by the UI (clean separation), or should the UI import them
> directly into the same Python process (simpler, lower overhead)?

---

## What PLAN2 Builds On This

PLAN2 fills in the actual tab contents:
- **Server**: Real log viewer, live client status table with readiness, training parameter form.
- **Client**: ETL pipeline status panel, readiness toggle switch, live log tail.
- **Both**: Wire all EventBus signals to real widgets.
