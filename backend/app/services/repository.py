import hashlib
import json
from datetime import UTC, datetime

from sqlalchemy import delete, func, select

from app.db.base import Base
from app.db.session import SessionLocal, engine
from app.models import ArbitrageOpportunityRecord, ConnectorHealthRecord, MarketMatchRecord, MarketRecord, MarketSnapshotRecord, OpportunitySnapshotRecord, OrderBookSnapshotRecord, PaperAccountRecord, PaperBalanceSnapshotRecord, PaperOrderRecord, PaperPositionRecord, PaperTradeRecord, ResolutionEventRecord, WatchedMarketRecord
from app.models import DynamicExecutionScenarioRecord, DynamicSignalRecord, MarketPriceTickRecord, MatchSessionRecord
from app.schemas.domain import ConnectorHealth, NormalizedMarket, OrderBook


class Repository:
    def __init__(self, snapshot_min_seconds: float = 15, opportunity_snapshot_min_ms: int = 250):
        self.snapshot_min_seconds = snapshot_min_seconds
        self.opportunity_snapshot_min_seconds = opportunity_snapshot_min_ms/1000
        self.available = False
        self.last_error: str | None = None
        self._market_hashes: dict[str, str] = {}
        self._book_signatures: dict[str, tuple] = {}
        self._book_saved_at: dict[str, datetime] = {}

    async def initialize(self) -> None:
        try:
            async with engine.begin() as connection: await connection.run_sync(Base.metadata.create_all)
            self.available = True
        except Exception as exc:
            self.last_error = str(exc)[:300]
            self.available = False

    async def ensure_paper_account(self, starting_balance:float)->None:
        if not self.available:return
        async with SessionLocal() as session:
            if not await session.get(PaperAccountRecord,1):
                now=datetime.now(UTC);session.add(PaperAccountRecord(id=1,starting_balance=starting_balance,cash=starting_balance,reserved_capital=0,realized_pnl=0,created_at=now,updated_at=now,is_test=False))
            if not await session.get(PaperAccountRecord,2):
                now=datetime.now(UTC);session.add(PaperAccountRecord(id=2,starting_balance=1000,cash=1000,reserved_capital=0,realized_pnl=0,created_at=now,updated_at=now,is_test=True))
            await session.commit()

    async def save_markets(self, markets: list[NormalizedMarket]) -> None:
        if not self.available: return
        now = datetime.now(UTC)
        async with SessionLocal() as session:
            for market in markets:
                payload = market.model_dump(mode="json")
                digest = hashlib.sha256(json.dumps(payload, sort_keys=True).encode()).hexdigest()
                record = await session.get(MarketRecord, market.id)
                if record:
                    record.title, record.status, record.payload, record.updated_at = market.title, market.status, payload, now
                else:
                    session.add(MarketRecord(id=market.id, platform=market.platform.value, external_id=market.external_id, title=market.title, status=market.status, source=market.source, payload=payload, updated_at=now))
                if self._market_hashes.get(market.id) != digest:
                    session.add(MarketSnapshotRecord(market_id=market.id, source=market.source, payload=payload, captured_at=now))
                    self._market_hashes[market.id] = digest
            await session.commit()

    async def save_orderbook(self, book: OrderBook) -> None:
        if not self.available: return
        now = datetime.now(UTC)
        best = lambda levels: levels[0].price if levels else None
        signature = (best(book.yes_bids), best(book.yes_asks), best(book.no_bids), best(book.no_asks))
        last = self._book_saved_at.get(book.market_id)
        if self._book_signatures.get(book.market_id) == signature and last and (now-last).total_seconds() < self.snapshot_min_seconds: return
        async with SessionLocal() as session:
            session.add(OrderBookSnapshotRecord(market_id=book.market_id, source=book.source, best_yes_bid=signature[0], best_yes_ask=signature[1], best_no_bid=signature[2], best_no_ask=signature[3], payload=book.model_dump(mode="json"), captured_at=now))
            await session.commit()
        self._book_signatures[book.market_id], self._book_saved_at[book.market_id] = signature, now

    async def set_watched(self, market_id: str, watched: bool) -> None:
        if not self.available: return
        async with SessionLocal() as session:
            record = await session.get(WatchedMarketRecord, market_id)
            if watched and not record: session.add(WatchedMarketRecord(market_id=market_id, created_at=datetime.now(UTC)))
            elif not watched and record: await session.delete(record)
            await session.commit()

    async def load_watched(self) -> list[str]:
        if not self.available: return []
        async with SessionLocal() as session:
            return list((await session.scalars(select(WatchedMarketRecord.market_id))).all())

    async def save_health(self, health: ConnectorHealth) -> None:
        if not self.available: return
        async with SessionLocal() as session:
            record = await session.get(ConnectorHealthRecord, health.platform.value)
            payload = health.model_dump(mode="json")
            if record: record.connected, record.payload, record.updated_at = health.connected, payload, datetime.now(UTC)
            else: session.add(ConnectorHealthRecord(platform=health.platform.value, connected=health.connected, payload=payload, updated_at=datetime.now(UTC)))
            await session.commit()

    async def save_matches(self, candidates: list[dict]) -> None:
        if not self.available: return
        now=datetime.now(UTC)
        async with SessionLocal() as session:
            for candidate in candidates:
                payload={k:(v.model_dump(mode="json") if hasattr(v,"model_dump") else v.value if hasattr(v,"value") else v) for k,v in candidate.items()}
                record=await session.get(MarketMatchRecord,candidate["id"])
                if record:
                    # Human decisions are durable across matcher cycles.
                    payload["status"]=record.status
                    record.confidence,record.payload,record.updated_at=candidate["confidence"],payload,now
                else:
                    session.add(MarketMatchRecord(id=candidate["id"],kalshi_market_id=candidate["kalshi_market_id"],polymarket_market_id=candidate["polymarket_market_id"],status="needs_review",confidence=candidate["confidence"],payload=payload,source="live",created_at=now,updated_at=now))
            await session.commit()

    async def load_matches(self, status: str | None = None) -> list[dict]:
        if not self.available:return []
        async with SessionLocal() as session:
            query=select(MarketMatchRecord).where(MarketMatchRecord.is_test.is_(False))
            if status:query=query.where(MarketMatchRecord.status==status)
            records=list((await session.scalars(query.order_by(MarketMatchRecord.confidence.desc()))).all())
            return [{**r.payload,"status":r.status} for r in records]

    async def set_match_status(self, match_id: str, status: str) -> dict | None:
        if not self.available:return None
        async with SessionLocal() as session:
            record=await session.get(MarketMatchRecord,match_id)
            if not record:return None
            record.status=status; record.updated_at=datetime.now(UTC); await session.commit()
            return {**record.payload,"status":record.status}

    async def upsert_opportunity(self, pair_id:str, direction:str, payload:dict, active:bool) -> dict:
        now=datetime.now(UTC)
        async with SessionLocal() as session:
            record=await session.scalar(select(ArbitrageOpportunityRecord).where(ArbitrageOpportunityRecord.pair_id==pair_id,ArbitrageOpportunityRecord.direction==direction).order_by(ArbitrageOpportunityRecord.lifecycle.desc()).limit(1))
            if record and record.status=="live" and active:
                record.last_seen=now; record.current_edge=payload["net_edge"]; record.best_edge=max(record.best_edge,payload["net_edge"]); record.worst_edge=min(record.worst_edge,payload["net_edge"]); record.payload={**record.payload,**payload,"id":record.id,"first_seen":record.first_seen.isoformat(),"last_seen":now.isoformat(),"best_edge":record.best_edge,"worst_edge":record.worst_edge,"live":True}
            elif record and record.status=="live" and not active:
                record.status="closed"; record.last_seen=now; record.payload={**record.payload,"last_seen":now.isoformat(),"live":False,"status":"closed"}
            elif active:
                lifecycle=(record.lifecycle+1) if record else 1; oid=f"{pair_id}:{direction}:{lifecycle}"
                full={**payload,"id":oid,"first_seen":now.isoformat(),"last_seen":now.isoformat(),"best_edge":payload["net_edge"],"worst_edge":payload["net_edge"],"live":True}
                record=ArbitrageOpportunityRecord(id=oid,pair_id=pair_id,direction=direction,lifecycle=lifecycle,status="live",source=payload.get("source","live"),first_seen=now,last_seen=now,current_edge=payload["net_edge"],best_edge=payload["net_edge"],worst_edge=payload["net_edge"],payload=full,is_test=bool(payload.get("is_test")));session.add(record)
            if record:await session.commit();return record.payload
            return payload

    async def save_opportunity_snapshot(self, opportunity:dict) -> None:
        if not self.available or not opportunity.get("id") or not opportunity.get("live"):return
        async with SessionLocal() as session:
            last=await session.scalar(select(OpportunitySnapshotRecord).where(OpportunitySnapshotRecord.opportunity_id==opportunity["id"]).order_by(OpportunitySnapshotRecord.timestamp.desc()).limit(1))
            now=datetime.now(UTC); min_seconds=self.opportunity_snapshot_min_seconds
            changed=not last or abs(last.net_edge-opportunity["net_edge"])>=.0005 or abs(last.available_liquidity-opportunity["available_size"])>=1
            if last and not changed and (now-last.timestamp).total_seconds()<min_seconds:return
            session.add(OpportunitySnapshotRecord(opportunity_id=opportunity["id"],timestamp=now,leg_a_price=opportunity["kalshi_vwap"],leg_b_price=opportunity["polymarket_vwap"],gross_edge=opportunity["gross_edge"],net_edge=opportunity["net_edge"],available_liquidity=opportunity["available_size"],payload=opportunity,is_test=bool(opportunity.get("is_test"))));await session.commit()

    async def load_opportunities(self, live_only:bool=False)->list[dict]:
        if not self.available:return []
        async with SessionLocal() as session:
            q=select(ArbitrageOpportunityRecord).where(ArbitrageOpportunityRecord.is_test.is_(False))
            if live_only:q=q.where(ArbitrageOpportunityRecord.status=="live")
            rows=list((await session.scalars(q.order_by(ArbitrageOpportunityRecord.last_seen.desc()).limit(500))).all())
            result=[]
            for r in rows:
                p={**r.payload,"live":r.status=="live","first_seen":r.first_seen.isoformat(),"last_seen":r.last_seen.isoformat(),"best_edge":r.best_edge,"worst_edge":r.worst_edge,"duration_seconds":(r.last_seen-r.first_seen).total_seconds()};result.append(p)
            return result

    async def load_opportunity(self, opportunity_id:str)->dict|None:
        if not self.available:return None
        async with SessionLocal() as session:
            r=await session.get(ArbitrageOpportunityRecord,opportunity_id)
            if not r:return None
            snaps=list((await session.scalars(select(OpportunitySnapshotRecord).where(OpportunitySnapshotRecord.opportunity_id==opportunity_id).order_by(OpportunitySnapshotRecord.timestamp))).all())
            return {**r.payload,"live":r.status=="live","duration_seconds":(r.last_seen-r.first_seen).total_seconds(),"history":[{"time":s.timestamp.isoformat(),"edge":s.net_edge} for s in snaps]}

    async def has_paper_trade(self,opportunity_id:str)->bool:
        if not self.available:return False
        async with SessionLocal() as session:return await session.scalar(select(PaperTradeRecord.id).where(PaperTradeRecord.opportunity_id==opportunity_id)) is not None

    async def create_paper_execution(self,opportunity:dict,result:dict)->dict|None:
        if not self.available:return None
        now=datetime.now(UTC);trade_id=f"paper:{opportunity['id']}"
        async with SessionLocal() as session:
            if await session.get(PaperTradeRecord,trade_id):return None
            is_test=bool(opportunity.get("is_test"));account=await session.get(PaperAccountRecord,2 if is_test else 1,with_for_update=True)
            capital=result["actual_capital_used"]
            status=result["status"]
            if not account or (status=="DUAL_FILLED" and account.cash<capital):status="FAILED";result={**result,"status":status,"failure_reason":"insufficient paper cash"}
            trade_payload={**result,"id":trade_id,"opportunity_id":opportunity["id"],"event":opportunity["event"],"expected_edge":opportunity["net_edge"],"data_source":"live","execution_mode":"paper","created_at":now.isoformat()}
            session.add(PaperTradeRecord(id=trade_id,opportunity_id=opportunity["id"],status=status,source="live",payload=trade_payload,created_at=now,updated_at=now,is_test=is_test))
            for leg in result["orders"]:session.add(PaperOrderRecord(id=f"{trade_id}:{leg['platform']}",trade_id=trade_id,platform=leg["platform"],market_id=leg["market_id"],side=leg["side"],status=leg["status"],payload=leg,execution_time=now,is_test=is_test))
            if status=="DUAL_FILLED" and account:
                account.cash-=capital;account.reserved_capital+=capital;account.updated_at=now
                position={"id":f"position:{trade_id}","trade_id":trade_id,"event":opportunity["event"],"capital_locked":capital,"expected_profit":result["expected_profit"],"status":"OPEN","opened_at":now.isoformat(),"kalshi_market_id":opportunity["kalshi_market_id"],"polymarket_market_id":opportunity["polymarket_market_id"],"direction":opportunity["direction"]}
                session.add(PaperPositionRecord(id=position["id"],trade_id=trade_id,status="OPEN",payload=position,opened_at=now,settled_at=None,is_test=is_test))
                equity=account.cash+account.reserved_capital
                session.add(PaperBalanceSnapshotRecord(timestamp=now,cash=account.cash,reserved_capital=account.reserved_capital,equity=equity,realized_pnl=account.realized_pnl,is_test=is_test))
            await session.commit();return trade_payload

    async def paper_summary(self)->dict:
        if not self.available:return {}
        async with SessionLocal() as session:
            account=await session.get(PaperAccountRecord,1);trades=list((await session.scalars(select(PaperTradeRecord).where(PaperTradeRecord.is_test.is_(False)).order_by(PaperTradeRecord.created_at.desc()).limit(200))).all());positions=list((await session.scalars(select(PaperPositionRecord).where(PaperPositionRecord.is_test.is_(False)).order_by(PaperPositionRecord.opened_at.desc()).limit(200))).all())
            trade_payloads=[{**t.payload,"status":t.status} for t in trades];position_payloads=[{**p.payload,"status":p.status} for p in positions]
            if not account:return {}
            equity=account.cash+account.reserved_capital
            dual=sum(t.status=="DUAL_FILLED" for t in trades)
            realized=[t.payload.get("realized_profit") for t in trades if t.payload.get("realized_profit") is not None]
            return {"account":{"starting_balance":account.starting_balance,"cash":account.cash,"reserved_capital":account.reserved_capital,"open_position_value":account.reserved_capital,"realized_pnl":account.realized_pnl,"unrealized_pnl":0,"equity":equity,"roi":(equity-account.starting_balance)/account.starting_balance},"metrics":{"attempted_trades":len(trades),"dual_fill_rate":dual/len(trades) if trades else 0,"profitable_rate":sum(x>0 for x in realized)/len(realized) if realized else 0,"avg_realized_edge":sum(t.payload.get("realized_entry_edge",0) for t in trades)/len(trades) if trades else 0},"positions":position_payloads,"trades":trade_payloads}

    async def research_stats(self)->dict:
        if not self.available:return {}
        async with SessionLocal() as session:
            count=lambda model:select(func.count()).select_from(model)
            candidates=await session.scalar(count(MarketMatchRecord).where(MarketMatchRecord.is_test.is_(False)));approved=await session.scalar(count(MarketMatchRecord).where(MarketMatchRecord.status=="approved",MarketMatchRecord.is_test.is_(False)));opportunities=await session.scalar(count(ArbitrageOpportunityRecord).where(ArbitrageOpportunityRecord.is_test.is_(False)));live=await session.scalar(count(ArbitrageOpportunityRecord).where(ArbitrageOpportunityRecord.status=="live",ArbitrageOpportunityRecord.is_test.is_(False)));snapshots=await session.scalar(count(OpportunitySnapshotRecord).where(OpportunitySnapshotRecord.is_test.is_(False)));trades=await session.scalar(count(PaperTradeRecord).where(PaperTradeRecord.is_test.is_(False)));dual=await session.scalar(count(PaperTradeRecord).where(PaperTradeRecord.status=="DUAL_FILLED",PaperTradeRecord.is_test.is_(False)));failed=await session.scalar(count(PaperTradeRecord).where(PaperTradeRecord.status.in_(["FAILED","PARTIAL_FILL","SINGLE_LEG"]),PaperTradeRecord.is_test.is_(False)));positions=await session.scalar(count(PaperPositionRecord).where(PaperPositionRecord.status=="OPEN",PaperPositionRecord.is_test.is_(False)));settled=await session.scalar(count(PaperPositionRecord).where(PaperPositionRecord.status=="SETTLED",PaperPositionRecord.is_test.is_(False)))
            return {"candidates":candidates or 0,"approved_pairs":approved or 0,"opportunities":opportunities or 0,"live_opportunities":live or 0,"opportunity_snapshots":snapshots or 0,"paper_trades":trades or 0,"dual_filled":dual or 0,"failed":failed or 0,"open_positions":positions or 0,"settled":settled or 0}

    async def open_positions(self)->list[dict]:
        if not self.available:return []
        async with SessionLocal() as session:
            rows=list((await session.scalars(select(PaperPositionRecord).where(PaperPositionRecord.status.in_(["OPEN","RESOLUTION_REVIEW"]),PaperPositionRecord.is_test.is_(False)))).all());return [{**r.payload,"status":r.status} for r in rows]

    async def record_resolution(self,position:dict,kalshi_outcome:str|None,polymarket_outcome:str|None)->None:
        if not self.available:return
        now=datetime.now(UTC)
        async with SessionLocal() as session:
            record=await session.get(PaperPositionRecord,position["id"]);trade=await session.get(PaperTradeRecord,position["trade_id"])
            if not record or record.status=="SETTLED" or not trade:return
            account=await session.get(PaperAccountRecord,2 if record.is_test else 1,with_for_update=True)
            if not account:return
            session.add(ResolutionEventRecord(position_id=record.id,platform="combined",outcome=kalshi_outcome if kalshi_outcome==polymarket_outcome else None,status="CONFIRMED" if kalshi_outcome and kalshi_outcome==polymarket_outcome else "RESOLUTION_MISMATCH",payload={"kalshi":kalshi_outcome,"polymarket":polymarket_outcome},observed_at=now,is_test=record.is_test))
            if not kalshi_outcome or kalshi_outcome!=polymarket_outcome:
                record.status="RESOLUTION_REVIEW";record.payload={**record.payload,"status":"RESOLUTION_REVIEW","resolution":{"kalshi":kalshi_outcome,"polymarket":polymarket_outcome}};await session.commit();return
            orders=trade.payload["orders"];payout=sum(o["filled_size"] for o in orders if o["side"]==kalshi_outcome);capital=trade.payload["actual_capital_used"];profit=payout-capital
            record.status="SETTLED";record.settled_at=now;record.payload={**record.payload,"status":"SETTLED","settled_at":now.isoformat(),"outcome":kalshi_outcome,"actual_payout":payout,"realized_profit":profit}
            trade.status="SETTLED";trade.updated_at=now;trade.payload={**trade.payload,"status":"SETTLED","realized_profit":profit,"settled_at":now.isoformat()}
            account.reserved_capital=max(0,account.reserved_capital-capital);account.cash+=payout;account.realized_pnl+=profit;account.updated_at=now
            session.add(PaperBalanceSnapshotRecord(timestamp=now,cash=account.cash,reserved_capital=account.reserved_capital,equity=account.cash+account.reserved_capital,realized_pnl=account.realized_pnl,is_test=record.is_test));await session.commit()

    async def create_test_pair(self,payload:dict)->dict:
        now=datetime.now(UTC);pair_id=payload["id"]
        async with SessionLocal() as session:
            record=await session.get(MarketMatchRecord,pair_id)
            if not record:
                record=MarketMatchRecord(id=pair_id,kalshi_market_id=payload["kalshi_market_id"],polymarket_market_id=payload["polymarket_market_id"],status="test_approved",confidence=payload["confidence"],payload=payload,source="live",created_at=now,updated_at=now,is_test=True,approval_source="test");session.add(record)
            await session.commit();return {**record.payload,"status":"test_approved","is_test":True,"approval_source":"test"}

    async def load_test_pairs(self)->list[dict]:
        async with SessionLocal() as session:
            rows=list((await session.scalars(select(MarketMatchRecord).where(MarketMatchRecord.is_test.is_(True)).order_by(MarketMatchRecord.updated_at.desc()))).all());return [{**r.payload,"status":r.status,"is_test":True,"approval_source":r.approval_source} for r in rows]

    async def test_verification(self,ids:dict|None=None)->dict:
        ids=ids or {}
        async with SessionLocal() as session:
            account=await session.get(PaperAccountRecord,2)
            pair=await session.get(MarketMatchRecord,ids.get("pair_id")) if ids.get("pair_id") else None
            opp=await session.get(ArbitrageOpportunityRecord,ids.get("opportunity_id")) if ids.get("opportunity_id") else None
            trade=await session.get(PaperTradeRecord,ids.get("paper_trade_id")) if ids.get("paper_trade_id") else None
            orders=list((await session.scalars(select(PaperOrderRecord).where(PaperOrderRecord.trade_id==ids.get("paper_trade_id"),PaperOrderRecord.is_test.is_(True)))).all()) if ids.get("paper_trade_id") else []
            position=await session.scalar(select(PaperPositionRecord).where(PaperPositionRecord.trade_id==ids.get("paper_trade_id"),PaperPositionRecord.is_test.is_(True))) if ids.get("paper_trade_id") else None
            snaps=await session.scalar(select(func.count()).select_from(OpportunitySnapshotRecord).where(OpportunitySnapshotRecord.opportunity_id==ids.get("opportunity_id"),OpportunitySnapshotRecord.is_test.is_(True))) if ids.get("opportunity_id") else 0
            total_pairs=await session.scalar(select(func.count()).select_from(MarketMatchRecord).where(MarketMatchRecord.is_test.is_(True)))
            test_pairs=list((await session.scalars(select(MarketMatchRecord).where(MarketMatchRecord.is_test.is_(True)))).all())
            metrics={"manual_test_pairs":len(test_pairs),"top_10_hits":sum(bool((r.payload or {}).get("top_10_hit")) for r in test_pairs),"candidate_hits":sum(bool((r.payload or {}).get("candidate_hit")) for r in test_pairs),"false_positives":sum((r.payload or {}).get("manual_label")=="incorrect" for r in test_pairs)}
            return {"test_pair_saved":bool(pair and pair.is_test),"opportunity_saved":bool(opp and opp.is_test),"snapshot_saved":bool(snaps),"paper_orders":len(orders),"paper_trade":int(bool(trade and trade.is_test)),"paper_position":int(bool(position and position.is_test)),"account_updated":bool(account),"test_account":{"starting_balance":account.starting_balance,"cash":account.cash,"reserved_capital":account.reserved_capital,"equity":account.cash+account.reserved_capital} if account else None,"manual_test_pairs":total_pairs or 0,"matcher_metrics":metrics,"ids":{**ids,"position_id":position.id if position else None}}

    async def clear_test_data(self)->dict:
        async with SessionLocal() as session:
            counts={}
            for name,model in [("dynamic_scenarios",DynamicExecutionScenarioRecord),("dynamic_signals",DynamicSignalRecord),("price_ticks",MarketPriceTickRecord),("match_sessions",MatchSessionRecord),("resolution_events",ResolutionEventRecord),("balance_snapshots",PaperBalanceSnapshotRecord),("positions",PaperPositionRecord),("orders",PaperOrderRecord),("trades",PaperTradeRecord),("snapshots",OpportunitySnapshotRecord),("opportunities",ArbitrageOpportunityRecord),("pairs",MarketMatchRecord)]:
                result=await session.execute(delete(model).where(model.is_test.is_(True)));counts[name]=result.rowcount or 0
            account=await session.get(PaperAccountRecord,2)
            if account:account.cash=account.starting_balance;account.reserved_capital=0;account.realized_pnl=0;account.updated_at=datetime.now(UTC)
            await session.commit();return counts
