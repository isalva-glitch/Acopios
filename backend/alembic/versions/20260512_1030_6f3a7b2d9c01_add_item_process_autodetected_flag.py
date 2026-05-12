"""Add item process autodetected flag

Revision ID: 6f3a7b2d9c01
Revises: 9f2c1d7a6b8e
Create Date: 2026-05-12 10:30:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '6f3a7b2d9c01'
down_revision = '9f2c1d7a6b8e'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        'acopio_items',
        sa.Column(
            'procesos_autodetectados',
            sa.Boolean(),
            nullable=False,
            server_default=sa.false(),
        ),
    )
    op.alter_column('acopio_items', 'procesos_autodetectados', server_default=None)


def downgrade() -> None:
    op.drop_column('acopio_items', 'procesos_autodetectados')
