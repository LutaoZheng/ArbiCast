import asyncio
from datetime import UTC, datetime, timedelta

from app.arbitrage.vwap import calculate_vwap
from app.csl.dynamic import DynamicSignalEngine, execute_dynamic_signal
from app.csl.matching import csl_candidate_pairs,inspect_csl_market,is_csl_like_market,is_football_market,is_semantically_compatible_csl,match_session_payload,parse_csl_contract
from app.schemas.domain import Platform
from app.services.csl_repository import CSLRepository

def collector_lag_quality(source_types:list[str],exchange_timestamps_available:bool,poll_ms:int)->str:
    if source_types and all(x=="websocket" for x in source_types) and exchange_timestamps_available:return "HIGH"
    if poll_ms<1000:return "MEDIUM"
    return "LOW"

class CSLResearchService:
    def __init__(self,runtime):
        self.runtime=runtime;self.repo=CSLRepository();s=runtime.settings
        self.engine=DynamicSignalEngine(s.dynamic_signal_move_cents/100,s.dynamic_signal_window_ms,s.dynamic_signal_ttl_ms,s.paper_slippage_buffer)
        self.latencies=[int(x) for x in s.dynamic_execution_latencies_ms.split(",") if x.strip()]
        self.discovery_markets={};self.last_discovery=None;self.discovery_running=False
        self.discovery={"data_mode":s.data_mode,"last_run":None,"kalshi":{"markets_scanned":0,"football_markets":0,"csl_like_markets":0},"polymarket":{"markets_scanned":0,"football_markets":0,"csl_like_markets":0},"candidate_fixtures":0,"resolution_compatible":0,"research_pairs":0,"recording_sessions":0,"rejections":{"team_mismatch":0,"date_mismatch":0,"market_type_mismatch":0,"resolution_mismatch":0,"ambiguous":0},"rows":[],"collector_health":{}}

    async def refresh_discovery(self,force=False):
        now=datetime.now(UTC)
        if self.discovery_running:return self.discovery
        if not force and self.last_discovery and (now-self.last_discovery).total_seconds()<self.runtime.settings.csl_discovery_refresh_seconds:return self.discovery
        self.discovery_running=True
        all_markets=[];meta={}
        for platform,connector in self.runtime.connectors.items():
            try:
                markets,details=await connector.discover_sports_markets(self.runtime.settings.csl_discovery_max_pages,self.runtime.settings.csl_discovery_max_markets)
                meta[platform.value]=details;all_markets.extend(markets)
            except Exception as exc:
                meta[platform.value]={"error":str(exc)[:240],"source_type":"rest_snapshot","pages":0,"events_scanned":0}
        self.discovery_markets={m.id:m for m in all_markets}
        if all_markets:await self.runtime.repository.save_markets(all_markets)
        candidates=await asyncio.to_thread(csl_candidate_pairs,all_markets)
        if candidates:await self.runtime.repository.save_matches(candidates)
        rows=[inspect_csl_market(x) for x in all_markets if is_csl_like_market(x)]
        by_id={x.id:x for x in all_markets};compatible_pairs=0;fully_compatible_pairs=0
        for candidate in candidates:
            compatible_pairs+=int(candidate["resolution_compatible"])
            fully_compatible_pairs+=int(candidate.get("fully_compatible",False))
            for row in rows:
                if row["market_id"] in (candidate["kalshi_market_id"],candidate["polymarket_market_id"]):
                    other=candidate["polymarket_market_id"] if row["platform"]=="kalshi" else candidate["kalshi_market_id"]
                    row.update(candidate_pair=other,match_score=candidate["confidence"],fixture_match=True,outcome_match=True,core_resolution="COMPATIBLE" if candidate.get("core_compatible") else "INCOMPATIBLE",full_resolution="COMPATIBLE" if candidate.get("fully_compatible") else "UNVERIFIED",resolution_risk=candidate.get("resolution_risk"),research_pair=bool(candidate.get("core_compatible")),paper_eligible=bool(candidate.get("paper_eligible")),status="RESEARCH_PAIR" if candidate["resolution_compatible"] else "REJECTED",reject_reason=None if candidate["resolution_compatible"] else "Resolution mismatch")
        rejections={"team_mismatch":0,"date_mismatch":0,"market_type_mismatch":sum(x["normalization_result"]!="OK" for x in rows),"resolution_mismatch":sum(not x["resolution_compatible"] for x in candidates),"ambiguous":sum(x["normalization_result"]=="OK" and not x["candidate_pair"] for x in rows)}
        platforms={}
        for name in ("kalshi","polymarket"):
            scanned=[x for x in all_markets if x.platform.value==name]
            raw=sum(is_csl_like_market(x) for x in scanned);fixtures=sum(parse_csl_contract(x) is not None for x in scanned);compatible_markets=sum(is_semantically_compatible_csl(x) for x in scanned)
            platforms[name]={"markets_scanned":len(scanned),"football_markets":sum(is_football_market(x) for x in scanned),"csl_like_markets":compatible_markets,"raw_csl_like_markets":raw,"fixture_markets":fixtures,"semantically_compatible_markets":compatible_markets,**meta.get(name,{})}
        self.last_discovery=now
        fixture_keys={(parse_csl_contract(c["kalshi_market"]).home_team,parse_csl_contract(c["kalshi_market"]).away_team,parse_csl_contract(c["kalshi_market"]).match_date.date()) for c in candidates}
        self.discovery={"data_mode":self.runtime.settings.data_mode,"last_run":now,"kalshi":platforms["kalshi"],"polymarket":platforms["polymarket"],"candidate_fixtures":len(fixture_keys),"canonical_fixture_matches":len(fixture_keys),"core_compatible_outcome_pairs":compatible_pairs,"fully_compatible_outcome_pairs":fully_compatible_pairs,"resolution_compatible":compatible_pairs,"research_pairs":compatible_pairs,"recording_sessions":0,"rejections":rejections,"rows":rows,"collector_health":await self.repo.collector_health(self.runtime.settings.dynamic_book_poll_ms)}
        self.discovery_running=False
        return self.discovery

    def market(self,market_id):return self.discovery_markets.get(market_id) or self.runtime.cache.markets.get(market_id)

    async def sync_sessions(self):
        await self.refresh_discovery()
        for pair in await self.runtime.repository.load_matches():
            left=self.market(pair["kalshi_market_id"]);right=self.market(pair["polymarket_market_id"])
            if not left or not right:continue
            preliminary=match_session_payload(pair,left,right)
            if not preliminary:continue
            existing=await self.repo.session(preliminary["id"]);payload=match_session_payload(pair,left,right,existing)
            now=datetime.now(UTC);start=payload["scheduled_start"];end=start+timedelta(hours=self.runtime.settings.csl_recording_max_hours)
            should_record=payload["metadata"].get("research_eligible") and now>=start-timedelta(minutes=self.runtime.settings.csl_recording_prestart_minutes) and now<=end
            payload["metadata"]["recording_enabled"]=should_record
            if should_record and not (existing or {}).get("recording_started_at"):payload["recording_started_at"]=now
            if now>end:payload.update(recording_stopped_at=(existing or {}).get("recording_stopped_at") or now,stop_reason="scheduled_window_elapsed")
            await self.repo.upsert_session(payload)
        self.discovery["recording_sessions"]=sum(x["metadata"].get("recording_enabled",False) for x in await self.repo.sessions())

    async def record_cycle(self):
        await self.sync_sessions();await self.repo.expire_signals()
        for session in await self.repo.sessions():
            if not session["metadata"].get("recording_enabled"):continue
            for venue,outcomes in session["markets"].items():
                for outcome,market_id in outcomes.items():
                    market=self.market(market_id)
                    if not market:continue
                    try:
                        received=datetime.now(UTC);book=await self.runtime.connectors[market.platform].get_orderbook(market_id);await self.runtime.cache.update_orderbook(market_id,book,self.runtime.connectors[market.platform].raw_orderbooks.get(market_id))
                        bid,ask=(book.yes_bids[0] if book.yes_bids else None),(book.yes_asks[0] if book.yes_asks else None)
                        v=lambda size:calculate_vwap(book.yes_asks,size).vwap
                        tick={"match_session_id":session["id"],"venue":venue,"market_id":market_id,"outcome":outcome,"exchange_timestamp":None,"received_timestamp":received,"processed_at":datetime.now(UTC),"source_type":"polling","best_bid":bid.price if bid else None,"best_ask":ask.price if ask else None,"bid_size":bid.quantity if bid else None,"ask_size":ask.quantity if ask else None,"mid_price":((bid.price+ask.price)/2 if bid and ask else ask.price if ask else bid.price if bid else None),"vwap_5":v(5),"vwap_25":v(25),"vwap_100":v(100),"payload":{"book_timestamp":book.timestamp.isoformat(),"exchange_timestamp_available":False,"configured_poll_ms":self.runtime.settings.dynamic_book_poll_ms},"is_test":False}
                        saved=await self.repo.record_tick(tick,self.runtime.settings.dynamic_tick_min_change,self.runtime.settings.dynamic_snapshot_interval_ms)
                        if saved:
                            await self.repo.observe_follower_tick(saved)
                            history=await self.repo.ticks(session["id"],received-timedelta(milliseconds=self.runtime.settings.dynamic_signal_window_ms),outcome=outcome,limit=200)
                            signal=self.engine.detect(saved,history)
                            if signal:
                                signal["lag_quality"]=collector_lag_quality(["polling","polling"],False,self.runtime.settings.dynamic_book_poll_ms)
                                signal.setdefault("metadata",{})["quality_reason"]="Lead/Lag may include collector latency; both venues use REST polling."
                                await self.repo.save_signal(signal,self.latencies if session["metadata"].get("paper_execution_allowed") else [])
                    except Exception:continue
            await self.repo.update_markouts(session["id"])
        await self.execute_due()

    async def execute_due(self):
        for scenario in await self.repo.pending_scenarios():
            signal=next((x for x in await self.repo.signals(include_test=scenario["is_test"]) if x["id"]==scenario["signal_id"]),None)
            if not signal:continue
            session=await self.repo.session(signal["match_session_id"],include_test=scenario["is_test"])
            market_id=(session or {}).get("markets",{}).get(signal["follower_venue"],{}).get(signal["outcome"])
            book=self.runtime.cache.orderbooks.get(market_id) if market_id else None
            if not book and market_id:
                market=self.market(market_id)
                if market:book=await self.runtime.connectors[market.platform].get_orderbook(market_id)
            result=execute_dynamic_signal(signal,book,signal["follower_venue"],self.runtime.settings.paper_trade_size,self.runtime.settings.paper_slippage_buffer) if book else {"status":"FAILED","actual_vwap":None,"fill_size":0,"fill_ratio":0,"realized_entry_edge":None,"paper_pnl":None,"failure_reason":"No current follower order book"}
            await self.repo.complete_scenario(scenario["id"],result)

    async def overview(self):
        if self.runtime.settings.data_mode!="live":return {"research_focus":"CSL Dynamic Arbitrage Research","data_mode":self.runtime.settings.data_mode,"live_match":None,"prices":{},"active_signal":None,"paper":{"balance":self.runtime.settings.paper_starting_balance,"today_pnl":0,"trades":0},"signals_today":0}
        live=await self.repo.sessions(live_only=True);session=live[0] if live else None
        signals=await self.repo.signals(session["id"],active_only=True) if session else []
        prices={}
        if session:
            ticks=await self.repo.ticks(session["id"],datetime.now(UTC)-timedelta(minutes=5),limit=500)
            for tick in ticks:prices.setdefault(tick["venue"],{})[tick["outcome"]]=tick
        paper=await self.runtime.repository.paper_summary()
        return {"research_focus":"CSL Dynamic Arbitrage Research","data_mode":self.runtime.settings.data_mode,"live_match":session,"prices":prices,"active_signal":signals[0] if signals else None,"paper":{"balance":paper.get("account",{}).get("equity",self.runtime.settings.paper_starting_balance),"today_pnl":paper.get("account",{}).get("realized_pnl",0),"trades":paper.get("metrics",{}).get("attempted_trades",0)},"signals_today":(await self.repo.research_summary())["signals_today"],"discovery":self.discovery}
