"""Tests for acopio package API."""
from datetime import date
from decimal import Decimal

from main import app
from integrations.spf.database import get_spf_db
from models import Acopio
from services import acopio_paquete_service


def _override_spf_db():
    yield object()


def _fake_spf_details(presupuesto: str):
    fixtures = {
        "1001": {
            "v_presupuesto_id": "1001",
            "cliente_id": 10,
            "cliente_nombre": "Cliente ABC",
            "obra_nombre": "Obra A",
            "total_m2": 12.5,
            "total_ml": 8.25,
            "total_pesos": 150000.0,
            "items": [
                {
                    "descripcion": "DVH templado",
                    "cantidad": 4,
                    "total_m2": 12.5,
                    "total_ml": 8.25,
                    "total_pesos": 150000.0,
                    "panos": [],
                    "adicionales": [],
                }
            ],
        },
        "1002": {
            "v_presupuesto_id": "1002",
            "cliente_id": 10,
            "cliente_nombre": "Cliente ABC",
            "obra_nombre": "Obra B",
            "total_m2": 20.0,
            "total_ml": 10.0,
            "total_pesos": 250000.0,
            "items": [
                {
                    "descripcion": "Laminado",
                    "cantidad": 6,
                    "total_m2": 20.0,
                    "total_ml": 10.0,
                    "total_pesos": 250000.0,
                    "panos": [],
                    "adicionales": [],
                }
            ],
        },
    }
    return fixtures.get(str(presupuesto))


def _fake_pdf_package(numero: str = "PDF-001"):
    return {
        "presupuesto": {
            "numero": numero,
            "empresa": "Cliente PDF",
            "empresa_raw": "Cliente PDF / Obra PDF",
            "contacto": "Contacto PDF",
            "estado": "Ejecutado",
            "cotizado_por": "Admin User",
            "fecha_aprobacion": "17/06/26",
            "total_unidades": 3,
            "total_importe": 123456.78,
            "total_m2": 9.5,
            "total_ml": 7.25,
            "peso_estimado_kg": 0,
            "obra": "Obra PDF",
        },
        "items": [
            {
                "numero_item": 1,
                "descripcion": "DVH templado",
                "cantidad": 3,
                "total_pesos": 123456.78,
                "total_m2": 9.5,
                "total_ml": 7.25,
                "panos": [],
                "adicionales": [],
            }
        ],
        "warnings": [],
    }


def _install_fake_spf(monkeypatch):
    app.dependency_overrides[get_spf_db] = _override_spf_db
    monkeypatch.setattr(
        acopio_paquete_service.spf_services,
        "get_presupuesto_details",
        lambda _db, presupuesto: _fake_spf_details(presupuesto),
    )


def test_preview_acopio_paquete_flags_valid_duplicate_and_existing(client, db_session, monkeypatch):
    _install_fake_spf(monkeypatch)
    existing = Acopio(
        numero="1002",
        fecha_alta=date.today(),
        v_presupuesto_id="1002",
        total_m2=Decimal("1.00"),
        total_ml=Decimal("1.00"),
        total_pesos=Decimal("1.00"),
        total_unidades=1,
        saldo_m2=Decimal("1.00"),
        saldo_ml=Decimal("1.00"),
        saldo_pesos=Decimal("1.00"),
        saldo_unidades=1,
    )
    db_session.add(existing)
    db_session.commit()

    response = client.post(
        "/acopio-paquetes/preview",
        json={"presupuestos": ["1001", "1001", "1002", "9999"]},
    )

    assert response.status_code == 200
    data = response.json()["presupuestos"]
    assert data[0]["estado_validacion"] == "OK"
    assert data[0]["cliente"] == "Cliente ABC"
    assert data[1]["valido"] is False
    assert "repetido" in data[1]["observaciones"]
    assert data[2]["valido"] is False
    assert "Ya existe" in data[2]["observaciones"]
    assert data[3]["valido"] is False
    assert "no encontrado" in data[3]["observaciones"]


def test_create_acopio_paquete_creates_children_and_consolidates(client, db_session, monkeypatch):
    _install_fake_spf(monkeypatch)

    response = client.post(
        "/acopio-paquetes",
        json={
            "nombre": "Paquete Cliente ABC - Obras varias",
            "cliente": "Cliente ABC",
            "fecha_alta": "2026-06-17",
            "observaciones": "Primera etapa",
            "presupuestos": ["1001", "1002"],
        },
    )

    assert response.status_code == 200
    data = response.json()
    assert data["numero"] == "PAQ-000001"
    assert data["cantidad_acopios"] == 2
    assert Decimal(str(data["total_pesos"])) == Decimal("400000.0")
    assert Decimal(str(data["total_m2"])) == Decimal("32.5")
    assert data["total_unidades"] == 10
    assert [item["presupuesto"] for item in data["acopios"]] == ["1001", "1002"]
    assert [item["obra"] for item in data["acopios"]] == ["Obra A", "Obra B"]

    child_ids = [item["id"] for item in data["acopios"]]
    db_children = db_session.query(Acopio).filter(Acopio.id.in_(child_ids)).all()
    assert {child.paquete_id for child in db_children} == {data["id"]}

    list_response = client.get("/acopio-paquetes")
    assert list_response.status_code == 200
    assert list_response.json()[0]["cantidad_acopios"] == 2

    detail_response = client.get(f"/acopio-paquetes/{data['id']}")
    assert detail_response.status_code == 200
    assert len(detail_response.json()["acopios"]) == 2

    acopio_response = client.get(f"/acopios/{child_ids[0]}")
    assert acopio_response.status_code == 200
    assert acopio_response.json()["numero"] == "1001"


def test_update_acopio_paquete_only_updates_package_fields(client, db_session, monkeypatch):
    _install_fake_spf(monkeypatch)
    create_response = client.post(
        "/acopio-paquetes",
        json={
            "nombre": "Paquete original",
            "cliente": "Cliente ABC",
            "fecha_alta": "2026-06-17",
            "observaciones": "",
            "presupuestos": ["1001"],
        },
    )
    paquete_id = create_response.json()["id"]
    acopio_id = create_response.json()["acopios"][0]["id"]

    update_response = client.patch(
        f"/acopio-paquetes/{paquete_id}",
        json={"nombre": "Paquete actualizado", "estado": "PAUSADO"},
    )

    assert update_response.status_code == 200
    assert update_response.json()["nombre"] == "Paquete actualizado"
    assert update_response.json()["estado"] == "PAUSADO"

    acopio = db_session.query(Acopio).filter(Acopio.id == acopio_id).one()
    assert acopio.numero == "1001"
    assert acopio.paquete_id == paquete_id


def test_create_acopio_paquete_from_pdf_budget(client, db_session):
    response = client.post(
        "/acopio-paquetes",
        json={
            "nombre": "Paquete desde presupuesto madre",
            "cliente": "Cliente PDF",
            "fecha_alta": "2026-06-17",
            "observaciones": "Presupuesto madre cargado por PDF",
            "pdf_presupuestos": [_fake_pdf_package()],
        },
    )

    assert response.status_code == 200
    data = response.json()
    assert data["cantidad_acopios"] == 1
    assert Decimal(str(data["total_pesos"])) == Decimal("123456.78")
    child = data["acopios"][0]
    assert child["presupuesto"] == "PDF-001"
    assert child["obra"] == "Obra PDF"
    assert child["cliente"] == "Cliente PDF"

    acopio_response = client.get(f"/acopios/{child['id']}")
    assert acopio_response.status_code == 200
    assert acopio_response.json()["origen_datos"] == "pdf_upload"


def test_create_acopio_paquete_rejects_repeated_spf_and_pdf_source(client, db_session, monkeypatch):
    _install_fake_spf(monkeypatch)
    response = client.post(
        "/acopio-paquetes",
        json={
            "nombre": "Paquete duplicado",
            "cliente": "Cliente ABC",
            "fecha_alta": "2026-06-17",
            "presupuestos": ["1001"],
            "pdf_presupuestos": [_fake_pdf_package("1001")],
        },
    )

    assert response.status_code == 400
    assert "repetido" in response.json()["detail"]
