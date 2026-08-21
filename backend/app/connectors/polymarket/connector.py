import asyncio
import json
from datetime import UTC, datetime

from app.connectors.base import MarketConnector
from app.connectors.http import ConnectorHTTP
from app.schemas.domain import ConnectorHealth, NormalizedMarket, OrderBook, OrderBookLevel, Platform


def _array(value: object) -> list:
    if isinstance(value, list):
        return value
    if isinstance(value, str) and value:
        try: return json.loads(value)
        except json.JSONDecodeError: return []
    return []


class PolymarketConnector(MarketConnector):
    """Read-only Gamma discovery + CLOB market-data connector."""

    def __init__(self, gamma_url: str = "https://gamma-api.polymarket.com", clob_url: str = "https://clob.polymarket.com", max_markets: int = 500, connect_timeout: float = 5, read_timeout: float = 15):
        self.gamma = ConnectorHTTP(Platform.POLYMARKET, gamma_url, connect_timeout, read_timeout)
        self.clob = ConnectorHTTP(Platform.POLYMARKET, clob_url, connect_timeout, read_timeout)
        self.max_markets = max_markets
        self.market_tokens: dict[str, tuple[str, str]] = {}
        self.raw_orderbooks: dict[str, dict] = {}

    async def get_markets(self) -> list[NormalizedMarket]:
        results: list[NormalizedMarket] = []
        cursor: str | None = None
        while len(results) < self.max_markets:
            params: dict[str, str | int] = {"limit": min(100, self.max_markets-len(results)), "active": "true", "closed": "false", "ascending": "false"}
            if cursor: params["after_cursor"] = cursor
            response = await self.gamma.get("/markets/keyset", params=params)
            body = response.json()
            page = body.get("markets", [])
            for raw in page:
                try:
                    market = self._normalize_market(raw)
                except (ValueError, TypeError):
                    # Do not invent mandatory close times for malformed/legacy markets.
                    continue
                if market.yes_token_id and market.no_token_id:
                    self.market_tokens[market.id] = (market.yes_token_id, market.no_token_id)
                results.append(market)
            cursor = body.get("next_cursor")
            if not page or not cursor:
                break
        self.gamma.state.markets_loaded = len(results)
        return results[:self.max_markets]

    async def get_market(self, market_id: str) -> NormalizedMarket:
        external_id = market_id.removeprefix("polymarket:")
        response = await self.gamma.get(f"/markets/{external_id}")
        market = self._normalize_market(response.json())
        if market.yes_token_id and market.no_token_id:
            self.market_tokens[market.id] = (market.yes_token_id, market.no_token_id)
        return market

    async def get_orderbook(self, market_id: str) -> OrderBook:
        tokens = self.market_tokens.get(market_id)
        if not tokens:
            market = await self.get_market(market_id)
            tokens = (market.yes_token_id or "", market.no_token_id or "")
        if not all(tokens):
            raise ValueError(f"Polymarket market {market_id} does not expose a Yes/No token pair")
        yes_response, no_response = await asyncio.gather(
            self.clob.get("/book", params={"token_id": tokens[0]}),
            self.clob.get("/book", params={"token_id": tokens[1]}),
        )
        body = {"yes": yes_response.json(), "no": no_response.json(), "tokens": {"yes": tokens[0], "no": tokens[1]}}
        self.raw_orderbooks[market_id] = body
        return self.normalize_orderbook(market_id, body)

    async def health(self) -> ConnectorHealth:
        # Gamma drives metadata connectivity; aggregate CLOB counters for debug visibility.
        state = self.gamma.state.model_copy(deep=True)
        state.request_count += self.clob.state.request_count
        state.error_count += self.clob.state.error_count
        state.rate_limit_count += self.clob.state.rate_limit_count
        if self.clob.state.last_error: state.last_error = self.clob.state.last_error
        return state

    async def close(self) -> None:
        await self.gamma.close()
        await self.clob.close()

    @staticmethod
    def _levels(raw: list[dict], reverse: bool) -> list[OrderBookLevel]:
        return sorted([OrderBookLevel(price=float(x["price"]), quantity=float(x["size"])) for x in raw], key=lambda x: x.price, reverse=reverse)

    @classmethod
    def normalize_orderbook(cls, market_id: str, body: dict) -> OrderBook:
        yes, no = body["yes"], body["no"]
        # Cache timestamp means "successfully fetched at"; the raw exchange timestamp
        # remains available verbatim on /orderbook/debug for staleness inspection.
        timestamp = datetime.now(UTC)
        return OrderBook(
            market_id=market_id, timestamp=timestamp,
            yes_bids=cls._levels(yes.get("bids", []), True), yes_asks=cls._levels(yes.get("asks", []), False),
            no_bids=cls._levels(no.get("bids", []), True), no_asks=cls._levels(no.get("asks", []), False), source="live",
        )

    @staticmethod
    def _normalize_market(raw: dict) -> NormalizedMarket:
        outcomes, tokens, prices = _array(raw.get("outcomes")), _array(raw.get("clobTokenIds")), _array(raw.get("outcomePrices"))
        mapping = {str(name).lower(): str(tokens[i]) for i, name in enumerate(outcomes) if i < len(tokens)}
        price_map = {str(name).lower(): float(prices[i]) for i, name in enumerate(outcomes) if i < len(prices)}
        resolved = "YES" if price_map.get("yes") == 1 else "NO" if price_map.get("no") == 1 else None
        external_id = str(raw.get("id") or raw.get("conditionId"))
        close = raw.get("endDate") or raw.get("end_date_iso") or raw.get("endDateIso")
        if not close:
            raise ValueError(f"Polymarket market {external_id} has no close time")
        return NormalizedMarket(
            id=f"polymarket:{external_id}", platform=Platform.POLYMARKET, external_id=external_id,
            title=raw.get("question", ""), description=raw.get("description", ""),
            category=(raw.get("category") or "other").lower(), event_date=close, close_time=close,
            resolution_rules=raw.get("description", ""), resolution_source=raw.get("resolutionSource") or "Polymarket rules",
            status="closed" if raw.get("closed") else ("open" if raw.get("active", True) else "inactive"),
            yes_bid=float(raw["bestBid"]) if raw.get("bestBid") not in (None, "") else None,
            yes_ask=float(raw["bestAsk"]) if raw.get("bestAsk") not in (None, "") else None,
            no_bid=None, no_ask=None,
            yes_token_id=mapping.get("yes"), no_token_id=mapping.get("no"), event_id=str(raw.get("eventId") or ((raw.get("events") or [{}])[0].get("id", ""))),
            updated_at=raw.get("updatedAt") or raw.get("createdAt") or datetime.now(UTC), source="live",
            resolved_outcome=resolved,
        )
