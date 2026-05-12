from datetime import date
from decimal import Decimal

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from models import Acopio, AcopioItem
from services.proceso_inference import infer_item_processes_from_texts


def test_infers_processes_from_item_detail_text():
    result = infer_item_processes_from_texts([
        "DVH Vidrio Exterior templado",
        "Camara Offset",
        "Adicional: pulido y opacificado total",
    ])

    assert result["vidrio_exterior"] is True
    assert result["vidrio_interior"] is True
    assert result["fason_templado_exterior"] is True
    assert result["camara_offset"] is True
    assert result["camara_normal"] is False
    assert result["pulido"] is True
    assert result["opacificado_total"] is True


def test_dvh_marks_both_glasses_and_normal_camera():
    result = infer_item_processes_from_texts([
        "DVH 4+4",
    ])

    assert result["vidrio_exterior"] is True
    assert result["vidrio_interior"] is True
    assert result["camara_normal"] is True
    assert result["fason_templado_exterior"] is False
    assert result["pulido"] is False


def test_plus_separates_only_known_processes():
    result = infer_item_processes_from_texts([
        "DVH 4+4 + Templado + Pulido",
    ])

    assert result["vidrio_exterior"] is True
    assert result["vidrio_interior"] is True
    assert result["camara_normal"] is True
    assert result["fason_templado_exterior"] is True
    assert result["pulido"] is True

    laminated = infer_item_processes_from_texts([
        "Laminado 4+4",
    ])
    assert all(value is False for value in laminated.values())


def test_explicit_camera_normal_can_coexist_with_other_camera_processes():
    result = infer_item_processes_from_texts([
        "Camara Estructural + Camara Normal + Camara Offset",
    ])

    assert result["camara_estructural"] is True
    assert result["camara_normal"] is True
    assert result["camara_offset"] is True


def test_generic_camera_means_normal_camera():
    result = infer_item_processes_from_texts([
        "DVH con Camara",
    ])

    assert result["camara_normal"] is True
    assert result["camara_estructural"] is False
    assert result["camara_offset"] is False


def test_acopio_creation_marks_detected_processes_and_keeps_manual_uncheck(
    client: TestClient,
):
    payload = {
        "extraction_package": {
            "presupuesto": {
                "numero": "PROC-CREATE-1",
                "empresa": "Empresa Test",
                "contacto": None,
                "estado": "Aprobado",
                "cotizado_por": None,
                "fecha_aprobacion": None,
                "total_unidades": 1,
                "total_importe": 1000.0,
                "total_m2": 10.0,
                "total_ml": 20.0,
                "peso_estimado_kg": 50.0,
            },
            "items": [
                {
                    "numero_item": 1,
                    "descripcion": "Vidrio Exterior con Pulido",
                    "cantidad": 1,
                    "total_pesos": 1000.0,
                    "total_m2": 10.0,
                    "total_ml": 20.0,
                    "panos": [
                        {
                            "row_no": 1,
                            "cantidad": 1,
                            "ancho_mm": 1000,
                            "alto_mm": 2000,
                            "superficie_m2": 10.0,
                            "perimetro_ml": 20.0,
                            "denominacion": "Camara Offset",
                            "precio_unitario": 1000.0,
                            "precio_total": 1000.0,
                        }
                    ],
                    "adicionales": [],
                }
            ],
            "warnings": [],
        }
    }

    response = client.post("/acopios/confirm-pdf", json=payload)
    assert response.status_code == 200
    acopio_id = response.json()["acopio_id"]

    response = client.get(f"/acopios/{acopio_id}")
    assert response.status_code == 200
    item = response.json()["items"][0]
    procesos = item["procesos"]
    assert procesos["vidrio_exterior"] is True
    assert procesos["pulido"] is True
    assert procesos["camara_offset"] is True
    assert procesos["camara_normal"] is False

    response = client.patch(
        f"/acopios/{acopio_id}/items/{item['id']}/procesos",
        json={"pulido": False},
    )
    assert response.status_code == 200
    assert response.json()["procesos"]["pulido"] is False

    response = client.get(f"/acopios/{acopio_id}")
    assert response.status_code == 200
    procesos = response.json()["items"][0]["procesos"]
    assert procesos["vidrio_exterior"] is True
    assert procesos["pulido"] is False


def test_detail_does_not_autodetect_existing_items(
    client: TestClient,
    db_session: Session,
):
    acopio = Acopio(
        numero="PROC-1",
        fecha_alta=date.today(),
        total_m2=Decimal("10.00"),
        total_ml=Decimal("20.00"),
        total_pesos=Decimal("1000.00"),
        total_unidades=1,
        saldo_m2=Decimal("10.00"),
        saldo_ml=Decimal("20.00"),
        saldo_pesos=Decimal("1000.00"),
        saldo_unidades=1,
    )
    db_session.add(acopio)
    db_session.flush()

    item = AcopioItem(
        acopio_id=acopio.id,
        descripcion="Vidrio Exterior con Pulido",
        cantidad=1,
        total_m2=Decimal("10.00"),
        total_ml=Decimal("20.00"),
        total_pesos=Decimal("1000.00"),
        saldo_m2=Decimal("10.00"),
        saldo_ml=Decimal("20.00"),
        saldo_pesos=Decimal("1000.00"),
        saldo_cantidad=1,
    )
    db_session.add(item)
    db_session.commit()
    db_session.refresh(item)

    response = client.get(f"/acopios/{acopio.id}")
    assert response.status_code == 200
    data = response.json()
    procesos = data["items"][0]["procesos"]
    assert procesos["vidrio_exterior"] is False
    assert procesos["pulido"] is False
