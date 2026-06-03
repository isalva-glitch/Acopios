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


def test_filtrar_codigos_panos_y_numeros_puros():
    # Verify that panel marks (pa13, pv2, pfa10), "pdf" extension, and order IDs (23095) are filtered out,
    # resulting in a Jaccard score of 1.0 (exact match) for otherwise identical glass.
    acopio = normalizar_composicion([
        "Laminado 4+4 Incoloro con filos matados pdf pa5 pa10 pa6 pa11 pfa2 23095"
    ])
    pedido = normalizar_composicion([
        "Laminado 4+4 Incoloro con filos matados pa13 pa14 pa4 pa7 pa11 pfa5 pfa7 pf07 23095"
    ])

    score, diferencias = comparar_composiciones(acopio, pedido)
    assert score == Decimal("1.0000")
    assert diferencias == ()


def test_advertencia_diferencia_material_sin_procesos():
    acopio_items = [
        _item(1, "Laminado 4+4 Incoloro especial grande")
    ]
    pedido_comp = normalizar_composicion([
        "Laminado 4+4 Incoloro comun chico"
    ])

    match = encontrar_item_por_composicion(acopio_items, pedido_comp)
    assert match.estado == MATCH_CHANGED
    assert match.advertencia == "La composicion del pedido difiere de la composicion del acopio en los componentes de material."
    assert match.diferencias_procesos == ()


def test_cambio_material_se_registra_como_evento_no_equivalencia_global():
    acopio_items = [
        _item(1, "DVH Eclipse Advantage Grey + Camara 12 Estructural + Templado Float 6 Incoloro + Pegado estructural"),
    ]
    pedido_comp = normalizar_composicion([
        "DVH Eclipse Advantage Grey + Templado 5 / 6 Low E + Camara 12 Estructural + Laminado 3+3 Incoloro + Pegado estructural"
    ])

    match = encontrar_item_por_composicion(acopio_items, pedido_comp)

    assert match.item.id == 1
    assert match.estado == MATCH_CHANGED
    assert match.diferencias_procesos == ()
    assert match.advertencia == (
        "Evento de cambio de material detectado: contratado Templado 6, Float; "
        "pedido Laminado 3+3."
    )


def test_cambio_material_no_desplaza_item_offset_opacificado():
    acopio_items = [
        _item(1, "DVH Eclipse Advantage Grey + Camara 12 Estructural + Templado Float 6 Incoloro + Pegado estructural"),
        _item(4, "DVH Eclipse Advantage Grey + Camara 12 Estructural Offset + Templado Float 6 Incoloro + Opacificado negro en bandas o parciales + Pegado estructural"),
    ]
    pedido_comp = normalizar_composicion([
        "DVH Eclipse Advantage Grey + Templado 5 / 6 Low E + Camara 12 Estructural Offset + Laminado 3+3 Incoloro + Opacificado perimetral + Pegado estructural"
    ])

    match = encontrar_item_por_composicion(acopio_items, pedido_comp)

    assert match.item.id == 4
    assert match.estado == MATCH_CHANGED
    assert match.advertencia == (
        "Evento de cambio de material detectado: contratado Templado 6, Float; "
        "pedido Laminado 3+3."
    )
    assert match.diferencias_procesos == ()
