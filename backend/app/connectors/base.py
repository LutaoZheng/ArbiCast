from abc import ABC, abstractmethod

from app.schemas.domain import ConnectorHealth, NormalizedMarket, OrderBook


class MarketConnector(ABC):
    @abstractmethod
    async def get_markets(self) -> list[NormalizedMarket]: ...

    @abstractmethod
    async def get_market(self, market_id: str) -> NormalizedMarket: ...

    @abstractmethod
    async def get_orderbook(self, market_id: str) -> OrderBook: ...

    @abstractmethod
    async def health(self) -> ConnectorHealth: ...

    @abstractmethod
    async def close(self) -> None: ...

    async def subscribe_orderbooks(self, market_ids: list[str]):
        """Future streaming boundary. Phase 2 uses rate-safe polling."""
        raise NotImplementedError


MarketDataConnector = MarketConnector
