from types import SimpleNamespace
from decimal import Decimal

from services.composicion_normalization import (
    MATCH_CHANGED,
    MATCH_EQUIVALENT,
    comparar_composiciones,
    encontrar_item_por_composicion,
    normalizar_composicion,
)


def _item(item_id: int, descripcion: str):
    return SimpleNamespace(
        id=item_id,
        descripcion=descripcion,
        material="",
        tipologia="",
        panos=[],
        adicionales=[],
    )


def test_composicion_equivalente_con_distinto_orden_y_separadores():
    acopio = normalizar_composicion([
        "ECLIP.ADV.GREY BP TEM + CAMARA 12 NORMAL + TEMPLADO DE 6 MM"
    ])
    pedido = normalizar_composicion([
        "Templado Float 6 incoloro / Camara 12 normal / Eclipse Advantage Grey con bordes pulidos"
    ])

    score, diferencias = comparar_composiciones(acopio, pedido)

    assert score >= Decimal("0.7000")
    assert diferencias == ()


def test_matching_usa_composicion_y_advierte_cambios():
    acopio_items = [
        _item(1, "Eclipse Advantage Grey + Camara 12 estructural + Templado Float 6 + Pegado estructural"),
        _item(2, "Laminado 3+3 incoloro"),
    ]
    pedido_comp = normalizar_composicion([
        "Eclipse Advantage Grey + Camara 12 offset + Templado Float 6 + Pegado estructural"
    ])

    match = encontrar_item_por_composicion(acopio_items, pedido_comp)

    assert match.item.id == 1
    assert match.estado == MATCH_CHANGED
    assert match.advertencia
    assert "camara_estructural" in match.diferencias_procesos
    assert "camara_offset" in match.diferencias_procesos


def test_matching_no_depende_del_numero_de_item():
    acopio_items = [
        _item(1, "Laminado 3+3 incoloro"),
        _item(2, "Eclipse Advantage Grey + Camara 12 normal + Templado Float 6"),
    ]
    pedido_comp = normalizar_composicion([
        "Templado Float 6 + Eclipse Advantage Grey + Camara 12 normal"
    ])

    match = encontrar_item_por_composicion(acopio_items, pedido_comp)

    assert match.item.id == 2
    assert match.estado in {MATCH_EQUIVALENT, "exacta"}
