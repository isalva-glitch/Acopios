"""Documentacion comercial de acopios; importes netos, sin modificar consumos.

Revision ID: d7e8f9a0b123
Revises: c5d6e7f8a901
"""
from alembic import op
import sqlalchemy as sa

revision = 'd7e8f9a0b123'
down_revision = 'c5d6e7f8a901'
branch_labels = None
depends_on = None


def upgrade():
    if op.get_bind().dialect.name == 'postgresql':
        with op.get_context().autocommit_block():
            op.execute("ALTER TYPE tipocomprobante ADD VALUE IF NOT EXISTS 'ORDEN_COMPRA'")
    op.add_column('acopios', sa.Column('porcentaje_facturado', sa.Numeric(5, 2), nullable=True))
    op.create_check_constraint('ck_acopio_porcentaje_facturado', 'acopios',
                               'porcentaje_facturado BETWEEN 0 AND 100')
    op.add_column('comprobantes', sa.Column('emisor', sa.String(200), nullable=False, server_default=''))
    op.add_column('comprobantes', sa.Column('iva', sa.Numeric(15, 2), nullable=True))
    op.add_column('comprobantes', sa.Column('documento_id', sa.Integer(), nullable=True))
    op.create_foreign_key('fk_comprobante_documento', 'comprobantes', 'documentos', ['documento_id'], ['id'])
    op.create_unique_constraint('uq_comprobante_identidad', 'comprobantes', ['tipo', 'numero', 'emisor'])
    op.add_column('afectaciones_acopio', sa.Column('importe_facturado', sa.Numeric(15, 2), nullable=True))
    op.add_column('afectaciones_acopio', sa.Column('referencia_id', sa.Integer(), nullable=True))
    op.add_column('afectaciones_acopio', sa.Column('anulada', sa.Boolean(), nullable=False, server_default=sa.false()))
    op.create_index('ix_afectaciones_acopio_referencia_id', 'afectaciones_acopio', ['referencia_id'])
    op.create_foreign_key('fk_afectacion_referencia', 'afectaciones_acopio', 'afectaciones_acopio', ['referencia_id'], ['id'], ondelete='SET NULL')
    op.create_check_constraint('ck_afectacion_reparto', 'afectaciones_acopio',
                              'importe_facturado IS NULL OR (importe_facturado >= 0 AND importe_facturado <= importe)')


def downgrade():
    op.drop_constraint('ck_afectacion_reparto', 'afectaciones_acopio', type_='check')
    op.drop_constraint('fk_afectacion_referencia', 'afectaciones_acopio', type_='foreignkey')
    op.drop_index('ix_afectaciones_acopio_referencia_id', table_name='afectaciones_acopio')
    for column in ('anulada', 'referencia_id', 'importe_facturado'):
        op.drop_column('afectaciones_acopio', column)
    op.drop_constraint('uq_comprobante_identidad', 'comprobantes', type_='unique')
    op.drop_constraint('fk_comprobante_documento', 'comprobantes', type_='foreignkey')
    for column in ('documento_id', 'iva', 'emisor'):
        op.drop_column('comprobantes', column)
    op.drop_constraint('ck_acopio_porcentaje_facturado', 'acopios', type_='check')
    op.drop_column('acopios', 'porcentaje_facturado')
    # PostgreSQL conserva ORDEN_COMPRA en el enum para no alterar comprobantes historicos.
