"""isolate test balance snapshots and resolution events"""
from alembic import op
import sqlalchemy as sa

revision = "20260820_03"
down_revision = "20260820_02"
branch_labels = None
depends_on = None

def upgrade():
    op.add_column("paper_balance_snapshots", sa.Column("is_test", sa.Boolean(), nullable=False, server_default=sa.false()))
    op.create_index("ix_paper_balance_snapshots_is_test", "paper_balance_snapshots", ["is_test"])
    op.add_column("resolution_events", sa.Column("is_test", sa.Boolean(), nullable=False, server_default=sa.false()))
    op.create_index("ix_resolution_events_is_test", "resolution_events", ["is_test"])

def downgrade():
    op.drop_index("ix_resolution_events_is_test", table_name="resolution_events")
    op.drop_column("resolution_events", "is_test")
    op.drop_index("ix_paper_balance_snapshots_is_test", table_name="paper_balance_snapshots")
    op.drop_column("paper_balance_snapshots", "is_test")
