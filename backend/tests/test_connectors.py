import json
from pathlib import Path

import httpx
import pytest

from app.connectors.kalshi.connector import KalshiConnector
from app.connectors.polymarket.connector import PolymarketConnector
from app.schemas.domain import Platform
from app.services.market_cache import MarketCache
from app.services.watched import WatchedMarketService

FIXTURES = Path(__file__).parent / "fixtures"


def fixture(name): return json.loads((FIXTURES/name).read_text())


def test_kalshi_market_normalization_and_price_units():
    market = KalshiConnector._normalize_market(fixture("kalshi_market.json"))
    assert market.platform == Platform.KALSHI
    assert market.external_id == "KXTEST-26-A"
    assert market.status == "open"
    assert market.yes_bid == .43 and market.no_ask == .57
    assert market.source == "live"


def test_kalshi_orderbook_bid_ask_relationship():
    book = KalshiConnector.normalize_orderbook("kalshi:test", fixture("kalshi_orderbook.json"))
    assert book.yes_bids[0].price == .42
    assert book.yes_asks[0].price == pytest.approx(.43)  # complement of best NO bid .57
    assert book.no_bids[0].price == .57
    assert book.no_asks[0].price == pytest.approx(.58)  # complement of best YES bid .42
    assert book.yes_asks[0].quantity == 20


def test_polymarket_market_maps_event_and_outcome_tokens():
    market = PolymarketConnector._normalize_market(fixture("polymarket_market.json"))
    assert market.id == "polymarket:123"
    assert market.event_id == "event-7"
    assert market.yes_token_id == "yes-token" and market.no_token_id == "no-token"
    assert market.yes_bid == .42 and market.yes_ask == .44
    assert market.no_bid is None  # never mislabel outcome midpoint as best bid


def test_polymarket_orderbook_keeps_each_token_side():
    book = PolymarketConnector.normalize_orderbook("polymarket:123", fixture("polymarket_orderbook.json"))
    assert book.yes_bids[0].price == .42 and book.yes_asks[0].price == .44
    assert book.no_bids[0].price == .56 and book.no_asks[0].price == .58


@pytest.mark.asyncio
async def test_kalshi_cursor_pagination_and_maximum():
    calls = []
    async def handler(request):
        calls.append(request)
        cursor = request.url.params.get("cursor")
        raw = fixture("kalshi_market.json")
        raw["ticker"] = "PAGE-2" if cursor else "PAGE-1"
        return httpx.Response(200, json={"markets":[raw], "cursor":"next" if not cursor else ""})
    connector = KalshiConnector(max_markets=2)
    await connector.http.client.aclose()
    connector.http.client = httpx.AsyncClient(base_url="https://test", transport=httpx.MockTransport(handler))
    markets = await connector.get_markets()
    await connector.close()
    assert [m.external_id for m in markets] == ["PAGE-1", "PAGE-2"]
    assert len(calls) == 2 and calls[1].url.params["cursor"] == "next"


@pytest.mark.asyncio
async def test_empty_market_page():
    async def handler(request): return httpx.Response(200, json={"markets":[],"cursor":""})
    connector = KalshiConnector(max_markets=10)
    await connector.http.client.aclose(); connector.http.client=httpx.AsyncClient(base_url="https://test",transport=httpx.MockTransport(handler))
    assert await connector.get_markets() == []
    await connector.close()


@pytest.mark.asyncio
async def test_http_error_updates_health_without_crashing_other_state():
    async def handler(request): return httpx.Response(503, request=request)
    connector = KalshiConnector(max_markets=1)
    await connector.http.client.aclose(); connector.http.client=httpx.AsyncClient(base_url="https://test",transport=httpx.MockTransport(handler))
    with pytest.raises(httpx.HTTPStatusError): await connector.http.get("/markets", attempts=1)
    state = await connector.health()
    assert not state.connected and state.error_count == 1 and state.last_error
    await connector.close()


@pytest.mark.asyncio
async def test_timeout_updates_health():
    async def handler(request): raise httpx.ReadTimeout("timeout", request=request)
    connector = KalshiConnector(max_markets=1)
    await connector.http.client.aclose(); connector.http.client=httpx.AsyncClient(base_url="https://test",transport=httpx.MockTransport(handler))
    with pytest.raises(httpx.ReadTimeout): await connector.http.get("/markets", attempts=1)
    assert (await connector.health()).error_count == 1
    await connector.close()


@pytest.mark.asyncio
async def test_429_is_counted_and_retried(monkeypatch):
    calls = 0
    async def handler(request):
        nonlocal calls
        calls += 1
        return httpx.Response(429 if calls == 1 else 200, request=request, json={"ok": True})
    async def no_sleep(_): pass
    monkeypatch.setattr("app.connectors.http.asyncio.sleep", no_sleep)
    connector = KalshiConnector(max_markets=1)
    await connector.http.client.aclose(); connector.http.client=httpx.AsyncClient(base_url="https://test",transport=httpx.MockTransport(handler))
    response = await connector.http.get("/test", attempts=2)
    assert response.status_code == 200 and calls == 2
    state = await connector.health()
    assert state.rate_limit_count == 1 and state.connected and state.backoff_seconds == 0
    await connector.close()


@pytest.mark.asyncio
async def test_cache_and_watched_market():
    market = KalshiConnector._normalize_market(fixture("kalshi_market.json"))
    cache, watched = MarketCache(), WatchedMarketService()
    assert len(await cache.update_markets([market])) == 1
    assert await cache.update_markets([market]) == []
    watched.add(market.id); await cache.set_watched(market.id, True)
    assert watched.contains(market.id) and cache.markets[market.id].watched
    watched.remove(market.id)
    assert not watched.contains(market.id)
