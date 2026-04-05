# PLAN 2 — Server UI Tabs + Client Core Tabs (Log Viewer, Client Monitor, Controls, ETL, Readiness)

> **Depends on**: PLAN 1 completed (EventBus, ProcessManager, skeleton QMainWindow windows).
> **Scope**: Implement the functional content of all tabs except Inference and Insights Dashboard (those come in PLAN 3).

---

## Goal

Replace all placeholder tab widgets with real, working panels that display live data from:
1. The FL training log file (via `LogTailer`).
2. The `InMemoryStateStore` (polled via `QTimer` every 1s).
3. The `EventBus` signals fired by `ProcessRunner` and workflow callbacks.

---

## Server UI — Tab Implementations

---

### Tab 1 — Overview / Status (`ui/server_ui/widgets/overview_panel.py`)

#### [NEW] `overview_panel.py`

A `QWidget` with a grid layout showing:

| Field | Widget | Data Source |
|---|---|---|
| Training Status | `QLabel` (colored badge) | `EventBus.training_status_changed` |
| Current Round | `QLabel` | `EventBus.training_status_changed` |
| Session Started At | `QLabel` | `StateStore.get_training_state()["started_at"]` |
| Connected Clients | `QLabel` | `StateStore.get_pending_clients_count()` |
| Models Saved | `QLabel` | `StateStore.list_models()` count |
| Redis Available | `QLabel` (green/red) | `StateStore.is_available()` |

**Update mechanism:**
- `QTimer(interval=1000)` polling `state_store.get_training_state()`.
- `EventBus.training_status_changed` for immediate event-driven updates.

---

### Tab 2 — Training Logs (`ui/server_ui/widgets/log_viewer.py`)

#### [NEW] `log_viewer.py`

A reusable `QWidget` containing:
- `QPlainTextEdit` (read-only, monospace font, dark background).
- Auto-scroll to bottom on new lines (with a "Pin to bottom" toggle checkbox).
- Search bar (`QLineEdit`) with live highlight (`QTextEdit.find()`).
- Log level color coding (via string matching + `QTextCharFormat`):
  - `ERROR` -> red
  - `WARNING` -> orange
  - `INFO` -> light gray
  - `[ROUND N]` -> cyan highlight
- "Clear" and "Export to file" buttons.

**Data source:** `EventBus.log_line` signal (fired by `LogTailer` watching `TRAINING_LOG_PATH`).

> [!NOTE]
> `LogViewer` is a shared reusable widget used in BOTH server and client UIs.
> It lives at `ui/shared/widgets/log_viewer.py`.

---

### Tab 3 — Client Monitor (`ui/server_ui/widgets/client_monitor.py`)

#### [NEW] `client_monitor.py`

A `QWidget` with a `QTableWidget` showing per-client status:

| Column | Source |
|---|---|
| Client ID | `state_store.get_pending_clients()` |
| Status | Derived from readiness / training state |
| Data Hash (short) | `client["data_hash"][:12]` |
| Last Seen | Inferred from event timestamps |
| Ready | Green/Red badge |

**Update mechanism:**
- `QTimer(interval=2000)` refreshing from `state_store.get_pending_clients()`.
- `EventBus.client_ready_changed` for immediate updates.

Extra: a "Force Retrain" button per row that calls `state_store.clear_client_hash(client_id)`.

---

### Tab 4 — Training Controls (`ui/server_ui/widgets/training_controls.py`)

#### [NEW] `training_controls.py`

A `QScrollArea` containing a form with editable training parameters:

**Read from / Write to `.env` file and `state_store`:**

| Parameter | Widget | Env Var |
|---|---|---|
| Min Clients | `QSpinBox` | `MIN_CLIENTS` |
| Training Rounds | `QSpinBox` | `TRAINING_SESSION_ROUNDS` |
| Local Epochs | `QSpinBox` | `LOCAL_EPOCHS` |
| Batch Size | `QSpinBox` | `BATCH_SIZE` |
| Learning Rate | `QDoubleSpinBox` | `LEARNING_RATE` |
| Session Cooldown (s) | `QDoubleSpinBox` | `SESSION_COOLDOWN_SECONDS` |
| SecAgg Enabled | `QCheckBox` | `SECAGG_ENABLED` |
| Central DP Enabled | `QCheckBox` | `CENTRAL_DP_ENABLED` |

**Buttons:**
- "Start Training" -> `state_store.set_desired_training_status("running")`
- "Stop Training" -> `state_store.set_desired_training_status("stopped")`
- "Apply Parameters" -> writes changed values back to `.env` file + shows restart-required notice.

> [!WARNING]
> Parameter changes (epochs, batch size, etc.) require restarting the flower-server-app process
> because they are read at process startup from env. The UI must warn the user and offer
> a "Restart Server" button after applying changes.

---

## Client UI — Tab Implementations

---

### Tab 1 — Overview / Status (`ui/client_ui/widgets/overview_panel.py`)

#### [NEW] client `overview_panel.py`

Shows client-specific status:

| Field | Widget | Source |
|---|---|---|
| Client ID | `QLabel` | Env / CLI arg |
| Readiness | Toggle `QPushButton` (Ready / Not Ready) | `client/control_api` ready-file |
| FL Process Status | `QLabel` | `EventBus.process_exited` / `ProcessRunner.is_running()` |
| Training Status | `QLabel` | `EventBus.training_status_changed` |
| Current Round | `QLabel` | `EventBus.training_status_changed` |

**Readiness toggle mechanism:**
- Button toggles between "Ready" (green) and "Not Ready" (red).
- Internally writes to `READY_FILE_PATH` (same file the FL client reads via `_ready_state()`).
- No HTTP call needed — direct file write via `json.dump({"ready": bool}, f)`.

---

### Tab 2 — Training Logs

Reuses `ui/shared/widgets/log_viewer.py`.
Source: `EventBus.log_line` filtered by `source == "client"`.
Alternatively: tails a client-specific log file if `TRAINING_LOG_PATH` is client-scoped.

---

### Tab 3 — ETL Pipeline Status (`ui/client_ui/widgets/etl_panel.py`)

#### [NEW] `etl_panel.py`

Displays the state of the client's data:

| Field | Widget | Source |
|---|---|---|
| Training Data Path | `QLabel` | `.env` `CLIENT_N_TRAINING_SET` |
| Testing Data Path | `QLabel` | `.env` `CLIENT_N_TESTING_SET` |
| Data File Exists | `QLabel` (green/red) | `os.path.exists(train_path)` |
| File Size | `QLabel` | `os.path.getsize()` |
| Data Hash | `QLabel` (first 12 chars) | SHA-256 computed async |
| Hash Status | `QLabel` | Is hash in "used hashes"? (via StateStore if local) |
| Scaler Available | `QLabel` | `os.path.exists(SCALER_PATH)` |
| Columns File Available | `QLabel` | `os.path.exists(COLUMNS_PATH)` |

**Hash computation:**
- Done in a `QThread` (non-blocking) to avoid freezing UI.
- Updates `QLabel` when done.

**"Refresh" button**: re-runs all checks.

**ETL Pipeline Readiness indicator**: a composite green/yellow/red badge based on all checks passing.
This connects to `EventBus.etl_status_changed`.

---

## Shared Widgets

### [NEW] `ui/shared/widgets/status_badge.py`
A `QLabel` subclass that shows colored rounded-rectangle badges.
Colors: green=running, orange=idle/cooldown, red=stopped/error, blue=initializing.

### [NEW] `ui/shared/widgets/log_viewer.py`
(moved from server-only to shared; used by both server and client)

---

## StateStore Access from UI

> [!IMPORTANT]
> The `InMemoryStateStore` singleton is per-process. This means:
> - If the Server UI launches `flower-server-app` as a **subprocess**, the UI process and the FL process have **separate** stores.
> - To get near-realtime state without Redis, the Server UI must either:
>   a. **Launch flower-server-app in the same Python process** (in a thread) — complex but gives shared memory.
>   b. **Parse stdout** from the subprocess for state signals (simpler, already planned in `ProcessRunner`).
>   c. **Use the control API** (uvicorn subprocess) and poll HTTP — avoids shared memory issues.

**Decision for PLAN 2**: Use option (b) — parse stdout + `EventBus` signals for real-time state.
Use `QTimer` polling of the log file as a fallback for status reconstruction.
Full in-process integration (option a) is deferred to PLAN 4 if needed.

---

## Modifications to Existing Code

### [MODIFY] `server/event_driven_workflow.py`
Add optional `on_round_start: Callable[[int], None] | None` and `on_round_end: Callable[[int], None] | None` parameters.
Called if not None. Injected by the Server UI process if running the workflow in-process.

### [MODIFY] `server/custom_strategy.py`
Add optional `on_model_updated: Callable[[str, dict], None] | None` parameter.
Called after `_persist_global_artifact` if not None.

### [MODIFY] `client/client_common.py`
Add optional `on_training_start: Callable[[], None] | None` and `on_training_end: Callable[[], None] | None`.
Called in `fit()` around the training block if not None.

> [!NOTE]
> All modifications use `if callback is not None: callback(...)` pattern.
> Default is `None` so existing behavior is preserved.

---

## File Summary

| File | Status |
|---|---|
| `ui/shared/__init__.py` | [NEW] |
| `ui/shared/widgets/__init__.py` | [NEW] |
| `ui/shared/widgets/log_viewer.py` | [NEW] |
| `ui/shared/widgets/status_badge.py` | [NEW] |
| `ui/server_ui/widgets/__init__.py` | [NEW] |
| `ui/server_ui/widgets/overview_panel.py` | [NEW] |
| `ui/server_ui/widgets/client_monitor.py` | [NEW] |
| `ui/server_ui/widgets/training_controls.py` | [NEW] |
| `ui/server_ui/windows/main_window.py` | [MODIFY] — replace tab placeholders |
| `ui/client_ui/widgets/__init__.py` | [NEW] |
| `ui/client_ui/widgets/overview_panel.py` | [NEW] |
| `ui/client_ui/widgets/etl_panel.py` | [NEW] |
| `ui/client_ui/windows/main_window.py` | [MODIFY] — replace tab placeholders |
| `server/event_driven_workflow.py` | [MODIFY] — add callback params |
| `server/custom_strategy.py` | [MODIFY] — add callback params |
| `client/client_common.py` | [MODIFY] — add callback params |

---

## Verification Plan

### Manual
1. Launch Server UI, click "Start Server".
2. Observe log lines appearing in Training Logs tab in near real-time.
3. Observe round number incrementing in Overview tab and status bar.
4. Client Monitor table populates as clients connect.
5. Change `LOCAL_EPOCHS` in Training Controls, click "Apply" -> warning shown.
6. Launch Client UI `--client-id 1`. Toggle readiness button to "Not Ready".
7. Confirm client is skipped in next FL round (observe log).
8. ETL panel shows green checkmarks for data file, scaler, columns.

### Automated
- `test_log_viewer.py`: feed `log_line` signals, assert text appears in `QPlainTextEdit`.
- `test_training_controls.py`: change SpinBox value, click Apply, assert env file updated.
- `test_etl_panel.py`: mock `os.path.exists`, assert badge colors match expected state.

---

## What PLAN3 Builds On This

- **Inference tab** (Client UI): form to enter patient data -> run prediction -> display results.
- **Insights Dashboard tab** (Client UI): charts of feature distributions, model metrics, training history.
- **Server UI Overview**: model version history timeline, metric trend charts.
