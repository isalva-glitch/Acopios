"""Glassware previews and source audit snapshots."""
from alembic import op
import sqlalchemy as sa

revision = 'a012b3c4d567'
down_revision = 'f901a2b3c456'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table('glassware_imports',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.Column('token', sa.String(36), nullable=False, unique=True),
        sa.Column('glassware_id', sa.String(30), nullable=False),
        sa.Column('numero', sa.String(50), nullable=False),
        sa.Column('datos', sa.JSON(), nullable=False),
        sa.Column('acopio_id', sa.Integer(), sa.ForeignKey('acopios.id'), nullable=True, unique=True))
    op.create_index('ix_glassware_imports_glassware_id', 'glassware_imports', ['glassware_id'])
    op.create_index('ix_glassware_imports_numero', 'glassware_imports', ['numero'])


def downgrade():
    op.drop_table('glassware_imports')
