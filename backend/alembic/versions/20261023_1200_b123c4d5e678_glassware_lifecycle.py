"""Retain Glassware audit records when an imported acopio is deleted."""
from alembic import op
import sqlalchemy as sa

revision = 'b123c4d5e678'
down_revision = 'a012b3c4d567'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column('glassware_imports', sa.Column('confirmado_en', sa.DateTime(), nullable=True))
    op.execute('UPDATE glassware_imports SET confirmado_en = updated_at WHERE acopio_id IS NOT NULL')
    op.drop_constraint('glassware_imports_acopio_id_fkey', 'glassware_imports', type_='foreignkey')
    op.create_foreign_key('glassware_imports_acopio_id_fkey', 'glassware_imports', 'acopios', ['acopio_id'], ['id'], ondelete='SET NULL')


def downgrade():
    op.drop_constraint('glassware_imports_acopio_id_fkey', 'glassware_imports', type_='foreignkey')
    op.create_foreign_key('glassware_imports_acopio_id_fkey', 'glassware_imports', 'acopios', ['acopio_id'], ['id'])
    op.drop_column('glassware_imports', 'confirmado_en')
