from abc import ABC, abstractmethod

class ClassificationAlgo(ABC):
    @abstractmethod
    def train(self, location):
        pass

    @abstractmethod
    def test(self, location):
        pass

    @abstractmethod
    def get_weights(self):
        pass

    @abstractmethod
    def set_weights(self, weights):
        pass