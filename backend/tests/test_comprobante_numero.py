"""Number lookup from the existing manual input; no live Tango access."""
import pytest
from fastapi import HTTPException
from models import Comprobante, TipoComprobante
from services.comprobante_numero import number_query, number_matches
from tests.test_tango_access import acopio, record, mock_access


@pytest.mark.parametrize("value", [
    "11794", "00011794", "A0007-00011794", "A0000700011794",
    "A7-11794", "0007-11794", "0000700011794", "A 0007/11794",
])
def test_numero_corto_o_completo(value):
    query = number_query(value)
    assert number_matches("A0000700011794", query)
    assert not number_matches("A0000700911794", query)


def test_letra_y_punto_de_venta_distinguen_numeros_iguales():
    short = number_query("11794")
    assert number_matches("B0000800011794", short)
    full = number_query("A0007-11794")
    assert not number_matches("B0000700011794", full)
    assert not number_matches("A0000800011794", full)
    assert number_query("001")["numero_normalizado"] == "1"


@pytest.mark.parametrize("invalid", ["12", "11794'; DROP TABLE x", "%%%", "A12345678901234567890"])
def test_entrada_invalida_no_genera_consulta(invalid):
    with pytest.raises(HTTPException):
        number_query(invalid)


def test_busqueda_local_facturas_recibos_y_formato_no_duplica(db_session, client):
    from datetime import date
    for kind, number in [
        (TipoComprobante.FAC_ANTICIPO, "A0007-00011794"),
        (TipoComprobante.RECIBO, "E0000000011794"),
        (TipoComprobante.FAC_MERCADERIA, "B0008-00011794"),
        (TipoComprobante.FAC_ANTICIPO, "A0007-00911794"),
        (TipoComprobante.ORDEN_COMPRA, "11794"),
    ]:
        db_session.add(Comprobante(tipo=kind, numero=number, emisor="Emisor", fecha=date(2025, 10, 23), importe=100))
    db_session.commit()
    response = client.get("/documentacion/coincidencias-numero", params={"numero": "11794"})
    assert response.status_code == 200, response.text
    rows = response.json()["resultados"]
    assert len(rows) == 3
    assert any(r["tipo"] == "RECIBO" for r in rows)
    assert next(r for r in rows if r["tipo"] == "FAC_MERCADERIA")["bloqueo"] is None
    exact = client.get("/documentacion/coincidencias-numero", params={"numero": "A7-11794"}).json()
    assert len(exact["resultados"]) == 1
    assert db_session.query(Comprobante).count() == 5


def test_numero_consulta_ambas_clases_y_empresas_sin_guardar_comprobantes(db_session, client, monkeypatch):
    a = acopio(db_session, 100)
    invoice = record(1)
    invoice.update(numero="A0000700011794", es_anticipo=True, cliente_coincide=False,
                   cliente="Razón social en Tango", motivos=["El nombre no coincide: revisar."])
    receipt = record(2, "REC", total="500", net="0", iva="0", company="VIVIANA")
    receipt["numero"] = "E0000000011794"
    source, calls = mock_access(monkeypatch, [invoice, receipt])
    url = f"/acopios/{a.id}/tango/buscar-numero"
    response = client.post(url, json={"numero": "11794"})
    assert response.status_code == 200, response.text
    rows = response.json()["resultados"]
    assert {r["empresa"] for r in rows} == {"FONTELA", "VIVIANA"}
    assert {r["tipo"] for r in rows} == {"FAC_ANTICIPO", "RECIBO"}
    # A local nickname can differ from the legal name: show it for explicit review.
    fac = next(r for r in rows if r["tipo"] == "FAC_ANTICIPO")
    assert fac["cliente"] == "Razón social en Tango" and fac["motivos"] and not fac["bloqueo"]
    assert calls[0][0] == "lookup"
    assert calls[0][1]["numero_normalizado"] == "11794"
    assert calls[0][1]["numero_modo"] == "SECUENCIA"
    assert db_session.query(Comprobante).count() == 0
    exact = client.post(url, json={"numero": "A7-11794"}).json()
    assert len(exact["resultados"]) == 1
    source[0]["es_anticipo"] = False
    ordinary = client.post(url, json={"numero": "11794"}).json()
    merchandise = next(r for r in ordinary["resultados"] if r["tipo"] == "FAC_MERCADERIA")
    assert merchandise["bloqueo"] is None and merchandise["etiqueta"] == "Factura de mercadería"
    before = len(calls)
    assert client.post(url, json={"numero": "11794';DROP"}).status_code == 422
    assert len(calls) == before

def test_tango_no_disponible_no_impide_consulta_local(db_session, client, monkeypatch):
    from datetime import date
    from services import tango_service
    a = acopio(db_session, 100)
    db_session.add(Comprobante(tipo=TipoComprobante.RECIBO, numero="11794",
                               emisor="Manual", fecha=date(2025, 10, 23), importe=100))
    db_session.commit()
    async def offline(*args, **kwargs):
        raise HTTPException(503, "Access no disponible")
    monkeypatch.setattr(tango_service, "request_access", offline)
    assert client.post(f"/acopios/{a.id}/tango/buscar-numero", json={"numero": "11794"}).status_code == 503
    response = client.get("/documentacion/coincidencias-numero", params={"numero": "11794"})
    assert response.status_code == 200 and len(response.json()["resultados"]) == 1
    assert db_session.query(Comprobante).count() == 1
