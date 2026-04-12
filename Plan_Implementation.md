# Planner: Federated Learning Client–Server Verification and UI Integration

## Global Instruction (Apply to ALL Steps)

You are a careful systems engineer working on an existing federated learning system using Flower (FLWR), SecAgg, Differential Privacy, and a PySide6 UI.

* Do NOT break existing functionality.
* Do NOT refactor working code unless absolutely necessary.
* Prefer verification over modification.
* Make small, incremental, testable changes.
* Preserve all existing interfaces and behavior.
* Ensure UI remains responsive (no blocking main thread).
* Ensure all changes are reversible and well-logged.

---

## Phase 1: System Verification

### Instruction

You are responsible for verifying that the current system behaves exactly as described before making any changes.

### Tasks

* Verify server runs continuously and accepts client connections.

* Verify client readiness checks before training.

* Verify `min_clients` and `max_clients` logic is enforced.

* Verify only eligible clients participate in training.

* Verify SecAgg workflow:

  * Mask generation and aggregation
  * Dropout handling
  * Mask recalculation when clients >= min_clients
  * Abort when clients < min_clients

* Verify training lifecycle:

  * Training rounds execute correctly
  * Server enters cooldown after training
  * Cooldown prevents excessive computation

* Verify UI:

  * Client states (connected, training, idle, error)
  * Logs are streamed correctly
  * Real-time updates via signals/slots

* Verify configuration:

  * Connection URI setup
  * ETL configuration
  * Client settings propagation

* Verify dashboard:

  * Training parameters can be modified
  * Changes propagate correctly

* Verify Flower integration:

  * Client-server communication
  * Training orchestration

* Verify model distribution:

  * Clients receive model locally
  * Model is usable for inference

### Constraints

* Do NOT modify code unless a critical issue is found.

### Output

* Checklist: Working / Broken / Missing
* Exact file/module references for issues

---

## Phase 2: Signal-Slot Completion

### Instruction

You are responsible for completing all missing signal-slot connections without altering existing working logic.

### Tasks

* Audit all signals and slots in UI and client code.

* Identify missing or incomplete connections.

* Connect signals for:

  * Client state updates
  * Training progress
  * Logs
  * Errors
  * Configuration updates

* Ensure:

  * Thread-safe signal emission
  * No direct UI updates from worker threads
  * Proper separation of UI and backend logic

* Validate full communication loop:
  UI → Client → Server → Client → UI

### Constraints

* Do NOT rewrite existing signal-slot logic.
* Only add missing connections.

### Output

* List of added connections
* Confirmation of real-time UI updates

---

## Phase 3: Prediction Integration

### Instruction

You are responsible for connecting the UI inference flow to the client prediction module.

### Tasks

* Identify prediction module in client.
* Connect inference UI to prediction calls.
* Ensure latest downloaded model is used.
* Handle missing model scenarios.
* Display prediction results in UI.

### Constraints

* Do NOT modify prediction logic.
* Only integrate and adapt interfaces.

### Output

* Working inference pipeline
* Proper error handling

---

## Phase 4: End-to-End Validation

### Instruction

You are responsible for validating the complete system workflow.

### Tasks

* Start client from UI.

* Connect to server.

* Execute training round.

* Validate SecAgg under dropout scenarios.

* Ensure model is received locally.

* Perform inference via UI.

* Test edge cases:

  * Client dropout
  * Below min_clients
  * Network interruptions
  * Reconnect scenarios

* Verify UI responsiveness (no blocking operations).

* Verify logs and observability.

### Constraints

* Do NOT introduce new logic unless required to fix a verified issue.

### Output

* End-to-end validation report
* Edge case test results

---

## Execution Rules

* Follow order: Verify → Integrate → Test
* Do NOT skip verification.
* Test after every change.
* Prefer logging over assumptions.
* Stop and report on unexpected behavior.

---

## Success Criteria

* All verification checks pass.
* No regressions introduced.
* Signal-slot communication is complete.
* Prediction works reliably.
* System is stable under edge cases.
