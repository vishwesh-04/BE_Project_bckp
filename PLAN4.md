# PLAN 4 — Deep In-Process Integration + Polished Styling + Packaging

> **Depends on**: PLAN 1 + PLAN 2 + PLAN 3 completed and verified.
> **Scope**: Move from subprocess-based FL process management to in-process threading for the server,
> add a production-quality dark theme, and optionally package the app for distribution.

---

## Background

Plans 1-3 launch the Flower FL processes (`flower-superlink`, `flower-server-app`, `flower-supernode`)
as subprocesses and communicate with them by parsing stdout. This is reliable but has limitations:
- State is not directly shared (each process has its own `InMemoryStateStore`).
- Callback hooks in `EventDrivenWorkflow` / `FeatureParityFedAvg` only work if the UI is in-process.

PLAN 4 addresses this by making the **Server UI** optionally run the server workflow
in a `QThread` within the same Python process, enabling direct shared-memory access to the `StateStore`
and eliminating all stdout parsing for state updates.

The **Client UI** remains subprocess-based (since `flower-supernode` is a Flower binary),
but gets an enhanced sidecar for direct local IPC.

---

## Part A — In-Process Server Mode

### [NEW] `ui/server_ui/fl_thread.py`

```python
class FLServerThread(QThread):
    """
    Runs flower-server-app logic directly in a QThread.
    Shares the same Python process as the UI -> direct StateStore access.
    """
    started_signal = pyqtSignal()
    stopped_signal = pyqtSignal()
    error_signal = pyqtSignal(str)

    def run(self) -> None:
        try:
            # Replicate what flower-server-app does:
            # 1. Build strategy with injected callbacks
            # 2. Build legacy context
            # 3. Run EventDrivenWorkflow
            from server.server_app import main as server_main
            # Monkey-patch or inject callbacks before calling main
            self._inject_callbacks()
            # Run in this thread (blocking)
            server_main(grid=..., context=...)
        except Exception as e:
            self.error_signal.emit(str(e))
        finally:
            self.stopped_signal.emit()

    def _inject_callbacks(self) -> None:
        bus = get_event_bus()
        # Inject into EventDrivenWorkflow and FeatureParityFedAvg via
        # the optional callback parameters added in PLAN 2
        ...
```

**Benefits of in-process mode:**
- `StateStore` is shared between UI and FL workflow -> no polling overhead.
- All `EventBus` signals fire directly without stdout parsing.
- Debugging is simpler (single Python process, standard traceback).

**Tradeoff:**
- A crash in the FL workflow can crash the UI.
- Mitigation: wrap workflow in `try/except`, emit `error_signal`, allow restart.

### [MODIFY] `ui/server_ui/main.py`

Add `--in-process` CLI flag (default: True for desktop use).
When `--in-process`:
- Start `FLServerThread` instead of `ProcessManager` spawning subprocesses.
- Still launch `flower-superlink` as a subprocess (it's a C++ binary, can't run in-process).

---

## Part B — Client Sidecar IPC

Replace the file-based ready-signal (`/tmp/client_ready.json`)
with a Python `multiprocessing.Queue` or `threading.Event` for clients
running in-process or on the same machine.

For distributed clients (different machines), keep file-based approach.

### [NEW] `ui/client_ui/local_sidecar.py`

```python
class LocalClientSidecar:
    """
    Replaces the FastAPI sidecar for local (same-machine) client deployments.
    Directly writes the ready file and monitors FL process via subprocess stdout.
    """
    def set_ready(self, ready: bool) -> None:
        # writes READY_FILE_PATH directly
        ...
    def get_ready(self) -> bool: ...
    def request_retrain(self) -> None:
        # writes to the local StateStore directly (if server is local)
        # or falls back to HTTP if server is remote
        ...
```

---

## Part C — Global Dark Theme + Styling

### [NEW] `ui/shared/theme.py`

A centralized theme module:

```python
DARK_STYLESHEET = """
QMainWindow, QWidget {
    background-color: #1a1a2e;
    color: #e0e0e0;
    font-family: 'Inter', 'Segoe UI', sans-serif;
    font-size: 13px;
}
QTabWidget::pane {
    border: 1px solid #2d2d4e;
    border-radius: 8px;
    background: #16213e;
}
QTabBar::tab {
    background: #0f3460;
    color: #a0a0c0;
    padding: 8px 20px;
    border-radius: 4px;
    margin: 2px;
}
QTabBar::tab:selected {
    background: #e94560;
    color: white;
    font-weight: bold;
}
QPushButton {
    background: #0f3460;
    color: white;
    border: none;
    border-radius: 6px;
    padding: 8px 16px;
    font-weight: bold;
}
QPushButton:hover { background: #e94560; }
QPushButton:pressed { background: #c73652; }
QPushButton:disabled { background: #2d2d4e; color: #666; }
QPlainTextEdit, QTextEdit {
    background: #0d0d1a;
    color: #b0f0b0;
    font-family: 'Fira Code', 'Consolas', monospace;
    font-size: 12px;
    border: 1px solid #2d2d4e;
    border-radius: 4px;
}
QTableWidget {
    background: #16213e;
    alternate-background-color: #1a1a2e;
    gridline-color: #2d2d4e;
    border: none;
}
QHeaderView::section {
    background: #0f3460;
    padding: 6px;
    border: none;
    font-weight: bold;
}
QSpinBox, QDoubleSpinBox, QLineEdit {
    background: #0f3460;
    color: white;
    border: 1px solid #2d2d4e;
    border-radius: 4px;
    padding: 4px 8px;
}
QStatusBar { background: #0d0d1a; color: #a0a0c0; }
QToolBar { background: #16213e; border: none; spacing: 4px; }
QProgressBar {
    border: 2px solid #2d2d4e;
    border-radius: 5px;
    text-align: center;
}
QProgressBar::chunk { background-color: #e94560; border-radius: 3px; }
"""

def apply_theme(app: QApplication) -> None:
    app.setStyleSheet(DARK_STYLESHEET)
    # Optionally set window icon
    ...
```

**Color palette:**
- Background: `#1a1a2e` (deep navy)
- Surface: `#16213e` (panel blue)
- Accent: `#e94560` (coral red — matches medical/health aesthetic)
- Success: `#4ecca3` (teal)
- Warning: `#f5a623` (amber)
- Text: `#e0e0e0`
- Monospace log: `#b0f0b0` (terminal green)

---

## Part D — Animated Status Transitions

### [NEW] `ui/shared/widgets/animated_badge.py`

A `QLabel` subclass with:
- `QPropertyAnimation` on `opacity` when status changes (fade in/out).
- Color transition using `QVariantAnimation` on `background-color` via stylesheet.
- Pulse animation for "running" status (using `QTimer` + opacity oscillation).

### [NEW] `ui/shared/widgets/progress_ring.py`

A custom `QWidget` painting a circular arc progress indicator using `QPainter`.
Used in the Inference panel for probability visualization (more premium than `QProgressBar`).

---

## Part E — Advanced Training Controls

### [MODIFY] `ui/server_ui/widgets/training_controls.py`

Add:
- **Per-client override panel**: expandable `QGroupBox` per connected client allowing
  override of `LOCAL_EPOCHS`, `LEARNING_RATE` etc. (requires custom `on_fit_config_fn` injection).
- **Round scheduling**: set a maximum rounds cap without restarting via `state_store`.
- **Real-time parameter preview**: show what the next round will use vs what's in `.env`.
- **Export config**: save current config to a named `.env` preset file.
- **Import config**: load a preset `.env` file.

---

## Part F — Optional Packaging (PyInstaller)

### [NEW] `ui/build/build_server.spec` and `ui/build/build_client.spec`

PyInstaller spec files for:
- `launch_server.py` -> `FederatedServer` executable
- `launch_client.py` -> `FederatedClient` executable

Key PyInstaller considerations:
- Bundle `preprocessing/` (columns.txt, scaler.pkl).
- Bundle `model/` if needed.
- Hidden imports: `flwr`, `torch`, `PyQt6`.
- `--onedir` mode (not `--onefile`) for faster startup with large ML dependencies.

### [NEW] `ui/build/README.md`
Build instructions.

---

## File Summary

| File | Status |
|---|---|
| `ui/server_ui/fl_thread.py` | [NEW] |
| `ui/server_ui/local_sidecar.py` | [NEW] (moved from client) |
| `ui/client_ui/local_sidecar.py` | [NEW] |
| `ui/shared/theme.py` | [NEW] |
| `ui/shared/widgets/animated_badge.py` | [NEW] |
| `ui/shared/widgets/progress_ring.py` | [NEW] |
| `ui/server_ui/main.py` | [MODIFY] — add --in-process flag |
| `ui/server_ui/widgets/training_controls.py` | [MODIFY] — per-client overrides, presets |
| `ui/build/build_server.spec` | [NEW] |
| `ui/build/build_client.spec` | [NEW] |
| `ui/build/README.md` | [NEW] |
| All `main.py` launchers | [MODIFY] — call apply_theme() |

---

## Verification Plan

### Manual
1. Launch Server UI in `--in-process` mode. Verify FL training starts without subprocess.
2. Observe `EventBus` signals fire **immediately** (no log-parsing delay) when rounds complete.
3. Verify dark theme applied consistently across all tabs and both UIs.
4. Test animated badge: training status transitions animate smoothly.
5. Test progress ring in Inference tab with various probability values.
6. Run PyInstaller build for server. Launch resulting binary. Verify it works.

### Automated
- `test_fl_server_thread.py`: run `FLServerThread` with a mock workflow that completes 1 round.
  Assert `stopped_signal` fires.
- `test_theme.py`: apply theme, check no runtime errors in QApplication.

---

## Summary of All Plans

| Plan | Focus | Key Deliverables |
|---|---|---|
| **PLAN 1** | Foundation | EventBus, ProcessRunner, LogTailer, Skeleton UIs, Launch Scripts |
| **PLAN 2** | Core Tabs | Log Viewer, Client Monitor, Training Controls, ETL Panel, Readiness Toggle |
| **PLAN 3** | Advanced Tabs | Inference Panel, Insights Dashboard, Model Browser, Charts |
| **PLAN 4** | Deep Integration | In-Process FL Thread, Dark Theme, Animations, Packaging |
