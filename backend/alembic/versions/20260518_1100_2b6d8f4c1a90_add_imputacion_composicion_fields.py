"""Add composition matching fields to imputaciones

Revision ID: 2b6d8f4c1a90
Revises: 8c4d2f1e9a30
Create Date: 2026-05-18 11:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '2b6d8f4c1a90'
down_revision = '8c4d2f1e9a30'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column('imputaciones', sa.Column('pedido_item_descripcion', sa.String(length=500), nullable=True))
    op.add_column('imputaciones', sa.Column('composicion_normalizada', sa.String(length=1200), nullable=True))
    op.add_column('imputaciones', sa.Column('composicion_match_estado', sa.String(length=50), nullable=True))
    op.add_column('imputaciones', sa.Column('composicion_match_score', sa.Numeric(6, 4), nullable=True))
    op.add_column('imputaciones', sa.Column('composicion_advertencia', sa.String(length=1200), nullable=True))


def downgrade() -> None:
    op.drop_column('imputaciones', 'composicion_advertencia')
    op.drop_column('imputaciones', 'composicion_match_score')
    op.drop_column('imputaciones', 'composicion_match_estado')
    op.drop_column('imputaciones', 'composicion_normalizada')
    op.drop_column('imputaciones', 'pedido_item_descripcion')
