from datetime import timedelta
from urllib.parse import unquote

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel

from app.config import get_settings
from app.matching.candidates import candidate_pairs
from app.schemas.domain import MatchStatus, NormalizedMarket, OrderBook
from app.services import mock_data
from app.services.runtime import ArbiCastRuntime
from app.services.research_test import ResearchTestService
from pydantic import Field

router = APIRouter(prefix="/api")


def runtime(request: Request) -> ArbiCastRuntime:
    return request.app.state.runtime

def research(request:Request)->ResearchTestService:return ResearchTestService(runtime(request))

class PairBody(BaseModel):kalshi_market_id:str;polymarket_market_id:str
class PipelineBody(BaseModel):pair_id:str;direction:str;trade_size:float=Field(10,gt=0,le=1000);latency_ms:int=Field(250,ge=0,le=10000);min_net_edge:float=Field(-.05,ge=-1,le=.5)
class CleanupBody(BaseModel):confirmation:str

@router.get("/research-test/markets",summary="Search live cached markets for the research console")
async def research_markets(request:Request,platform:str,query:str="",limit:int=20):
    try:return research(request).search(platform,query,min(limit,50))
    except ValueError as exc:raise HTTPException(409,str(exc))

@router.post("/research-test/analyze",summary="Explain every matcher filter for one manually selected pair")
async def research_analyze(request:Request,body:PairBody):
    try:return research(request).analyze(body.kalshi_market_id,body.polymarket_market_id)
    except KeyError as exc:raise HTTPException(404,f"Market not found: {exc}")

@router.get("/research-test/closest/{market_id:path}",summary="Top-10 cross-platform markets using the production matcher features")
async def research_closest(request:Request,market_id:str,limit:int=10):
    try:return research(request).closest(unquote(market_id),min(limit,20))
    except KeyError:raise HTTPException(404,"Market not found")

@router.post("/research-test/pairs",summary="Create an isolated TEST_APPROVED pair")
async def research_create_pair(request:Request,body:PairBody):
    try:return await research(request).create_pair(body.kalshi_market_id,body.polymarket_market_id)
    except KeyError as exc:raise HTTPException(404,f"Market not found: {exc}")

@router.get("/research-test/pairs",summary="List isolated test pairs")
async def research_pairs(request:Request):return await runtime(request).repository.load_test_pairs()

@router.post("/research-test/orderbooks",summary="Refresh and validate both real order books")
async def research_books(request:Request,body:PairBody):
    try:return await research(request).inspect_books(body.kalshi_market_id,body.polymarket_market_id)
    except Exception as exc:raise HTTPException(502,str(exc)[:300])

@router.post("/research-test/arbitrage",summary="Show positive and negative depth-adjusted quotes for both directions")
async def research_arbitrage(request:Request,body:PairBody):
    try:return await research(request).calculate(body.kalshi_market_id,body.polymarket_market_id)
    except Exception as exc:raise HTTPException(502,str(exc)[:300])

@router.post("/research-test/pipeline",summary="Run isolated paper execution with real order books")
async def research_pipeline(request:Request,body:PipelineBody):
    try:return await research(request).run_pipeline(body.pair_id,body.direction,body.trade_size,body.latency_ms,body.min_net_edge)
    except KeyError:raise HTTPException(404,"Test pair not found")
    except ValueError as exc:raise HTTPException(422,str(exc))
    except Exception as exc:raise HTTPException(502,str(exc)[:300])

@router.get("/research-test/verification",summary="Test database isolation and account status")
async def research_verification(request:Request):return await runtime(request).repository.test_verification()

@router.delete("/research-test/data",summary="Delete only is_test=true records")
async def research_cleanup(request:Request,body:CleanupBody):
    if body.confirmation!="CLEAR TEST DATA":raise HTTPException(400,"Exact confirmation required")
    return await runtime(request).repository.clear_test_data()


@router.get("/health", summary="Application and connector health", description="Returns live connector, database, loading and data-mode state. Never triggers an external request.")
async def health(request: Request):
    return await runtime(request).health()


@router.get("/connectors", summary="Connector diagnostics", description="Health counters and the last 20 outbound public market-data requests.")
async def connectors(request: Request):
    service = runtime(request)
    state = await service.health()
    return {**state, "recent_requests": service.recent_requests()}


@router.get("/dashboard", summary="Dashboard cache summary")
async def dashboard(request: Request):
    service = runtime(request)
    state = await service.health()
    if service.settings.data_mode == "mock":
        opps, pairs, trades = mock_data.opportunities(), mock_data.matches(), mock_data.paper_trades()
        summary = {"liveOpportunities": sum(o.live for o in opps), "bestNetEdge": max(o.net_edge for o in opps if o.live), "approvedMarkets": sum(p.status == MatchStatus.APPROVED for p in pairs), "paperPnl": sum(t.estimated_profit for t in trades)}
    else:
        opps=await service.repository.load_opportunities(True);paper=await service.repository.paper_summary();stats=await service.repository.research_stats();summary={"liveOpportunities":stats.get("live_opportunities",0),"bestNetEdge":max((o["net_edge"] for o in opps),default=0),"approvedMarkets":stats.get("approved_pairs",0),"paperPnl":paper.get("account",{}).get("realized_pnl",0),"paperBalance":paper.get("account",{}).get("equity",service.settings.paper_starting_balance),"paperRoi":paper.get("account",{}).get("roi",0)}
    return {"dataMode": service.settings.data_mode, "loading": state["loading"], "status": state["connectors"], "summary": summary, "opportunities": opps, "feeAssumptions": {"kalshi": "configurable; verify official current schedule", "polymarket": "configurable; verify official current schedule"}}


@router.get("/markets", response_model=list[NormalizedMarket], summary="List normalized cached markets", description="Reads ArbiCast cache only. It never calls Kalshi or Polymarket directly.")
async def get_markets(request: Request, platform: str | None = None, status: str | None = None, watched: bool | None = None, search: str | None = None):
    items = list(runtime(request).cache.markets.values())
    if platform: items = [m for m in items if m.platform.value == platform]
    if status: items = [m for m in items if m.status == status]
    if watched is not None: items = [m for m in items if m.watched == watched]
    if search: items = [m for m in items if search.lower() in m.title.lower()]
    return sorted(items, key=lambda m: (not m.watched, m.platform.value, m.close_time))


@router.get("/markets/{market_id}", response_model=NormalizedMarket, summary="Get one normalized cached market")
async def get_market(request: Request, market_id: str):
    item = runtime(request).cache.markets.get(unquote(market_id))
    if not item: raise HTTPException(404, "Market not found in cache")
    return item


@router.get("/markets/{market_id}/orderbook", response_model=OrderBook, summary="Get cached normalized order book", description="Order books are refreshed in the background for watched markets.")
async def get_orderbook(request: Request, market_id: str):
    item = runtime(request).cache.orderbooks.get(unquote(market_id))
    if not item: raise HTTPException(404, "No cached order book. Watch the market first.")
    return item


@router.get("/markets/{market_id}/orderbook/debug", summary="Compare raw and normalized order book")
async def debug_orderbook(request: Request, market_id: str):
    service = runtime(request); mid = unquote(market_id)
    market = service.cache.markets.get(mid)
    if not market: raise HTTPException(404, "Market not found")
    return {"market": market, "raw": service.cache.raw_orderbooks.get(mid), "normalized": service.cache.orderbooks.get(mid)}


@router.post("/markets/{market_id}/watch", response_model=NormalizedMarket, summary="Watch a market", description="Starts high-frequency cached order-book refresh for this market.")
async def watch_market(request: Request, market_id: str):
    try: return await runtime(request).watch(unquote(market_id), True)
    except KeyError: raise HTTPException(404, "Market not found")
    except Exception as exc: raise HTTPException(502, f"Initial order book request failed: {str(exc)[:240]}")


@router.delete("/markets/{market_id}/watch", response_model=NormalizedMarket, summary="Stop watching a market")
async def unwatch_market(request: Request, market_id: str):
    try: return await runtime(request).watch(unquote(market_id), False)
    except KeyError: raise HTTPException(404, "Market not found")


@router.get("/matches", summary="Candidate market pairs")
async def get_matches(request: Request):
    service = runtime(request)
    if service.settings.data_mode == "live": return await service.repository.load_matches()
    by_id = {m.id: m for m in mock_data.markets()}
    return [{**pair.model_dump(), "kalshi_market": by_id[pair.kalshi_market_id], "polymarket_market": by_id[pair.polymarket_market_id]} for pair in mock_data.matches()]

class MatchReview(BaseModel): status: MatchStatus

@router.patch("/matches/{match_id}",summary="Review a candidate market pair",description="Persists an explicit human Approve, Reject, or Needs Review decision.")
async def review_match(request:Request,match_id:str,body:MatchReview):
    if runtime(request).settings.data_mode!="live":raise HTTPException(409,"Match review persistence is available in live mode")
    match=await runtime(request).review_match(unquote(match_id),body.status.value)
    if not match:raise HTTPException(404,"Candidate match not found")
    return match


@router.get("/opportunities", summary="Approved-pair research opportunities")
async def get_opportunities(request: Request):
    return mock_data.opportunities() if runtime(request).settings.data_mode == "mock" else await runtime(request).repository.load_opportunities()


@router.get("/opportunities/{opportunity_id}")
async def get_opportunity(request: Request, opportunity_id: str):
    if runtime(request).settings.data_mode != "mock":
        opportunity=await runtime(request).repository.load_opportunity(unquote(opportunity_id))
        if not opportunity:raise HTTPException(404,"Opportunity not found")
        return opportunity
    opportunity = next((o for o in mock_data.opportunities() if o.id == opportunity_id), None)
    if not opportunity: raise HTTPException(404, "Opportunity not found")
    base = opportunity.net_edge
    history = [{"time": (mock_data.NOW-timedelta(seconds=60-i*5)).isoformat(), "edge": max(0, base+((i%4)-2)*.0015)} for i in range(13)]
    depth = [{"price": round(opportunity.kalshi_price+i*.005, 3), "kalshi": 18+i*11, "polymarket": 12+i*15} for i in range(6)]
    return {**opportunity.model_dump(), "history": history, "depth": depth}


@router.get("/paper")
async def get_paper(request: Request): return mock_data.paper_trades() if runtime(request).settings.data_mode == "mock" else await runtime(request).repository.paper_summary()


@router.get("/analytics")
async def get_analytics(request: Request):
    if runtime(request).settings.data_mode != "mock":
        service=runtime(request);stats=await service.repository.research_stats();paper=await service.repository.paper_summary();opps=await service.repository.load_opportunities()
        edges=[o["net_edge"] for o in opps]
        return {"summary":{"detected":stats.get("opportunities",0),"above1":sum(x>.01 for x in edges),"above2":sum(x>.02 for x in edges),"above3":sum(x>.03 for x in edges),"medianDuration":0,"medianLiquidity":0,"paperProfit":paper.get("account",{}).get("realized_pnl",0)},"performance":{"account":paper.get("account",{}),"metrics":paper.get("metrics",{}),"research":stats},"daily":[],"edgeDistribution":[],"durations":[],"categories":[],"profitBySize":[]}
    return mock_data.analytics()

@router.get("/research/stats",summary="Persisted research pipeline counts")
async def research_stats(request:Request):return await runtime(request).repository.research_stats()


@router.get("/settings")
async def get_runtime_settings(request: Request):
    service = runtime(request); health_state = await service.health(); settings = get_settings()
    return {"dataMode": settings.data_mode, "marketRefreshSeconds": settings.market_refresh_seconds, "orderbookRefreshSeconds": settings.orderbook_refresh_seconds, "watchedMarketsCount": len(service.watched.list()), "database": health_state["database"], "connectors": health_state["connectors"], "minNetEdge": settings.min_net_edge, "minExpectedProfit": settings.min_expected_profit, "defaultTradeSize": settings.default_trade_size, "paperLatencyMs": settings.paper_execution_latency_ms, "paperSlippageBuffer": settings.paper_slippage_buffer, "pollingFrequency": settings.orderbook_refresh_seconds, "kalshiFee": .07, "polymarketFee": 0,"paperTestMode":settings.paper_test_mode}
