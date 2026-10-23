"""Business regressions for net documentation and commercial allocations."""
from datetime import date
from decimal import Decimal
import json
import pytest
from models import Acopio, AcopioPaquete, EstadoAcopio, Documento, Comprobante, AfectacionAcopio
from config import settings


@pytest.fixture(autouse=True)
def document_storage(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, 'storage_path', tmp_path)


def acopio(db, total='1000.00', porcentaje=None, paquete=None):
    row = Acopio(numero=f'TEST-{db.query(Acopio).count() + 1}', fecha_alta=date(2026, 10, 16),
                 estado=EstadoAcopio.ACTIVO, total_pesos=Decimal(total), saldo_pesos=Decimal(total),
                 porcentaje_facturado=porcentaje, paquete_id=paquete)
    db.add(row)
    db.commit()
    return row


def reparto(client, row, porcentaje=50):
    response = client.put(f'/acopios/{row.id}/documentacion/reparto', json={'porcentaje_facturado': porcentaje})
    assert response.status_code == 200, response.text
    return response.json()


def add(client, row, tipo, numero, amount, facturado, reference=None, original=None, pdf=None, iva=None):
    payload = {'tipo': tipo, 'numero': numero, 'emisor': 'Emisor de prueba', 'fecha': '2026-10-16',
               'importe': str(original or amount), 'importe_aplicado': str(amount),
               'importe_facturado': str(facturado), 'referencia_id': reference, 'iva': iva}
    kwargs = {'data': {'payload': json.dumps(payload)}}
    if pdf:
        kwargs['files'] = {'file': pdf}
    return client.post(f'/acopios/{row.id}/documentacion/comprobantes', **kwargs)


def last(response):
    assert response.status_code in (200, 201), response.text
    return response.json()['documentos'][-1]


def test_historicos_sin_clasificar_y_reparto_decimal(client, db_session):
    a = acopio(db_session, total='1000.01')
    snapshot = client.get(f'/acopios/{a.id}/documentacion').json()
    assert snapshot['porcentaje_facturado'] is None
    assert snapshot['acordado_facturado'] is None
    assert add(client, a, 'RECIBO', 'R1', 10, 0).status_code == 422
    data = reparto(client, a)
    assert data['acordado_facturado'] == 500.01
    assert data['acordado_viviana'] == 500.00
    assert Decimal(str(data['acordado_facturado'])) + Decimal(str(data['acordado_viviana'])) == Decimal('1000.01')
    for invalid in (-1, 101, '50.001', 'NaN'):
        assert client.put(f'/acopios/{a.id}/documentacion/reparto', json={'porcentaje_facturado': invalid}).status_code == 422
    db_session.refresh(a)
    assert a.saldo_pesos == Decimal('1000.01')


@pytest.mark.parametrize('oc_total,oc_facturado', [('1000', '500'), ('500', '500')])
def test_oc_total_o_solo_facturado_conciliadas_sin_duplicar(client, db_session, oc_total, oc_facturado):
    a = acopio(db_session)
    reparto(client, a)
    oc = last(add(client, a, 'ORDEN_COMPRA', 'OC-0001', oc_total, oc_facturado))
    assert oc['estado'] == 'PENDIENTE_FACTURA'
    invoice = last(add(client, a, 'FAC_ANTICIPO', 'A-0001', 500, 500, oc['id'], iva='105'))
    assert invoice['estado'] == 'COINCIDENTE'
    assert invoice['comprobante']['total'] == 605
    response = add(client, a, 'RECIBO', 'R-VIVIANA', 500, 0)
    data = response.json()
    assert data['documentos'][0]['estado'] == 'COINCIDENTE'
    assert data['totales']['anticipos_facturados'] == 500
    assert data['totales']['cobrado_viviana'] == 500
    assert data['totales']['cobrado_facturado'] == 0
    db_session.refresh(a)
    assert a.total_pesos == 1000 and a.saldo_pesos == 1000


def test_factura_primero_con_diferencia_y_edicion(client, db_session):
    a = acopio(db_session)
    reparto(client, a, 100)
    invoice = last(add(client, a, 'FAC_ANTICIPO', 'F1', 400, 400))
    assert invoice['estado'] == 'PENDIENTE_OC'
    oc = last(add(client, a, 'ORDEN_COMPRA', 'OC1', 500, 500))
    payload = {'tipo': 'FAC_ANTICIPO', 'numero': 'F1', 'emisor': 'Emisor de prueba', 'fecha': '2026-10-16',
               'importe': '400', 'importe_aplicado': '400', 'importe_facturado': '400', 'referencia_id': oc['id']}
    response = client.put(f'/acopios/{a.id}/documentacion/comprobantes/{invoice["id"]}', data={'payload': json.dumps(payload)})
    assert response.status_code == 200, response.text
    statuses = {r['id']: r for r in response.json()['documentos']}
    assert statuses[invoice['id']]['estado'] == 'CON_DIFERENCIA'
    assert statuses[oc['id']]['diferencia'] == 100
    payload.update(importe='500', importe_aplicado='500', importe_facturado='500')
    response = client.put(f'/acopios/{a.id}/documentacion/comprobantes/{invoice["id"]}', data={'payload': json.dumps(payload)})
    assert all(r['estado'] == 'COINCIDENTE' for r in response.json()['documentos'])


def test_varias_facturas_contra_oc_y_cobros_independientes(client, db_session):
    a = acopio(db_session)
    reparto(client, a, 100)
    oc = last(add(client, a, 'ORDEN_COMPRA', 'OC1', 1000, 1000))
    f1 = last(add(client, a, 'FAC_ANTICIPO', 'F1', 600, 600, oc['id']))
    last(add(client, a, 'FAC_ANTICIPO', 'F2', 400, 400, oc['id']))
    last(add(client, a, 'RECIBO', 'R1', 300, 300, f1['id']))
    response = add(client, a, 'RECIBO', 'R2', 400, 400, f1['id'])
    assert last(response)['estado'] == 'COBRO_EXCEDIDO'
    totals = response.json()['totales']
    assert totals['anticipos_facturados'] == 1000
    assert totals['cobrado_facturado'] == 700
    assert response.json()['documentos'][0]['estado'] == 'COINCIDENTE'


def test_comprobante_compartido_capacidad_referencias_y_paquete(client, db_session):
    p = AcopioPaquete(nombre='Paquete de prueba', cliente='Cliente', fecha_alta=date(2026, 10, 16))
    db_session.add(p)
    db_session.commit()
    a = acopio(db_session, total='600', paquete=p.id)
    b = acopio(db_session, total='400', paquete=p.id)
    reparto(client, a, 0)
    reparto(client, b, 0)
    first = last(add(client, a, 'RECIBO', 'R-COMPARTIDO', 600, 0, original=1000))
    comp_id = first['comprobante']['id']
    assert add(client, b, 'RECIBO', 'R-COMPARTIDO', 400, 0, original=1000).status_code == 409
    url = f'/acopios/{b.id}/documentacion/asociaciones'
    assert client.post(url, json={'comprobante_id': comp_id, 'importe_aplicado': '500', 'importe_facturado': '0'}).status_code == 422
    response = client.post(url, json={'comprobante_id': comp_id, 'importe_aplicado': '400', 'importe_facturado': '0'})
    second = last(response)
    assert second['comprobante']['disponible'] == 0
    consolidated = client.get(f'/acopio-paquetes/{p.id}/documentacion').json()
    assert consolidated['totales']['cobrado_viviana'] == 1000
    assert consolidated['totales']['anticipos_facturados'] == 0
    assert consolidated['sin_clasificar'] == 0
    assert client.post(url, json={'comprobante_id': comp_id, 'importe_aplicado': '0.01', 'importe_facturado': '0'}).status_code == 422
    assert client.patch(f'/acopios/{b.id}/documentacion/asociaciones/{first["id"]}', json={'anulada': True}).status_code == 404


def test_anular_y_restaurar_no_borra_archivos_ni_altera_saldo(client, db_session):
    a = acopio(db_session)
    reparto(client, a)
    oc = last(add(client, a, 'ORDEN_COMPRA', 'OC1', 1000, 500))
    f = last(add(client, a, 'FAC_ANTICIPO', 'F1', 500, 500, oc['id']))
    oc_url = f'/acopios/{a.id}/documentacion/asociaciones/{oc["id"]}'
    f_url = f'/acopios/{a.id}/documentacion/asociaciones/{f["id"]}'
    assert client.patch(oc_url, json={'anulada': True}).status_code == 422
    response = client.patch(f_url, json={'anulada': True})
    assert response.json()['totales']['anticipos_facturados'] == 0
    assert client.patch(oc_url, json={'anulada': True}).status_code == 200
    assert client.patch(f_url, json={'anulada': False}).status_code == 422
    assert client.patch(oc_url, json={'anulada': False}).status_code == 200
    response = client.patch(f_url, json={'anulada': False})
    assert response.json()['totales']['anticipos_facturados'] == 500
    db_session.refresh(a)
    assert a.saldo_pesos == 1000


def test_pdf_descarga_deduplicada_validacion_y_relacion_real(client, db_session):
    a = acopio(db_session)
    reparto(client, a)
    content = b'%PDF-1.4\n% respaldo de prueba, sin extraccion\n%%EOF'
    first = last(add(client, a, 'ORDEN_COMPRA', 'OC1', 500, 500, pdf=('Orden de compra.pdf', content, 'application/pdf')))
    invoice = last(add(client, a, 'FAC_ANTICIPO', 'F1', 500, 500, first['id'], pdf=('factura.PDF', content, 'application/pdf')))
    assert db_session.query(Documento).count() == 1
    assert db_session.query(Comprobante).count() == 2
    assert db_session.query(AfectacionAcopio).count() == 2
    response = client.get(invoice['comprobante']['archivo']['url'])
    assert response.status_code == 200 and response.content == content
    assert response.headers['content-type'] == 'application/pdf'
    assert response.headers['content-disposition'].startswith('inline')
    before = db_session.query(Comprobante).count()
    assert add(client, a, 'RECIBO', 'BAD', 1, 0, pdf=('bad.pdf', b'not a PDF', 'application/pdf')).status_code == 422
    assert db_session.query(Comprobante).count() == before
    assert add(client, a, 'RECIBO', 'BIG', 1, 0, pdf=('big.pdf', b'%PDF-' + b'x' * (20 * 1024 * 1024), 'application/pdf')).status_code == 422
    assert db_session.query(Comprobante).count() == before
    missing = last(add(client, a, 'RECIBO', 'SIN-PDF', 10, 0))
    assert missing['comprobante']['archivo'] is None
    assert client.get(f'/documentacion/archivos/{missing["comprobante"]["id"]}').status_code == 404
    doc = db_session.query(Documento).first()
    assert doc.entidad_tipo == 'comprobante'


def test_referencias_incorrectas_y_reparto_incompatible(client, db_session):
    a, b = acopio(db_session), acopio(db_session)
    reparto(client, a)
    reparto(client, b)
    oc = last(add(client, a, 'ORDEN_COMPRA', 'OC1', 500, 500))
    assert add(client, b, 'FAC_ANTICIPO', 'F-OTRO', 500, 500, oc['id']).status_code == 404
    assert add(client, a, 'RECIBO', 'R-REF', 500, 0, oc['id']).status_code == 422
    assert add(client, a, 'FAC_ANTICIPO', 'F-VIVIANA', 500, 0).status_code == 422
    assert add(client, a, 'ORDEN_COMPRA', 'OC-MAL', 500, 501).status_code == 422
    assert add(client, a, 'RECIBO', 'R-PRECISION', '1.001', 0).status_code == 422
    assert client.put(f'/acopios/{a.id}/documentacion/reparto', json={'porcentaje_facturado': 0}).status_code == 422
    assert client.put(f'/acopios/{a.id}/documentacion/reparto', json={'porcentaje_facturado': None}).status_code == 422


def test_recibo_viviana_no_requiere_factura_y_cero_cien(client, db_session):
    a = acopio(db_session)
    reparto(client, a, 0)
    receipt = last(add(client, a, 'RECIBO', 'R-VIVIANA', 1000, 0))
    assert receipt['estado'] == 'REGISTRADO'
    assert add(client, a, 'FAC_ANTICIPO', 'F-INVALIDA', 1000, 1000).status_code == 422
    assert client.get(f'/acopios/{a.id}/documentacion').json()['totales']['cobrado_viviana'] == 1000


def test_busqueda_escapa_comodines_y_acopio_inexistente(client, db_session):
    a = acopio(db_session)
    reparto(client, a)
    last(add(client, a, 'RECIBO', 'R-01', 10, 0))
    assert len(client.get('/documentacion/comprobantes', params={'buscar': 'R-01'}).json()) == 1
    assert client.get('/documentacion/comprobantes', params={'buscar': '%'}).json() == []
    assert client.get('/acopios/99999/documentacion').status_code == 404
    assert client.get('/acopio-paquetes/99999/documentacion').status_code == 404


def test_documentacion_coexiste_con_facturas_remitos_y_saldos_de_consumos(client, db_session, monkeypatch):
    """Una factura y un remito de SPF no vuelven a descontarse al documentar el anticipo."""
    from main import app
    from integrations.spf.database import get_spf_db
    from routers.acopios import spf_services
    from models import Pedido, Remito, Imputacion
    from services.acopio_service import update_saldos

    a = acopio(db_session)
    a.v_presupuesto_id = '000123456'
    a.total_m2 = a.saldo_m2 = Decimal('10')
    a.total_ml = a.saldo_ml = Decimal('20')
    a.total_unidades = a.saldo_unidades = 4
    pedido = Pedido(numero='P-450', fecha=date(2026, 10, 16), total_pesos=Decimal('450'))
    db_session.add(pedido)
    db_session.flush()
    db_session.add(Remito(numero='R-MERCADERIA', fecha=pedido.fecha, pedido_id=pedido.id))
    db_session.add(Imputacion(pedido_id=pedido.id, acopio_id=a.id,
                             cantidad_pesos=Decimal('450'), cantidad_m2=Decimal('4'),
                             cantidad_ml=Decimal('8'), cantidad_unidades=2))
    db_session.commit()
    update_saldos(db_session, a.id)

    def fake_spf_db():
        yield object()

    references = [{'nro_factura': 'F-MERCADERIA', 'nro_remito': None, 'empresa': 'Fontela'},
                  {'nro_factura': None, 'nro_remito': 'R-MERCADERIA', 'empresa': 'Fontela'}]

    def fake_avance(spf_db, presupuesto_id, pedidos_imputados):
        assert presupuesto_id == '000123456'
        assert pedidos_imputados == ['P-450']
        return {'v_presupuesto_id': presupuesto_id,
                'resumen': {'importe_total': 450, 'facturado_total': 450, 'remitido_total': 450},
                'pedidos': [{'id': pedido.id, 'nro_pedido': pedido.numero,
                             'comprobantes': references, 'items': [{'comprobantes': references}]}]}

    monkeypatch.setitem(app.dependency_overrides, get_spf_db, fake_spf_db)
    monkeypatch.setattr(spf_services, 'get_avance_comercial_acopio', fake_avance)
    before = client.get(f'/acopios/{a.id}').json()
    avance_before = client.get(f'/acopios/{a.id}/avance-comercial').json()
    assert before['saldos'] == {'pesos': 550, 'm2': 6, 'ml': 12, 'unidades': 2}
    assert len(before['imputaciones']) == 1
    assert avance_before['pedidos'][0]['comprobantes'] == references
    assert client.get(f'/acopios/{a.id}/documentacion').json()['documentos'] == []

    reparto(client, a, 50)
    oc = last(add(client, a, 'ORDEN_COMPRA', 'OC-INICIAL', 1000, 500))
    factura = last(add(client, a, 'FAC_ANTICIPO', 'F-ANTICIPO', 500, 500, oc['id']))
    recibo = last(add(client, a, 'RECIBO', 'REC-VIVIANA', 500, 0))
    edit = {'tipo': 'FAC_ANTICIPO', 'numero': 'F-ANTICIPO', 'emisor': 'Emisor de prueba',
            'fecha': '2026-10-16', 'importe': '500', 'importe_aplicado': '500',
            'importe_facturado': '500', 'referencia_id': oc['id']}
    pdf = b'%PDF-1.4\n% anticipo sin nuevo consumo\n%%EOF'
    response = client.put(f'/acopios/{a.id}/documentacion/comprobantes/{factura["id"]}',
                          data={'payload': json.dumps(edit)},
                          files={'file': ('anticipo.pdf', pdf, 'application/pdf')})
    assert response.status_code == 200, response.text
    receipt_url = f'/acopios/{a.id}/documentacion/asociaciones/{recibo["id"]}'
    assert client.patch(receipt_url, json={'anulada': True}).status_code == 200
    assert client.patch(receipt_url, json={'anulada': False}).status_code == 200

    after = client.get(f'/acopios/{a.id}').json()
    assert after['saldos'] == before['saldos']
    assert after['imputaciones'] == before['imputaciones']
    assert client.get(f'/acopios/{a.id}/avance-comercial').json() == avance_before
    documentation = client.get(f'/acopios/{a.id}/documentacion').json()
    assert documentation['totales']['anticipos_facturados'] == 500
    assert documentation['totales']['cobrado_viviana'] == 500
    assert documentation['totales']['cobrado_facturado'] == 0
    assert len(documentation['documentos']) == 3
    assert db_session.query(Remito).count() == 1
    assert db_session.query(Imputacion).count() == 1

    # Los consumos nuevos siguen descontandose una sola vez despues de documentar el acopio.
    siguiente = Pedido(numero='P-100', fecha=date(2026, 10, 19), total_pesos=Decimal('100'))
    db_session.add(siguiente)
    db_session.flush()
    db_session.add(Imputacion(pedido_id=siguiente.id, acopio_id=a.id,
                             cantidad_pesos=Decimal('100'), cantidad_m2=Decimal('1'),
                             cantidad_ml=Decimal('2'), cantidad_unidades=1))
    db_session.commit()
    update_saldos(db_session, a.id)
    final = client.get(f'/acopios/{a.id}').json()
    assert final['saldos'] == {'pesos': 450, 'm2': 5, 'ml': 10, 'unidades': 1}
    assert sum(row['cantidad_pesos'] for row in final['imputaciones']) == 550
    assert client.get(f'/acopios/{a.id}/documentacion').json()['totales'] == documentation['totales']

def test_factura_mercaderia_pdf_recibo_y_saldos_independientes(client, db_session):
    a = acopio(db_session)
    reparto(client, a, 100)
    oc = last(add(client, a, 'ORDEN_COMPRA', 'OC-MERC', 1000, 1000))
    response = add(client, a, 'FAC_MERCADERIA', 'A0007-00123456', 1000, 1000, oc['id'],
                   iva='210', pdf=('mercaderia.pdf', b'%PDF-1.4\\n%%EOF', 'application/pdf'))
    invoice = last(response)
    assert invoice['estado'] == 'COINCIDENTE'
    assert response.json()['totales']['mercaderia_documentada'] == 1000
    assert response.json()['totales']['anticipos_facturados'] == 0
    assert response.json()['totales']['cobrado_facturado'] == 0
    assert client.get(invoice['comprobante']['archivo']['url']).content.startswith(b'%PDF-')
    found = client.get('/documentacion/comprobantes', params={'buscar': '123456'}).json()
    assert found[0]['tipo'] == 'FAC_MERCADERIA'
    last(add(client, a, 'RECIBO', 'R-MERC', 900, 900, invoice['id']))
    data = client.get(f'/acopios/{a.id}/documentacion').json()
    assert data['totales']['cobrado_facturado'] == 900
    assert data['totales']['mercaderia_documentada'] == 1000
    assert data['totales']['anticipos_facturados'] == 0
    db_session.refresh(a)
    assert a.saldo_pesos == 1000 and a.total_pesos == 1000
    assert add(client, a, 'FAC_MERCADERIA', 'A0007-00123456', 1000, 1000).status_code == 409
    assert add(client, a, 'FAC_ANTICIPO', 'A0007-00123456', 1000, 1000).status_code == 409
    assert add(client, a, 'FAC_MERCADERIA', 'MERC-VIV', 100, 0).status_code == 422


def test_oc_con_anticipo_y_mercaderia_requiere_revisar_aplicacion(client, db_session):
    a = acopio(db_session)
    reparto(client, a, 100)
    oc = last(add(client, a, 'ORDEN_COMPRA', 'OC-AMBAS', 1000, 1000))
    advance = last(add(client, a, 'FAC_ANTICIPO', 'ANT-AMBAS', 1000, 1000, oc['id']))
    response = add(client, a, 'FAC_MERCADERIA', 'MERC-AMBAS', 1000, 1000, oc['id'])
    data = response.json()
    assert all(r['estado'] == 'REVISAR_ANTICIPOS' and r['diferencia'] is None for r in data['documentos'])
    assert data['totales']['anticipos_facturados'] == 1000
    assert data['totales']['mercaderia_documentada'] == 1000
    assert data['totales']['cobrado_facturado'] == 0
    assert any('aplicacion de anticipos' in alert for alert in data['alertas'])
    response = client.patch(f'/acopios/{a.id}/documentacion/asociaciones/{advance["id"]}', json={'anulada': True})
    assert response.status_code == 200
    assert response.json()['documentos'][0]['estado'] == 'COINCIDENTE'
    assert response.json()['totales']['anticipos_facturados'] == 0
    assert response.json()['totales']['mercaderia_documentada'] == 1000


def test_mercaderia_compartida_consolidada_por_importe_aplicado(client, db_session):
    package = AcopioPaquete(nombre='Mercaderia compartida', cliente='Cliente', fecha_alta=date(2026, 10, 20))
    db_session.add(package)
    db_session.commit()
    a = acopio(db_session, total='600', paquete=package.id)
    b = acopio(db_session, total='400', paquete=package.id)
    reparto(client, a, 100)
    reparto(client, b, 100)
    row = last(add(client, a, 'FAC_MERCADERIA', 'MERC-COMPARTIDA', 600, 600, original=1000))
    response = client.post(f'/acopios/{b.id}/documentacion/asociaciones', json={
        'comprobante_id': row['comprobante']['id'], 'importe_aplicado': '400', 'importe_facturado': '400'})
    assert response.status_code == 201
    result = client.get(f'/acopio-paquetes/{package.id}/documentacion').json()
    assert result['totales']['mercaderia_documentada'] == 1000
    assert result['totales']['anticipos_facturados'] == 0
    assert db_session.query(Comprobante).count() == 1
