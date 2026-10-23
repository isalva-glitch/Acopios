"""Reviewed snapshots read through the local Access connector."""
from alembic import op
import sqlalchemy as sa

revision = "e8f901a2b345"
down_revision = "d7e8f9a0b123"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "tango_registros",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.Column("acopio_id", sa.Integer(), sa.ForeignKey("acopios.id", ondelete="CASCADE"), nullable=False),
        sa.Column("empresa", sa.String(20), nullable=False),
        sa.Column("origen_tipo", sa.String(10), nullable=False),
        sa.Column("origen_id", sa.Integer(), nullable=False),
        sa.Column("huella", sa.String(64), nullable=False),
        sa.Column("datos", sa.JSON(), nullable=False),
        sa.Column("estado", sa.String(12), nullable=False),
        sa.Column("revisado_at", sa.DateTime(), nullable=True),
        sa.UniqueConstraint("acopio_id", "empresa", "origen_tipo", "origen_id", "huella", name="uq_tango_registro_version"),
        sa.CheckConstraint("estado IN ('PENDIENTE','CONSERVADO','DESCARTADO','SUPERADO')", name="ck_tango_revision"),
    )
    op.create_index("ix_tango_registros_acopio_id", "tango_registros", ["acopio_id"])


def downgrade():
    op.drop_table("tango_registros")