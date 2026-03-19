"""Tests for SPF integration services."""
import pytest
from unittest.mock import MagicMock
from integrations.spf.services import search_presupuestos, get_presupuesto_details
from integrations.spf.models import SpfPedido, SpfItem, SpfItemMedida, SpfItemComplemento

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
    assert result["total_m2"] == 3.5  # (2*1.5) + (1*0.5)
    assert result["total_ml"] == 5.0  # (2*2.0) + (1*1.0)
    assert result["items_count"] == 2
    assert "items" in result
    assert result["items"][0]["cantidad"] == 3  # medida1 (2) + medida2 (1)
    assert len(result["items"][0]["panos"]) == 2
