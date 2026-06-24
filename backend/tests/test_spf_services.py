"""Tests for SPF integration services."""
import pytest
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import MagicMock
from integrations.spf.services import (
    _normalize_presupuesto_id,
    _spf_cliente_display_name,
    get_pedido_for_imputation,
    search_presupuestos,
    get_presupuesto_details,
)
from integrations.spf.models import SpfPedido, SpfItem, SpfItemMedida, SpfItemComplemento


def test_normalize_presupuesto_id_pads_numeric_values():
    assert _normalize_presupuesto_id("212455") == "000212455"
    assert _normalize_presupuesto_id("000212455") == "000212455"
    assert _normalize_presupuesto_id("P123") == "P123"


def test_spf_cliente_display_name_prefers_business_name_over_contact_name():
    cliente = SimpleNamespace(
        nombre="Lucas",
        apellido="Open  World  Ow",
        razon_social="Open  World  Ow",
        nombre_corto=None,
        descripcion="CARPINTERO",
    )

    assert _spf_cliente_display_name(cliente) == "Open World Ow"


def test_search_presupuestos_empty_query():
    """Test search early exits on empty query."""
    mock_db = MagicMock()
    results = search_presupuestos(mock_db, "")
    assert results == []
    mock_db.query.assert_not_called()

def test_get_presupuesto_details_not_found():
    """Test details returns None when budget not found."""
    mock_db = MagicMock()
    
    mock_query = MagicMock()
    mock_query.filter.return_value.all.return_value = []
    mock_db.query.return_value = mock_query
    
    result = get_presupuesto_details(mock_db, "NOT_EXIST")
    assert result is None

def test_get_presupuesto_details_aggregates():
    """Test details aggregates m2, ml, and pesos correctly."""
    mock_db = MagicMock()
    
    # Create mock entities
    pedido = SpfPedido(nro_pedido="PED1", cliente_id=99)
    
    item1 = SpfItem(id=1, v_presupuesto_id="P123", pedido=pedido)
    medida1 = SpfItemMedida(cantidad=2, superficie=1.5, perimtero=2.0, total_item=100.0)
    medida2 = SpfItemMedida(cantidad=1, superficie=0.5, perimtero=1.0, total_item=50.0)
    item1.medidas = [medida1, medida2]
    
    comp1 = SpfItemComplemento(cantidad=1, total_complemento=25.0)
    item1.complementos = [comp1]
    
    item2 = SpfItem(id=2, v_presupuesto_id="P123", pedido=pedido)
    item2.medidas = []
    item2.complementos = []
    
    mock_query = MagicMock()
    mock_query.filter.return_value.all.return_value = [item1, item2]
    mock_db.query.return_value = mock_query
    
    # Execute
    result = get_presupuesto_details(mock_db, "P123")
    
    # Assert returns
    assert result is not None
    assert result["v_presupuesto_id"] == "P123"
    assert result["cliente_id"] == 99
    assert result["total_m2"] == 2.0  # 1.5 + 0.5 (already subtotals)
    assert result["total_ml"] == 3.0  # 2.0 + 1.0 (already subtotals)
    assert result["items_count"] == 2
    assert "items" in result
    assert result["items"][0]["cantidad"] == 3  # medida1 (2) + medida2 (1)
    assert len(result["items"][0]["panos"]) == 2


def test_get_pedido_for_imputation_uses_decimal_for_money_totals():
    mock_db = MagicMock()

    pedido = SpfPedido(id=23365, nro_pedido=23365, id_presupuesto=212455, estado_id=3)
    item = SpfItem(
        id=1,
        v_item_id=1,
        v_presupuesto_id="212455",
        descripcion="Laminado 4+4 Gris Claro con Borde Pulido",
    )
    item.medidas = [
        SpfItemMedida(
            cantidad=19,
            superficie=Decimal("16.61"),
            perimtero=Decimal("73.41"),
            total_item=Decimal("1128417.60"),
        )
    ]
    item.complementos = [
        SpfItemComplemento(cantidad=1, total_complemento=Decimal("0.10")),
        SpfItemComplemento(cantidad=1, total_complemento=Decimal("0.20")),
    ]

    pedido_query = MagicMock()
    pedido_query.filter.return_value.first.return_value = pedido
    items_query = MagicMock()
    items_query.filter.return_value.all.return_value = [item]
    talonario_query = MagicMock()
    talonario_query.filter.return_value.all.return_value = []
    mock_db.query.side_effect = [pedido_query, items_query, talonario_query]

    result = get_pedido_for_imputation(mock_db, "23365")

    assert Decimal(str(result["items"][0]["total_pesos"])) == Decimal("1128417.90")
    assert Decimal(str(result["totals"]["pesos"])) == Decimal("1128417.90")
    assert str(result["items"][0]["total_pesos"]) != "1128417.9000000001"

