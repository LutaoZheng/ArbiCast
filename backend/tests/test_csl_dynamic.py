from datetime import UTC,datetime,timedelta

import pytest

from app.csl.dynamic import DynamicSignalEngine,execute_dynamic_signal,simulate_latency_scenarios
from app.csl.matching import canonical_team,csl_candidate_pairs,deterministic_csl_match,is_csl_like_market,is_football_market,is_semantically_compatible_csl,match_session_payload,parse_csl_contract
from app.services.csl import collector_lag_quality
from app.schemas.domain import NormalizedMarket,OrderBook,OrderBookLevel,Platform
from app.services.csl_repository import should_persist_tick

def market(platform,title,when,rules="Settles on the winner after 90 minutes plus stoppage time. Regulation result only."):
    return NormalizedMarket(id=f"{platform.value}:{title}",platform=platform,external_id=title,title=title,description="Chinese Super League CSL",category="sports",event_date=when,close_time=when+timedelta(hours=2),resolution_rules=rules,resolution_source="official league",source="live")

def tick(venue,price,at):return {"match_session_id":"csl:test","venue":venue,"market_id":venue,"outcome":"HOME","received_timestamp":at,"mid_price":price,"vwap_5":price,"vwap_25":price,"vwap_100":None}

def book(price=.5,qty=25):return OrderBook(market_id="m",timestamp=datetime.now(UTC),yes_asks=[OrderBookLevel(price=price,quantity=qty)] if qty else [],no_asks=[OrderBookLevel(price=1-price,quantity=qty)] if qty else [],source="live")

def test_csl_team_normalization():
    assert canonical_team("Beijing FC")==canonical_team("Beijing Guoan FC")=="Beijing Guoan"

def test_same_match_and_session_creation():
    when=datetime.now(UTC);left=market(Platform.KALSHI,"CSL Shanghai Port vs Beijing FC Shanghai Port winner",when);right=market(Platform.POLYMARKET,"Chinese Super League Shanghai Port FC vs Beijing Guoan FC home win",when)
    result=deterministic_csl_match(left,right);session=match_session_payload({"id":"p","status":"approved"},left,right,now=when+timedelta(minutes=5))
    assert result["matched"] and session["status"]=="LIVE" and session["metadata"]["recording_enabled"]
    candidates=csl_candidate_pairs([left,right])
    assert len(candidates)==1 and candidates[0]["status"].value=="needs_review" and candidates[0]["research_universe"]=="CSL"

def test_research_pair_records_without_human_approval_but_disables_paper():
    when=datetime.now(UTC);left=market(Platform.KALSHI,"CSL Shanghai Port vs Beijing FC home win",when);right=market(Platform.POLYMARKET,"CSL Shanghai Port FC vs Beijing Guoan home win",when)
    session=match_session_payload({"id":"research","status":"needs_review"},left,right,now=when)
    assert session and session["metadata"]["research_eligible"]
    assert session["metadata"]["recording_enabled"]
    assert not session["metadata"]["paper_execution_allowed"]

def test_csl_discovery_filters_and_collector_quality():
    when=datetime.now(UTC);csl=market(Platform.KALSHI,"Chinese Super League Shanghai Port vs Beijing FC home win",when)
    other=NormalizedMarket(id="kalshi:epl",platform=Platform.KALSHI,external_id="epl",title="Premier League Arsenal vs Chelsea",description="football",category="sports",close_time=when,source="live",resolution_rules="90 minutes",resolution_source="official")
    assert is_football_market(csl) and is_csl_like_market(csl)
    assert is_football_market(other) and not is_csl_like_market(other)
    assert collector_lag_quality(["polling","polling"],False,1000)=="LOW"
    assert collector_lag_quality(["websocket","websocket"],True,100)=="HIGH"

def test_kalshi_series_ticker_is_deterministic_csl_and_outcome_is_structured():
    when=datetime.now(UTC)
    row=NormalizedMarket(id="kalshi:k",platform=Platform.KALSHI,external_id="k",title="Beijing Guoan vs Yunnan Yukun Winner?",description="Beijing Guoan vs Yunnan Yukun",category="sports",close_time=when,event_date=when,resolution_rules="Winner after 90 minutes plus stoppage time; does not include extra time or penalties.",resolution_source="Kalshi",series_ticker="KXCHNSLGAME",outcome_label="Yunnan Yukun",source="live")
    contract=parse_csl_contract(row)
    assert is_csl_like_market(row) and is_semantically_compatible_csl(row)
    assert contract and contract.outcome=="AWAY"

@pytest.mark.parametrize("event_title,outcome_label",[
    ("Wuhan San Zhen FC vs. Tianjin Jinmen Hu FC","Tianjin Jinmen Hu FC"),
    ("Chengdu Rongcheng FC vs. Shanghai Shenhua FC","Shanghai Shenhua FC"),
])
def test_polymarket_event_orientation_controls_away_outcome(event_title,outcome_label):
    when=datetime(2026,8,22,tzinfo=UTC)
    row=NormalizedMarket(id="polymarket:p",platform=Platform.POLYMARKET,external_id="p",title=f"Will {outcome_label} win?",event_title=event_title,outcome_label=outcome_label,description="Chinese Super League",category="sports",event_date=when,close_time=when,resolution_rules="First 90 minutes of regular play plus stoppage time.",resolution_source="official",source="live")
    contract=parse_csl_contract(row)
    assert contract and contract.outcome=="AWAY"

def test_csl_different_date_rejected():
    when=datetime.now(UTC);result=deterministic_csl_match(market(Platform.KALSHI,"CSL Shanghai Port vs Beijing FC home win",when),market(Platform.POLYMARKET,"CSL Shanghai Port vs Beijing FC home win",when+timedelta(days=1)))
    assert not result["matched"] and "Different match date" in result["reasons"]

def test_csl_incompatible_resolution_rejected():
    when=datetime.now(UTC);result=deterministic_csl_match(market(Platform.KALSHI,"CSL Shanghai Port vs Beijing FC home win",when),market(Platform.POLYMARKET,"CSL Shanghai Port vs Beijing FC home win",when,"Winner including overtime and penalties"))
    assert not result["matched"] and result["reasons"]

def test_tick_change_detection_and_periodic_snapshot():
    now=datetime.now(UTC);old={"best_bid":.4,"best_ask":.42,"bid_size":10,"ask_size":10,"received_timestamp":now};same={**old,"received_timestamp":now+timedelta(milliseconds=100)}
    assert not should_persist_tick(old,same,.001,1000)
    assert should_persist_tick(old,{**same,"best_ask":.43},.001,1000)
    assert should_persist_tick(old,{**same,"received_timestamp":now+timedelta(milliseconds=1000)},.001,1000)

def test_lead_move_detection_and_reverse_direction():
    now=datetime.now(UTC);engine=DynamicSignalEngine(.03,1500,2000)
    history=[tick("kalshi",.45,now),tick("polymarket",.44,now),tick("polymarket",.45,now+timedelta(milliseconds=400))]
    poly=engine.detect(tick("kalshi",.51,now+timedelta(milliseconds=500)),history)
    reverse=engine.detect(tick("polymarket",.52,now+timedelta(milliseconds=500)),[tick("polymarket",.45,now),tick("kalshi",.44,now),tick("kalshi",.45,now+timedelta(milliseconds=400))])
    assert poly and poly["leader_venue"]=="kalshi" and reverse and reverse["leader_venue"]=="polymarket"

def test_small_move_does_not_signal():
    now=datetime.now(UTC);engine=DynamicSignalEngine(.03,1500,2000);history=[tick("kalshi",.45,now),tick("polymarket",.44,now)]
    assert engine.detect(tick("kalshi",.46,now+timedelta(milliseconds=500)),history) is None

def test_signal_ttl_expiration():
    now=datetime.now(UTC);signal={"status":"OPEN","detected_at":now,"expires_at":now+timedelta(milliseconds=100)}
    assert DynamicSignalEngine.expire(signal,now+timedelta(milliseconds=101))["status"]=="EXPIRED"

def signal(direction="UP"):return {"expected_direction":direction,"follower_price_at_signal":.45,"raw_edge":.05}

def test_dynamic_execution_full_partial_zero_and_fees():
    full=execute_dynamic_signal(signal(),book(.46,25),"kalshi",25);partial=execute_dynamic_signal(signal(),book(.46,10),"polymarket",25);empty=execute_dynamic_signal(signal(),book(.46,0),"kalshi",25)
    assert full["status"]=="FILLED" and full["fees"]>0
    assert partial["status"]=="PARTIAL_FILL" and partial["fill_ratio"]==pytest.approx(.4)
    assert empty["status"]=="FAILED" and empty["paper_pnl"] is None

def test_multi_latency_scenarios_keep_strategy_separate():
    rows=simulate_latency_scenarios(signal(),{100:book(.46),250:book(.48),500:book(.51)},"polymarket",10)
    assert [x["latency_ms"] for x in rows]==[100,250,500]
    assert rows[0]["realized_entry_edge"]>rows[-1]["realized_entry_edge"]
    assert all("paper_pnl" in x for x in rows)
