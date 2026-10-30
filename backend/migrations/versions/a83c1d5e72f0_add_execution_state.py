"""add durable simulation execution state"""

from alembic import op
import sqlalchemy as sa

revision = "a83c1d5e72f0"
down_revision = "e9b5a7c3d210"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("simulation_runs", sa.Column("error_message", sa.String(300)))
    op.add_column("simulation_participants", sa.Column("rng_state", sa.JSON()))


def downgrade():
    op.drop_column("simulation_participants", "rng_state")
    op.drop_column("simulation_runs", "error_message")
