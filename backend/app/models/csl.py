from datetime import datetime

from sqlalchemy import Boolean, DateTime, Float, Index, Integer, JSON, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class MatchSessionRecord(Base):
    __tablename__ = "csl_match_sessions"
    id: Mapped[str] = mapped_column(String(180), primary_key=True)
    league: Mapped[str] = mapped_column(String(20), index=True, default="CSL")
    season: Mapped[str] = mapped_column(String(20))
    home_team: Mapped[str] = mapped_column(String(120), index=True)
    away_team: Mapped[str] = mapped_column(String(120), index=True)
    scheduled_start: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    actual_start: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    status: Mapped[str] = mapped_column(String(24), index=True)
    match_minute: Mapped[int | None] = mapped_column(Integer, nullable=True)
    match_second: Mapped[int | None] = mapped_column(Integer, nullable=True)
    home_score: Mapped[int | None] = mapped_column(Integer, nullable=True)
    away_score: Mapped[int | None] = mapped_column(Integer, nullable=True)
    pair_id: Mapped[str | None] = mapped_column(String(700), nullable=True, index=True)
    markets: Mapped[dict] = mapped_column(JSON)
    metadata_json: Mapped[dict] = mapped_column(JSON)
    is_test: Mapped[bool] = mapped_column(Boolean, default=False, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    recording_started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    recording_stopped_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    stop_reason: Mapped[str | None] = mapped_column(String(120), nullable=True)


class MarketPriceTickRecord(Base):
    __tablename__ = "csl_market_price_ticks"
    __table_args__ = (
        Index("ix_csl_ticks_session_time", "match_session_id", "received_timestamp"),
        Index("ix_csl_ticks_series", "match_session_id", "venue", "outcome", "received_timestamp"),
    )
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    match_session_id: Mapped[str] = mapped_column(String(180), index=True)
    venue: Mapped[str] = mapped_column(String(20), index=True)
    market_id: Mapped[str] = mapped_column(String(300), index=True)
    outcome: Mapped[str] = mapped_column(String(12), index=True)
    exchange_timestamp: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    received_timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    stored_timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    processed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    source_type: Mapped[str] = mapped_column(String(24), index=True, default="polling")
    best_bid: Mapped[float | None] = mapped_column(Float, nullable=True)
    best_ask: Mapped[float | None] = mapped_column(Float, nullable=True)
    bid_size: Mapped[float | None] = mapped_column(Float, nullable=True)
    ask_size: Mapped[float | None] = mapped_column(Float, nullable=True)
    mid_price: Mapped[float | None] = mapped_column(Float, nullable=True)
    vwap_5: Mapped[float | None] = mapped_column(Float, nullable=True)
    vwap_25: Mapped[float | None] = mapped_column(Float, nullable=True)
    vwap_100: Mapped[float | None] = mapped_column(Float, nullable=True)
    book_sequence: Mapped[str | None] = mapped_column(String(120), nullable=True)
    payload: Mapped[dict] = mapped_column(JSON)
    is_test: Mapped[bool] = mapped_column(Boolean, default=False, index=True)


class DynamicSignalRecord(Base):
    __tablename__ = "csl_dynamic_signals"
    __table_args__ = (Index("ix_csl_signals_session_status", "match_session_id", "status"),)
    id: Mapped[str] = mapped_column(String(220), primary_key=True)
    match_session_id: Mapped[str] = mapped_column(String(180), index=True)
    outcome: Mapped[str] = mapped_column(String(12), index=True)
    strategy_type: Mapped[str] = mapped_column(String(32), index=True, default="DYNAMIC_LEAD_LAG")
    leader_venue: Mapped[str] = mapped_column(String(20), index=True)
    follower_venue: Mapped[str] = mapped_column(String(20), index=True)
    signal_started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    detected_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    status: Mapped[str] = mapped_column(String(20), index=True)
    estimated_net_edge: Mapped[float] = mapped_column(Float)
    lag_quality: Mapped[str] = mapped_column(String(12), index=True, default="LOW")
    payload: Mapped[dict] = mapped_column(JSON)
    is_test: Mapped[bool] = mapped_column(Boolean, default=False, index=True)


class DynamicExecutionScenarioRecord(Base):
    __tablename__ = "csl_dynamic_execution_scenarios"
    __table_args__ = (
        UniqueConstraint("signal_id", "latency_ms", name="uq_csl_signal_latency"),
        Index("ix_csl_scenarios_signal_latency", "signal_id", "latency_ms"),
    )
    id: Mapped[str] = mapped_column(String(260), primary_key=True)
    signal_id: Mapped[str] = mapped_column(String(220), index=True)
    strategy_type: Mapped[str] = mapped_column(String(32), index=True, default="DYNAMIC_LEAD_LAG")
    latency_ms: Mapped[int] = mapped_column(Integer, index=True)
    execute_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    status: Mapped[str] = mapped_column(String(24), index=True)
    actual_vwap: Mapped[float | None] = mapped_column(Float, nullable=True)
    fill_size: Mapped[float] = mapped_column(Float, default=0)
    fill_ratio: Mapped[float] = mapped_column(Float, default=0)
    realized_entry_edge: Mapped[float | None] = mapped_column(Float, nullable=True)
    paper_pnl: Mapped[float | None] = mapped_column(Float, nullable=True)
    payload: Mapped[dict] = mapped_column(JSON)
    is_test: Mapped[bool] = mapped_column(Boolean, default=False, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
