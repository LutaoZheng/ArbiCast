from dataclasses import dataclass
from typing import Literal


@dataclass(frozen=True)
class PaperFill:
    total_cost: float
    locked_payout: float
    estimated_profit: float
    slippage: float


def simulate_fill(
    kalshi_price: float,
    polymarket_price: float,
    quantity: float,
    fees: float,
    mode: Literal["optimistic", "realistic", "conservative"] = "realistic",
    slippage_buffer: float = 0.005,
) -> PaperFill:
    multiplier = {"optimistic": 0, "realistic": 1, "conservative": 2}[mode]
    slippage = quantity * slippage_buffer * multiplier
    total_cost = quantity * (kalshi_price + polymarket_price) + fees + slippage
    payout = quantity
    return PaperFill(total_cost, payout, payout - total_cost, slippage)

