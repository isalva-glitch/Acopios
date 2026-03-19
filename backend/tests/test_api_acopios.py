"""Tests for acopios API."""
import pytest
from datetime import date


def test_health_check(client):
    """Test health check endpoint."""
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "healthy"}


def test_list_acopios_empty(client):
    """Test listing acopios when database is empty."""
    response = client.get("/acopios")
    assert response.status_code == 200
    assert response.json() == []


def test_create_acopio_from_package(client, db_session):
    """Test creating acopio from extraction package."""
    # Create a minimal extraction package
    package = {
        "meta": {
            "extraction_date": "2024-01-01T00:00:00",
            "pdf_filename": "test.pdf",
            "pdf_hash": "a" * 64,
            "extractor_version": "1.0.0"
        },
        "acopio": {
            "numero": "TEST001",
            "fecha_alta": "2024-01-01",
            "obra": "Obra Test",
            "cliente": "Cliente Test",
            "total_m2": 100.5,
            "total_ml": 50.25,
            "total_pesos": 10000.00
        },
        "presupuestos": [
            {
                "numero": "TEST001",
                "fecha": "2024-01-01",
                "condiciones": "Test",
                "estado": "ACTIVO"
            }
        ],
        "items": [],
        "panos": [],
        "pedidos": [],
        "remitos": [],
        "imputaciones": [],
        "comprobantes": [],
        "afectaciones_acopio": [],
        "documentos": [
            {
                "tipo_documento": "presupuesto_original",
                "nombre_archivo": "test.pdf",
                "hash": "a" * 64
            }
        ],
        "warnings": []
    }
    
    response = client.post("/acopios/confirm", json={"extraction_package": package})
    
    assert response.status_code == 200
    data = response.json()
    assert data["numero"] == "TEST001"
    assert float(data["total_m2"]) == 100.5
    assert float(data["saldo_m2"]) == 100.5  # Initially, saldo = total


def test_get_acopio_detail(client, db_session):
    """Test getting acopio detail."""
    # First create an acopio
    package = {
        "meta": {
            "extraction_date": "2024-01-01T00:00:00",
            "pdf_filename": "test.pdf",
            "pdf_hash": "b" * 64,
            "extractor_version": "1.0.0"
        },
        "acopio": {
            "numero": "TEST002",
            "fecha_alta": "2024-01-01",
            "obra": "Obra Test 2",
            "cliente": "Cliente Test 2",
            "total_m2": 200.0,
            "total_ml": 100.0,
            "total_pesos": 20000.00
        },
        "presupuestos": [],
        "items": [],
        "panos": [],
        "pedidos": [],
        "remitos": [],
        "imputaciones": [],
        "comprobantes": [],
        "afectaciones_acopio": [],
        "documentos": [],
        "warnings": []
    }
    
    create_response = client.post("/acopios/confirm", json={"extraction_package": package})
    acopio_id = create_response.json()["id"]
    
    # Get detail
    response = client.get(f"/acopios/{acopio_id}")
    assert response.status_code == 200
    data = response.json()
    assert data["numero"] == "TEST002"
    assert data["obra"]["nombre"] == "Obra Test 2"
