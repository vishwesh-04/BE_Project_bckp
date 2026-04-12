from client.client_common import FLClientRuntime
from common.network import NeuralNetworkAlgo
import sys

client = FLClientRuntime(
    client_id="1",
    train_path="data/node1_train.csv",
    test_path="data/node1_test.csv",
    algo=NeuralNetworkAlgo(input_dim=10),
)
try:
    print(client.to_client())
except Exception as e:
    print(f"Exception: {type(e).__name__}: {e}")
