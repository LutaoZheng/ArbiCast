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
        self.csl_series_probe: dict = {}

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

    async def discover_sports_markets(self, max_pages: int, max_markets: int) -> tuple[list[NormalizedMarket], dict]:
        """Bounded event-level sports discovery, independent of the general market cache."""
        results: list[NormalizedMarket] = []
        cursor: str | None = None
        pages = 0
        events_scanned = 0
        markets_scanned = 0
        # Series-specific discovery runs first. Global ordering must never decide
        # whether the known CSL research universe is visible.
        probe = await self.probe_csl_series()
        for event in probe.get("active_events_raw", []):
            for market in self._normalize_event_markets(event):
                if market.id not in {x.id for x in results}: results.append(market)
        while pages < max_pages and len(results) < max_markets:
            params: dict[str, str | int | bool] = {"status": "open", "limit": 200, "with_nested_markets": "true"}
            if cursor: params["cursor"] = cursor
            body = (await self.http.get("/events", params=params)).json()
            events = body.get("events", [])
            pages += 1
            events_scanned += len(events)
            for event in events:
                markets_scanned += len(event.get("markets", []))
                event_text = " ".join(str(event.get(k, "")) for k in ("title", "sub_title", "category", "series_ticker"))
                if "sport" not in str(event.get("category", "")).lower() and not any(x in event_text.lower() for x in ("soccer", "football", "super league", " csl")):
                    continue
                for market in self._normalize_event_markets(event):
                    if market.id not in {x.id for x in results}: results.append(market)
                    if len(results) >= max_markets: break
                if len(results) >= max_markets: break
            cursor = body.get("cursor")
            if not events or not cursor: break
        return results, {"endpoint": "/events?series_ticker=KXCHNSLGAME + bounded sports scan", "pages": pages, "events_scanned": events_scanned, "markets_scanned": markets_scanned+probe.get("active_markets",0), "series_probe":{k:v for k,v in probe.items() if k!="active_events_raw"},"source_type": "rest_snapshot"}

    def _normalize_event_markets(self,event:dict)->list[NormalizedMarket]:
        rows=[]
        for raw in event.get("markets",[]):
            enriched={**raw,"series_ticker":event.get("series_ticker"),"event_title":event.get("title"),"category":event.get("category","Sports"),"title":raw.get("title") or event.get("title",""),"subtitle":" ".join(filter(None,[event.get("sub_title"),raw.get("yes_sub_title"),event.get("title"),event.get("product_metadata",{}).get("competition")])),"occurrence_datetime":raw.get("occurrence_datetime") or event.get("strike_date") or raw.get("open_time")}
            try:rows.append(self._normalize_market(enriched))
            except (ValueError,TypeError,KeyError):continue
        return rows

    async def probe_csl_series(self)->dict:
        ticker="KXCHNSLGAME"
        try:
            series=(await self.http.get(f"/series/{ticker}")).json().get("series",{})
            all_events=(await self.http.get("/events",params={"series_ticker":ticker,"limit":200,"with_nested_markets":"true"})).json().get("events",[])
            open_events=(await self.http.get("/events",params={"series_ticker":ticker,"status":"open","limit":200,"with_nested_markets":"true"})).json().get("events",[])
            unopened=(await self.http.get("/events",params={"series_ticker":ticker,"status":"unopened","limit":200,"with_nested_markets":"true"})).json().get("events",[])
            def item(event):
                markets=event.get("markets",[]);start=next((m.get("occurrence_datetime") or m.get("expected_expiration_time") for m in markets if m.get("occurrence_datetime") or m.get("expected_expiration_time")),None)
                return {"event_ticker":event.get("event_ticker"),"title":event.get("title"),"status":sorted({m.get("status") for m in markets if m.get("status")}),"start_date":start,"markets_count":len(markets)}
            active=open_events+unopened;events=sorted((item(x) for x in active),key=lambda x:x.get("start_date") or "")
            self.csl_series_probe={"series":"KXCHNSLGAME","exists":bool(series),"api_reachable":True,"title":series.get("title"),"category":series.get("category"),"tags":series.get("tags",[]),"current_events":len(all_events),"open_events":len(open_events),"upcoming_events":len(unopened),"active_markets":sum(len(x.get("markets",[])) for x in active),"nearest_fixture":events[0] if events else None,"events":events[:20],"active_events_raw":active}
        except Exception as exc:self.csl_series_probe={"series":ticker,"exists":False,"api_reachable":False,"error":str(exc)[:240],"current_events":0,"open_events":0,"upcoming_events":0,"active_markets":0,"events":[],"active_events_raw":[]}
        return self.csl_series_probe

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
            event_id=raw.get("event_ticker"), event_title=raw.get("event_title"), series_ticker=raw.get("series_ticker"), outcome_label=raw.get("yes_sub_title"), updated_at=updated, source="live",
            resolved_outcome=str(raw.get("result","")).upper() if str(raw.get("result","")).lower() in {"yes","no"} else None,
        )
