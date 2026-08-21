import asyncio
from datetime import UTC, datetime

from app.schemas.domain import NormalizedMarket, OrderBook


class MarketCache:
    def __init__(self):
        self.markets: dict[str, NormalizedMarket] = {}
        self.orderbooks: dict[str, OrderBook] = {}
        self.raw_orderbooks: dict[str, dict] = {}
        self.loading = True
        self.started_at = datetime.now(UTC)
        self._lock = asyncio.Lock()

    async def update_markets(self, items: list[NormalizedMarket]) -> list[NormalizedMarket]:
        changed: list[NormalizedMarket] = []
        async with self._lock:
            for item in items:
                previous = self.markets.get(item.id)
                if previous is None or previous.model_dump(exclude={"updated_at", "watched"}) != item.model_dump(exclude={"updated_at", "watched"}):
                    changed.append(item)
                item.watched = previous.watched if previous else item.watched
                self.markets[item.id] = item
        return changed

    async def set_watched(self, market_id: str, watched: bool) -> NormalizedMarket:
        async with self._lock:
            market = self.markets[market_id]
            market.watched = watched
            return market

    async def update_orderbook(self, market_id: str, book: OrderBook, raw: dict | None = None) -> None:
        async with self._lock:
            self.orderbooks[market_id] = book
            if raw is not None: self.raw_orderbooks[market_id] = raw
            market = self.markets.get(market_id)
            if market:
                market.yes_bid = book.yes_bids[0].price if book.yes_bids else None
                market.yes_ask = book.yes_asks[0].price if book.yes_asks else None
                market.no_bid = book.no_bids[0].price if book.no_bids else None
                market.no_ask = book.no_asks[0].price if book.no_asks else None
                market.updated_at = book.timestamp

