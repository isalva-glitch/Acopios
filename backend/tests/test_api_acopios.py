"""Tests for acopios API."""
import pytest
from datetime import date
from decimal import Decimal

from models import Acopio, AcopioItem, Cliente, Imputacion, Obra, Pedido, PrecioReferencia


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
    assert data["fecha_vencimiento"] is None


def test_update_acopio_fecha_vencimiento(client, db_session):
    """Test manually setting the required acopio expiration date."""
    package = {
        "meta": {
            "extraction_date": "2024-01-01T00:00:00",
            "pdf_filename": "test.pdf",
            "pdf_hash": "c" * 64,
            "extractor_version": "1.0.0"
        },
        "acopio": {
            "numero": "TEST003",
            "fecha_alta": "2024-01-01",
            "obra": "Obra Test 3",
            "cliente": "Cliente Test 3",
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

    empty_response = client.patch(f"/acopios/{acopio_id}", json={})
    assert empty_response.status_code == 422

    update_response = client.patch(
        f"/acopios/{acopio_id}",
        json={"fecha_vencimiento": "2026-12-31"}
    )
    assert update_response.status_code == 200
    assert update_response.json()["fecha_vencimiento"] == "2026-12-31"

    detail_response = client.get(f"/acopios/{acopio_id}")
    assert detail_response.status_code == 200
    assert detail_response.json()["fecha_vencimiento"] == "2026-12-31"


def _create_stale_precision_excedente(db_session):
    cliente = Cliente(nombre="Cliente Precision")
    db_session.add(cliente)
    db_session.flush()

    obra = Obra(nombre="Obra Precision", cliente_id=cliente.id)
    db_session.add(obra)
    db_session.flush()

    acopio = Acopio(
        numero="PRECISION-EXC",
        obra_id=obra.id,
        fecha_alta=date(2024, 1, 1),
        total_m2=Decimal("16.62"),
        total_ml=Decimal("73.41"),
        total_pesos=Decimal("1128417.90"),
        total_unidades=19,
        saldo_m2=Decimal("0.01"),
        saldo_ml=Decimal("0.00"),
        saldo_pesos=Decimal("0.00"),
        saldo_unidades=0,
    )
    db_session.add(acopio)
    db_session.flush()

    item = AcopioItem(
        acopio_id=acopio.id,
        numero_item=1,
        descripcion="Laminado 4+4 Gris Claro con Borde Pulido",
        cantidad=19,
        total_m2=Decimal("16.62"),
        total_ml=Decimal("73.41"),
        total_pesos=Decimal("1128417.90"),
        saldo_m2=Decimal("0.01"),
        saldo_ml=Decimal("0.00"),
        saldo_pesos=Decimal("0.00"),
        saldo_cantidad=0,
    )
    pedido = Pedido(
        numero="23365",
        obra_id=obra.id,
        fecha=date(2024, 6, 23),
        total_m2=Decimal("16.61"),
        total_ml=Decimal("73.41"),
        total_pesos=Decimal("1128417.90"),
    )
    db_session.add_all([item, pedido])
    db_session.flush()

    imputacion = Imputacion(
        pedido_id=pedido.id,
        acopio_id=acopio.id,
        acopio_item_id=item.id,
        cantidad_m2=Decimal("16.61"),
        cantidad_ml=Decimal("73.41"),
        cantidad_pesos=Decimal("1128417.90"),
        cantidad_unidades=19,
        es_excedente=True,
        excedente_tipo="ITEM",
        excedente_motivo="Item viejo: consumo acumulado pesos 1128417.9000000001 excede saldo 1128417.90",
    )
    db_session.add(imputacion)
    db_session.commit()

    return acopio, pedido, imputacion


def _create_real_money_excedente(db_session, tipo: str):
    cliente = Cliente(nombre=f"Cliente Excedente {tipo}")
    db_session.add(cliente)
    db_session.flush()

    obra = Obra(nombre=f"Obra Excedente {tipo}", cliente_id=cliente.id)
    db_session.add(obra)
    db_session.flush()

    is_item = tipo == "ITEM"
    acopio = Acopio(
        numero=f"REAL-{tipo}",
        obra_id=obra.id,
        fecha_alta=date(2024, 1, 1),
        total_m2=Decimal("100.00"),
        total_ml=Decimal("100.00"),
        total_pesos=Decimal("9999999.99") if is_item else Decimal("1128417.90"),
        total_unidades=100,
        saldo_m2=Decimal("100.00"),
        saldo_ml=Decimal("100.00"),
        saldo_pesos=Decimal("9999999.99") if is_item else Decimal("1128417.90"),
        saldo_unidades=100,
    )
    db_session.add(acopio)
    db_session.flush()

    item = None
    if is_item:
        item = AcopioItem(
            acopio_id=acopio.id,
            numero_item=1,
            descripcion="Item con excedente real de un centavo",
            cantidad=100,
            total_m2=Decimal("100.00"),
            total_ml=Decimal("100.00"),
            total_pesos=Decimal("1128417.90"),
            saldo_m2=Decimal("100.00"),
            saldo_ml=Decimal("100.00"),
            saldo_pesos=Decimal("1128417.90"),
            saldo_cantidad=100,
        )
        db_session.add(item)
        db_session.flush()

    pedido = Pedido(
        numero=f"PED-REAL-{tipo}",
        obra_id=obra.id,
        fecha=date(2024, 6, 24),
        total_m2=Decimal("16.61"),
        total_ml=Decimal("73.41"),
        total_pesos=Decimal("1128417.91"),
    )
    db_session.add(pedido)
    db_session.flush()

    imputacion = Imputacion(
        pedido_id=pedido.id,
        acopio_id=acopio.id,
        acopio_item_id=item.id if item else None,
        cantidad_m2=Decimal("16.61"),
        cantidad_ml=Decimal("73.41"),
        cantidad_pesos=Decimal("1128417.91"),
        cantidad_unidades=19,
        es_excedente=True,
        excedente_tipo=tipo,
        excedente_motivo="motivo anterior",
    )
    db_session.add(imputacion)
    db_session.commit()

    return imputacion


def test_get_acopio_detail_recalculates_stale_money_precision_excedente(client, db_session):
    acopio, _pedido, imputacion = _create_stale_precision_excedente(db_session)

    response = client.get(f"/acopios/{acopio.id}")

    assert response.status_code == 200
    data = response.json()
    assert data["imputaciones"][0]["es_excedente"] is False
    assert data["imputaciones"][0]["excedente_tipo"] == "NONE"
    assert data["imputaciones"][0]["excedente_motivo"] is None

    db_session.refresh(imputacion)
    assert imputacion.es_excedente is False
    assert imputacion.excedente_tipo == "NONE"
    assert imputacion.excedente_motivo is None


def test_excedentes_report_recalculates_stale_money_precision_flags(client, db_session):
    _acopio, _pedido, imputacion = _create_stale_precision_excedente(db_session)

    response = client.get("/reportes/excedentes")

    assert response.status_code == 200
    assert response.json()["count"] == 0

    db_session.refresh(imputacion)
    assert imputacion.es_excedente is False
    assert imputacion.excedente_tipo == "NONE"
    assert imputacion.excedente_motivo is None


def test_pedido_detail_recalculates_stale_money_precision_flags(client, db_session):
    _acopio, pedido, imputacion = _create_stale_precision_excedente(db_session)

    response = client.get(f"/pedidos/{pedido.id}")

    assert response.status_code == 200
    data = response.json()
    assert data["imputaciones"][0]["es_excedente"] is False

    db_session.refresh(imputacion)
    assert imputacion.es_excedente is False
    assert imputacion.excedente_tipo == "NONE"
    assert imputacion.excedente_motivo is None


def test_excedentes_report_keeps_real_item_money_excedente(client, db_session):
    imputacion = _create_real_money_excedente(db_session, "ITEM")

    response = client.get("/reportes/excedentes")

    assert response.status_code == 200
    assert imputacion.id in {row["id"] for row in response.json()["excedentes"]}

    db_session.refresh(imputacion)
    assert imputacion.es_excedente is True
    assert imputacion.excedente_tipo == "ITEM"
    assert "pesos excede total" in imputacion.excedente_motivo


def test_excedentes_report_keeps_real_acopio_money_excedente(client, db_session):
    imputacion = _create_real_money_excedente(db_session, "ACOPIO")

    response = client.get("/reportes/excedentes")

    assert response.status_code == 200
    assert imputacion.id in {row["id"] for row in response.json()["excedentes"]}

    db_session.refresh(imputacion)
    assert imputacion.es_excedente is True
    assert imputacion.excedente_tipo == "ACOPIO"
    assert "consumo acumulado pesos 1128417.91 excede total 1128417.90" in imputacion.excedente_motivo


def _create_reference_price_acopio(db_session):
    acopio = Acopio(
        numero="PRECIOS-ITEM",
        fecha_alta=date.today(),
        total_m2=Decimal("150.00"),
        total_ml=Decimal("200.00"),
        total_pesos=Decimal("1000.00"),
        total_unidades=10,
        saldo_m2=Decimal("150.00"),
        saldo_ml=Decimal("200.00"),
        saldo_pesos=Decimal("1000.00"),
        saldo_unidades=10,
    )
    db_session.add(acopio)
    db_session.flush()

    item = AcopioItem(
        acopio_id=acopio.id,
        numero_item=1,
        descripcion="DVH templado",
        cantidad=5,
        total_m2=Decimal("100.00"),
        total_ml=Decimal("120.00"),
        total_pesos=Decimal("600.00"),
        saldo_m2=Decimal("100.00"),
        saldo_ml=Decimal("120.00"),
        saldo_pesos=Decimal("600.00"),
        saldo_cantidad=5,
        proceso_vidrio_exterior=True,
    )
    db_session.add(item)
    db_session.add(PrecioReferencia(
        acopio_id=acopio.id,
        vidrio_exterior=Decimal("10.00"),
        pulido=Decimal("2.00"),
    ))
    db_session.commit()
    return acopio, item


def test_items_precios_referencia_migra_global_por_item(client, db_session):
    acopio, item = _create_reference_price_acopio(db_session)

    response = client.get(f"/acopios/{acopio.id}/items-precios-referencia")

    assert response.status_code == 200
    data = response.json()
    assert data["acopio_id"] == acopio.id
    assert data["items"][0]["item_id"] == item.id
    assert data["items"][0]["estado_precios_referencia"] == "completo"
    concepto = data["items"][0]["conceptos"][0]
    assert concepto["concepto"] == "vidrio_exterior"
    assert concepto["unidad"] == "m2"
    assert concepto["habilitado"] is True
    assert Decimal(str(concepto["precio_base"])) == Decimal("10.00")
    assert Decimal(str(concepto["precio_actual"])) == Decimal("10.00")
    assert concepto["origen"] == "migrado"


def test_items_precios_referencia_actualiza_precio_manual(client, db_session):
    acopio, item = _create_reference_price_acopio(db_session)
    client.get(f"/acopios/{acopio.id}/items-precios-referencia")

    response = client.put(
        f"/acopios/{acopio.id}/items-precios-referencia",
        json={
            "items": [
                {
                    "item_id": item.id,
                    "conceptos": [
                        {
                            "concepto": "vidrio_exterior",
                            "unidad": "m2",
                            "precio_base": "10.00",
                            "precio_actual": "15.50",
                            "habilitado": True,
                        }
                    ],
                }
            ]
        },
    )

    assert response.status_code == 200
    concepto = response.json()["items"][0]["conceptos"][0]
    assert Decimal(str(concepto["precio_base"])) == Decimal("10.00")
    assert Decimal(str(concepto["precio_actual"])) == Decimal("15.50")
    assert concepto["origen"] == "manual"


def test_items_precios_referencia_rechaza_precio_negativo(client, db_session):
    acopio, item = _create_reference_price_acopio(db_session)
    response = client.put(
        f"/acopios/{acopio.id}/items-precios-referencia",
        json={
            "items": [
                {
                    "item_id": item.id,
                    "conceptos": [
                        {
                            "concepto": "vidrio_exterior",
                            "unidad": "m2",
                            "precio_base": "10.00",
                            "precio_actual": "-1.00",
                            "habilitado": True,
                        }
                    ],
                }
            ]
        },
    )

    assert response.status_code == 400
    assert "negativo" in response.json()["detail"]


def test_items_precios_referencia_rechaza_concepto_no_habilitado(client, db_session):
    acopio, item = _create_reference_price_acopio(db_session)
    response = client.put(
        f"/acopios/{acopio.id}/items-precios-referencia",
        json={
            "items": [
                {
                    "item_id": item.id,
                    "conceptos": [
                        {
                            "concepto": "pulido",
                            "unidad": "ml",
                            "precio_base": "2.00",
                            "precio_actual": "2.00",
                            "habilitado": True,
                        }
                    ],
                }
            ]
        },
    )

    assert response.status_code == 400
    assert "no esta habilitado" in response.json()["detail"]
