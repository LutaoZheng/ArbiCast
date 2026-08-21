"""research test isolation"""
from alembic import op
import sqlalchemy as sa
revision="20260820_02";down_revision="20260820_01";branch_labels=None;depends_on=None
def upgrade():
    op.add_column("market_matches",sa.Column("is_test",sa.Boolean(),nullable=False,server_default=sa.false()));op.add_column("market_matches",sa.Column("approval_source",sa.String(20),nullable=False,server_default="manual"))
    for table in ["arbitrage_opportunities","opportunity_snapshots","paper_accounts","paper_orders","paper_trades","paper_positions"]:op.add_column(table,sa.Column("is_test",sa.Boolean(),nullable=False,server_default=sa.false()))
def downgrade():
    for table in ["paper_positions","paper_trades","paper_orders","paper_accounts","opportunity_snapshots","arbitrage_opportunities"]:op.drop_column(table,"is_test")
    op.drop_column("market_matches","approval_source");op.drop_column("market_matches","is_test")
