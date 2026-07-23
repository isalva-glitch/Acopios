from datetime import date
from decimal import Decimal

from models import Acopio, AcopioItem


def _create_learning_acopio(db_session):
    acopio = Acopio(
        numero="LEARN-1",
        fecha_alta=date(2024, 1, 1),
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
        numero_item=1,
        descripcion="Mirage 5 mm. Incoloro con Borde Pulido Brillante en maquina retilinea.",
        cantidad=1,
        total_m2=Decimal("10.00"),
        total_ml=Decimal("20.00"),
        total_pesos=Decimal("1000.00"),
        saldo_m2=Decimal("10.00"),
        saldo_ml=Decimal("20.00"),
        saldo_pesos=Decimal("1000.00"),
        saldo_cantidad=1,
        proceso_pulido=True,
    )
    db_session.add(item)
    db_session.commit()
    return acopio, item


def _create_learning_acopio_with_description(db_session, description: str):
    acopio = Acopio(
        numero="LEARN-2",
        fecha_alta=date(2024, 1, 1),
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
        numero_item=1,
        descripcion=description,
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
    return acopio, item


def test_manual_process_update_registers_learning_correction_and_rule(client, db_session):
    acopio, item = _create_learning_acopio(db_session)

    response = client.patch(
        f"/acopios/{acopio.id}/items/{item.id}/procesos",
        json={"vidrio_interior": True},
    )
    assert response.status_code == 200
    assert response.json()["procesos"]["vidrio_interior"] is True

    corrections_response = client.get("/aprendizaje-procesos/correcciones")
    assert corrections_response.status_code == 200
    corrections = corrections_response.json()
    assert len(corrections) == 1
    correction = corrections[0]
    assert correction["acopio_id"] == acopio.id
    assert correction["acopio_item_id"] == item.id
    assert correction["origen"] == "manual"
    assert correction["cambios"] == {
        "vidrio_interior": {"antes": False, "despues": True}
    }
    assert "mirage 5 mm incoloro" in correction["texto_normalizado"]

    rules_response = client.get("/aprendizaje-procesos/reglas")
    assert rules_response.status_code == 200
    rules = rules_response.json()
    assert len(rules) == 1
    rule = rules[0]
    assert rule["estado"] == "propuesta"
    assert rule["proceso"] == "vidrio_interior"
    assert rule["accion"] == "activar"
    assert rule["alcance"] == "item_text_exact"
    assert rule["soporte_count"] == 1
    assert rule["ejemplos"][0]["acopio_item_id"] == item.id


def test_process_update_without_real_change_does_not_create_learning_rows(client, db_session):
    acopio, item = _create_learning_acopio(db_session)

    response = client.patch(
        f"/acopios/{acopio.id}/items/{item.id}/procesos",
        json={"pulido": True},
    )
    assert response.status_code == 200

    corrections_response = client.get("/aprendizaje-procesos/correcciones")
    assert corrections_response.status_code == 200
    assert corrections_response.json() == []

    rules_response = client.get("/aprendizaje-procesos/reglas")
    assert rules_response.status_code == 200
    assert rules_response.json() == []


def test_approved_rule_is_simulated_and_applied_to_new_acopio(client, db_session):
    description = "Laminado 4+4 Especial Cliente"
    acopio, item = _create_learning_acopio_with_description(db_session, description)

    update_response = client.patch(
        f"/acopios/{acopio.id}/items/{item.id}/procesos",
        json={"vidrio_interior": True},
    )
    assert update_response.status_code == 200

    rules = client.get("/aprendizaje-procesos/reglas").json()
    rule_id = rules[0]["id"]

    simulation_response = client.post(f"/aprendizaje-procesos/reglas/{rule_id}/simular")
    assert simulation_response.status_code == 200
    simulation = simulation_response.json()
    assert simulation["affected_count"] == 1
    assert simulation["affected_items"][0]["acopio_item_id"] == item.id
    assert simulation["affected_items"][0]["antes"] is False
    assert simulation["affected_items"][0]["despues"] is True

    approve_response = client.post(f"/aprendizaje-procesos/reglas/{rule_id}/aprobar")
    assert approve_response.status_code == 200
    assert approve_response.json()["estado"] == "aprobada"

    package = {
        "meta": {
            "extraction_date": "2024-01-01T00:00:00",
            "pdf_filename": "learn.pdf",
            "pdf_hash": "d" * 64,
            "extractor_version": "1.0.0"
        },
        "acopio": {
            "numero": "LEARN-NEW",
            "fecha_alta": "2024-01-01",
            "obra": "Obra Learning",
            "cliente": "Cliente Learning",
            "total_m2": 10.0,
            "total_ml": 20.0,
            "total_pesos": 1000.0
        },
        "presupuestos": [],
        "items": [
            {
                "descripcion": description,
                "material": "",
                "tipologia": "",
                "cantidad": 1,
                "total_m2": 10.0,
                "total_ml": 20.0,
                "total_pesos": 1000.0,
                "adicionales": [],
            }
        ],
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
    assert create_response.status_code == 200
    created_acopio_id = create_response.json()["id"]

    created_item = db_session.query(AcopioItem).filter(
        AcopioItem.acopio_id == created_acopio_id,
        AcopioItem.descripcion == description,
    ).one()
    assert created_item.proceso_vidrio_interior is True

    approved_rules = client.get("/aprendizaje-procesos/reglas?estado=aprobada").json()
    assert approved_rules[0]["id"] == rule_id
