from datetime import datetime
from sqlalchemy import Boolean, DateTime, Float, Integer, JSON, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column
from app.db.base import Base

class MarketMatchRecord(Base):
    __tablename__="market_matches"
    id:Mapped[str]=mapped_column(String(600),primary_key=True)
    kalshi_market_id:Mapped[str]=mapped_column(String(300),index=True)
    polymarket_market_id:Mapped[str]=mapped_column(String(300),index=True)
    status:Mapped[str]=mapped_column(String(30),index=True,default="needs_review")
    confidence:Mapped[float]=mapped_column(Float)
    payload:Mapped[dict]=mapped_column(JSON)
    source:Mapped[str]=mapped_column(String(10),index=True)
    created_at:Mapped[datetime]=mapped_column(DateTime(timezone=True))
    updated_at:Mapped[datetime]=mapped_column(DateTime(timezone=True))
    is_test:Mapped[bool]=mapped_column(Boolean,default=False,index=True)
    approval_source:Mapped[str]=mapped_column(String(20),default="manual")

class ArbitrageOpportunityRecord(Base):
    __tablename__="arbitrage_opportunities"; __table_args__=(UniqueConstraint("pair_id","direction","lifecycle",name="uq_opportunity_lifecycle"),)
    id:Mapped[str]=mapped_column(String(700),primary_key=True); pair_id:Mapped[str]=mapped_column(String(600),index=True); direction:Mapped[str]=mapped_column(String(60)); lifecycle:Mapped[int]=mapped_column(Integer,default=1); status:Mapped[str]=mapped_column(String(30),index=True); source:Mapped[str]=mapped_column(String(10),index=True); first_seen:Mapped[datetime]=mapped_column(DateTime(timezone=True)); last_seen:Mapped[datetime]=mapped_column(DateTime(timezone=True)); current_edge:Mapped[float]=mapped_column(Float); best_edge:Mapped[float]=mapped_column(Float); worst_edge:Mapped[float]=mapped_column(Float); payload:Mapped[dict]=mapped_column(JSON)
    is_test:Mapped[bool]=mapped_column(Boolean,default=False,index=True)

class OpportunitySnapshotRecord(Base):
    __tablename__="opportunity_snapshots"
    id:Mapped[int]=mapped_column(Integer,primary_key=True,autoincrement=True); opportunity_id:Mapped[str]=mapped_column(String(700),index=True); timestamp:Mapped[datetime]=mapped_column(DateTime(timezone=True),index=True); leg_a_price:Mapped[float]=mapped_column(Float); leg_b_price:Mapped[float]=mapped_column(Float); gross_edge:Mapped[float]=mapped_column(Float); net_edge:Mapped[float]=mapped_column(Float); available_liquidity:Mapped[float]=mapped_column(Float); payload:Mapped[dict]=mapped_column(JSON)
    is_test:Mapped[bool]=mapped_column(Boolean,default=False,index=True)

class PaperAccountRecord(Base):
    __tablename__="paper_accounts"
    id:Mapped[int]=mapped_column(Integer,primary_key=True,default=1); starting_balance:Mapped[float]=mapped_column(Float); cash:Mapped[float]=mapped_column(Float); reserved_capital:Mapped[float]=mapped_column(Float,default=0); realized_pnl:Mapped[float]=mapped_column(Float,default=0); created_at:Mapped[datetime]=mapped_column(DateTime(timezone=True)); updated_at:Mapped[datetime]=mapped_column(DateTime(timezone=True))
    is_test:Mapped[bool]=mapped_column(Boolean,default=False,index=True)

class PaperStrategyRecord(Base):
    __tablename__="paper_strategies"
    id:Mapped[int]=mapped_column(Integer,primary_key=True,default=1); enabled:Mapped[bool]=mapped_column(Boolean,default=True); payload:Mapped[dict]=mapped_column(JSON); updated_at:Mapped[datetime]=mapped_column(DateTime(timezone=True))

class PaperOrderRecord(Base):
    __tablename__="paper_orders"
    id:Mapped[str]=mapped_column(String(800),primary_key=True); trade_id:Mapped[str]=mapped_column(String(800),index=True); platform:Mapped[str]=mapped_column(String(30)); market_id:Mapped[str]=mapped_column(String(300)); side:Mapped[str]=mapped_column(String(10)); status:Mapped[str]=mapped_column(String(30)); payload:Mapped[dict]=mapped_column(JSON); execution_time:Mapped[datetime]=mapped_column(DateTime(timezone=True))
    is_test:Mapped[bool]=mapped_column(Boolean,default=False,index=True)

class PaperTradeRecord(Base):
    __tablename__="paper_trades"
    id:Mapped[str]=mapped_column(String(800),primary_key=True); opportunity_id:Mapped[str]=mapped_column(String(700),unique=True,index=True); status:Mapped[str]=mapped_column(String(30),index=True); source:Mapped[str]=mapped_column(String(10)); payload:Mapped[dict]=mapped_column(JSON); created_at:Mapped[datetime]=mapped_column(DateTime(timezone=True)); updated_at:Mapped[datetime]=mapped_column(DateTime(timezone=True))
    is_test:Mapped[bool]=mapped_column(Boolean,default=False,index=True)

class PaperPositionRecord(Base):
    __tablename__="paper_positions"
    id:Mapped[str]=mapped_column(String(800),primary_key=True); trade_id:Mapped[str]=mapped_column(String(800),unique=True); status:Mapped[str]=mapped_column(String(40),index=True); payload:Mapped[dict]=mapped_column(JSON); opened_at:Mapped[datetime]=mapped_column(DateTime(timezone=True)); settled_at:Mapped[datetime|None]=mapped_column(DateTime(timezone=True),nullable=True)
    is_test:Mapped[bool]=mapped_column(Boolean,default=False,index=True)

class PaperBalanceSnapshotRecord(Base):
    __tablename__="paper_balance_snapshots"
    id:Mapped[int]=mapped_column(Integer,primary_key=True,autoincrement=True); timestamp:Mapped[datetime]=mapped_column(DateTime(timezone=True),index=True); cash:Mapped[float]=mapped_column(Float); reserved_capital:Mapped[float]=mapped_column(Float); equity:Mapped[float]=mapped_column(Float); realized_pnl:Mapped[float]=mapped_column(Float)
    is_test:Mapped[bool]=mapped_column(Boolean,default=False,index=True)

class ResolutionEventRecord(Base):
    __tablename__="resolution_events"
    id:Mapped[int]=mapped_column(Integer,primary_key=True,autoincrement=True); position_id:Mapped[str]=mapped_column(String(800),index=True); platform:Mapped[str]=mapped_column(String(30)); outcome:Mapped[str|None]=mapped_column(String(20),nullable=True); status:Mapped[str]=mapped_column(String(40)); payload:Mapped[dict]=mapped_column(JSON); observed_at:Mapped[datetime]=mapped_column(DateTime(timezone=True))
    is_test:Mapped[bool]=mapped_column(Boolean,default=False,index=True)
