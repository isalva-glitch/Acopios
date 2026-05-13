"""Add imputation process snapshots

Revision ID: 8c4d2f1e9a30
Revises: 6f3a7b2d9c01
Create Date: 2026-05-13 14:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '8c4d2f1e9a30'
down_revision = '6f3a7b2d9c01'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        'imputacion_procesos',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.Column('proceso', sa.String(length=100), nullable=False),
        sa.Column('unidad', sa.String(length=10), nullable=False),
        sa.Column('cantidad', sa.Numeric(14, 4), nullable=False),
        sa.Column('origen', sa.String(length=50), nullable=False),
        sa.Column('imputacion_id', sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(['imputacion_id'], ['imputaciones.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('imputacion_id', 'proceso', name='uq_imputacion_proceso'),
    )
    op.create_index(
        op.f('ix_imputacion_procesos_id'),
        'imputacion_procesos',
        ['id'],
        unique=False,
    )
    op.create_index(
        op.f('ix_imputacion_procesos_imputacion_id'),
        'imputacion_procesos',
        ['imputacion_id'],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(op.f('ix_imputacion_procesos_imputacion_id'), table_name='imputacion_procesos')
    op.drop_index(op.f('ix_imputacion_procesos_id'), table_name='imputacion_procesos')
    op.drop_table('imputacion_procesos')
