from functools import lru_cache
from typing import Literal

from pydantic import Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    data_mode: Literal["mock", "live"] = "mock"
    use_mock_data: bool | None = None
    database_url: str = "postgresql+asyncpg://arbicast:arbicast@db:5432/arbicast"
    kalshi_base_url: str = "https://external-api.kalshi.com/trade-api/v2"
    polymarket_gamma_url: str = "https://gamma-api.polymarket.com"
    polymarket_clob_url: str = "https://clob.polymarket.com"
    kalshi_max_markets: int = Field(500, ge=1, le=5000)
    polymarket_max_markets: int = Field(500, ge=1, le=5000)
    csl_discovery_max_pages: int = Field(20, ge=1, le=100)
    csl_discovery_max_markets: int = Field(5000, ge=100, le=20000)
    csl_discovery_refresh_seconds: float = Field(300, ge=30, le=3600)
    csl_recording_prestart_minutes: int = Field(30, ge=0, le=240)
    csl_recording_max_hours: int = Field(4, ge=2, le=12)
    market_refresh_seconds: float = Field(60, ge=10, le=3600)
    orderbook_refresh_seconds: float = Field(3, ge=1, le=300)
    orderbook_snapshot_min_seconds: float = Field(15, ge=5, le=3600)
    http_connect_timeout_seconds: float = 5
    http_read_timeout_seconds: float = 15
    matching_refresh_seconds: float = Field(120, ge=30, le=3600)
    matching_min_score: float = Field(.50, ge=0, le=1)
    arbitrage_safety_buffer: float = Field(.0025, ge=0, le=.1)
    min_net_edge: float = Field(.01, ge=-.1, le=.5)
    min_expected_profit: float = Field(.10, ge=0)
    default_trade_size: float = Field(25, gt=0)
    opportunity_snapshot_min_ms: int = Field(250, ge=100, le=60000)
    paper_starting_balance: float = Field(10000, gt=0)
    paper_trade_size: float = Field(25, gt=0)
    paper_min_net_edge: float = Field(.015, ge=-.1, le=.5)
    paper_min_liquidity: float = Field(25, ge=0)
    paper_min_match_confidence: float = Field(.98, ge=0, le=1)
    paper_execution_latency_ms: int = Field(250, ge=0, le=60000)
    paper_slippage_buffer: float = Field(.0025, ge=0, le=.1)
    paper_test_mode: bool = False
    dynamic_book_poll_ms: int = Field(1000, ge=500, le=60000)
    dynamic_tick_min_change: float = Field(.001, ge=0, le=.1)
    dynamic_snapshot_interval_ms: int = Field(5000, ge=250, le=60000)
    dynamic_signal_move_cents: float = Field(3.0, ge=.1, le=50)
    dynamic_signal_window_ms: int = Field(1500, ge=100, le=30000)
    dynamic_signal_ttl_ms: int = Field(2000, ge=100, le=60000)
    dynamic_execution_latencies_ms: str = "100,250,500,750,1000,2000,3000"

    @model_validator(mode="after")
    def legacy_mock_flag(self):
        if "data_mode" not in self.model_fields_set and self.use_mock_data is not None:
            self.data_mode = "mock" if self.use_mock_data else "live"
        return self


@lru_cache
def get_settings() -> Settings:
    return Settings()
