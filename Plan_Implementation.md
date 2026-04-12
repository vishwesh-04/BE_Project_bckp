Planner: Federated Learning Client–Server Verification and UI Integration

Project Overview

This planner guides an AI agent through the verification, correction, and enhancement of a Federated Learning (FL) system utilizing Flower (FLWR), SecAgg, Differential Privacy, and a PySide6 UI.

Global Instructions (System Engineer Protocol)

Do NOT break existing functionality.

Do NOT refactor working code unless absolutely necessary for the fix.

Small, incremental, testable changes are mandatory.

Preserve interfaces: Maintain existing API contracts and class structures.

Thread Safety: Ensure the UI remains responsive; never block the main thread with network or training logic.

Logging: Use verbose logging to trace state transitions and errors.

Execution Environment

Server Startup: Managed via ./server-starter.sh.

Client Startup: Executed via DEV_MODE=1 python3 -m ui.client.main.

Environment Variables: DEV_MODE=1 must be respected to enable developer/mock features.

Phase 0: Environment & Bootstrap Verification

Goal: Ensure the tooling and scripts are ready for execution.

Task 0.1: Verify server-starter.sh has execution permissions and starts the Flower server without immediate crashes.

Task 0.2: Verify the client entry point ui.client.main is accessible via the provided python module command.

Task 0.3: Check if DEV_MODE=1 is correctly interpreted by the codebase to bypass hardware-specific or production-only constraints.

Phase 1: Connection Logic & Interface Correction

Goal: Solve the NotImplementedError preventing client-server registration.

Task 1.1: Audit Client Implementation: Inspect the Flower client class (inheriting from flwr.client.Client or NumPyClient).

Task 1.2: Resolve NotImplementedError: * Identify missing mandatory Flower methods (e.g., get_parameters, fit, evaluate).

Implement the bridge between these Flower callbacks and the internal training/data logic.

Task 1.3: Verification of Flow:

Verify server accepts connections and remains continuous.

Verify min_clients and max_clients logic is enforced.

Verify SecAgg workflow (Mask generation, dropout handling, and recalculation).

Output: Successful connection logs showing the client registered with the server.

Phase 2: Signal-Slot Completion

Goal: Ensure the UI and the Backend Worker threads communicate flawlessly.

Task 2.1: Audit Signal Map: Identify missing QtCore.Signal connections between the client worker and the PySide6 UI.

Task 2.2: Thread-Safe Updates:

Connect client state updates (Connected, Training, Idle, Error).

Stream logs from the background process to the UI log viewer.

Update training progress bars/stats via signals.

Task 2.3: Configuration Loop: Ensure UI dashboard changes (training parameters) propagate correctly to the client settings.

Output: Real-time UI updates reflecting the actual state of the background FL client.

Phase 3: Prediction Integration

Goal: Connect the UI inference tab to the latest local model.

Task 3.1: Module Mapping: Identify the prediction/inference module within the client code.

Task 3.2: Weights Loading: Ensure the inference engine uses the latest global model weights received from the server.

Task 3.3: UI Bridge: Connect the "Predict" button to the inference logic. Handle scenarios where no model has been downloaded yet with a user-friendly message.

Output: Functional inference pipeline with results displayed in the UI.


Success Criteria

Connection Fixed: Client no longer throws NotImplementedError on startup.

Reactive UI: All logs and state changes are visible in the UI via Signal-Slots.

Inference Ready: Users can perform predictions using the latest aggregated model.

Stability: System handles client dropouts and server cooldowns gracefully.