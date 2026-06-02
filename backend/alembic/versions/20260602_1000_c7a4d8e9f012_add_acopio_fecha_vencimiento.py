"""Add acopio expiration date

Revision ID: c7a4d8e9f012
Revises: 2b6d8f4c1a90
Create Date: 2026-06-02 10:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'c7a4d8e9f012'
down_revision = '2b6d8f4c1a90'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column('acopios', sa.Column('fecha_vencimiento', sa.Date(), nullable=True))


def downgrade() -> None:
    op.drop_column('acopios', 'fecha_vencimiento')
