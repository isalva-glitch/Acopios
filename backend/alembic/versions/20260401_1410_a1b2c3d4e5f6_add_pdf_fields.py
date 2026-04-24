"""Add PDF fields to presupuestos, acopio_items and acopio_item_panos.

Revision ID: a1b2c3d4e5f6
Revises: 58e60f26c21a
Create Date: 2026-04-01
"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic
revision = 'a1b2c3d4e5f6'
down_revision = '58e60f26c21a'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ── presupuestos ────────────────────────────────────────────────────────
    # Hacer fecha nullable (antes era NOT NULL)
    op.alter_column('presupuestos', 'fecha',
                    existing_type=sa.Date(),
                    nullable=True)
    # Nuevos campos PDF
    op.add_column('presupuestos',
                  sa.Column('empresa', sa.String(200), nullable=True))
    op.add_column('presupuestos',
                  sa.Column('contacto', sa.String(200), nullable=True))
    op.add_column('presupuestos',
                  sa.Column('cotizado_por', sa.String(100), nullable=True))
    op.add_column('presupuestos',
                  sa.Column('peso_estimado_kg', sa.Numeric(10, 2), nullable=True))

    # ── acopio_items ────────────────────────────────────────────────────────
    op.add_column('acopio_items',
                  sa.Column('numero_item', sa.Integer(), nullable=True))

    # ── acopio_item_panos ───────────────────────────────────────────────────
    op.add_column('acopio_item_panos',
                  sa.Column('denominacion', sa.String(50), nullable=True))


def downgrade() -> None:
    op.drop_column('acopio_item_panos', 'denominacion')
    op.drop_column('acopio_items', 'numero_item')
    op.drop_column('presupuestos', 'peso_estimado_kg')
    op.drop_column('presupuestos', 'cotizado_por')
    op.drop_column('presupuestos', 'contacto')
    op.drop_column('presupuestos', 'empresa')
    op.alter_column('presupuestos', 'fecha',
                    existing_type=sa.Date(),
                    nullable=False)
