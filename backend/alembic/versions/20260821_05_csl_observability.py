"""CSL acquisition and collector observability."""
from alembic import op
import sqlalchemy as sa

revision="20260821_05"
down_revision="20260821_04"
branch_labels=None
depends_on=None

def upgrade():
    op.add_column("csl_match_sessions",sa.Column("recording_started_at",sa.DateTime(timezone=True)))
    op.add_column("csl_match_sessions",sa.Column("recording_stopped_at",sa.DateTime(timezone=True)))
    op.add_column("csl_match_sessions",sa.Column("stop_reason",sa.String(120)))
    op.add_column("csl_market_price_ticks",sa.Column("processed_at",sa.DateTime(timezone=True),nullable=True))
    op.add_column("csl_market_price_ticks",sa.Column("source_type",sa.String(24),nullable=False,server_default="polling"))
    op.execute("UPDATE csl_market_price_ticks SET processed_at = stored_timestamp WHERE processed_at IS NULL")
    op.alter_column("csl_market_price_ticks","processed_at",nullable=False)
    op.create_index("ix_csl_market_price_ticks_source_type","csl_market_price_ticks",["source_type"])
    op.add_column("csl_dynamic_signals",sa.Column("lag_quality",sa.String(12),nullable=False,server_default="LOW"))
    op.create_index("ix_csl_dynamic_signals_lag_quality","csl_dynamic_signals",["lag_quality"])

def downgrade():
    op.drop_index("ix_csl_dynamic_signals_lag_quality",table_name="csl_dynamic_signals")
    op.drop_column("csl_dynamic_signals","lag_quality")
    op.drop_index("ix_csl_market_price_ticks_source_type",table_name="csl_market_price_ticks")
    op.drop_column("csl_market_price_ticks","source_type")
    op.drop_column("csl_market_price_ticks","processed_at")
    op.drop_column("csl_match_sessions","stop_reason")
    op.drop_column("csl_match_sessions","recording_stopped_at")
    op.drop_column("csl_match_sessions","recording_started_at")
