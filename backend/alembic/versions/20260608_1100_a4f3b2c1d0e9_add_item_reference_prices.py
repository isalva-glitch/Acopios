"""Add item-scoped reference prices

Revision ID: a4f3b2c1d0e9
Revises: c7a4d8e9f012
Create Date: 2026-06-08 11:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'a4f3b2c1d0e9'
down_revision = 'c7a4d8e9f012'
branch_labels = None
depends_on = None


PROCESS_COLUMNS = [
    ("vidrio_exterior", "m2"),
    ("vidrio_interior", "m2"),
    ("camara_estructural", "ml"),
    ("pulido", "ml"),
    ("fason_templado_exterior", "m2"),
    ("pegado_bastidor", "ml"),
    ("camara_normal", "ml"),
    ("opacificado_perimetral", "ml"),
    ("opacificado_total", "m2"),
    ("camara_offset", "ml"),
]


def upgrade() -> None:
    op.create_table(
        'acopio_item_precios_referencia',
        sa.Column('acopio_id', sa.Integer(), nullable=False),
        sa.Column('acopio_item_id', sa.Integer(), nullable=False),
        sa.Column('concepto', sa.String(length=80), nullable=False),
        sa.Column('unidad', sa.String(length=20), nullable=False),
        sa.Column('precio_base', sa.Numeric(precision=15, scale=2), nullable=True),
        sa.Column('precio_actual', sa.Numeric(precision=15, scale=2), nullable=True),
        sa.Column('habilitado', sa.Boolean(), nullable=False),
        sa.Column('origen', sa.String(length=40), nullable=False),
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['acopio_id'], ['acopios.id']),
        sa.ForeignKeyConstraint(['acopio_item_id'], ['acopio_items.id']),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint(
            'acopio_item_id',
            'concepto',
            name='uq_acopio_item_precio_referencia_item_concepto',
        ),
    )
    op.create_index(
        op.f('ix_acopio_item_precios_referencia_acopio_id'),
        'acopio_item_precios_referencia',
        ['acopio_id'],
        unique=False,
    )
    op.create_index(
        op.f('ix_acopio_item_precios_referencia_acopio_item_id'),
        'acopio_item_precios_referencia',
        ['acopio_item_id'],
        unique=False,
    )
    op.create_index(
        op.f('ix_acopio_item_precios_referencia_id'),
        'acopio_item_precios_referencia',
        ['id'],
        unique=False,
    )

    connection = op.get_bind()
    for concepto, unidad in PROCESS_COLUMNS:
        process_column = f"proceso_{concepto}"
        connection.execute(
            sa.text(f"""
                INSERT INTO acopio_item_precios_referencia (
                    acopio_id,
                    acopio_item_id,
                    concepto,
                    unidad,
                    precio_base,
                    precio_actual,
                    habilitado,
                    origen,
                    created_at,
                    updated_at
                )
                SELECT
                    ai.acopio_id,
                    ai.id,
                    :concepto,
                    :unidad,
                    pr.{concepto},
                    pr.{concepto},
                    true,
                    'migrado',
                    CURRENT_TIMESTAMP,
                    CURRENT_TIMESTAMP
                FROM acopio_items ai
                JOIN precios_referencia pr ON pr.acopio_id = ai.acopio_id
                WHERE ai.{process_column} = true
            """),
            {"concepto": concepto, "unidad": unidad},
        )


def downgrade() -> None:
    op.drop_index(
        op.f('ix_acopio_item_precios_referencia_id'),
        table_name='acopio_item_precios_referencia',
    )
    op.drop_index(
        op.f('ix_acopio_item_precios_referencia_acopio_item_id'),
        table_name='acopio_item_precios_referencia',
    )
    op.drop_index(
        op.f('ix_acopio_item_precios_referencia_acopio_id'),
        table_name='acopio_item_precios_referencia',
    )
    op.drop_table('acopio_item_precios_referencia')
