from dataclasses import dataclass

from app.schemas.domain import OrderBookLevel


@dataclass(frozen=True)
class VWAPResult:
    vwap: float | None
    filled_quantity: float
    remaining_quantity: float
    sufficient_liquidity: bool


def calculate_vwap(levels: list[OrderBookLevel], quantity: float) -> VWAPResult:
    if quantity <= 0:
        raise ValueError("quantity must be positive")
    remaining = quantity
    filled = 0.0
    cost = 0.0
    for level in sorted(levels, key=lambda item: item.price):
        take = min(remaining, level.quantity)
        cost += take * level.price
        filled += take
        remaining -= take
        if remaining <= 1e-9:
            remaining = 0.0
            break
    return VWAPResult(
        vwap=(cost / filled) if filled else None,
        filled_quantity=filled,
        remaining_quantity=remaining,
        sufficient_liquidity=remaining == 0,
    )

