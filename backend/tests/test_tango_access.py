"""Tango review/queue regressions. No real Access or SQL connections."""
import asyncio
from copy import deepcopy
from datetime import date
from decimal import Decimal
import json
import time
import pytest
from fastapi import HTTPException
from models import Acopio, Cliente, Obra, Comprobante, TipoComprobante, AfectacionAcopio
from models.tango_registro import TangoRegistro
from services import tango_service as service
from services.tango_access_bridge import request_access, bridge_status


def acopio(db, pct=None):
    c = Cliente(nombre="Cliente de prueba")
    db.add(c)
    db.flush()
    o = Obra(nombre="Obra prueba", cliente_id=c.id)
    db.add(o)
    db.flush()
    a = Acopio(numero="TANGO-TEST", fecha_alta=date(2026, 6, 29), obra_id=o.id,
               total_pesos=1000, saldo_pesos=900, total_m2=10, saldo_m2=9,
               total_unidades=2, saldo_unidades=1, porcentaje_facturado=pct)
    db.add(a)
    db.commit()
    return a


def record(id, tipo="FAC", total="1210", net="1000", iva="210", company="FONTELA"):
    return {"origen_id": id, "tipo": tipo, "empresa": company, "numero": tipo + str(id),
            "fecha": "2026-05-22", "cliente": "Cliente de prueba", "cliente_codigo": "TEST",
            "total": total, "importe_control": net, "iva": iva, "neto_origen": net,
            "moneda_corriente": True, "cotizacion": "1", "estado_origen": "CAN",
            "fecha_anulacion": "1800-01-01", "motivos": ["Coincide importe y cliente"],
            "aplicaciones": [], "referencias_pedido": [], "pdf_disponible": tipo == "REC",
            "base_importe": "Neto", "observacion": ""}


def example():
    invoice = record(1)
    receipt = record(2, "REC", "2000", "0", "0")
    receipt["aplicaciones"] = [{"factura_id": 1, "factura_numero": "FAC1", "importe_bruto": "1089"}]
    credit = record(3, "NCD", "121", "100", "21")
    credit["aplicaciones"] = [{"factura_id": 1, "factura_numero": "FAC1", "importe_bruto": "121"}]
    return [invoice, receipt, credit]


def mock_access(monkeypatch, records=None):
    source = records if records is not None else example()
    calls = []
    async def request(operation, arguments):
        calls.append((operation, arguments))
        if operation == "pdf":
            return b"%PDF-1.4\n%test\n%%EOF"
        return {"registros": deepcopy(source), "avisos": ["Revisar coincidencias"]}
    monkeypatch.setattr(service, "request_access", request)
    from routers import tango_access
    monkeypatch.setattr(tango_access, "request_access", request)
    from services import tango_asociacion_service
    monkeypatch.setattr(tango_asociacion_service, "request_access", request)
    return source, calls


def test_consulta_sin_reparto_no_toca_documentacion_ni_saldos(db_session, client, monkeypatch):
    a = acopio(db_session)
    manual = Comprobante(tipo=TipoComprobante.FAC_ANTICIPO, numero="MANUAL",
                         emisor="Emisor", fecha=date.today(), importe=100)
    db_session.add(manual)
    db_session.flush()
    db_session.add(AfectacionAcopio(acopio_id=a.id, comprobante_id=manual.id, importe=100))
    db_session.commit()
    _, calls = mock_access(monkeypatch)
    url = f"/acopios/{a.id}/tango"
    response = client.post(url + "/consultar", json={})
    assert response.status_code == 200, response.text
    data = response.json()
    assert data["consulta"]["nuevos"] == 3
    assert all(r["estado"] == "PENDIENTE" for r in data["registros"])
    assert calls[0][1]["objetivos"] == {"FONTELA": ["1000.00"], "VIVIANA": ["1000.00"]}
    rows = {r["datos"]["tipo"]: r for r in data["registros"]}
    receipt = rows["REC"]["datos"]
    assert receipt["total"] == "2000.00"
    assert receipt["aplicaciones"][0]["importe_bruto"] == "1089"
    assert receipt["aplicaciones"][0]["neto_equivalente"] == "900.00"
    assert rows["NCD"]["datos"]["aplicaciones"][0]["neto_equivalente"] == "100.00"
    db_session.refresh(a)
    assert a.saldo_pesos == 900 and a.saldo_m2 == 9 and a.porcentaje_facturado is None
    assert db_session.query(Comprobante).count() == db_session.query(AfectacionAcopio).count() == 1
    receipt_id = rows["REC"]["id"]
    assert client.patch(url + f"/registros/{receipt_id}", json={"estado": "DESCARTADO"}).status_code == 200
    again = client.post(url + "/consultar", json={}).json()
    assert again["consulta"]["nuevos"] == 0 and db_session.query(TangoRegistro).count() == 3
    assert next(r for r in again["registros"] if r["id"] == receipt_id)["estado"] == "DESCARTADO"
    restored = client.patch(url + f"/registros/{receipt_id}", json={"estado": "PENDIENTE"}).json()
    assert next(r for r in restored["registros"] if r["id"] == receipt_id)["estado"] == "PENDIENTE"


@pytest.mark.parametrize("pct,a,b", [(50, ["500.00"], ["500.00"]), (100, ["1000.00"], []), (0, [], ["1000.00"])])
def test_objetivos_neto_por_empresa(db_session, client, monkeypatch, pct, a, b):
    row = acopio(db_session, pct)
    _, calls = mock_access(monkeypatch, [])
    assert client.post(f"/acopios/{row.id}/tango/consultar", json={}).status_code == 200
    assert calls[0][1]["objetivos"] == {"FONTELA": a, "VIVIANA": b}


def test_cambios_de_origen_requieren_revision_y_preservan_version_anterior(db_session, client, monkeypatch):
    a = acopio(db_session)
    source, _ = mock_access(monkeypatch, [record(1)])
    url = f"/acopios/{a.id}/tango"
    old = client.post(url + "/consultar", json={}).json()["registros"][0]
    assert client.patch(url + f"/registros/{old['id']}", json={"estado": "CONSERVADO"}).status_code == 200
    source[0]["observacion"] = "Dato actualizado"
    updated = client.post(url + "/consultar", json={}).json()
    new = updated["registros"][0]
    assert new["estado"] == "PENDIENTE" and new["version_conservada_id"] == old["id"]
    previous = next(r for r in updated["registros"] if r["id"] == old["id"])
    assert previous["estado"] == "CONSERVADO" and previous["datos"]["observacion"] == ""
    assert client.patch(url + f"/registros/{old['id']}", json={"estado": "CONSERVADO"}).status_code == 409
    dismissed = client.patch(url + f"/registros/{new['id']}", json={"estado": "DESCARTADO"}).json()
    assert next(r for r in dismissed["registros"] if r["id"] == old["id"])["es_actual"]
    client.patch(url + f"/registros/{new['id']}", json={"estado": "PENDIENTE"})
    accepted = client.patch(url + f"/registros/{new['id']}", json={"estado": "CONSERVADO"}).json()
    assert next(r for r in accepted["registros"] if r["id"] == old["id"])["estado"] == "SUPERADO"


def test_acopio_aislado_pdf_y_descarte_pendientes(db_session, client, monkeypatch):
    a, b = acopio(db_session), acopio(db_session)
    mock_access(monkeypatch)
    url = f"/acopios/{a.id}/tango"
    rows = client.post(url + "/consultar", json={}).json()["registros"]
    kept = rows[0]
    client.patch(url + f"/registros/{kept['id']}", json={"estado": "CONSERVADO"})
    assert client.patch(f"/acopios/{b.id}/tango/registros/{kept['id']}", json={"estado": "DESCARTADO"}).status_code == 404
    assert client.get(f"/acopios/{b.id}/tango/registros/{kept['id']}/pdf").status_code == 404
    assert client.patch(url + f"/registros/{kept['id']}", json={"estado": "INVALIDO"}).status_code == 422
    discarded = client.post(url + "/descartar-pendientes").json()["registros"]
    assert sum(r["estado"] == "DESCARTADO" for r in discarded) == 2
    assert next(r for r in discarded if r["id"] == kept["id"])["estado"] == "CONSERVADO"
    pdf = client.get(url + f"/registros/{kept['id']}/pdf")
    assert pdf.status_code == 200 and pdf.content.startswith(b"%PDF-")


def test_neto_recibos_centavos_y_moneda_extranjera():
    records = example()
    records[0].update(total="3263581.18", importe_control="2697174.53")
    records[1]["aplicaciones"][0]["importe_bruto"] = "3023048.30"
    records[2].update(total="240532.88", importe_control="198787.50")
    records[2]["aplicaciones"][0]["importe_bruto"] = "240532.88"
    service.add_net_applications(records)
    assert records[1]["aplicaciones"][0]["neto_equivalente"] == "2498387.03"
    assert records[2]["aplicaciones"][0]["neto_equivalente"] == "198787.50"
    records[0]["moneda_corriente"] = False
    service.add_net_applications(records)
    assert records[1]["aplicaciones"][0]["neto_equivalente"] is None


def test_ids_numericos_no_se_mezclan_entre_empresas(db_session, client, monkeypatch):
    a = acopio(db_session)
    records = example()
    records += [record(1, total="1000", net="1000", iva="0", company="VIVIANA"),
                record(2, "REC", total="1000", net="0", iva="0", company="VIVIANA")]
    records[-1]["aplicaciones"] = [{"factura_id": 1, "factura_numero": "FAC1", "importe_bruto": "1000"}]
    mock_access(monkeypatch, records)
    result = client.post(f"/acopios/{a.id}/tango/consultar", json={}).json()["registros"]
    receipts = {r["datos"]["empresa"]: r["datos"] for r in result if r["datos"]["tipo"] == "REC"}
    assert receipts["FONTELA"]["aplicaciones"][0]["neto_equivalente"] == "900.00"
    assert receipts["VIVIANA"]["aplicaciones"][0]["neto_equivalente"] == "1000.00"


@pytest.mark.asyncio
async def test_cola_inactiva_respuesta_ajena_y_limpieza(tmp_path):
    assert not bridge_status(tmp_path)["activo"]
    with pytest.raises(HTTPException) as exc:
        await request_access("lookup", {}, root=tmp_path)
    assert exc.value.status_code == 503
    (tmp_path / "heartbeat.json").write_text(json.dumps({"version": 1, "utc": time.time(), "access": True}))
    async def fake_worker():
        while not list((tmp_path / "requests").glob("*.json")):
            await asyncio.sleep(0.01)
        request = next((tmp_path / "requests").glob("*.json"))
        (tmp_path / "responses" / request.name).write_text(json.dumps({"version": 1, "id": "wrong", "ok": True}))
    worker = asyncio.create_task(fake_worker())
    with pytest.raises(HTTPException) as exc:
        await request_access("lookup", {}, root=tmp_path, timeout=2)
    assert exc.value.status_code == 502
    await worker
    assert not list((tmp_path / "requests").glob("*.json"))


@pytest.mark.asyncio
async def test_cola_timeout_y_pdf_no_acepta_ruta_de_respuesta(tmp_path):
    (tmp_path / "heartbeat.json").write_text(json.dumps({"version": 1, "utc": time.time(), "access": True}))
    with pytest.raises(HTTPException) as exc:
        await request_access("lookup", {}, root=tmp_path, timeout=0.01)
    assert exc.value.status_code == 504
    async def fake_worker():
        while not list((tmp_path / "requests").glob("*.json")):
            await asyncio.sleep(0.01)
        request = next((tmp_path / "requests").glob("*.json"))
        packet = json.loads(request.read_text())
        folder = tmp_path / "responses"
        (folder / (packet["id"] + ".pdf")).write_bytes(b"%PDF-1.4\n%%EOF")
        (folder / request.name).write_text(json.dumps({"version": 1, "id": packet["id"], "ok": True, "path": "/etc/passwd"}))
    worker = asyncio.create_task(fake_worker())
    content = await request_access("pdf", {"empresa": "FONTELA", "origen_id": 1}, root=tmp_path, timeout=2)
    assert content.startswith(b"%PDF-")
    await worker
    assert not list((tmp_path / "responses").glob("*.pdf"))

def test_actualizacion_anulacion_y_vuelta_a_valor_anterior(db_session, client, monkeypatch):
    a = acopio(db_session)
    source, _ = mock_access(monkeypatch, [record(1)])
    url = f"/acopios/{a.id}/tango"
    original = client.post(url + "/consultar", json={}).json()["registros"][0]
    # CAN is settled, not annulled. Preserve the actual source annulment date.
    assert original["datos"]["estado_origen"] == "CAN"
    assert original["datos"]["fecha_anulacion"] == "1800-01-01"
    source[0]["fecha_anulacion"] = "2026-10-20"
    changed = client.post(url + "/consultar", json={}).json()
    assert changed["consulta"]["nuevos"] == 1
    assert changed["registros"][0]["datos"]["fecha_anulacion"] == "2026-10-20"
    assert next(r for r in changed["registros"] if r["id"] == original["id"])["estado"] == "SUPERADO"
    source[0]["fecha_anulacion"] = "1800-01-01"
    reverted = client.post(url + "/consultar", json={}).json()
    assert reverted["consulta"]["nuevos"] == 1
    latest = reverted["registros"][0]
    assert latest["id"] != original["id"] and latest["es_actual"]
    assert latest["datos"] == original["datos"]
    assert sum(r["estado"] == "PENDIENTE" for r in reverted["registros"]) == 1
    assert client.post(url + "/consultar", json={}).json()["consulta"]["nuevos"] == 0
    records = example()
    records[1]["fecha_anulacion"] = "2026-10-20"
    service.add_net_applications(records)
    assert records[1]["aplicaciones"][0]["neto_equivalente"] is None
    assert "anulado" in records[1]["aplicaciones"][0]["criterio_neto"]

@pytest.fixture(autouse=True)
def isolated_document_files(tmp_path, monkeypatch):
    from config import settings
    monkeypatch.setattr(settings, "storage_path", tmp_path)


def receipt_context():
    def row(invoice, total, net, source, applied):
        return {"factura_id": invoice, "factura_numero": "FAC" + str(invoice),
                "factura_total": total, "factura_neto": net, "factura_moneda": True,
                "factura_anulacion": "1800-01-01", "origen_id": source["origen_id"],
                "tipo": source["tipo"], "numero": source["numero"], "total": source["total"],
                "neto": source["importe_control"], "moneda_corriente": True,
                "fecha_anulacion": "1800-01-01", "aplicado": applied}
    source = example()
    source[1]["total"] = "2420"
    source[1]["contexto_neto"] = [
        row(1, "1210", "1000", source[1], "1089"),
        row(1, "1210", "1000", source[2], "121"),
        row(4, "1331", "1100", source[1], "1331"),
    ]
    return source


def test_asociar_desde_tango_pdf_y_aplicacion_sin_repetir(db_session, client, monkeypatch):
    a = acopio(db_session, 100)
    mock_access(monkeypatch, receipt_context())
    base = f"/acopios/{a.id}/tango"
    panel = client.post(base + "/consultar", json={}).json()
    choices = client.get(base + "/asociables").json()["resultados"]
    receipt = next(r for r in choices if r["numero"] == "REC2")
    invoice = next(r for r in choices if r["numero"] == "FAC1")
    assert receipt["importe"] == "2000.00" and receipt["original_bruto"] == "2420.00"
    assert receipt["sugerido"] == "900.00"
    credit = next(r for r in choices if r["numero"] == "NCD3")
    assert credit["bloqueo"] and not receipt["bloqueo"]
    assert db_session.query(Comprobante).count() == 0  # Lookup/choice never imports.
    fac_payload = {"importe_aplicado": "1000", "importe_facturado": "1000"}
    saved = client.post(base + f"/registros/{invoice['id']}/asociar", json=fac_payload)
    assert saved.status_code == 201, saved.text
    reference = saved.json()["documentos"][0]["id"]
    choices = client.get(base + "/asociables").json()["resultados"]
    assert next(r for r in choices if r["numero"] == "REC2")["referencia_id"] == reference
    payload = {"importe_aplicado": "900", "importe_facturado": "900", "referencia_id": reference}
    saved = client.post(base + f"/registros/{receipt['id']}/asociar", json=payload)
    assert saved.status_code == 201, saved.text
    docs = saved.json()
    assert docs["totales"]["cobrado_facturado"] == 900
    comp = next(r["comprobante"] for r in docs["documentos"] if r["comprobante"]["tipo"] == "RECIBO")
    assert comp["importe"] == 2000 and comp["disponible"] == 1100
    assert comp["origen_tango"]["bruto_original"] == "2420.00"
    assert client.get(comp["archivo"]["url"]).content.startswith(b"%PDF-")
    assert client.post(base + f"/registros/{receipt['id']}/asociar", json=payload).status_code == 409
    assert db_session.query(Comprobante).count() == 2
    assert db_session.query(AfectacionAcopio).count() == 2
    db_session.refresh(a)
    assert a.saldo_pesos == 900 and a.saldo_m2 == 9
    # An imported original cannot be rewritten through the manual edit route.
    rec_app = next(r for r in docs["documentos"] if r["comprobante"]["tipo"] == "RECIBO")
    edit = {**payload, "tipo": "RECIBO", "numero": "CHANGED", "emisor": comp["emisor"], "fecha": comp["fecha"],
            "importe": "2000", "iva": None, "descripcion": comp["descripcion"]}
    assert client.put(f"/acopios/{a.id}/documentacion/comprobantes/{rec_app['id']}",
                      data={"payload": json.dumps(edit)}).status_code == 409
    # A different acopio can use the remaining capacity of the same original.
    b = acopio(db_session, 100)
    source_b = receipt_context()
    source_b[0] = record(4, total="1331", net="1100", iva="231")
    source_b[1]["aplicaciones"] = [{"factura_id": 4, "factura_numero": "FAC4", "importe_bruto": "1331"}]
    mock_access(monkeypatch, source_b[:2])
    base_b = f"/acopios/{b.id}/tango"
    client.post(base_b + "/consultar", json={})
    rec_b = next(r for r in client.get(base_b + "/asociables").json()["resultados"] if r["numero"] == "REC2")
    assert rec_b["disponible"] == "1100.00"
    result = client.post(base_b + f"/registros/{rec_b['id']}/asociar",
                         json={"importe_aplicado": "1100", "importe_facturado": "1100"})
    assert result.status_code == 201, result.text
    assert db_session.query(Comprobante).count() == 2
    assert client.get(base_b + "/asociables").json()["resultados"]
    assert panel["consulta"]["nuevos"] == 3


def test_viviana_asociable_sin_factura_y_sin_neto_fabricado(db_session, client, monkeypatch):
    a = acopio(db_session, 0)
    receipt = record(9, "REC", total="500", net="0", iva="0", company="VIVIANA")
    source, _ = mock_access(monkeypatch, [receipt])
    base = f"/acopios/{a.id}/tango"
    client.post(base + "/consultar", json={})
    choice = client.get(base + "/asociables").json()["resultados"][0]
    assert choice["importe"] == choice["sugerido"] == "500.00"
    url = base + f"/registros/{choice['id']}/asociar"
    assert client.post(url, json={"importe_aplicado": "500", "importe_facturado": "500"}).status_code == 422
    saved = client.post(url, json={"importe_aplicado": "500", "importe_facturado": "0"})
    assert saved.status_code == 201, saved.text
    assert saved.json()["totales"]["cobrado_viviana"] == 500
    # The same receipt identity cannot be reassigned to Facturado via the local picker.
    b = acopio(db_session, 100)
    comp_id = saved.json()["documentos"][0]["comprobante"]["id"]
    assert client.post(f"/acopios/{b.id}/documentacion/asociaciones",
                       json={"comprobante_id": comp_id, "importe_aplicado": "1", "importe_facturado": "1"}).status_code == 422
    # A Fontela receipt with an unknown full net is displayed with a blocking explanation.
    source[:] = [record(10, "REC", total="1210", net="0", iva="0")]
    client.post(base + "/consultar", json={})
    unknown = next(r for r in client.get(base + "/asociables").json()["resultados"] if r["numero"] == "REC10")
    assert unknown["importe"] is None and unknown["bloqueo"]
    assert client.post(base + f"/registros/{unknown['id']}/asociar",
                       json={"importe_aplicado": "100", "importe_facturado": "0"}).status_code == 422


def test_asociacion_rechaza_descartados_anteriores_y_otro_acopio(db_session, client, monkeypatch):
    a, b = acopio(db_session, 100), acopio(db_session, 100)
    source, _ = mock_access(monkeypatch, [record(1)])
    base = f"/acopios/{a.id}/tango"
    old = client.post(base + "/consultar", json={}).json()["registros"][0]
    payload = {"importe_aplicado": "1000", "importe_facturado": "1000"}
    assert client.post(f"/acopios/{b.id}/tango/registros/{old['id']}/asociar", json=payload).status_code == 404
    source[0]["observacion"] = "Cambio"
    new = client.post(base + "/consultar", json={}).json()["registros"][0]
    assert client.post(base + f"/registros/{old['id']}/asociar", json=payload).status_code == 409
    client.patch(base + f"/registros/{new['id']}", json={"estado": "DESCARTADO"})
    assert client.post(base + f"/registros/{new['id']}/asociar", json=payload).status_code == 409
    assert db_session.query(Comprobante).count() == 0


def test_pdf_faltante_no_pierde_asociacion_y_no_supera_aplicacion(db_session, client, monkeypatch):
    a = acopio(db_session, 100)
    mock_access(monkeypatch, receipt_context())
    base = f"/acopios/{a.id}/tango"
    client.post(base + "/consultar", json={})
    choice = next(r for r in client.get(base + "/asociables").json()["resultados"] if r["numero"] == "REC2")
    from services import tango_asociacion_service
    async def unavailable(*args, **kwargs):
        raise HTTPException(503, "Access cerrado")
    monkeypatch.setattr(tango_asociacion_service, "request_access", unavailable)
    url = base + f"/registros/{choice['id']}/asociar"
    assert client.post(url, json={"importe_aplicado": "901", "importe_facturado": "901"}).status_code == 422
    saved = client.post(url, json={"importe_aplicado": "900", "importe_facturado": "900"})
    assert saved.status_code == 201, saved.text
    assert saved.json()["tango_aviso"] and saved.json()["documentos"][0]["comprobante"]["archivo"] is None

def test_recibo_compartido_respeta_aplicacion_a_factura_elegida(db_session, client, monkeypatch):
    a = acopio(db_session, 100)
    source = receipt_context()
    source.append(record(4, total="1331", net="1100", iva="231"))
    source[1]["aplicaciones"].append({"factura_id": 4, "factura_numero": "FAC4", "importe_bruto": "1331"})
    mock_access(monkeypatch, source)
    base = f"/acopios/{a.id}/tango"
    client.post(base + "/consultar", json={})
    choices = client.get(base + "/asociables").json()["resultados"]
    invoice = next(r for r in choices if r["numero"] == "FAC1")
    saved = client.post(base + f"/registros/{invoice['id']}/asociar",
                        json={"importe_aplicado": "1000", "importe_facturado": "1000"})
    assert saved.status_code == 201, saved.text
    reference = saved.json()["documentos"][0]["id"]
    receipt = next(r for r in choices if r["numero"] == "REC2")
    response = client.post(base + f"/registros/{receipt['id']}/asociar",
         json={"importe_aplicado": "2000", "importe_facturado": "2000", "referencia_id": reference})
    assert response.status_code == 422 and "factura elegida" in response.json()["detail"]
    assert db_session.query(AfectacionAcopio).count() == 1

def test_tango_mercaderia_asociable_y_recibo_vinculado(db_session, client, monkeypatch):
    a = acopio(db_session, 100)
    source = receipt_context()
    source[0]["es_anticipo"] = False
    mock_access(monkeypatch, source)
    base = f"/acopios/{a.id}/tango"
    client.post(base + "/consultar", json={})
    invoice = next(r for r in client.get(base + "/asociables").json()["resultados"] if r["numero"] == "FAC1")
    assert invoice["tipo"] == "FAC_MERCADERIA" and invoice["permite_clasificar"] and not invoice["bloqueo"]
    saved = client.post(base + f"/registros/{invoice['id']}/asociar",
                       json={"importe_aplicado": "1000", "importe_facturado": "1000"})
    assert saved.status_code == 201, saved.text
    docs = saved.json()
    assert docs["documentos"][0]["comprobante"]["tipo"] == "FAC_MERCADERIA"
    assert docs["totales"]["mercaderia_documentada"] == 1000 and docs["totales"]["anticipos_facturados"] == 0
    receipt = next(r for r in client.get(base + "/asociables").json()["resultados"] if r["numero"] == "REC2")
    reference = docs["documentos"][0]["id"]
    assert receipt["referencia_id"] == reference
    saved = client.post(base + f"/registros/{receipt['id']}/asociar",
                       json={"importe_aplicado": "900", "importe_facturado": "900", "referencia_id": reference})
    assert saved.status_code == 201, saved.text
    assert saved.json()["totales"]["cobrado_facturado"] == 900
    db_session.refresh(a)
    assert a.saldo_pesos == 900 and a.saldo_m2 == 9


def test_clasificacion_elegida_para_factura_tango_se_conserva_al_compartir(db_session, client, monkeypatch):
    a, b = acopio(db_session, 100), acopio(db_session, 100)
    source = [record(1)]
    source[0]["es_anticipo"] = True
    mock_access(monkeypatch, source)
    base = f"/acopios/{a.id}/tango"
    row = client.post(base + "/consultar", json={}).json()["registros"][0]
    saved = client.post(base + f"/registros/{row['id']}/asociar", json={
        "importe_aplicado": "600", "importe_facturado": "600", "tipo_factura": "FAC_MERCADERIA"})
    assert saved.status_code == 201, saved.text
    assert saved.json()["documentos"][0]["comprobante"]["tipo"] == "FAC_MERCADERIA"
    base_b = f"/acopios/{b.id}/tango"
    client.post(base_b + "/consultar", json={})
    choice = client.get(base_b + "/asociables").json()["resultados"][0]
    assert choice["tipo"] == "FAC_MERCADERIA" and not choice["permite_clasificar"]
    assert choice["disponible"] == "400.00"
    url = base_b + f"/registros/{choice['id']}/asociar"
    assert client.post(url, json={"importe_aplicado": "400", "importe_facturado": "400",
                                  "tipo_factura": "FAC_ANTICIPO"}).status_code == 409
    saved = client.post(url, json={"importe_aplicado": "400", "importe_facturado": "400"})
    assert saved.status_code == 201, saved.text
    assert saved.json()["totales"]["mercaderia_documentada"] == 400
    assert db_session.query(Comprobante).count() == 1


def add_manual_invoice(db, a, number="A00007-00012371", issuer="Fontela", cancelled=False):
    comp = Comprobante(tipo=TipoComprobante.FAC_ANTICIPO, numero=number,
        emisor=issuer, fecha=date(2026, 10, 13), importe="19794704.51", iva="4156887.95")
    db.add(comp)
    db.flush()
    ref = AfectacionAcopio(acopio_id=a.id, comprobante_id=comp.id,
        importe="19794704.51", importe_facturado="19794704.51", anulada=cancelled)
    db.add(ref)
    db.commit()
    return ref


def test_facturas_manuales_son_evidencia_solo_del_acopio_activo(db_session, client, monkeypatch):
    a, b = acopio(db_session), acopio(db_session)
    add_manual_invoice(db_session, a)
    add_manual_invoice(db_session, a, "A00007-00012372", cancelled=True)
    add_manual_invoice(db_session, a, "12373")  # sequence is not a unique identity
    add_manual_invoice(db_session, a, "A00007-00012374", issuer="Otro emisor")
    add_manual_invoice(db_session, b, "A00007-00012375")
    _, calls = mock_access(monkeypatch, [])
    assert client.post(f"/acopios/{a.id}/tango/consultar", json={}).status_code == 200
    assert calls[0][1]["facturas_confirmadas"] == [{"empresa": "FONTELA", "numero": "A0000700012371"}]
    assert client.post(f"/acopios/{b.id}/tango/consultar", json={}).status_code == 200
    assert calls[1][1]["facturas_confirmadas"] == [{"empresa": "FONTELA", "numero": "A0000700012375"}]


def motorparts_records():
    invoice = record(64901, total="23951592.46", net="19794704.51", iva="4156887.95")
    invoice.update(numero="A0000700012371", cliente="Titular fiscal diferente", es_anticipo=True)
    receipts = []
    for id, number, amount in [(1, "E0000000045975", "12605593.47"), (2, "E0000000045980", "11345998.99")]:
        receipt = record(id, "REC", total=amount, net="0", iva="0")
        receipt.update(numero=number, pdf_disponible=False,
            aplicaciones=[{"factura_id": 64901, "factura_numero": invoice["numero"], "importe_bruto": amount}])
        receipts.append(receipt)
    context = [{"factura_id": 64901, "factura_numero": invoice["numero"],
        "factura_total": invoice["total"], "factura_neto": invoice["importe_control"],
        "factura_moneda": True, "factura_anulacion": "1800-01-01",
        "origen_id": rec["origen_id"], "tipo": "REC", "numero": rec["numero"],
        "total": rec["total"], "neto": "0", "moneda_corriente": True,
        "fecha_anulacion": "1800-01-01", "aplicado": rec["total"]} for rec in receipts]
    for rec in receipts:
        rec["contexto_neto"] = deepcopy(context)
    return [invoice] + receipts


def test_motorparts_recibos_referencian_factura_manual_sin_duplicar(db_session, client, monkeypatch):
    a = acopio(db_session, 100)
    ref = add_manual_invoice(db_session, a)
    mock_access(monkeypatch, motorparts_records())
    base = f"/acopios/{a.id}/tango"
    assert client.post(base + "/consultar", json={}).status_code == 200
    rows = client.get(base + "/asociables").json()["resultados"]
    invoice = next(r for r in rows if r["tipo"] == "FAC_ANTICIPO")
    assert "Ya est" in invoice["bloqueo"]
    receipts = [r for r in rows if r["tipo"] == "RECIBO"]
    assert {r["numero"]: r["sugerido"] for r in receipts} == {
        "E0000000045975": "10417845.84", "E0000000045980": "9376858.67"}
    assert all(r["referencia_id"] == ref.id and not r["bloqueo"] for r in receipts)
    assert sum(Decimal(r["sugerido"]) for r in receipts) == Decimal("19794704.51")
    assert db_session.query(Comprobante).count() == db_session.query(AfectacionAcopio).count() == 1
    # An explicit selection may associate a receipt with the existing manual invoice.
    row = receipts[0]
    response = client.post(base + f"/registros/{row['id']}/asociar", json={
        "importe_aplicado": row["sugerido"], "importe_facturado": row["sugerido"], "referencia_id": ref.id})
    assert response.status_code == 201, response.text
    assert db_session.query(Comprobante).count() == 2
    db_session.refresh(a)
    assert a.saldo_pesos == 900 and a.saldo_m2 == 9


def test_recibo_rechaza_factura_manual_ajena_a_sus_aplicaciones(db_session, client, monkeypatch):
    a = acopio(db_session, 100)
    ref = add_manual_invoice(db_session, a, number="A00007-00012372")
    mock_access(monkeypatch, motorparts_records())
    base = f"/acopios/{a.id}/tango"
    client.post(base + "/consultar", json={})
    receipt = next(r for r in client.get(base + "/asociables").json()["resultados"] if r["tipo"] == "RECIBO")
    assert receipt["referencia_id"] is None
    response = client.post(base + f"/registros/{receipt['id']}/asociar", json={
        "importe_aplicado": "1", "importe_facturado": "1", "referencia_id": ref.id})
    assert response.status_code == 422 and "factura elegida" in response.json()["detail"]


def test_anular_factura_quita_evidencia_en_siguiente_consulta(db_session):
    from services.tango_discovery import confirmed_invoices
    a = acopio(db_session)
    ref = add_manual_invoice(db_session, a)
    assert confirmed_invoices(db_session, a.id)
    ref.anulada = True
    db_session.commit()
    assert confirmed_invoices(db_session, a.id) == []


def test_evidencia_no_acepta_numero_ambiguo_ni_emisor_parcial():
    from services.tango_discovery import invoice_identity
    assert invoice_identity("12371", "Fontela") is None
    assert invoice_identity("A00007-00012371", "Fontela ajena") is None
    assert invoice_identity("A00007-00012371", "Fontela") == ("FONTELA", "A0000700012371")
    assert invoice_identity("A00007-00012371", "Viviana") == ("VIVIANA", "A0000700012371")
