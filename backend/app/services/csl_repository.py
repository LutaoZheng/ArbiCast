from datetime import UTC, datetime, timedelta

from sqlalchemy import delete, func, select, update

from app.db.session import SessionLocal
from app.models import DynamicExecutionScenarioRecord, DynamicSignalRecord, MarketPriceTickRecord, MatchSessionRecord


def _session(row):
    return {"id":row.id,"league":row.league,"season":row.season,"home_team":row.home_team,"away_team":row.away_team,"scheduled_start":row.scheduled_start,"actual_start":row.actual_start,"status":row.status,"match_minute":row.match_minute,"match_second":row.match_second,"home_score":row.home_score,"away_score":row.away_score,"pair_id":row.pair_id,"markets":row.markets,"metadata":row.metadata_json,"is_test":row.is_test,"created_at":row.created_at,"updated_at":row.updated_at,"recording_started_at":row.recording_started_at,"recording_stopped_at":row.recording_stopped_at,"stop_reason":row.stop_reason}

def _tick(row):
    return {"id":row.id,"match_session_id":row.match_session_id,"venue":row.venue,"market_id":row.market_id,"outcome":row.outcome,"exchange_timestamp":row.exchange_timestamp,"received_timestamp":row.received_timestamp,"stored_timestamp":row.stored_timestamp,"processed_at":row.processed_at,"source_type":row.source_type,"best_bid":row.best_bid,"best_ask":row.best_ask,"bid_size":row.bid_size,"ask_size":row.ask_size,"mid_price":row.mid_price,"vwap_5":row.vwap_5,"vwap_25":row.vwap_25,"vwap_100":row.vwap_100,"book_sequence":row.book_sequence,"is_test":row.is_test}

def should_persist_tick(last:dict|None,tick:dict,min_change:float,snapshot_interval_ms:int)->bool:
    if not last:return True
    values=(tick.get("best_bid"),tick.get("best_ask"),tick.get("bid_size"),tick.get("ask_size"));old=(last.get("best_bid"),last.get("best_ask"),last.get("bid_size"),last.get("ask_size"))
    price_change=max(abs((a or 0)-(b or 0)) for a,b in zip(values[:2],old[:2]));age=(tick["received_timestamp"]-last["received_timestamp"]).total_seconds()*1000
    return price_change>=min_change or values!=old or age>=snapshot_interval_ms

class CSLRepository:
    async def upsert_session(self,payload:dict)->dict:
        now=datetime.now(UTC)
        async with SessionLocal() as db:
            row=await db.get(MatchSessionRecord,payload["id"])
            if not row:
                row=MatchSessionRecord(id=payload["id"],league="CSL",season=payload["season"],home_team=payload["home_team"],away_team=payload["away_team"],scheduled_start=payload["scheduled_start"],actual_start=payload.get("actual_start"),status=payload.get("status","PRE_MATCH"),match_minute=None,match_second=None,home_score=None,away_score=None,pair_id=payload.get("pair_id"),markets=payload.get("markets",{}),metadata_json=payload.get("metadata",{}),is_test=payload.get("is_test",False),created_at=now,updated_at=now,recording_started_at=payload.get("recording_started_at"),recording_stopped_at=payload.get("recording_stopped_at"),stop_reason=payload.get("stop_reason"));db.add(row)
            else:
                row.markets=payload.get("markets",row.markets);row.pair_id=payload.get("pair_id",row.pair_id);row.status=payload.get("status",row.status);row.metadata_json={**row.metadata_json,**payload.get("metadata",{})};row.recording_started_at=payload.get("recording_started_at",row.recording_started_at);row.recording_stopped_at=payload.get("recording_stopped_at",row.recording_stopped_at);row.stop_reason=payload.get("stop_reason",row.stop_reason);row.updated_at=now
            await db.commit();return _session(row)

    async def sessions(self,live_only=False,include_test=False)->list[dict]:
        async with SessionLocal() as db:
            q=select(MatchSessionRecord)
            if live_only:q=q.where(MatchSessionRecord.status.in_(["LIVE","HALFTIME"]))
            if not include_test:q=q.where(MatchSessionRecord.is_test.is_(False))
            rows=list((await db.scalars(q.order_by(MatchSessionRecord.scheduled_start.desc()).limit(100))).all());return [_session(x) for x in rows]

    async def session(self,session_id:str,include_test=False)->dict|None:
        async with SessionLocal() as db:
            row=await db.get(MatchSessionRecord,session_id)
            return _session(row) if row and (include_test or not row.is_test) else None

    async def record_tick(self,tick:dict,min_change:float,snapshot_interval_ms:int)->dict|None:
        async with SessionLocal() as db:
            last=await db.scalar(select(MarketPriceTickRecord).where(MarketPriceTickRecord.match_session_id==tick["match_session_id"],MarketPriceTickRecord.venue==tick["venue"],MarketPriceTickRecord.outcome==tick["outcome"],MarketPriceTickRecord.is_test==tick.get("is_test",False)).order_by(MarketPriceTickRecord.received_timestamp.desc()).limit(1))
            last_tick={"best_bid":last.best_bid,"best_ask":last.best_ask,"bid_size":last.bid_size,"ask_size":last.ask_size,"received_timestamp":last.received_timestamp} if last else None
            if not should_persist_tick(last_tick,tick,min_change,snapshot_interval_ms):return None
            processed=datetime.now(UTC);row=MarketPriceTickRecord(match_session_id=tick["match_session_id"],venue=tick["venue"],market_id=tick["market_id"],outcome=tick["outcome"],exchange_timestamp=tick.get("exchange_timestamp"),received_timestamp=tick["received_timestamp"],stored_timestamp=processed,processed_at=tick.get("processed_at",processed),source_type=tick.get("source_type","polling"),best_bid=tick.get("best_bid"),best_ask=tick.get("best_ask"),bid_size=tick.get("bid_size"),ask_size=tick.get("ask_size"),mid_price=tick.get("mid_price"),vwap_5=tick.get("vwap_5"),vwap_25=tick.get("vwap_25"),vwap_100=tick.get("vwap_100"),book_sequence=tick.get("book_sequence"),payload=tick.get("payload",{}),is_test=tick.get("is_test",False));db.add(row);await db.commit();return _tick(row)

    async def ticks(self,session_id:str,since:datetime|None=None,until:datetime|None=None,outcome:str|None=None,limit:int=2000,include_test=False)->list[dict]:
        async with SessionLocal() as db:
            q=select(MarketPriceTickRecord).where(MarketPriceTickRecord.match_session_id==session_id)
            if since:q=q.where(MarketPriceTickRecord.received_timestamp>=since)
            if until:q=q.where(MarketPriceTickRecord.received_timestamp<=until)
            if outcome:q=q.where(MarketPriceTickRecord.outcome==outcome)
            if not include_test:q=q.where(MarketPriceTickRecord.is_test.is_(False))
            rows=list((await db.scalars(q.order_by(MarketPriceTickRecord.received_timestamp.desc()).limit(min(limit,5000)))).all());return [_tick(x) for x in reversed(rows)]

    async def save_signal(self,signal:dict,latencies:list[int])->dict:
        async with SessionLocal() as db:
            row=await db.get(DynamicSignalRecord,signal["id"])
            if row:return row.payload
            row=DynamicSignalRecord(id=signal["id"],match_session_id=signal["match_session_id"],outcome=signal["outcome"],strategy_type=signal["strategy_type"],leader_venue=signal["leader_venue"],follower_venue=signal["follower_venue"],signal_started_at=signal["signal_started_at"],detected_at=signal["detected_at"],expires_at=signal["expires_at"],status=signal["status"],estimated_net_edge=signal["estimated_net_edge"],lag_quality=signal.get("lag_quality","LOW"),payload=signal,is_test=signal.get("is_test",False));db.add(row)
            for latency in latencies:
                sid=f"{signal['id']}:{latency}";execute_at=signal["detected_at"]+timedelta(milliseconds=latency);payload={"signal_id":signal["id"],"latency_ms":latency,"intended_price":signal["follower_price_at_signal"],"markouts":{},"strategy_type":"DYNAMIC_LEAD_LAG"}
                db.add(DynamicExecutionScenarioRecord(id=sid,signal_id=signal["id"],strategy_type="DYNAMIC_LEAD_LAG",latency_ms=latency,execute_at=execute_at,status="PENDING",actual_vwap=None,fill_size=0,fill_ratio=0,realized_entry_edge=None,paper_pnl=None,payload=payload,is_test=signal.get("is_test",False),created_at=signal["detected_at"],updated_at=signal["detected_at"]))
            await db.commit();return signal

    async def signals(self,session_id:str|None=None,active_only=False,include_test=False,limit=500)->list[dict]:
        async with SessionLocal() as db:
            q=select(DynamicSignalRecord)
            if session_id:q=q.where(DynamicSignalRecord.match_session_id==session_id)
            if active_only:q=q.where(DynamicSignalRecord.status=="OPEN",DynamicSignalRecord.expires_at>datetime.now(UTC))
            if not include_test:q=q.where(DynamicSignalRecord.is_test.is_(False))
            rows=list((await db.scalars(q.order_by(DynamicSignalRecord.detected_at.desc()).limit(limit))).all());return [{**x.payload,"status":x.status} for x in rows]

    async def expire_signals(self)->int:
        async with SessionLocal() as db:
            result=await db.execute(update(DynamicSignalRecord).where(DynamicSignalRecord.status=="OPEN",DynamicSignalRecord.expires_at<=datetime.now(UTC)).values(status="EXPIRED"));await db.commit();return result.rowcount or 0

    async def observe_follower_tick(self,tick:dict)->None:
        if tick.get("mid_price") is None:return
        async with SessionLocal() as db:
            rows=list((await db.scalars(select(DynamicSignalRecord).where(DynamicSignalRecord.match_session_id==tick["match_session_id"],DynamicSignalRecord.outcome==tick["outcome"],DynamicSignalRecord.follower_venue==tick["venue"],DynamicSignalRecord.status=="OPEN",DynamicSignalRecord.expires_at>=tick["received_timestamp"]))).all())
            for row in rows:
                payload=dict(row.payload);metadata=dict(payload.get("metadata",{}))
                if metadata.get("observed_lag_ms") is not None:continue
                follower_move=tick["mid_price"]-payload["follower_price_at_signal"];leader_move=payload["leader_move_cents"]/100
                if follower_move*leader_move>0 and abs(follower_move)>=abs(leader_move)*.5:
                    metadata["observed_lag_ms"]=max(0,(tick["received_timestamp"]-payload["signal_started_at"]).total_seconds()*1000);metadata["follower_price_after"]=tick["mid_price"];payload["metadata"]=metadata;row.payload=payload
            await db.commit()

    async def pending_scenarios(self)->list[dict]:
        async with SessionLocal() as db:
            rows=list((await db.scalars(select(DynamicExecutionScenarioRecord).where(DynamicExecutionScenarioRecord.status=="PENDING",DynamicExecutionScenarioRecord.execute_at<=datetime.now(UTC)).order_by(DynamicExecutionScenarioRecord.execute_at).limit(100))).all())
            return [{"id":x.id,"signal_id":x.signal_id,"latency_ms":x.latency_ms,"is_test":x.is_test,**x.payload} for x in rows]

    async def complete_scenario(self,scenario_id:str,result:dict)->None:
        async with SessionLocal() as db:
            row=await db.get(DynamicExecutionScenarioRecord,scenario_id)
            if not row:return
            row.status=result["status"];row.actual_vwap=result.get("actual_vwap");row.fill_size=result["fill_size"];row.fill_ratio=result["fill_ratio"];row.realized_entry_edge=result.get("realized_entry_edge");row.paper_pnl=result.get("paper_pnl");row.payload={**row.payload,**result};row.updated_at=datetime.now(UTC);await db.commit()

    async def update_markouts(self,session_id:str)->None:
        horizons=(250,500,1000,2000,5000)
        async with SessionLocal() as db:
            scenarios=list((await db.scalars(select(DynamicExecutionScenarioRecord).where(DynamicExecutionScenarioRecord.status!="PENDING",DynamicExecutionScenarioRecord.actual_vwap.is_not(None)).order_by(DynamicExecutionScenarioRecord.execute_at.desc()).limit(500))).all())
            for scenario in scenarios:
                signal=await db.get(DynamicSignalRecord,scenario.signal_id)
                if not signal or signal.match_session_id!=session_id:continue
                payload=dict(scenario.payload);markouts=dict(payload.get("markouts",{}));changed=False
                for horizon in horizons:
                    key=f"{horizon}ms"
                    if key in markouts:continue
                    target=scenario.execute_at+timedelta(milliseconds=horizon)
                    tick=await db.scalar(select(MarketPriceTickRecord).where(MarketPriceTickRecord.match_session_id==session_id,MarketPriceTickRecord.venue==signal.follower_venue,MarketPriceTickRecord.outcome==signal.outcome,MarketPriceTickRecord.received_timestamp>=target,MarketPriceTickRecord.is_test==scenario.is_test).order_by(MarketPriceTickRecord.received_timestamp).limit(1))
                    if tick and tick.mid_price is not None:
                        direction=1 if signal.payload["expected_direction"]=="UP" else -1;markouts[key]=(tick.mid_price-scenario.actual_vwap)*direction;changed=True
                if changed:payload["markouts"]=markouts;scenario.payload=payload;scenario.updated_at=datetime.now(UTC)
            await db.commit()

    async def research_summary(self)->dict:
        async with SessionLocal() as db:
            count=lambda model:select(func.count()).select_from(model)
            matches=await db.scalar(count(MatchSessionRecord).where(MatchSessionRecord.is_test.is_(False))) or 0
            ticks=await db.scalar(count(MarketPriceTickRecord).where(MarketPriceTickRecord.is_test.is_(False))) or 0
            signals=await db.scalar(count(DynamicSignalRecord).where(DynamicSignalRecord.is_test.is_(False))) or 0
            today=datetime.now(UTC).replace(hour=0,minute=0,second=0,microsecond=0)
            signals_today=await db.scalar(count(DynamicSignalRecord).where(DynamicSignalRecord.is_test.is_(False),DynamicSignalRecord.detected_at>=today)) or 0
            executions=await db.scalar(count(DynamicExecutionScenarioRecord).where(DynamicExecutionScenarioRecord.is_test.is_(False),DynamicExecutionScenarioRecord.status!="PENDING")) or 0
            rows=list((await db.scalars(select(DynamicExecutionScenarioRecord).where(DynamicExecutionScenarioRecord.is_test.is_(False),DynamicExecutionScenarioRecord.status!="PENDING"))).all())
            latency={}
            for ms in (100,250,500,750,1000,2000,3000):
                group=[x for x in rows if x.latency_ms==ms];filled=[x for x in group if x.fill_size>0]
                latency[str(ms)]={"attempts":len(group),"fill_rate":len(filled)/len(group) if group else None,"average_net_edge":sum(x.realized_entry_edge or 0 for x in filled)/len(filled) if filled else None,"average_pnl":sum(x.paper_pnl or 0 for x in filled)/len(filled) if filled else None,"win_rate":sum((x.paper_pnl or 0)>0 for x in filled)/len(filled) if filled else None}
            signal_rows=list((await db.scalars(select(DynamicSignalRecord).where(DynamicSignalRecord.is_test.is_(False)))).all())
            def lags(leader):return [x.payload.get("metadata",{}).get("observed_lag_ms") for x in signal_rows if x.leader_venue==leader and x.payload.get("metadata",{}).get("observed_lag_ms") is not None]
            def median(xs):
                if not xs:return None
                values=sorted(xs);n=len(values);return values[n//2] if n%2 else (values[n//2-1]+values[n//2])/2
            poly_lags=lags("polymarket");kalshi_lags=lags("kalshi")
            fees=sum((x.payload or {}).get("fees",0) or 0 for x in rows);slippage=sum(((x.payload or {}).get("slippage",0) or 0)*x.fill_size for x in rows);net_pnl=sum(x.paper_pnl or 0 for x in rows)
            return {"matches_observed":matches,"price_moves_recorded":ticks,"dynamic_signals":signals,"signals_today":signals_today,"paper_executions":executions,"median_poly_to_kalshi_lag_ms":median(poly_lags),"median_kalshi_to_poly_lag_ms":median(kalshi_lags),"lag_distribution":{"polymarket_to_kalshi":poly_lags,"kalshi_to_polymarket":kalshi_lags},"latency":latency,"costs":{"gross_pnl":net_pnl+fees+slippage,"fees":fees,"slippage":slippage,"net_pnl":net_pnl},"fill_probability":None,"data_sufficient":signals>0 and executions>0,"strategy_type":"DYNAMIC_LEAD_LAG","static_arb_included":False,"test_data_excluded":True,"collector_health":await self._collector_health(db,1000)}

    async def _collector_health(self,db,configured_ms:int)->dict:
        result={}
        for venue in ("kalshi","polymarket"):
            rows=list((await db.scalars(select(MarketPriceTickRecord).where(MarketPriceTickRecord.venue==venue,MarketPriceTickRecord.is_test.is_(False)).order_by(MarketPriceTickRecord.received_timestamp.desc()).limit(1000))).all())
            stamps=sorted(x.received_timestamp for x in rows);intervals=[(b-a).total_seconds()*1000 for a,b in zip(stamps,stamps[1:])]
            intervals.sort()
            percentile=lambda p: intervals[min(len(intervals)-1,int((len(intervals)-1)*p))] if intervals else None
            source=rows[0].source_type if rows else "polling"
            quality="HIGH" if source=="websocket" and rows and all(x.exchange_timestamp for x in rows) else "MEDIUM" if configured_ms<1000 else "LOW"
            result[venue]={"source":source,"configured_interval_ms":configured_ms,"median_receive_interval_ms":percentile(.5),"p95_receive_interval_ms":percentile(.95),"lag_quality":quality,"warning":"Lead/Lag may include collector latency." if quality=="LOW" else None}
        return result

    async def collector_health(self,configured_ms:int)->dict:
        async with SessionLocal() as db:return await self._collector_health(db,configured_ms)

    async def clear_test_data(self)->dict:
        async with SessionLocal() as db:
            counts={}
            for name,model in (("dynamic_scenarios",DynamicExecutionScenarioRecord),("dynamic_signals",DynamicSignalRecord),("price_ticks",MarketPriceTickRecord),("match_sessions",MatchSessionRecord)):
                result=await db.execute(delete(model).where(model.is_test.is_(True)));counts[name]=result.rowcount or 0
            await db.commit();return counts
