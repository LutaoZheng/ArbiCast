from datetime import datetime
from enum import Enum
from typing import Literal

from pydantic import BaseModel, Field


class Platform(str, Enum):
    KALSHI = "kalshi"
    POLYMARKET = "polymarket"


class MatchStatus(str, Enum):
    APPROVED = "approved"
    NEEDS_REVIEW = "needs_review"
    REJECTED = "rejected"


class NormalizedMarket(BaseModel):
    id: str
    platform: Platform
    external_id: str
    title: str
    description: str
    category: str
    event_date: datetime | None = None
    close_time: datetime
    resolution_rules: str
    resolution_source: str
    status: str = "open"
    yes_bid: float | None = Field(default=None, ge=0, le=1)
    yes_ask: float | None = Field(default=None, ge=0, le=1)
    no_bid: float | None = Field(default=None, ge=0, le=1)
    no_ask: float | None = Field(default=None, ge=0, le=1)
    yes_token_id: str | None = None
    no_token_id: str | None = None
    event_id: str | None = None
    event_title: str | None = None
    series_ticker: str | None = None
    outcome_label: str | None = None
    updated_at: datetime | None = None
    source: Literal["mock", "live"] = "mock"
    watched: bool = False
    resolved_outcome: Literal["YES", "NO"] | None = None


class OrderBookLevel(BaseModel):
    price: float = Field(ge=0, le=1)
    quantity: float = Field(gt=0)


class OrderBook(BaseModel):
    market_id: str
    timestamp: datetime
    yes_bids: list[OrderBookLevel] = []
    yes_asks: list[OrderBookLevel] = []
    no_bids: list[OrderBookLevel] = []
    no_asks: list[OrderBookLevel] = []
    source: Literal["mock", "live"] = "live"


class ConnectorHealth(BaseModel):
    platform: Platform
    connected: bool = False
    last_success: datetime | None = None
    last_attempt: datetime | None = None
    latency_ms: float | None = None
    error_count: int = 0
    last_error: str | None = None
    markets_loaded: int = 0
    request_count: int = 0
    rate_limit_count: int = 0
    backoff_seconds: float = 0


class RecentRequest(BaseModel):
    platform: Platform
    method: str
    path: str
    status: int | None
    latency_ms: float
    timestamp: datetime
    error: str | None = None


class MarketMatch(BaseModel):
    id: str
    kalshi_market_id: str
    polymarket_market_id: str
    similarity_score: float
    resolution_compatible: bool
    confidence: float
    warnings: list[str]
    status: MatchStatus


class SizeQuote(BaseModel):
    size: float
    net_edge: float | None
    expected_profit: float | None
    liquidity_available: bool


class Opportunity(BaseModel):
    id: str
    event: str
    category: str
    match_id: str
    direction: str
    kalshi_side: str
    polymarket_side: str
    kalshi_price: float
    polymarket_price: float
    kalshi_vwap: float
    polymarket_vwap: float
    gross_edge: float
    estimated_fees: float
    slippage: float
    safety_buffer: float
    net_edge: float
    available_size: float
    expected_profit: float
    match_confidence: float
    first_seen: datetime
    last_seen: datetime
    duration_seconds: float
    best_edge: float
    worst_edge: float
    size_quotes: list[SizeQuote]
    live: bool = True


class PaperTrade(BaseModel):
    id: str
    opportunity_id: str
    event: str
    mode: Literal["optimistic", "realistic", "conservative"]
    entry_time: datetime
    quantity: float
    kalshi_fill: float
    polymarket_fill: float
    fees: float
    slippage: float
    total_cost: float
    locked_payout: float
    estimated_profit: float
    status: str = "open"
