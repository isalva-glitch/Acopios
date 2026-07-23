"""add_process_learning_tables

Revision ID: c5d6e7f8a901
Revises: b9b2f03f1d9f
Create Date: 2026-07-06 18:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'c5d6e7f8a901'
down_revision = 'b9b2f03f1d9f'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        'correcciones_proceso',
        sa.Column('acopio_id', sa.Integer(), nullable=True),
        sa.Column('acopio_item_id', sa.Integer(), nullable=True),
        sa.Column('pedido_id', sa.Integer(), nullable=True),
        sa.Column('origen', sa.String(length=40), nullable=False),
        sa.Column('estado', sa.String(length=40), nullable=False),
        sa.Column('texto_original', sa.Text(), nullable=False),
        sa.Column('texto_normalizado', sa.Text(), nullable=False),
        sa.Column('procesos_antes', sa.JSON(), nullable=False),
        sa.Column('procesos_despues', sa.JSON(), nullable=False),
        sa.Column('cambios', sa.JSON(), nullable=False),
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['acopio_id'], ['acopios.id']),
        sa.ForeignKeyConstraint(['acopio_item_id'], ['acopio_items.id']),
        sa.ForeignKeyConstraint(['pedido_id'], ['pedidos.id']),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_correcciones_proceso_acopio_id'), 'correcciones_proceso', ['acopio_id'], unique=False)
    op.create_index(op.f('ix_correcciones_proceso_acopio_item_id'), 'correcciones_proceso', ['acopio_item_id'], unique=False)
    op.create_index(op.f('ix_correcciones_proceso_id'), 'correcciones_proceso', ['id'], unique=False)
    op.create_index(op.f('ix_correcciones_proceso_pedido_id'), 'correcciones_proceso', ['pedido_id'], unique=False)

    op.create_table(
        'reglas_proceso',
        sa.Column('patron', sa.Text(), nullable=False),
        sa.Column('tipo_patron', sa.String(length=40), nullable=False),
        sa.Column('proceso', sa.String(length=100), nullable=False),
        sa.Column('accion', sa.String(length=20), nullable=False),
        sa.Column('alcance', sa.String(length=50), nullable=False),
        sa.Column('estado', sa.String(length=40), nullable=False),
        sa.Column('prioridad', sa.Integer(), nullable=False),
        sa.Column('soporte_count', sa.Integer(), nullable=False),
        sa.Column('confianza', sa.Numeric(precision=6, scale=4), nullable=False),
        sa.Column('ejemplos', sa.JSON(), nullable=False),
        sa.Column('creada_desde_correccion_id', sa.Integer(), nullable=True),
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['creada_desde_correccion_id'], ['correcciones_proceso.id']),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint(
            'patron',
            'proceso',
            'accion',
            'alcance',
            name='uq_regla_proceso_patron_proceso_accion_alcance',
        ),
    )
    op.create_index(op.f('ix_reglas_proceso_creada_desde_correccion_id'), 'reglas_proceso', ['creada_desde_correccion_id'], unique=False)
    op.create_index(op.f('ix_reglas_proceso_id'), 'reglas_proceso', ['id'], unique=False)


def downgrade() -> None:
    op.drop_index(op.f('ix_reglas_proceso_id'), table_name='reglas_proceso')
    op.drop_index(op.f('ix_reglas_proceso_creada_desde_correccion_id'), table_name='reglas_proceso')
    op.drop_table('reglas_proceso')
    op.drop_index(op.f('ix_correcciones_proceso_pedido_id'), table_name='correcciones_proceso')
    op.drop_index(op.f('ix_correcciones_proceso_id'), table_name='correcciones_proceso')
    op.drop_index(op.f('ix_correcciones_proceso_acopio_item_id'), table_name='correcciones_proceso')
    op.drop_index(op.f('ix_correcciones_proceso_acopio_id'), table_name='correcciones_proceso')
    op.drop_table('correcciones_proceso')
