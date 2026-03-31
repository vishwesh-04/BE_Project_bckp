from logging import INFO

from flwr.common.logger import log

from common.config import get_input_dim
from common.network import NeuralNetworkAlgo


def get_evaluate_fn(global_test_path):
    def evaluate(server_round, parameters, config):
        model = NeuralNetworkAlgo(input_dim=get_input_dim())
        model.set_weights(parameters)

        loss_global, acc_global = model.test(global_test_path)

        log(INFO, "\n" + "-" * 40)
        log(INFO, f"ROUND {server_round} GLOBAL EVALUATION")
        log(INFO, f"   Acc: {acc_global:.4f} | Loss: {loss_global:.4f}")
        log(INFO, "-" * 40 + "\n")

        return float(loss_global), {"accuracy": float(acc_global)}

    return evaluate
