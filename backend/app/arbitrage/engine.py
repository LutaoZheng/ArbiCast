from dataclasses import dataclass

from app.arbitrage.fees import FeeModel
from app.arbitrage.vwap import calculate_vwap
from app.schemas.domain import OrderBookLevel


@dataclass(frozen=True)
class ArbitrageQuote:
    direction: str
    gross_edge: float
    fees: float
    net_edge: float
    expected_profit: float
    sufficient_liquidity: bool


def quote_direction(
    direction: str,
    kalshi_levels: list[OrderBookLevel],
    polymarket_levels: list[OrderBookLevel],
    quantity: float,
    kalshi_fee_model: FeeModel,
    polymarket_fee_model: FeeModel,
    slippage: float = 0,
    safety_buffer: float = 0,
) -> ArbitrageQuote:
    kalshi = calculate_vwap(kalshi_levels, quantity)
    polymarket = calculate_vwap(polymarket_levels, quantity)
    sufficient = kalshi.sufficient_liquidity and polymarket.sufficient_liquidity
    if not sufficient or kalshi.vwap is None or polymarket.vwap is None:
        return ArbitrageQuote(direction, 0, 0, 0, 0, False)
    gross_edge = 1 - kalshi.vwap - polymarket.vwap
    fees = (kalshi_fee_model.estimate(kalshi.vwap, quantity) + polymarket_fee_model.estimate(polymarket.vwap, quantity)) / quantity
    net_edge = gross_edge - fees - slippage - safety_buffer
    return ArbitrageQuote(direction, gross_edge, fees, net_edge, net_edge * quantity, True)

