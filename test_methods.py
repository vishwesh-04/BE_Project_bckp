import sys
print("starting wrapper override test")
try:
    from client.client_common import FLClientRuntime
    from common.network import NeuralNetworkAlgo
    client = FLClientRuntime(
        client_id="1",
        train_path="data/node1_train.csv",
        test_path="data/node1_test.csv",
        algo=NeuralNetworkAlgo(input_dim=10),
    )
    print("instance created")
    from flwr.client.numpy_client import _wrap_numpy_client
    c = _wrap_numpy_client(client)
    c.get_parameters(None)
    c.fit(None, None)
    c.evaluate(None, None)
except Exception as e:
    import traceback
    traceback.print_exc()
print("done test")
