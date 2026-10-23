"""One read-only list for manually entered and Tango sourced documentation."""
from copy import deepcopy
import json
import pytest
from models import Comprobante, AfectacionAcopio
from models.tango_comprobante import TangoComprobante
from tests.test_tango_access import acopio, record, mock_access


def source(number="A0000700011794", company="FONTELA"):
    data = record(1, company=company)
    data["numero"] = number
    return data


@pytest.mark.parametrize("number,issuer,expected", [
    ("A0007-00011794", "Fontela", 1),
    ("A0007-00011794", "José M. Fontela e Hijos S.A.C.I.F.", 1),
    ("11794", "Fontela", 2),
    ("A0008-00011794", "Fontela", 2),
    ("A0007-00011794", "Otro emisor", 2),
])
def test_unifica_numero_completo_y_emisor_sin_ocultar_otros_documentos(db_session, client, monkeypatch, number, issuer, expected):
    a = acopio(db_session, 100)
    mock_access(monkeypatch, [source()])
    client.post(f"/acopios/{a.id}/tango/consultar", json={})
    # A manually classified merchandise invoice is the same fiscal document.
    payload = {"tipo": "FAC_MERCADERIA", "numero": number, "emisor": issuer, "fecha": "2026-05-22",
               "importe": "1000", "iva": "210", "importe_aplicado": "500", "importe_facturado": "500"}
    saved = client.post(f"/acopios/{a.id}/documentacion/comprobantes", data={"payload": json.dumps(payload)})
    assert saved.status_code == 201, saved.text
    before = deepcopy(saved.json()["totales"])
    result = client.get(f"/acopios/{a.id}/documentacion/panel")
    assert result.status_code == 200, result.text
    panel = result.json()
    assert len(panel["listado"]) == expected
    assert panel["totales"] == before and panel["totales"]["mercaderia_documentada"] == 500
    if expected == 1:
        assert panel["listado"][0]["aplicacion"] and panel["listado"][0]["tango"]
    assert db_session.query(Comprobante).count() == db_session.query(AfectacionAcopio).count() == 1
    assert db_session.query(TangoComprobante).count() == 0  # projection never imports/links.
    db_session.refresh(a)
    assert a.saldo_pesos == 900 and a.saldo_m2 == 9


def test_asociado_desde_tango_aparece_una_vez_con_sus_actualizaciones(db_session, client, monkeypatch):
    a = acopio(db_session, 100)
    original, _ = mock_access(monkeypatch, [source()])
    base = f"/acopios/{a.id}"
    old = client.post(base + "/tango/consultar", json={}).json()["registros"][0]
    saved = client.post(base + f"/tango/registros/{old['id']}/asociar",
                       json={"importe_aplicado": "1000", "importe_facturado": "1000"})
    assert saved.status_code == 201, saved.text
    initial = client.get(base + "/documentacion/panel").json()
    assert len(initial["listado"]) == 1
    row = initial["listado"][0]
    assert row["aplicacion"] and row["tango"]["id"] == old["id"]
    assert not row["actualizacion_tango"]
    origin = row["aplicacion"]["comprobante"]["origen_tango"]
    assert origin["origen_id"] == 1 and origin["origen_tipo"] == "FAC"
    original[0]["observacion"] = "Nueva referencia en Tango"
    client.post(base + "/tango/consultar", json={})
    updated = client.get(base + "/documentacion/panel").json()
    assert len(updated["listado"]) == 1
    row = updated["listado"][0]
    assert row["actualizacion_tango"] and len(row["versiones_tango"]) == 2
    assert row["tango"]["estado"] == "PENDIENTE"
    assert row["candidato"] is None
    assert row["aplicacion"]["comprobante"]["descripcion"] != "Nueva referencia en Tango"
    assert initial["totales"] == updated["totales"]
    assert db_session.query(Comprobante).count() == db_session.query(AfectacionAcopio).count() == 1


def test_historial_descartados_y_version_conservada_se_agrupan(db_session, client, monkeypatch):
    a = acopio(db_session, 100)
    original, _ = mock_access(monkeypatch, [source()])
    base = f"/acopios/{a.id}"
    old = client.post(base + "/tango/consultar", json={}).json()["registros"][0]
    client.patch(base + f"/tango/registros/{old['id']}", json={"estado": "CONSERVADO"})
    original[0]["observacion"] = "Cambio descartado"
    new = client.post(base + "/tango/consultar", json={}).json()["registros"][0]
    client.patch(base + f"/tango/registros/{new['id']}", json={"estado": "DESCARTADO"})
    panel = client.get(base + "/documentacion/panel").json()
    assert len(panel["listado"]) == 1 and panel["pendientes_tango"] == 0
    row = panel["listado"][0]
    assert row["tango"]["id"] == old["id"] and not row["archivado"]
    assert len(row["versiones_tango"]) == 2 and row["candidato"] is None
    assert panel["totales"]["anticipos_facturados"] == 0  # conserved is not associated.
    client.patch(base + f"/tango/registros/{old['id']}", json={"estado": "DESCARTADO"})
    archived = client.get(base + "/documentacion/panel").json()["listado"][0]
    assert archived["archivado"] and len(archived["versiones_tango"]) == 2
    assert db_session.query(Comprobante).count() == 0


def test_empresas_no_se_mezclan_y_lectura_no_requiere_access(db_session, client, monkeypatch):
    a = acopio(db_session, 100)
    records = [source(), source(company="VIVIANA")]
    mock_access(monkeypatch, records)
    base = f"/acopios/{a.id}"
    first = client.post(base + "/tango/consultar", json={}).json()["registros"]
    fontela = next(r for r in first if r["datos"]["empresa"] == "FONTELA")
    client.post(base + f"/tango/registros/{fontela['id']}/asociar",
                json={"importe_aplicado": "1000", "importe_facturado": "1000"})
    from services import tango_service
    monkeypatch.setattr(tango_service, "bridge_status", lambda: {
        "activo": False, "access_abierto": False, "mensaje": "Access no disponible"})
    panel = client.get(base + "/documentacion/panel").json()
    assert len(panel["listado"]) == 2
    associated = next(r for r in panel["listado"] if r["aplicacion"])
    other = next(r for r in panel["listado"] if not r["aplicacion"])
    assert associated["tango"]["datos"]["empresa"] == "FONTELA"
    assert other["tango"]["datos"]["empresa"] == "VIVIANA"
    assert not panel["conexion_tango"]["activo"]
    assert panel["totales"]["anticipos_facturados"] == 1000
