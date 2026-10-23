"""Stable source identity for Tango documents associated from the existing picker."""
from alembic import op
import sqlalchemy as sa

revision = "f901a2b3c456"
down_revision = "e8f901a2b345"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table("tango_comprobantes",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.Column("empresa", sa.String(20), nullable=False),
        sa.Column("origen_tipo", sa.String(10), nullable=False),
        sa.Column("origen_id", sa.Integer(), nullable=False),
        sa.Column("comprobante_id", sa.Integer(), sa.ForeignKey("comprobantes.id"), nullable=False, unique=True),
        sa.Column("datos", sa.JSON(), nullable=False),
        sa.UniqueConstraint("empresa", "origen_tipo", "origen_id", name="uq_tango_comprobante_origen"))


def downgrade():
    op.drop_table("tango_comprobantes")
