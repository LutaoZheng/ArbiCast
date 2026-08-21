from dataclasses import dataclass
from datetime import datetime


@dataclass
class OpportunityState:
    first_seen: datetime
    last_seen: datetime
    best_edge: float
    worst_edge: float
    maximum_size: float

    @property
    def duration_seconds(self) -> float:
        return (self.last_seen - self.first_seen).total_seconds()

    def update(self, timestamp: datetime, edge: float, size: float) -> None:
        self.last_seen = max(self.last_seen, timestamp)
        self.best_edge = max(self.best_edge, edge)
        self.worst_edge = min(self.worst_edge, edge)
        self.maximum_size = max(self.maximum_size, size)

