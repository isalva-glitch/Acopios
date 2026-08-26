import pytest
from datetime import date
from decimal import Decimal
from fastapi.testclient import TestClient
from models import Acopio, Obra, Cliente, Presupuesto
from sqlalchemy.orm import Session

def test_list_acopios_with_null_numero(client: TestClient, db_session: Session):
    """Verifica que un acopio con número nulo no rompe el listado (Error 422)."""
    # Crear un acopio mínimo con número nulo
    acopio = Acopio(
        numero=None,
        fecha_alta=date.today(),
        total_m2=Decimal("10.5"),
        total_ml=Decimal("5.0"),
        total_pesos=Decimal("1500.0"),
        total_unidades=1,
        saldo_m2=Decimal("10.5"),
        saldo_ml=Decimal("5.0"),
        saldo_pesos=Decimal("1500.0"),
        saldo_unidades=1
    )
    db_session.add(acopio)
    db_session.commit()
    db_session.refresh(acopio)

    response = client.get("/acopios")
    assert response.status_code == 200
    data = response.json()
    assert len(data) >= 1
    # Buscar el acopio creado
    found = next((a for a in data if a["id"] == acopio.id), None)
    assert found is not None
    assert found["numero"] is None

def test_confirm_pdf_with_missing_fields_in_payload(client: TestClient, db_session: Session):
    """Verifica que la confirmación de PDF no rompe si faltan campos opcionales en el resultado."""
    # Este test valida que el router maneje correctamente la construcción de AcopioCreationResult
    # aunque algunos campos del acopio recién creado sean nulos.
    
    # Simular un paquete de extracción que resultará en datos mínimos
    payload = {
        "extraction_package": {
            "presupuesto": {
                "numero": "TEST-NULL-FIELDS",
                "empresa": "Empresa Test",
                "contacto": None,
                "estado": "Aprobado",
                "cotizado_por": None,
                "fecha_aprobacion": None,
                "total_unidades": 1,
                "total_importe": 1000.0,
                "total_m2": 2.0,
                "total_ml": 1.0,
                "peso_estimado_kg": 50.0
            },
            "items": [
                {
                    "numero_item": 1,
                    "descripcion": "Item Test",
                    "cantidad": 1,
                    "total_pesos": 1000.0,
                    "total_m2": 2.0,
                    "total_ml": 1.0,
                    "panos": [
                        {
                            "row_no": 1,
                            "cantidad": 1,
                            "ancho_mm": 1000,
                            "alto_mm": 2000,
                            "superficie_m2": 2.0,
                            "perimetro_ml": 1.0,
                            "denominacion": None,
                            "precio_unitario": 1000.0,
                            "precio_total": 1000.0
                        }
                    ]
                }
            ],
            "warnings": []
        }
    }

    response = client.post("/acopios/confirm-pdf", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert data["success"] is True
    assert data["acopio_id"] is not None
    # Verificar que numero_presupuesto y cliente se manejen bien aunque sean null en DB
    # Nota: El servicio de creación podría estar seteando el número del presupuesto al acopio.


def test_items_precios_referencia_custom_origen(client: TestClient, db_session: Session):
    """Verifica que orígenes de precios no estándar no causen error 500 al consultar el endpoint."""
    from models import AcopioItem, AcopioItemPrecioReferencia

    acopio = Acopio(
        numero="ROBUST01",
        fecha_alta=date.today(),
        total_m2=Decimal("10.0"),
        total_ml=Decimal("5.0"),
        total_pesos=Decimal("1000.0"),
        total_unidades=1,
        saldo_m2=Decimal("10.0"),
        saldo_ml=Decimal("5.0"),
        saldo_pesos=Decimal("1000.0"),
        saldo_unidades=1
    )
    db_session.add(acopio)
    db_session.commit()

    item = AcopioItem(
        acopio_id=acopio.id,
        descripcion="Item Test Custom Origen",
        proceso_vidrio_exterior=True,
        total_m2=Decimal("10.0"),
        total_ml=Decimal("5.0"),
        total_pesos=Decimal("1000.0"),
        saldo_m2=Decimal("10.0"),
        saldo_ml=Decimal("5.0"),
        saldo_pesos=Decimal("1000.0")
    )
    db_session.add(item)
    db_session.commit()

    ref = AcopioItemPrecioReferencia(
        acopio_id=acopio.id,
        acopio_item_id=item.id,
        concepto="vidrio_exterior",
        unidad="m2",
        precio_base=Decimal("100.0"),
        precio_actual=Decimal("100.0"),
        habilitado=True,
        origen="origen_custom_no_standard"
    )
    db_session.add(ref)
    db_session.commit()

    response = client.get(f"/acopios/{acopio.id}/items-precios-referencia")
    assert response.status_code == 200
    data = response.json()
    assert data["acopio_id"] == acopio.id
    assert len(data["items"]) == 1
    assert data["items"][0]["conceptos"][0]["origen"] == "origen_custom_no_standard"

