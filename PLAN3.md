# PLAN 3 — Inference Tab + Insights Dashboard (Client) + Model History (Server)

> **Depends on**: PLAN 1 + PLAN 2 completed.
> **Scope**: Implement the Inference and Insights Dashboard tabs on the Client UI,
> and a Model Browser / Metrics chart on the Server UI.

---

## Goal

Give the hospital operator (Client UI user) the ability to:
1. Submit patient data for cardiovascular risk prediction using the **latest aggregated global model**.
2. See a visual risk readout with probability, risk label, and per-feature contribution insights.
3. Explore charts — feature distributions, training accuracy/loss trends over rounds, model comparisons.

Give the server operator (Server UI) a view into:
1. Saved model versions with metadata.
2. Accuracy/loss trends across rounds.

---

## Client UI — Tab 4: Inference (`ui/client_ui/widgets/inference_panel.py`)

### [NEW] `inference_panel.py`

**Layout:** Horizontal split — left: input form; right: results panel.

#### Left — Input Form

- Dynamically built from `COLUMNS_PATH` (reads column names from file).
- Groups columns:
  - Demographics section: age, gender, height, weight (shown first, labeled).
  - Clinical section: remaining columns (blood pressure, cholesterol, etc.).
- Each column: `QDoubleSpinBox` with sensible range/defaults.
- "Load Defaults" button: fills form with reference means from `common/config.DASHBOARD_FEATURE_KEYS`.
- "Predict" button: triggers inference.

**Inference call (no HTTP):**
```python
from common.inference_service import predict_from_inputs
result = predict_from_inputs(inputs_dict)
```
This is called in a `QThread` worker to avoid blocking the UI.

#### Right — Results Panel

- **Risk Probability Gauge**: `QProgressBar` styled as an arc or filled bar.
  - 0-30%: green (Low)
  - 30-70%: orange (Medium)
  - 70-100%: red (High)
- **Risk Label**: Large `QLabel` with color-coded text (LOW / MEDIUM / HIGH).
- **Summary text**: `QLabel` wrapping `result.summary`.
- **Feature Insights table**: `QTableWidget` showing for each insight feature:
  - Label, Value, Reference (federated norm), Delta, Delta %, Contribution (bar graph in cell).
- **Model Info footer**: version, round, source, updated_at.

#### Model Loading Behavior

- `inference_service._get_cached_assets()` is already cache-aware (version polling from disk).
- The inference panel calls `get_model_info()` on startup to check if a model is available.
- If no model: displays a placeholder "No model available yet. Waiting for FL training to complete."
- If model available: enables the Predict button.
- `EventBus.model_updated` signal triggers a model reload notification and re-enables the button.

---

## Client UI — Tab 5: Insights Dashboard (`ui/client_ui/widgets/insights_panel.py`)

### [NEW] `insights_panel.py`

Uses **pyqtgraph** for real-time and historical charts.

**Sub-panels (via `QTabWidget` nested inside the main tab):**

#### Sub-tab A — Feature Distribution

- Bar chart: shows per-feature mean values from the **current client's dataset** vs. the **federated global norm** (from model metadata `feature_reference_means`).
- Computed once on panel open, "Refresh" button to recompute.
- Uses `pyqtgraph.BarGraphItem`.
- X-axis: feature labels (age, gender, height, weight).
- Two bar groups per feature: "Local" (client data) and "Global Norm" (federated).

**Data source:**
```python
import pandas as pd
df = pd.read_csv(CLIENT_N_TRAINING_SET)
local_means = {col: df[col].mean() for col in DASHBOARD_FEATURE_KEYS if col in df.columns}
global_means = metadata["feature_reference_means"]
```

#### Sub-tab B — Training Metrics History

- Line chart: accuracy and loss over training rounds.
- X-axis: round number.
- Y-axis (dual): accuracy (left), loss (right).
- Data: loaded from all saved model metadata JSON files via `list_saved_models(ARTIFACT_DIR)`.
- Updated in real-time via `EventBus.model_updated`.

**Uses:** `pyqtgraph.PlotWidget` with two `PlotDataItem` curves.

#### Sub-tab C — Risk Score Distribution (Prediction History)

- Tracks every Predict button press; stores `(timestamp, probability)` in-memory.
- Plotted as a scatter plot or bar histogram.
- "Clear History" button.
- Shows statistics: mean, min, max, count.

#### Sub-tab D — Model Version Table

- `QTableWidget` listing all saved model versions:
  - Version, Round, Source, Updated At, Accuracy, Loss.
- "Load Version" button: sets the inference panel to use a specific model version.
  (Requires exposing a `version` override to `inference_service`.)

---

## Server UI — Additional Enhancements

### Overview Tab — Add Metric Charts

#### [MODIFY] `ui/server_ui/widgets/overview_panel.py`

Add a section below the status grid with two small `pyqtgraph.PlotWidget`:
1. **Accuracy over rounds** (line chart).
2. **Loss over rounds** (line chart).

Both updated via `EventBus.model_updated`.

### [NEW] `ui/server_ui/widgets/model_browser.py`

A new panel (added as Tab 5 to the Server UI):
- `QTableWidget` listing all model versions (from `state_store.list_models()` or `list_saved_models()`).
- Columns: Version, Round, Source, Participants, Accuracy, Loss, Updated At.
- "Evaluate" button per row: calls `server/evaluator.get_evaluate_fn(global_test_path)(round, weights, {})` in a `QThread`.
- Results shown in a `QDialog` popup.

---

## Shared Utilities Needed

### [NEW] `ui/shared/workers/inference_worker.py`

```python
class InferenceWorker(QThread):
    result_ready = pyqtSignal(dict)   # PredictionResult.to_dict()
    error_occurred = pyqtSignal(str)

    def __init__(self, inputs: dict[str, float]):
        self.inputs = inputs

    def run(self):
        try:
            result = predict_from_inputs(self.inputs)
            self.result_ready.emit(result.to_dict())
        except Exception as e:
            self.error_occurred.emit(str(e))
```

### [NEW] `ui/shared/workers/hash_worker.py`

```python
class HashWorker(QThread):
    hash_ready = pyqtSignal(str)  # hex digest

    def __init__(self, path: str): ...
    def run(self):
        # SHA-256 hash of file, emitting progress
        ...
```

### [NEW] `ui/shared/widgets/chart_panel.py`

Wrapper around `pyqtgraph.PlotWidget` with:
- Title, axis labels, legend.
- `add_curve(name, x_data, y_data, color)` method.
- `update_curve(name, x_data, y_data)` method.
- `clear_all()` method.

---

## Modifications to Existing Code

### [MODIFY] `common/inference_service.py`

Add `version: str | None = None` parameter to `predict_from_inputs()` and `_get_cached_assets()`
so the UI can request a specific model version (for the "Load Version" feature in the insights tab).

### [MODIFY] `common/config.py`

Add `DASHBOARD_FEATURE_LABELS` as a parallel list to `DASHBOARD_FEATURE_KEYS` for display labels
in charts (already present in file but not exported — just ensure it's importable).

---

## File Summary

| File | Status |
|---|---|
| `ui/client_ui/widgets/inference_panel.py` | [NEW] |
| `ui/client_ui/widgets/insights_panel.py` | [NEW] |
| `ui/client_ui/windows/main_window.py` | [MODIFY] — wire tabs 4 and 5 |
| `ui/server_ui/widgets/model_browser.py` | [NEW] |
| `ui/server_ui/widgets/overview_panel.py` | [MODIFY] — add metric charts |
| `ui/server_ui/windows/main_window.py` | [MODIFY] — add model browser tab 5 |
| `ui/shared/workers/__init__.py` | [NEW] |
| `ui/shared/workers/inference_worker.py` | [NEW] |
| `ui/shared/workers/hash_worker.py` | [NEW] |
| `ui/shared/widgets/chart_panel.py` | [NEW] |
| `common/inference_service.py` | [MODIFY] — version param |

---

## Verification Plan

### Manual
1. Launch Client UI with a trained model available.
2. Open Inference tab -> form shows all feature columns.
3. Enter values, click "Predict" -> result appears with probability and risk label.
4. Open Insights -> Feature Distribution chart shows local vs global bars.
5. Training Metrics sub-tab shows accuracy/loss curve if multiple rounds have run.
6. Launch Server UI -> Model Browser tab lists models, "Evaluate" button runs evaluation.

### Automated
- `test_inference_worker.py`: mock `predict_from_inputs`, assert `result_ready` signal fires.
- `test_chart_panel.py`: add_curve then update_curve, assert no crash with PyQt6 test harness.

---

## What PLAN4 Builds On This

- **Deep integration**: Run `flower-server-app` in-thread (same Python process as Server UI)
  for true in-process shared state (no stdout parsing needed).
- **Advanced training controls**: per-client override forms, custom round config.
- **Polished styling**: dark theme, custom QSS stylesheet, animated transitions.
- **Packaging**: PyInstaller or AppImage for distributable desktop app.
