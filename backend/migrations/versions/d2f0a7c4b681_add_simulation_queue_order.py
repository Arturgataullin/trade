"""Track when a run last executed a step."""

from alembic import op
import sqlalchemy as sa

revision = "d2f0a7c4b681"
down_revision = "a83c1d5e72f0"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("simulation_runs", sa.Column("last_step_at", sa.DateTime(timezone=True)))


def downgrade():
    op.drop_column("simulation_runs", "last_step_at")
