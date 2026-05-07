"""Add item process flags

Revision ID: 9f2c1d7a6b8e
Revises: 4b842cc9d075
Create Date: 2026-05-07 11:45:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '9f2c1d7a6b8e'
down_revision = '4b842cc9d075'
branch_labels = None
depends_on = None


PROCESS_COLUMNS = [
    'proceso_vidrio_exterior',
    'proceso_vidrio_interior',
    'proceso_camara_estructural',
    'proceso_pulido',
    'proceso_fason_templado_exterior',
    'proceso_pegado_bastidor',
    'proceso_camara_normal',
    'proceso_opacificado_perimetral',
    'proceso_opacificado_total',
    'proceso_camara_offset',
]


def upgrade() -> None:
    for column_name in PROCESS_COLUMNS:
        op.add_column(
            'acopio_items',
            sa.Column(
                column_name,
                sa.Boolean(),
                nullable=False,
                server_default=sa.false(),
            ),
        )

    for column_name in PROCESS_COLUMNS:
        op.alter_column('acopio_items', column_name, server_default=None)


def downgrade() -> None:
    for column_name in reversed(PROCESS_COLUMNS):
        op.drop_column('acopio_items', column_name)
