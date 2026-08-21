from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from uuid import uuid4

from app.arbitrage.fees import KalshiFeeModel, PolymarketFeeModel
from app.arbitrage.vwap import calculate_vwap

STRATEGY_TYPE="DYNAMIC_LEAD_LAG"

@dataclass
class DynamicSignalEngine:
    move_threshold: float = .03
    window_ms: int = 1500
    ttl_ms: int = 2000
    fee_buffer: float = .0025

    def detect(self, new_tick:dict, history:list[dict], is_test:bool=False)->dict|None:
        now=new_tick["received_timestamp"]
        start=now-timedelta(milliseconds=self.window_ms)
        same=[x for x in history if x["match_session_id"]==new_tick["match_session_id"] and x["outcome"]==new_tick["outcome"] and x["received_timestamp"]>=start and x.get("mid_price") is not None]
        leader_old=next((x for x in same if x["venue"]==new_tick["venue"]),None)
        follower_venue="polymarket" if new_tick["venue"]=="kalshi" else "kalshi"
        follower=[x for x in same if x["venue"]==follower_venue]
        if not leader_old or not follower or new_tick.get("mid_price") is None:return None
        follower_old,follower_now=follower[0],follower[-1]
        leader_move=new_tick["mid_price"]-leader_old["mid_price"]
        follower_move=follower_now["mid_price"]-follower_old["mid_price"]
        if abs(leader_move)<self.move_threshold or abs(follower_move)>=abs(leader_move)*.6:return None
        gap=new_tick["mid_price"]-follower_now["mid_price"]
        if gap*leader_move<=0:return None
        detected=datetime.now(UTC);net=max(0,abs(gap)-self.fee_buffer)
        return {"id":f"dyn:{uuid4().hex}","match_session_id":new_tick["match_session_id"],"outcome":new_tick["outcome"],"signal_type":"CROSS_VENUE_LEAD_LAG","strategy_type":STRATEGY_TYPE,"leader_venue":new_tick["venue"],"follower_venue":follower_venue,"leader_price_before":leader_old["mid_price"],"leader_price_after":new_tick["mid_price"],"follower_price_at_signal":follower_now["mid_price"],"leader_move_cents":leader_move*100,"follower_move_cents":follower_move*100,"current_gap_cents":gap*100,"signal_started_at":leader_old["received_timestamp"],"detected_at":detected,"signal_age_ms":max(0,(detected-now).total_seconds()*1000),"expected_direction":"UP" if leader_move>0 else "DOWN","raw_edge":abs(gap),"estimated_fee":0.0,"estimated_slippage":self.fee_buffer,"estimated_net_edge":net,"available_size_5":5 if follower_now.get("vwap_5") is not None else 0,"available_size_25":25 if follower_now.get("vwap_25") is not None else 0,"available_size_100":100 if follower_now.get("vwap_100") is not None else 0,"status":"OPEN","ttl_ms":self.ttl_ms,"expires_at":detected+timedelta(milliseconds=self.ttl_ms),"is_test":is_test,"metadata":{"window_ms":self.window_ms,"statistical_signal":True,"observed_lag_ms":None}}

    @staticmethod
    def expire(signal:dict,now:datetime)->dict:
        if signal["status"]=="OPEN" and now>=signal["expires_at"]:signal={**signal,"status":"EXPIRED","signal_age_ms":(now-signal["detected_at"]).total_seconds()*1000}
        return signal

def execute_dynamic_signal(signal:dict,book,venue:str,size:float,slippage_buffer:float=.0025)->dict:
    levels=book.yes_asks if signal["expected_direction"]=="UP" else book.no_asks
    fill=calculate_vwap(levels,size)
    price=fill.vwap
    fee=0.0 if price is None else (KalshiFeeModel().estimate(price,fill.filled_quantity) if venue=="kalshi" else PolymarketFeeModel().estimate(price,fill.filled_quantity))
    status="FILLED" if fill.sufficient_liquidity else "PARTIAL_FILL" if fill.filled_quantity else "FAILED"
    intended=signal["follower_price_at_signal"]
    slippage=(price-intended if signal["expected_direction"]=="UP" else intended-price) if price is not None else 0
    realized=signal["raw_edge"]-(fee/fill.filled_quantity if fill.filled_quantity else 0)-max(0,slippage)-slippage_buffer
    return {"status":status,"intended_price":intended,"actual_vwap":price,"fill_size":fill.filled_quantity,"fill_ratio":fill.filled_quantity/size,"fees":fee,"slippage":slippage,"realized_entry_edge":realized if fill.filled_quantity else None,"paper_pnl":realized*fill.filled_quantity if fill.filled_quantity else None,"requested_size":size}

def simulate_latency_scenarios(signal:dict,books_by_latency:dict[int,object],venue:str,size:float,slippage_buffer:float=.0025)->list[dict]:
    return [{"latency_ms":latency,**execute_dynamic_signal(signal,book,venue,size,slippage_buffer)} for latency,book in sorted(books_by_latency.items())]
