from datetime import datetime

from sqlalchemy import Boolean, DateTime, Float, Integer, JSON, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class MarketRecord(Base):
    __tablename__ = "markets"
    id: Mapped[str] = mapped_column(String(300), primary_key=True)
    platform: Mapped[str] = mapped_column(String(30), index=True)
    external_id: Mapped[str] = mapped_column(String(260), index=True)
    title: Mapped[str] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(30), index=True)
    source: Mapped[str] = mapped_column(String(10), index=True)
    payload: Mapped[dict] = mapped_column(JSON)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class MarketSnapshotRecord(Base):
    __tablename__ = "market_snapshots"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    market_id: Mapped[str] = mapped_column(String(300), index=True)
    source: Mapped[str] = mapped_column(String(10), index=True)
    payload: Mapped[dict] = mapped_column(JSON)
    captured_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)


class OrderBookSnapshotRecord(Base):
    __tablename__ = "orderbook_snapshots"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    market_id: Mapped[str] = mapped_column(String(300), index=True)
    source: Mapped[str] = mapped_column(String(10), index=True)
    best_yes_bid: Mapped[float | None] = mapped_column(Float)
    best_yes_ask: Mapped[float | None] = mapped_column(Float)
    best_no_bid: Mapped[float | None] = mapped_column(Float)
    best_no_ask: Mapped[float | None] = mapped_column(Float)
    payload: Mapped[dict] = mapped_column(JSON)
    captured_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)


class WatchedMarketRecord(Base):
    __tablename__ = "watched_markets"
    market_id: Mapped[str] = mapped_column(String(300), primary_key=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class ConnectorHealthRecord(Base):
    __tablename__ = "connector_health"
    platform: Mapped[str] = mapped_column(String(30), primary_key=True)
    connected: Mapped[bool] = mapped_column(Boolean)
    payload: Mapped[dict] = mapped_column(JSON)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))

