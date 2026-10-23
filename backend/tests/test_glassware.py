# Glassware contract tests with captured fragments and synthetic approved envelopes.
from copy import deepcopy
from datetime import datetime, timedelta
from decimal import Decimal
from pathlib import Path
import json
import pytest
from models import Acopio
from models.glassware_import import GlasswareImport
from integrations.glassware.parser import Document, GlasswareError, parse_budget, allocate, budget_id
from services.proceso_inference import infer_item_processes_from_texts

FIXTURES = Path(__file__).parent / 'fixtures/glassware'


def source(name='dvh', total=None):
    data = json.loads((FIXTURES / (name+'.json')).read_text())
    summary = Document(data['budget_html']).root.one(id='items').one(id='item_'+data['items'][0]['id'])
    quantity = '27' if name == 'dvh' else '22'
    area = '62,97' if name == 'dvh' else '17,29'
    perimeter = '183,24' if name == 'dvh' else '143,53'
    amount = '$14.524.598,63' if name == 'dvh' else '$1.691.172,14'
    complements = '134' if name == 'dvh' else '30'
    adjustment = ''
    if total:
        from integrations.glassware.parser import number
        pct = ((number(total)/number(amount)-1)*100).quantize(Decimal('0.01'))
        adjustment = f'<p>Ajuste: <span>{str(pct).replace(".", ",")}%</span></p>'
    # Retain the captured item markup. The one-item approved envelope is synthetic.
    import re
    original = data['budget_html']
    start = original.index('<turbo-frame class="item" id="item_'+data['items'][0]['id']+'">')
    fragment = original[start:original.index('</turbo-frame>', start)+len('</turbo-frame>')]
    data['budget_html'] = f'''<div class="budget-detail">
      <div class="budget-detail__header-info"><div class="identifier"><strong>#000216163</strong></div>
      <div class="chip chip--budget-detail accepted">Aceptado</div>
      <p class="title"><b>Cliente de prueba</b> / Obra de prueba</p></div>
      <turbo-frame id="items">{fragment}</turbo-frame>
      <div class="budget-detail__bottom-resume"><p>Total superficie: <span>{area} m2</span></p>
      <p>Total perimetro: <span>{perimeter} m</span></p><p>Vidrios: <span>{quantity} u</span></p>
      <p>Complementos: <span>{complements} u</span></p><p>Peso estimado: <span>100,00 Kg</span></p>{adjustment}<div class="total">Total: <span><b>{total or amount}</b></span></div></div></div>'''
    return data


def test_dvh_measures_components_and_unknown_pano_prices():
    data = parse_budget(source())
    item = data.items[0]
    assert item.cantidad == 27 and len(item.panos) == 14
    assert sum(p.superficie_m2 for p in item.panos) == item.total_m2 == Decimal('62.97')
    assert sum(p.perimetro_ml for p in item.panos) == item.total_ml == Decimal('183.24')
    assert all(p.precio_unitario is None and p.precio_total is None for p in item.panos)
    assert item.adicionales[0].cantidad == 134
    components = data.metadata['items'][0]['componentes']
    assert len(components) == 4
    assert components[0]['precio'] == '56154.17'
    assert components[0]['ajuste_visible'] == '-18,00%'
    assert infer_item_processes_from_texts([item.descripcion])['camara_normal']
    # No automatic removal based on an ALTERNATIVA label in an accepted source.
    assert item.descripcion.startswith('ALTERNATIVA 1:')


def test_profilit_complements_and_full_detail():
    data = parse_budget(source('profilit'))
    item = data.items[0]
    assert item.cantidad == 22 and len(item.adicionales) == 4
    assert data.total_m2 == Decimal('17.29')
    assert data.total_pesos == Decimal('1691172.14')


def test_global_adjustment_preserves_exact_total():
    data = parse_budget(source(total='$13.123.456,78'))
    assert sum(i.total_pesos for i in data.items) == data.total_pesos == Decimal('13123456.78')
    assert data.metadata['importe_sin_ajuste'] == '14524598.63'
    assert data.warnings
    assert sum(allocate(Decimal('20204900.01'), [Decimal('19477894.39'), Decimal('2658229.20')])) == Decimal('20204900.01')


@pytest.mark.parametrize('url', ['http://glassware.fontela.com.ar/budgets/1',
    'https://evil.test/budgets/1', 'https://glassware.fontela.com.ar@evil.test/budgets/1',
    'https://glassware.fontela.com.ar/budgets/1/state', 'https://glassware.fontela.com.ar/budgets/1?x=2'])
def test_only_budget_links_are_accepted(url):
    with pytest.raises(GlasswareError): budget_id(url)


def test_unapproved_source_is_rejected():
    data = source()
    data['budget_html'] = data['budget_html'].replace('>Aceptado<', '>Enviado<')
    with pytest.raises(GlasswareError, match='Solo se pueden importar'): parse_budget(data)


@pytest.mark.parametrize('change', ['missing_item', 'duplicate_item', 'quantity', 'dimension', 'changed_total', 'description'])
def test_incomplete_or_changed_sources_fail_closed(change):
    data = source()
    if change == 'missing_item': data['items'] = []
    if change == 'duplicate_item': data['items'].append(deepcopy(data['items'][0]))
    if change == 'quantity': data['items'][0]['measures'][0][3] = '200'
    if change == 'dimension': data['items'][0]['measures'][0][1] = '1000.5'
    if change == 'changed_total': data['items'][0]['html'] = data['items'][0]['html'].replace('$14.524.598,63', '$14.524.598,64')
    if change == 'description': data['items'][0]['html'] = data['items'][0]['html'].replace('ALTERNATIVA 1:', 'OTRO:')
    with pytest.raises(GlasswareError): parse_budget(data)


def test_preview_confirm_duplicate_and_source_audit(client, db_session):
    result = client.post('/integrations/glassware/preview', json=source())
    assert result.status_code == 200, result.text
    token = result.json()['preview_id']
    assert db_session.query(Acopio).count() == 0
    assert 'authenticity_token' not in json.dumps(result.json())
    confirmed = client.post('/integrations/glassware/confirm', json={'preview_id': token})
    assert confirmed.status_code == 200, confirmed.text
    aid = confirmed.json()['acopio_id']
    item = db_session.get(Acopio, aid)
    assert item.origen_datos == 'glassware' and item.numero == '000216163'
    assert item.obra.cliente.nombre == 'Cliente de prueba'
    assert item.total_pesos == sum(i.total_pesos for i in item.items)
    assert item.items[0].proceso_vidrio_exterior and item.items[0].proceso_vidrio_interior
    assert item.items[0].proceso_camara_normal
    assert db_session.query(GlasswareImport).one().acopio_id == aid
    repeated = client.post('/integrations/glassware/confirm', json={'preview_id': token})
    assert repeated.json()['acopio_id'] == aid and repeated.json()['already_created']
    assert db_session.query(Acopio).count() == 1
    assert client.post('/integrations/glassware/preview', json=source()).status_code == 409


def test_preview_expiry_and_payload_tampering(client, db_session):
    result = client.post('/integrations/glassware/preview', json=source()).json()
    row = db_session.query(GlasswareImport).one()
    row.created_at = datetime.utcnow()-timedelta(hours=3)
    db_session.commit()
    assert client.post('/integrations/glassware/confirm', json={'preview_id': result['preview_id']}).status_code == 409
    assert client.post('/integrations/glassware/confirm', json={'preview_id': result['preview_id'], 'total_pesos': 1}).status_code == 422
    assert db_session.query(Acopio).count() == 0


def test_incomplete_preview_creates_nothing(client, db_session):
    data = source()
    data['items'] = []
    assert client.post('/integrations/glassware/preview', json=data).status_code == 422
    assert db_session.query(GlasswareImport).count() == db_session.query(Acopio).count() == 0


def test_detail_exposes_provenance_without_raw_html(client, db_session):
    result = client.post('/integrations/glassware/preview', json=source()).json()
    aid = client.post('/integrations/glassware/confirm', json={'preview_id': result['preview_id']}).json()['acopio_id']
    detail = client.get(f'/acopios/{aid}')
    assert detail.status_code == 200, detail.text
    provenance = detail.json()['glassware_origen']
    assert provenance['glassware_id'] == '17292'
    assert provenance['estado'] == 'Aceptado'
    assert len(provenance['items'][0]['componentes']) == 4
    assert 'budget_html' not in provenance


def test_duplicate_previews_and_legacy_unpadded_budget(client, db_session):
    first = client.post('/integrations/glassware/preview', json=source()).json()
    second = client.post('/integrations/glassware/preview', json=source()).json()
    assert client.post('/integrations/glassware/confirm', json={'preview_id': first['preview_id']}).status_code == 200
    assert client.post('/integrations/glassware/confirm', json={'preview_id': second['preview_id']}).status_code == 409
    acopio = db_session.query(Acopio).one()
    acopio.numero = '216163'
    acopio.v_presupuesto_id = '216163'
    db_session.commit()
    assert client.post('/integrations/glassware/preview', json=source()).status_code == 409


def test_real_accepted_templado_preserves_global_total_and_processes():
    captured = json.loads((FIXTURES / 'templado.json').read_text())
    data = parse_budget(captured)
    assert data.numero == '000215390'
    assert data.total_unidades == 104
    assert data.total_m2 == Decimal('184.81') and data.total_ml == Decimal('641.50')
    assert data.total_pesos == Decimal('20204900.01')
    assert sum(i.total_pesos for i in data.items) == data.total_pesos
    assert data.metadata['importe_sin_ajuste'] == '22136123.59'
    assert data.metadata['ajuste_importe'] == '-1931223.58'
    assert [len(i.panos) for i in data.items] == [9, 2]
    assert [len(i['componentes']) for i in data.metadata['items']] == [1, 3]
    assert data.metadata['items'][0]['componentes'][0]['ajuste_visible'] == '+20,00%'
    second = data.metadata['items'][1]['componentes']
    assert second[1]['tipo'] == second[2]['tipo'] == 'proceso'
    assert second[1]['precio'] == '10128.00' and second[2]['precio'] == '63756.00'
    flags = infer_item_processes_from_texts([data.items[1].descripcion])
    assert flags['pulido'] and flags['fason_templado_exterior']


def test_original_observations_are_retained():
    data = source()
    data['budget_html'] = data['budget_html'].replace('<div class="budget-detail__bottom-resume">',
        '<div class="budget-detail__bottom-resume"><textarea id="observations">LOS CURVADOS REQUIEREN APOYO ESTRUCTURAL INFERIOR</textarea>')
    parsed = parse_budget(data)
    assert parsed.metadata['observaciones'] == 'LOS CURVADOS REQUIEREN APOYO ESTRUCTURAL INFERIOR'
    assert parsed.metadata['observaciones'] in parsed.presupuestos[0].condiciones


def test_partial_source_requires_separate_verification_and_keeps_full_agreement(client, db_session):
    captured = json.loads((FIXTURES / 'parcial.json').read_text())
    result = client.post('/integrations/glassware/preview', json=captured)
    assert result.status_code == 200, result.text
    data = result.json()
    assert data['data']['total_unidades'] == 46
    assert data['data']['total_pesos'] == '19794704.51'
    assert data['data']['metadata']['observaciones'] == 'LOS CURVADOS REQUIEREN APOYO ESTRUCTURAL INFERIOR'
    token = data['preview_id']
    assert client.get(f'/integrations/glassware/preview/{token}').status_code == 200
    assert client.post('/integrations/glassware/confirm', json={'preview_id': token}).status_code == 409
    assert db_session.query(Acopio).count() == 0
    confirmed = client.post('/integrations/glassware/confirm', json={'preview_id': token, 'aprobacion_verificada': True})
    assert confirmed.status_code == 200, confirmed.text
    acopio = db_session.get(Acopio, confirmed.json()['acopio_id'])
    assert acopio.total_unidades == acopio.saldo_unidades == 46
    assert acopio.total_pesos == acopio.saldo_pesos == Decimal('19794704.51')
    assert sum(a.cantidad for i in acopio.items for a in i.adicionales) == 144
    assert db_session.query(GlasswareImport).one().datos['metadata']['aprobacion_verificada']
    assert client.get(f'/integrations/glassware/preview/{token}').status_code == 409



def test_no_negative_cent_allocation_with_many_rows():
    amounts = allocate(Decimal('1.50'), [Decimal('1')] * 200)
    assert sum(amounts) == Decimal('1.50')
    assert all(v in {Decimal('0'), Decimal('0.01')} for v in amounts)
    assert sum(allocate(Decimal('0.01'), [Decimal('1')]*5000)) == Decimal('0.01')
    with pytest.raises(GlasswareError): allocate(Decimal('1'), [Decimal('-1'), Decimal('2')])


@pytest.mark.parametrize('change', ['missing_quantity', 'fractional_total_quantity', 'missing_complements',
    'mismatched_complements', 'missing_material_price', 'negative_component_price', 'unknown_adjustment',
    'wrong_adjustment', 'nonfinite', 'duplicate_measure', 'oversized_dimension'])
def test_invalid_contract_data_is_rejected_without_creating_preview(client, db_session, change):
    data = source()
    if change == 'missing_quantity':
        data['budget_html'] = data['budget_html'].replace('class="item__left quantity"', 'class="missing"').replace('class="quantity"', 'class="missing"')
    if change == 'fractional_total_quantity':
        data['budget_html'] = data['budget_html'].replace('>27 u<', '>27,5 u<')
    if change == 'missing_complements':
        data['budget_html'] = data['budget_html'].replace('<p>Complementos: <span>134 u</span></p>', '')
    if change == 'mismatched_complements':
        data['budget_html'] = data['budget_html'].replace('>134 u<', '>135 u<')
    if change == 'missing_material_price':
        data['items'][0]['html'] = data['items'][0]['html'].replace('class="total minor"', 'class="missing"', 1)
    if change == 'negative_component_price':
        data['items'][0]['html'] = data['items'][0]['html'].replace('$56.154,17', '-$56.154,17')
    if change == 'unknown_adjustment':
        data['budget_html'] = data['budget_html'].replace('<b>$14.524.598,63</b>', '<b>$14.000.000,00</b>')
    if change == 'wrong_adjustment':
        data['budget_html'] = data['budget_html'].replace('<b>$14.524.598,63</b>', '<b>$14.000.000,00</b>').replace('<div class="total">', '<p>Ajuste: 10,00%</p><div class="total">')
    if change == 'nonfinite': data['items'][0]['measures'][0][1] = 'NaN'
    if change == 'duplicate_measure': data['items'][0]['measures'].append(data['items'][0]['measures'][0])
    if change == 'oversized_dimension': data['items'][0]['measures'][0][1] = '999999999999999'
    result = client.post('/integrations/glassware/preview', json=data)
    assert result.status_code == 422, result.text
    assert db_session.query(Acopio).count() == db_session.query(GlasswareImport).count() == 0


def test_confirmation_rolls_back_all_entities_on_failure(client, db_session, monkeypatch):
    from routers.glassware import AcopioCreationService
    from models import Cliente, Obra, Presupuesto, AcopioItem, AcopioItemPano
    original = AcopioCreationService.persist_from_normalized_data
    token = client.post('/integrations/glassware/preview', json=source()).json()['preview_id']
    def fail_after_flush(db, data, **kwargs):
        original(db, data, **kwargs)
        raise RuntimeError('simulated failure after inserting entities')
    monkeypatch.setattr(AcopioCreationService, 'persist_from_normalized_data', fail_after_flush)
    with pytest.raises(RuntimeError):
        client.post('/integrations/glassware/confirm', json={'preview_id': token})
    assert all(db_session.query(model).count() == 0 for model in (Cliente, Obra, Presupuesto, Acopio, AcopioItem, AcopioItemPano))
    assert db_session.query(GlasswareImport).one().acopio_id is None


def test_approval_requires_a_real_boolean(client, db_session):
    token = client.post('/integrations/glassware/preview', json=source()).json()['preview_id']
    result = client.post('/integrations/glassware/confirm', json={'preview_id': token, 'aprobacion_verificada': 'yes'})
    assert result.status_code == 422
    assert db_session.query(Acopio).count() == 0



def test_deleted_acopio_cannot_be_recreated_with_a_consumed_preview(client, db_session):
    token = client.post('/integrations/glassware/preview', json=source()).json()['preview_id']
    aid = client.post('/integrations/glassware/confirm', json={'preview_id': token}).json()['acopio_id']
    assert client.delete(f'/acopios/{aid}').status_code == 204
    assert client.post('/integrations/glassware/confirm', json={'preview_id': token}).status_code == 409
    assert db_session.query(Acopio).count() == 0
    assert db_session.query(GlasswareImport).one().confirmado_en is not None


def test_request_body_limit(client):
    response = client.post('/integrations/glassware/preview', content=b' ' * 8000001,
        headers={'Content-Type': 'application/json'})
    assert response.status_code == 413
