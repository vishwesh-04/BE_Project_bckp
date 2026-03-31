import torch
import torch.nn as nn
import numpy as np
from collections import OrderedDict
from .classification_base import ClassificationAlgo

class NeuralNetworkAlgo(ClassificationAlgo):
    def __init__(self, input_dim):
        self.input_dim = input_dim
        self.device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
        self.model = self._build_model().to(self.device)

    def _build_model(self):
        model = nn.Sequential(
            nn.Linear(self.input_dim, 256),
            nn.GroupNorm(8, 256), 
            nn.ReLU(),
            nn.Dropout(0.20),

            nn.Linear(256, 128),
            nn.ReLU(),
            nn.Dropout(0.15),

            nn.Linear(128, 64),
            nn.ReLU(),
            nn.Dropout(0.10),

            nn.Linear(64, 1),
            nn.Sigmoid()
        )
        return model

    def get_weights(self):

        return [val.cpu().numpy() for _, val in self.model.state_dict().items()]

    def set_weights(self, weights):
 
        state_dict = OrderedDict()
        for key, value in zip(self.model.state_dict().keys(), weights):
            state_dict[key] = torch.tensor(np.array(value))
        self.model.load_state_dict(state_dict, strict=True)

    def test(self, path):

        if not path:
            return 0.0, 0.0
            
        from common.data_loader import load_local_data
        x_data, y_data = load_local_data(path)
        

        x = torch.from_numpy(x_data).float().to(self.device)
        y = torch.from_numpy(y_data).float().to(self.device).reshape(-1, 1)
        
        self.model.eval()
        criterion = nn.BCELoss()
        
        with torch.no_grad():
            outputs = self.model(x)
            loss = criterion(outputs, y).item()

            predicted = (outputs > 0.5).float()
            accuracy = (predicted == y).sum().item() / len(y)
            
        return float(loss), float(accuracy)

    def train(self, path):
        pass