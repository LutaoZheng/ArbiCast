class WatchedMarketService:
    def __init__(self): self._ids: set[str] = set()
    def add(self, market_id: str) -> None: self._ids.add(market_id)
    def remove(self, market_id: str) -> None: self._ids.discard(market_id)
    def contains(self, market_id: str) -> bool: return market_id in self._ids
    def list(self) -> list[str]: return sorted(self._ids)

