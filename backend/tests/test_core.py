import pytest
from datetime import UTC, datetime, timedelta

from app.arbitrage.engine import quote_direction
from app.arbitrage.fees import KalshiFeeModel, PolymarketFeeModel
from app.arbitrage.lifecycle import OpportunityState
from app.arbitrage.vwap import calculate_vwap
from app.matching.resolution import resolution_warnings
from app.paper_trading.simulator import simulate_fill
from app.schemas.domain import OrderBookLevel
from app.matching.candidates import candidate_pairs, extract_numbers, normalize_market_title
from app.matching.resolution import resolution_compatibility
from app.paper_trading.execution import execute_opportunity
from app.schemas.domain import NormalizedMarket, OrderBook, Platform
from app.arbitrage.replay import replay_snapshots
from app.matching.analysis import analyze_market_pair


def test_vwap_multiple_levels():
    result = calculate_vwap([OrderBookLevel(price=.43, quantity=5), OrderBookLevel(price=.44, quantity=20), OrderBookLevel(price=.46, quantity=100)], 10)
    assert result.vwap == pytest.approx(.435)
    assert result.filled_quantity == 10
    assert result.sufficient_liquidity


def test_vwap_insufficient_liquidity():
    result = calculate_vwap([OrderBookLevel(price=.43, quantity=5)], 10)
    assert result.filled_quantity == 5
    assert result.remaining_quantity == 5
    assert not result.sufficient_liquidity


def test_vwap_rejects_invalid_quantity():
    with pytest.raises(ValueError): calculate_vwap([], 0)


def test_fee_models_are_configurable():
    assert KalshiFeeModel(.07).estimate(.5, 100) == pytest.approx(1.75)
    assert PolymarketFeeModel(.01).estimate(.5, 100) == pytest.approx(.5)


def test_resolution_win_and_advance_mismatch():
    warnings = resolution_warnings("Win in regulation time", "Advance including overtime and penalties")
    assert warnings


def test_paper_modes_are_increasingly_conservative():
    optimistic = simulate_fill(.43, .52, 100, .5, "optimistic")
    realistic = simulate_fill(.43, .52, 100, .5, "realistic")
    conservative = simulate_fill(.43, .52, 100, .5, "conservative")
    assert optimistic.estimated_profit > realistic.estimated_profit > conservative.estimated_profit


@pytest.mark.parametrize("direction", ["kalshi_yes_polymarket_no", "kalshi_no_polymarket_yes"])
def test_both_arbitrage_directions(direction):
    levels_a = [OrderBookLevel(price=.43, quantity=100)]
    levels_b = [OrderBookLevel(price=.52, quantity=100)]
    quote = quote_direction(direction, levels_a, levels_b, 10, KalshiFeeModel(0), PolymarketFeeModel(0))
    assert quote.sufficient_liquidity
    assert quote.gross_edge == pytest.approx(.05)
    assert quote.expected_profit == pytest.approx(.5)


def test_opportunity_duration_updates_without_duplicate():
    start = datetime.now(UTC)
    state = OpportunityState(start, start, .02, .02, 25)
    state.update(start + timedelta(seconds=8.4), .032, 73)
    assert state.duration_seconds == pytest.approx(8.4)
    assert state.best_edge == .032
    assert state.maximum_size == 73

def market(platform,title,date):
    return NormalizedMarket(id=f"{platform.value}:{title}",platform=platform,external_id=title,title=title,description=title,category="sports",event_date=date,close_time=date,resolution_rules="Result after 90 minutes regulation time according to official league source.",resolution_source="official",source="live")

def test_title_normalization_aliases_and_currency():
    assert normalize_market_title("Man Utd versus Chelsea above $120,000") == "manchester united chelsea above 120000"

def test_candidate_same_sports_event_and_different_teams():
    date=datetime.now(UTC)
    good=candidate_pairs([market(Platform.KALSHI,"Arsenal defeat Chelsea",date),market(Platform.POLYMARKET,"Arsenal vs Chelsea Arsenal winner",date)])
    bad=candidate_pairs([market(Platform.KALSHI,"Arsenal defeat Chelsea",date),market(Platform.POLYMARKET,"Liverpool vs Everton Liverpool winner",date)])
    assert good and not bad

def test_candidate_rejects_date_and_threshold_mismatch():
    date=datetime.now(UTC)
    assert not candidate_pairs([market(Platform.KALSHI,"Arsenal Chelsea over 2.5 goals",date),market(Platform.POLYMARKET,"Arsenal Chelsea over 3.5 goals",date)])
    assert not candidate_pairs([market(Platform.KALSHI,"Arsenal defeat Chelsea",date),market(Platform.POLYMARKET,"Arsenal vs Chelsea winner",date+timedelta(days=2))])

def test_resolution_regulation_overtime_mismatch():
    result=resolution_compatibility("Win after 90 minutes regulation", "Advance including overtime and penalties")
    assert not result.compatible and result.differences

def test_execution_full_partial_and_failed():
    class S:paper_trade_size=25;paper_slippage_buffer=.0025;paper_execution_latency_ms=250
    opportunity={"direction":"kalshi_yes_polymarket_no","kalshi_market_id":"k","polymarket_market_id":"p","kalshi_side":"YES","polymarket_side":"NO"}
    def book(k,p):return OrderBook(market_id="x",timestamp=datetime.now(UTC),yes_asks=k,no_asks=p,source="live")
    full=execute_opportunity(opportunity,book([OrderBookLevel(price=.43,quantity=25)],[]),book([],[OrderBookLevel(price=.54,quantity=25)]),S)
    partial=execute_opportunity(opportunity,book([OrderBookLevel(price=.43,quantity=10)],[]),book([],[OrderBookLevel(price=.54,quantity=25)]),S)
    failed=execute_opportunity(opportunity,book([],[]),book([],[]),S)
    assert full["status"]=="DUAL_FILLED" and partial["status"]=="PARTIAL_FILL" and failed["status"]=="FAILED"

def test_replay_uses_observed_snapshots_without_interpolation():
    start=datetime.now(UTC);snapshots=[{"timestamp":start,"net_edge":.02,"available_liquidity":25},{"timestamp":start+timedelta(milliseconds=500),"net_edge":.005,"available_liquidity":20}]
    rows=replay_snapshots(snapshots,(0,250,500,1000))
    assert rows[0]["average_edge"]==.02
    assert rows[1]["average_edge"]==.005 and rows[1]["precision"]=="observed_snapshot"
    assert rows[-1]["precision"]=="insufficient_data"

def test_match_analysis_explains_date_numeric_and_scope_failures():
    date=datetime.now(UTC);left=market(Platform.KALSHI,"Arsenal match wins over 2.5 goals",date);right=market(Platform.POLYMARKET,"Arsenal season champion over 3.5 goals",date+timedelta(days=2));result=analyze_market_pair(left,right)
    assert result["decision"]=="REJECTED"
    assert any("Numeric threshold mismatch" in x for x in result["reasons"])
    assert any("Event scope mismatch" in x for x in result["reasons"])
    assert any(x["status"]=="FAIL" for x in result["pipeline"])
