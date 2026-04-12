import flwr
import inspect
import sys
with open("flwr_sig.txt", "w") as f:
    f.write(str(inspect.signature(flwr.client.start_client)))
