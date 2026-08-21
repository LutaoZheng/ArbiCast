from abc import ABC, abstractmethod
from dataclasses import dataclass


class FeeModel(ABC):
    @abstractmethod
    def estimate(self, price: float, quantity: float) -> float: ...


@dataclass(frozen=True)
class KalshiFeeModel(FeeModel):
    coefficient: float = 0.07

    def estimate(self, price: float, quantity: float) -> float:
        return self.coefficient * quantity * price * (1 - price)


@dataclass(frozen=True)
class PolymarketFeeModel(FeeModel):
    rate: float = 0.0

    def estimate(self, price: float, quantity: float) -> float:
        return self.rate * price * quantity

