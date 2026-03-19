"""Add SPF tracking fields to Acopio

Revision ID: 2b8d9f92e34a
Revises: bd85c5eb1f16
Create Date: 2026-03-17 15:15:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = '2b8d9f92e34a'
down_revision: Union[str, None] = 'bd85c5eb1f16'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Add new columns to 'acopios'
    op.add_column('acopios', sa.Column('v_presupuesto_id', sa.String(length=100), nullable=True))
    op.add_column('acopios', sa.Column('cliente_id', sa.Integer(), nullable=True))
    op.add_column('acopios', sa.Column('origen_datos', sa.String(length=50), nullable=False, server_default='spf_production'))
    
    # Create index on v_presupuesto_id
    op.create_index(op.f('ix_acopios_v_presupuesto_id'), 'acopios', ['v_presupuesto_id'], unique=False)
    
    # Alter obra_id to be nullable
    op.alter_column('acopios', 'obra_id', existing_type=sa.Integer(), nullable=True)


def downgrade() -> None:
    # Revert obra_id to not nullable
    op.alter_column('acopios', 'obra_id', existing_type=sa.Integer(), nullable=False)
    
    # Drop index
    op.drop_index(op.f('ix_acopios_v_presupuesto_id'), table_name='acopios')
    
    # Drop columns
    op.drop_column('acopios', 'origen_datos')
    op.drop_column('acopios', 'cliente_id')
    op.drop_column('acopios', 'v_presupuesto_id')
