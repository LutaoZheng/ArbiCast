"""research pipeline tables"""
from alembic import op
from app.db.base import Base
from app import models  # noqa: F401
revision="20260820_01";down_revision=None;branch_labels=None;depends_on=None
TABLES=["market_matches","arbitrage_opportunities","opportunity_snapshots","paper_accounts","paper_strategies","paper_orders","paper_trades","paper_positions","paper_balance_snapshots","resolution_events"]
def upgrade():
    bind=op.get_bind()
    for table in Base.metadata.sorted_tables:
        if table.name in TABLES:table.create(bind,checkfirst=True)
def downgrade():
    bind=op.get_bind()
    for name in reversed(TABLES):Base.metadata.tables[name].drop(bind,checkfirst=True)
