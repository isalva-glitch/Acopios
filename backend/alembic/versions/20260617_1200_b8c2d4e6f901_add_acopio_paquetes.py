"""Add acopio paquetes

Revision ID: b8c2d4e6f901
Revises: a4f3b2c1d0e9
Create Date: 2026-06-17 12:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'b8c2d4e6f901'
down_revision = 'a4f3b2c1d0e9'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        'acopio_paquetes',
        sa.Column('numero', sa.String(length=50), nullable=True),
        sa.Column('nombre', sa.String(length=200), nullable=False),
        sa.Column('cliente', sa.String(length=200), nullable=False),
        sa.Column('fecha_alta', sa.Date(), nullable=False),
        sa.Column('estado', sa.String(length=50), nullable=False),
        sa.Column('observaciones', sa.Text(), nullable=True),
        sa.Column('total_pesos', sa.Numeric(precision=15, scale=2), nullable=False),
        sa.Column('total_m2', sa.Numeric(precision=12, scale=2), nullable=False),
        sa.Column('total_ml', sa.Numeric(precision=12, scale=2), nullable=False),
        sa.Column('total_unidades', sa.Integer(), nullable=False),
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('numero'),
    )
    op.create_index(op.f('ix_acopio_paquetes_id'), 'acopio_paquetes', ['id'], unique=False)
    op.create_index(op.f('ix_acopio_paquetes_numero'), 'acopio_paquetes', ['numero'], unique=False)

    op.add_column('acopios', sa.Column('paquete_id', sa.Integer(), nullable=True))
    op.create_index(op.f('ix_acopios_paquete_id'), 'acopios', ['paquete_id'], unique=False)
    op.create_foreign_key(
        'fk_acopios_paquete_id_acopio_paquetes',
        'acopios',
        'acopio_paquetes',
        ['paquete_id'],
        ['id'],
    )


def downgrade() -> None:
    op.drop_constraint('fk_acopios_paquete_id_acopio_paquetes', 'acopios', type_='foreignkey')
    op.drop_index(op.f('ix_acopios_paquete_id'), table_name='acopios')
    op.drop_column('acopios', 'paquete_id')

    op.drop_index(op.f('ix_acopio_paquetes_numero'), table_name='acopio_paquetes')
    op.drop_index(op.f('ix_acopio_paquetes_id'), table_name='acopio_paquetes')
    op.drop_table('acopio_paquetes')
