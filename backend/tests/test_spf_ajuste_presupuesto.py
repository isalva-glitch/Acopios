
"""Signed SPF budget adjustment, including the persisted consumption path."""
import asyncio
from datetime import date
from decimal import Decimal
from unittest.mock import MagicMock

import pytest

from integrations.spf.models import SpfPedido, SpfItem, SpfItemMedida, SpfItemComplemento
from integrations.spf.services import get_pedido_for_imputation
from models import Acopio, AcopioItem, Imputacion, Pedido
from routers.pedidos import PedidoConfirmSpf, create_pedido_from_spf


def spf_session(porcentaje, amounts, complementos=False):
    pedido = SpfPedido(
        id=23790, nro_pedido=23790, id_presupuesto=215040,
        estado_id=2, porcentaje_presupuesto=porcentaje,
    )
    items = []
    descriptions = ["Laminado 3+3 Incoloro", "Laminado 3+3 Esmerilado", "Templado 8 mm"]
    for index, amount in enumerate(amounts):
        item = SpfItem(
            id=index + 1, v_item_id=index + 1, v_presupuesto_id="215040",
            descripcion=descriptions[index], pedido=pedido,
        )
        item.medidas = [SpfItemMedida(
            cantidad=1, superficie=Decimal("1"), perimtero=Decimal("4"),
            total_item=Decimal(amount),
        )]
        item.complementos = (
            [SpfItemComplemento(cantidad=2, total_complemento=Decimal("50"))]
            if complementos else []
        )
        items.append(item)
    db = MagicMock()
    def query(model, *args):
        result = MagicMock()
        result.filter.return_value.all.return_value = items if model is SpfItem else []
        result.filter.return_value.first.return_value = pedido if model is SpfPedido else None
        return result
    db.query.side_effect = query
    return db


@pytest.mark.parametrize("percentage,expected", [
    (Decimal("-17.36"), Decimal("826.40")),
    (Decimal("17.36"), Decimal("1173.60")),
    (Decimal("0"), Decimal("1000.00")),
    (None, Decimal("1000.00")),
])
def test_signed_adjustment_includes_complements_once(percentage, expected):
    result = get_pedido_for_imputation(
        spf_session(percentage, ["900"], complementos=True), "23790"
    )
    item = result["items"][0]
    assert Decimal(str(item["subtotal_pesos"])) == Decimal("1000")
    assert Decimal(str(item["total_pesos"])) == expected
    assert Decimal(str(item["ajuste_pesos"])) == expected - Decimal("1000")
    assert Decimal(str(result["totals"]["pesos"])) == expected
    assert result["porcentaje_presupuesto"] == (float(percentage) if percentage is not None else None)
    assert item["total_unidades"] == 1
    assert item["total_m2"] == 1
    assert item["total_ml"] == 4


def test_rounds_each_item_before_summing():
    result = get_pedido_for_imputation(
        spf_session(Decimal("-50"), ["0.05", "0.05", "0.05"]), "23790"
    )
    assert [i["total_pesos"] for i in result["items"]] == [0.03, 0.03, 0.03]
    assert result["totals"]["pesos"] == 0.09


def test_23790_discount_reaches_imputaciones_and_saldo(db_session):
    source = spf_session(Decimal("-17.36"), ["1554439.36", "71443.06", "829389.32"])
    preview = get_pedido_for_imputation(source, "23790", learning_db=db_session)
    expected = [
        (Decimal(value) * Decimal("0.8264")).quantize(Decimal("0.01"))
        for value in ["1554439.36", "71443.06", "829389.32"]
    ]
    assert [Decimal(str(i["total_pesos"])) for i in preview["items"]] == expected
    acopio = Acopio(
        numero="000214948", v_presupuesto_id="000214948", fecha_alta=date.today(),
        total_pesos=Decimal("4876877.30"), saldo_pesos=Decimal("4876877.30"),
        total_m2=100, saldo_m2=100, total_ml=400, saldo_ml=400,
        total_unidades=100, saldo_unidades=100,
    )
    db_session.add(acopio)
    db_session.flush()
    for item in preview["items"]:
        db_session.add(AcopioItem(
            acopio_id=acopio.id, descripcion=item["descripcion"],
            cantidad=10, saldo_cantidad=10, total_m2=10, saldo_m2=10,
            total_ml=40, saldo_ml=40,
            total_pesos=Decimal("2000000"), saldo_pesos=Decimal("2000000"),
        ))
    db_session.commit()
    response = asyncio.run(create_pedido_from_spf(
        PedidoConfirmSpf(nro_pedido="23790", acopio_id=acopio.id),
        db=db_session, spf_db=source,
    ))
    rows = db_session.query(Imputacion).order_by(Imputacion.id).all()
    assert len(rows) == 3
    assert [r.cantidad_pesos for r in rows] == expected
    assert all(r.acopio_id == acopio.id and r.acopio_item_id is not None for r in rows)
    for row in rows:
        db_session.refresh(row.acopio_item)
        assert row.acopio_item.saldo_pesos == Decimal("2000000") - row.cantidad_pesos
    db_session.refresh(acopio)
    total = sum(expected)
    assert db_session.query(Pedido).one().total_pesos == total
    assert Decimal(str(response.total_pesos)) == total
    assert acopio.saldo_pesos == Decimal("4876877.30") - total
    assert preview["totals"]["pesos"] == response.total_pesos

