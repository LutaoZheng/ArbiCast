from datetime import UTC, datetime

from app.connectors.base import MarketConnector
from app.connectors.http import ConnectorHTTP
from app.schemas.domain import ConnectorHealth, NormalizedMarket, OrderBook, OrderBookLevel, Platform


def _price(raw: object) -> float | None:
    if raw in (None, ""):
        return None
    value = float(raw)
    # Current API uses *_dollars strings; legacy fixtures may use integer cents.
    return value / 100 if value > 1 else value


class KalshiConnector(MarketConnector):
    """Read-only public Kalshi Trade API connector. No credentials or trading methods."""

    def __init__(self, base_url: str = "https://external-api.kalshi.com/trade-api/v2", max_markets: int = 500, connect_timeout: float = 5, read_timeout: float = 15):
        self.http = ConnectorHTTP(Platform.KALSHI, base_url, connect_timeout, read_timeout)
        self.max_markets = max_markets
        self.raw_orderbooks: dict[str, dict] = {}

    async def get_markets(self) -> list[NormalizedMarket]:
        results: list[NormalizedMarket] = []
        cursor: str | None = None
        while len(results) < self.max_markets:
            limit = min(1000, self.max_markets - len(results))
            params: dict[str, str | int] = {"status": "open", "limit": limit, "mve_filter": "exclude"}
            if cursor:
                params["cursor"] = cursor
            response = await self.http.get("/markets", params=params)
            body = response.json()
            page = body.get("markets", [])
            results.extend(self._normalize_market(item) for item in page)
            cursor = body.get("cursor")
            if not page or not cursor:
                break
        self.http.state.markets_loaded = len(results)
        return results[:self.max_markets]

    async def get_market(self, market_id: str) -> NormalizedMarket:
        ticker = market_id.removeprefix("kalshi:")
        response = await self.http.get(f"/markets/{ticker}")
        return self._normalize_market(response.json()["market"])

    async def get_orderbook(self, market_id: str) -> OrderBook:
        ticker = market_id.removeprefix("kalshi:")
        response = await self.http.get(f"/markets/{ticker}/orderbook", params={"depth": 100})
        body = response.json()
        self.raw_orderbooks[market_id] = body
        return self.normalize_orderbook(market_id, body)

    async def health(self) -> ConnectorHealth:
        return self.http.state.model_copy(deep=True)

    async def close(self) -> None:
        await self.http.close()

    @staticmethod
    def normalize_orderbook(market_id: str, body: dict) -> OrderBook:
        raw = body.get("orderbook_fp") or body.get("orderbook") or body
        yes_raw = raw.get("yes_dollars") or raw.get("yes") or []
        no_raw = raw.get("no_dollars") or raw.get("no") or []
        yes_bids = [OrderBookLevel(price=_price(p), quantity=float(q)) for p, q, *_ in yes_raw]
        no_bids = [OrderBookLevel(price=_price(p), quantity=float(q)) for p, q, *_ in no_raw]
        # Official Kalshi model: YES bid p == NO ask 1-p, same size, and vice versa.
        yes_asks = [OrderBookLevel(price=1-level.price, quantity=level.quantity) for level in no_bids]
        no_asks = [OrderBookLevel(price=1-level.price, quantity=level.quantity) for level in yes_bids]
        return OrderBook(
            market_id=market_id, timestamp=datetime.now(UTC),
            yes_bids=sorted(yes_bids, key=lambda x: x.price, reverse=True),
            yes_asks=sorted(yes_asks, key=lambda x: x.price),
            no_bids=sorted(no_bids, key=lambda x: x.price, reverse=True),
            no_asks=sorted(no_asks, key=lambda x: x.price), source="live",
        )

    @staticmethod
    def _normalize_market(raw: dict) -> NormalizedMarket:
        close = raw.get("close_time") or raw.get("expected_expiration_time")
        updated = raw.get("updated_time") or raw.get("created_time") or datetime.now(UTC)
        status = {"active": "open", "inactive": "paused", "initialized": "unopened"}.get(raw.get("status"), raw.get("status", "open"))
        return NormalizedMarket(
            id=f"kalshi:{raw['ticker']}", platform=Platform.KALSHI, external_id=raw["ticker"],
            title=raw.get("title", ""), description=raw.get("subtitle") or raw.get("yes_sub_title", ""),
            category=(raw.get("category") or "other").lower(), event_date=raw.get("occurrence_datetime") or close,
            close_time=close, resolution_rules=raw.get("rules_primary", ""),
            resolution_source=raw.get("rules_secondary") or "Kalshi contract rules", status=status,
            yes_bid=_price(raw.get("yes_bid_dollars") or raw.get("yes_bid")),
            yes_ask=_price(raw.get("yes_ask_dollars") or raw.get("yes_ask")),
            no_bid=_price(raw.get("no_bid_dollars") or raw.get("no_bid")),
            no_ask=_price(raw.get("no_ask_dollars") or raw.get("no_ask")),
            event_id=raw.get("event_ticker"), updated_at=updated, source="live",
            resolved_outcome=str(raw.get("result","")).upper() if str(raw.get("result","")).lower() in {"yes","no"} else None,
        )
