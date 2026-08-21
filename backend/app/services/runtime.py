import asyncio
import logging
from contextlib import suppress
from datetime import UTC, datetime

from app.config import Settings
from app.connectors.kalshi import KalshiConnector
from app.connectors.polymarket import PolymarketConnector
from app.schemas.domain import ConnectorHealth, NormalizedMarket, OrderBook, OrderBookLevel, Platform
from app.services import mock_data
from app.services.market_cache import MarketCache
from app.services.repository import Repository
from app.services.watched import WatchedMarketService
from app.services.csl import CSLResearchService
from app.matching.candidates import candidate_pairs
from app.arbitrage.service import evaluate_pair
from app.paper_trading.execution import execute_opportunity

logger = logging.getLogger("arbicast.scheduler")


class ArbiCastRuntime:
    def __init__(self, settings: Settings):
        self.settings = settings
        self.cache = MarketCache()
        self.watched = WatchedMarketService()
        self.repository = Repository(settings.orderbook_snapshot_min_seconds,settings.opportunity_snapshot_min_ms)
        self.connectors = {
            Platform.KALSHI: KalshiConnector(settings.kalshi_base_url, settings.kalshi_max_markets, settings.http_connect_timeout_seconds, settings.http_read_timeout_seconds),
            Platform.POLYMARKET: PolymarketConnector(settings.polymarket_gamma_url, settings.polymarket_clob_url, settings.polymarket_max_markets, settings.http_connect_timeout_seconds, settings.http_read_timeout_seconds),
        }
        self.tasks: list[asyncio.Task] = []
        self.stop = asyncio.Event()
        self.paper_pending:set[str]=set()
        self.csl = CSLResearchService(self)

    async def start(self) -> None:
        await self.repository.initialize()
        await self.repository.ensure_paper_account(self.settings.paper_starting_balance)
        for market_id in await self.repository.load_watched(): self.watched.add(market_id)
        if self.settings.data_mode == "mock":
            items = mock_data.markets()
            await self.cache.update_markets(items)
            self.cache.loading = False
            return
        for platform in self.connectors:
            self.tasks.append(asyncio.create_task(self._market_loop(platform), name=f"{platform.value}-markets"))
        self.tasks.append(asyncio.create_task(self._orderbook_loop(), name="watched-orderbooks"))
        self.tasks.append(asyncio.create_task(self._matching_loop(), name="market-matching"))
        self.tasks.append(asyncio.create_task(self._arbitrage_loop(), name="arbitrage-detection"))
        self.tasks.append(asyncio.create_task(self._resolution_loop(), name="resolution-monitor"))
        self.tasks.append(asyncio.create_task(self._csl_loop(), name="csl-dynamic-research"))

    async def close(self) -> None:
        self.stop.set()
        for task in self.tasks: task.cancel()
        for task in self.tasks:
            with suppress(asyncio.CancelledError): await task
        for connector in self.connectors.values(): await connector.close()

    async def _wait(self, seconds: float) -> None:
        try: await asyncio.wait_for(self.stop.wait(), timeout=seconds)
        except TimeoutError: pass

    async def _market_loop(self, platform: Platform) -> None:
        connector = self.connectors[platform]
        while not self.stop.is_set():
            started = datetime.now(UTC)
            try:
                markets = await connector.get_markets()
                for market in markets:
                    market.watched = self.watched.contains(market.id)
                changed = await self.cache.update_markets(markets)
                await self.repository.save_markets(changed)
                health = await connector.health()
                await self.repository.save_health(health)
                logger.info("[%s] loaded %d active markets in %.0fms", platform.value.upper(), len(markets), health.latency_ms or 0)
            except Exception as exc:
                logger.warning("[%s] market refresh failed: %s", platform.value.upper(), str(exc)[:240])
            self.cache.loading = not any(m.platform == platform for m in self.cache.markets.values()) and not self.cache.markets
            elapsed = (datetime.now(UTC)-started).total_seconds()
            await self._wait(max(1, self.settings.market_refresh_seconds-elapsed))

    async def _orderbook_loop(self) -> None:
        semaphore = asyncio.Semaphore(5)
        while not self.stop.is_set():
            async def refresh(market_id: str):
                market = self.cache.markets.get(market_id)
                if not market: return
                connector = self.connectors[market.platform]
                async with semaphore:
                    try:
                        book = await connector.get_orderbook(market_id)
                        raw = connector.raw_orderbooks.get(market_id)
                        await self.cache.update_orderbook(market_id, book, raw)
                        await self.repository.save_orderbook(book)
                        logger.info("[%s] orderbook updated market=%s", market.platform.value.upper(), market.external_id)
                    except Exception as exc:
                        logger.warning("[%s] orderbook failed market=%s: %s", market.platform.value.upper(), market.external_id, str(exc)[:180])
            await asyncio.gather(*(refresh(mid) for mid in self.watched.list()), return_exceptions=True)
            await self._wait(self.settings.orderbook_refresh_seconds)

    async def _matching_loop(self) -> None:
        while not self.stop.is_set():
            ready=all(any(m.platform==platform for m in self.cache.markets.values()) for platform in Platform)
            if ready:
                try:
                    candidates=await asyncio.to_thread(candidate_pairs,list(self.cache.markets.values()),self.settings.matching_min_score)
                    await self.repository.save_matches(candidates)
                    logger.info("[MATCHER] generated %d high-confidence candidates",len(candidates))
                except Exception as exc:logger.warning("[MATCHER] cycle failed: %s",str(exc)[:240])
            await self._wait(self.settings.matching_refresh_seconds if ready else 2)

    async def review_match(self, match_id: str, status: str) -> dict | None:
        match=await self.repository.set_match_status(match_id,status)
        if match and status=="approved":
            for market_id in (match["kalshi_market_id"],match["polymarket_market_id"]):
                if market_id in self.cache.markets and not self.watched.contains(market_id):await self.watch(market_id,True)
        return match

    async def _arbitrage_loop(self) -> None:
        while not self.stop.is_set():
            try:
                for match in await self.repository.load_matches("approved"):
                    kb=self.cache.orderbooks.get(match["kalshi_market_id"]);pb=self.cache.orderbooks.get(match["polymarket_market_id"])
                    if not kb or not pb:continue
                    for direction,payload,active in evaluate_pair(match,kb,pb,self.settings):
                        opportunity=await self.repository.upsert_opportunity(match["id"],direction,payload,active)
                        if active:
                            await self.repository.save_opportunity_snapshot(opportunity)
                            if opportunity["net_edge"]>=self.settings.paper_min_net_edge and opportunity["available_size"]>=self.settings.paper_min_liquidity and opportunity["match_confidence"]>=self.settings.paper_min_match_confidence and opportunity["id"] not in self.paper_pending and not await self.repository.has_paper_trade(opportunity["id"]):
                                self.paper_pending.add(opportunity["id"]);asyncio.create_task(self._execute_paper(opportunity))
            except Exception as exc:logger.warning("[ARBITRAGE] cycle failed: %s",str(exc)[:240])
            await self._wait(self.settings.orderbook_refresh_seconds)

    async def _execute_paper(self,opportunity:dict)->None:
        try:
            await self._wait(self.settings.paper_execution_latency_ms/1000)
            kb=self.cache.orderbooks.get(opportunity["kalshi_market_id"]);pb=self.cache.orderbooks.get(opportunity["polymarket_market_id"])
            if kb and pb:await self.repository.create_paper_execution(opportunity,execute_opportunity(opportunity,kb,pb,self.settings))
        finally:self.paper_pending.discard(opportunity["id"])

    async def _resolution_loop(self)->None:
        while not self.stop.is_set():
            for position in await self.repository.open_positions():
                try:
                    kalshi=await self.connectors[Platform.KALSHI].get_market(position["kalshi_market_id"]);poly=await self.connectors[Platform.POLYMARKET].get_market(position["polymarket_market_id"])
                    if kalshi.resolved_outcome or poly.resolved_outcome:await self.repository.record_resolution(position,kalshi.resolved_outcome,poly.resolved_outcome)
                except Exception as exc:logger.warning("[RESOLUTION] check failed position=%s: %s",position["id"],str(exc)[:180])
            await self._wait(self.settings.market_refresh_seconds)

    async def _csl_loop(self)->None:
        while not self.stop.is_set():
            try:await self.csl.record_cycle()
            except Exception as exc:logger.warning("[CSL] dynamic cycle failed: %s",str(exc)[:240])
            await self._wait(self.settings.dynamic_book_poll_ms/1000)

    async def watch(self, market_id: str, watched: bool) -> NormalizedMarket:
        if market_id not in self.cache.markets: raise KeyError(market_id)
        (self.watched.add if watched else self.watched.remove)(market_id)
        market = await self.cache.set_watched(market_id, watched)
        await self.repository.set_watched(market_id, watched)
        if watched and self.settings.data_mode == "live":
            connector = self.connectors[market.platform]
            book = await connector.get_orderbook(market_id)
            await self.cache.update_orderbook(market_id, book, connector.raw_orderbooks.get(market_id))
            await self.repository.save_orderbook(book)
        elif watched:
            await self.cache.update_orderbook(market_id, self._mock_book(market))
        return market

    async def health(self) -> dict:
        if self.settings.data_mode == "mock":
            now = datetime.now(UTC)
            states = [ConnectorHealth(platform=p, connected=True, last_success=now, last_attempt=now, latency_ms=0, markets_loaded=sum(m.platform==p for m in self.cache.markets.values())) for p in Platform]
        else:
            states = [await connector.health() for connector in self.connectors.values()]
        return {"data_mode": self.settings.data_mode, "loading": self.cache.loading, "database": {"connected": self.repository.available, "last_error": self.repository.last_error}, "watched_count": len(self.watched.list()), "connectors": states}

    def recent_requests(self) -> list[dict]:
        rows = []
        for connector in self.connectors.values():
            clients = [getattr(connector, "http", None), getattr(connector, "gamma", None), getattr(connector, "clob", None)]
            for client in filter(None, clients): rows.extend(item.model_dump(mode="json") for item in client.recent)
        return sorted(rows, key=lambda x: x["timestamp"], reverse=True)[:20]

    @staticmethod
    def _mock_book(market: NormalizedMarket) -> OrderBook:
        yes = market.yes_bid or .43
        no = market.no_bid or .54
        return OrderBook(market_id=market.id, timestamp=datetime.now(UTC), yes_bids=[OrderBookLevel(price=yes, quantity=50)], yes_asks=[OrderBookLevel(price=1-no, quantity=60)], no_bids=[OrderBookLevel(price=no, quantity=60)], no_asks=[OrderBookLevel(price=1-yes, quantity=50)], source="mock")
