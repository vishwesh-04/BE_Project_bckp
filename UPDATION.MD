# TASK: FLWR 1.10.0 TO 1.28.0 ARCHITECTURAL REFACTORING

## Objective
Update the Federated Learning system logic to comply with Flower 1.28.0 standards. The agent must identify legacy imperative code and refactor it into the modern, declarative `ClientApp` and `ServerApp` structures.

---

## 1. Core Architectural Logic Audit
The Agent must ensure the following logic transitions are implemented:

### A. Client-Side Logic
* **Deprecation Check:** Remove `flwr.client.start_numpy_client`.
* **New Paradigm:** Implement `flwr.client.ClientApp`.
* **Actor Logic:** Ensure the `client_fn()` is pure and returns a `NumPyClient` or `Client` instance.
* **Context Awareness:** Utilize the `Context` object in `client_fn` to access node-specific configurations or state.

### B. Server-Side Logic
* **Deprecation Check:** Remove `flwr.server.start_server`.
* **New Paradigm:** Implement `flwr.server.ServerApp`.
* **Strategy Logic:** Update `Strategy` initialization to ensure compatibility with the new `ServerConfig` and `Task` messaging system.
* **Driver API:** Check if the implementation requires the new `Driver` API for manual control of the FL loop.

---

## 2. Specific Logic Correction Requirements

### Strategy & Aggregation
* Validate that any custom `aggregate_fit` or `aggregate_evaluate` logic correctly handles the `Metrics` dictionaries, as the typing has become stricter in recent versions.
* Check for compatibility with **Differential Privacy (DP)** wrappers if used, ensuring they wrap the strategy according to the 1.28.0 interface.

### Resource Allocation
* In the refactored `ClientApp`, ensure that logic for GPU/CPU allocation is handled via the `client_resources` parameter within the `ServerApp` or the deployment engine, rather than hardcoded client-side limits.

### State Management
* Flower 1.28.0 introduces persistent state. Check if the logic correctly utilizes `context.state` to resume training or store metadata across rounds, replacing manual local file saving where appropriate.

---

## 3. Implementation Blueprint for Agent

### Step 1: `client.py` Refactor
```python
# From: 
# flwr.client.start_numpy_client(server_address="...", client=MyClient())

# To:
from flwr.client import ClientApp, NumPyClient

class MyClient(NumPyClient):
    # Ensure logic here matches updated NumPyClient signatures
    ...

def client_fn(context):
    return MyClient().to_client()

app = ClientApp(client_fn=client_fn)

Step 2: server.py Refactor
Python

# From:
# flwr.server.start_server(strategy=my_strategy, config=...)

# To:
from flwr.server import ServerApp, ServerConfig, ServerAppComponents

def server_fn(context):
    config = ServerConfig(num_rounds=3)
    return ServerAppComponents(strategy=my_strategy, config=config)

app = ServerApp(server_fn=server_fn)

4. Final Verification Checklist

    Pydantic Integration: 1.28.0 relies heavily on Pydantic for configs. Ensure all config dictionaries are valid.

    Serialization: Verify that parameters_to_ndarrays and ndarrays_to_parameters logic remains consistent during the transition.

    Execution: The system should now be runnable via the flwr run CLI command rather than manual Python execution of individual files.


---

### Key Changes to Watch Out For:
* **The "App" Concept:** In 1.10.0, you ran scripts. In 1.28.0, you define **Apps**. The Agent should look for a `pyproject.toml` or `flower.toml` to see if you are using the new Flower Next deployment engine.
* **Typing:** Flower is moving toward stricter type hinting. If your logic involves custom `FitRes` or `GetParametersRes` objects, ensure the Agent checks the `flwr.common` types.
* **Simulations:** If you are using `start_simulation`, it is highly recommended to move toward the `ClientApp` / `ServerApp` flow for better scalability.


Gemini is AI and can make mistakes.