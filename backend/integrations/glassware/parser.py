"""Read Glassware's budget fragments; never evaluate their scripts or fetch URLs."""
from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP, ROUND_DOWN
from html.parser import HTMLParser
import re
from urllib.parse import urlparse

from services.acopio_creation_models import (
    NormalizedAcopioData, NormalizedItem, NormalizedPano,
    NormalizedAdicional, NormalizedPresupuesto,
)

CENT = Decimal('0.01')


class GlasswareError(ValueError):
    pass


@dataclass
class Node:
    tag: str = ''
    attrs: dict = field(default_factory=dict)
    children: list = field(default_factory=list)

    @property
    def text(self):
        return re.sub(r'\s+', ' ', ' '.join(c if isinstance(c, str) else c.text for c in self.children)).strip()

    def find(self, *, id=None, cls=None, tag=None, prefix=None):
        found = []
        for child in self.children:
            if not isinstance(child, Node):
                continue
            if ((id is None or child.attrs.get('id') == id)
                    and (cls is None or cls in child.attrs.get('class', '').split())
                    and (tag is None or child.tag == tag)
                    and (prefix is None or child.attrs.get('id', '').startswith(prefix))):
                found.append(child)
            found.extend(child.find(id=id, cls=cls, tag=tag, prefix=prefix))
        return found

    def one(self, **kwargs):
        nodes = self.find(**kwargs)
        if len(nodes) != 1:
            raise GlasswareError('La estructura de Glassware cambió o falta un dato requerido. Volvé a consultar.')
        return nodes[0]


class Document(HTMLParser):
    def __init__(self, html):
        super().__init__(convert_charrefs=True)
        self.root = Node()
        self.stack = [self.root]
        self.feed(html)

    def handle_starttag(self, tag, attrs):
        if len(self.stack) > 80:
            raise GlasswareError('Respuesta de Glassware demasiado compleja.')
        node = Node(tag, dict(attrs))
        self.stack[-1].children.append(node)
        if tag not in {'area', 'base', 'br', 'col', 'embed', 'hr', 'img', 'input', 'link', 'meta', 'param', 'source', 'track', 'wbr'}:
            self.stack.append(node)

    def handle_startendtag(self, tag, attrs):
        self.stack[-1].children.append(Node(tag, dict(attrs)))

    def handle_endtag(self, tag):
        for i in range(len(self.stack)-1, 0, -1):
            if self.stack[i].tag == tag:
                del self.stack[i:]
                break

    def handle_data(self, data):
        self.stack[-1].children.append(data)


def number(text):
    """Visible amounts use Argentine separators; machine data is handled separately."""
    raw = re.sub(r'[^\d,+.\-]', '', str(text).replace('−', '-')).replace('.', '').replace(',', '.')
    try:
        value = Decimal(raw)
    except InvalidOperation as exc:
        raise GlasswareError('Glassware devolvió un importe o una cantidad inválida.') from exc
    if not value.is_finite() or abs(value) > Decimal('9999999999999'):
        raise GlasswareError('Valor fuera del rango admitido.')
    return value


def machine_number(value):
    try:
        result = Decimal(str(value))
    except InvalidOperation as exc:
        raise GlasswareError('Medida inválida.') from exc
    if not result.is_finite() or result <= 0 or result > 1000000:
        raise GlasswareError('Medida o cantidad fuera del rango admitido.')
    return result


def money(value):
    return value.quantize(CENT, rounding=ROUND_HALF_UP)


def allocate(total, weights):
    """Cent-exact proportional allocation, with the residual on the largest row."""
    base = sum(weights)
    if not weights or base <= 0 or total < 0 or total != money(total) or any(w < 0 for w in weights):
        raise GlasswareError('El presupuesto no tiene una base válida para distribuir importes.')
    # Largest remainder: every row is nonnegative, even for thousands of tiny amounts.
    shares = [total * 100 * w / base for w in weights]
    cents = [int(share.to_integral_value(rounding=ROUND_DOWN)) for share in shares]
    remaining = int(total * 100) - sum(cents)
    order = sorted(range(len(weights)), key=lambda i: shares[i]-cents[i], reverse=True)
    for i in order[:remaining]:
        cents[i] += 1
    return [Decimal(c) / 100 for c in cents]


def budget_id(url):
    parsed = urlparse(url)
    match = re.fullmatch(r'/budgets/([1-9]\d*)/?', parsed.path)
    if (parsed.scheme != 'https' or parsed.netloc != 'glassware.fontela.com.ar'
            or parsed.query or parsed.fragment or not match):
        raise GlasswareError('Pegá el enlace completo de un presupuesto de Glassware.')
    return match[1]


def labeled(node, prefix):
    matches = [p for p in node.find(tag='p') if p.text.startswith(prefix)]
    if len(matches) != 1:
        raise GlasswareError(f'No se encontró el total «{prefix}» en Glassware.')
    return number(matches[0].text[len(prefix):].replace('m2', '').replace('m²', ''))


def parse_budget(source):
    gid = budget_id(source['url'])
    root = Document(source['budget_html']).root.one(cls='budget-detail')
    header = root.one(cls='budget-detail__header-info')
    state = header.one(cls='chip--budget-detail').text
    if state.casefold() not in {'aceptado', 'parcial'}:
        raise GlasswareError(f'El presupuesto está «{state}». Solo se pueden importar presupuestos Aceptados o Parciales con aprobación verificada.')
    numero = header.one(cls='identifier').one(tag='strong').text.lstrip('#')
    if not re.fullmatch(r'\d{1,9}', numero):
        raise GlasswareError('Número de presupuesto inválido.')
    numero = numero.zfill(9)
    title = header.one(cls='title')
    cliente = title.one(tag='b').text
    obra = title.text[len(cliente):].strip(' /')
    if not cliente or len(cliente) > 200 or not obra or len(obra) > 200:
        raise GlasswareError('Falta cliente u obra, o su nombre supera el largo admitido.')
    resume = root.one(cls='budget-detail__bottom-resume')
    total = number(resume.one(cls='total').one(tag='b').text)
    if total <= 0:
        raise GlasswareError('El total contratado debe ser positivo.')
    expected_quantity = labeled(resume, 'Vidrios:')
    expected_area = labeled(resume, 'Total superficie:')
    expected_perim = labeled(resume, 'Total perimetro:')
    expected_complements = labeled(resume, 'Complementos:')
    if (expected_quantity <= 0 or expected_quantity != expected_quantity.to_integral_value()
            or expected_quantity > 2147483647 or expected_complements < 0
            or expected_complements != expected_complements.to_integral_value()
            or expected_complements > 2147483647):
        raise GlasswareError('Los totales de paños y complementos deben ser cantidades enteras válidas.')
    if not (0 <= expected_area <= Decimal('9999999999.99') and 0 <= expected_perim <= Decimal('9999999999.99')):
        raise GlasswareError('La superficie o el perímetro supera el rango admitido.')
    summaries = root.one(id='items').find(tag='turbo-frame', prefix='item_')
    details = {str(d['id']): d for d in source['items']}
    ids = [s.attrs['id'].removeprefix('item_') for s in summaries]
    if not ids or len(ids) != len(set(ids)) or len(details) != len(source['items']) or set(ids) != set(details):
        raise GlasswareError('El detalle recibido no incluye exactamente todos los ítems del presupuesto.')

    items, snapshots, raw_totals, warnings = [], [], [], []
    if state.casefold() == 'parcial':
        warnings.append('Glassware muestra Parcial. Se consulta el presupuesto completo; antes del alta debés verificar que está aprobado por el total. No se deducen consumos ni producción de este estado.')
    total_area = total_perim = Decimal('0')
    for index, (sid, summary) in enumerate(zip(ids, summaries), 1):
        description = summary.one(cls='description').text
        if len(description) > 500:
            raise GlasswareError('La descripción de un ítem supera el largo admitido.')
        quantities = summary.find(cls='quantity')
        if not quantities:
            raise GlasswareError('Falta la cantidad de paños del ítem.')
        qty = number(quantities[-1].text)
        if qty <= 0 or qty > 2147483647 or qty != qty.to_integral_value():
            raise GlasswareError('Cantidad de paños inválida.')
        raw_total = number(summary.one(cls='amount').one(cls='total').text)
        if raw_total <= 0:
            raise GlasswareError('El importe de cada ítem debe ser positivo.')
        detail = Document(details[sid]['html']).root.one(id=f'item-{sid}')
        if detail.one(id='item_description').text != description:
            raise GlasswareError('La descripción del ítem cambió durante la consulta. Volvé a consultar.')
        if number(detail.one(id='total-sum').text) != raw_total:
            raise GlasswareError('El importe del ítem cambió durante la consulta. Volvé a consultar.')
        panos, row_ids, area, perimeter = [], set(), Decimal('0'), Decimal('0')
        for row in details[sid]['measures']:
            if len(row) != 5 or str(row[0]) in row_ids:
                raise GlasswareError('Fila de medidas inválida o duplicada.')
            row_ids.add(str(row[0]))
            w, h, q = [machine_number(v) for v in row[1:4]]
            if q != q.to_integral_value() or w != w.to_integral_value() or h != h.to_integral_value():
                raise GlasswareError('Las medidas deben expresarse en milímetros enteros y las cantidades en unidades enteras.')
            a, p = w*h*q/1000000, 2*(w+h)*q/1000
            area += a
            perimeter += p
            denomination = str(row[4] or '')
            if len(denomination) > 50:
                raise GlasswareError('La denominación de un paño supera el largo admitido.')
            panos.append(NormalizedPano(cantidad=int(q), ancho_mm=int(w), alto_mm=int(h),
                superficie_m2=a, perimetro_ml=p, denominacion=denomination))
        if area > Decimal('9999999999.99') or perimeter > Decimal('9999999999.99'):
            raise GlasswareError('Las medidas del ítem superan el rango admitido.')
        if sum(p.cantidad for p in panos) != qty:
            raise GlasswareError(f'Las medidas del ítem {index} no coinciden con su cantidad de paños.')
        measures = summary.one(cls='measures')
        for calculated, css in ((area, 'surface'), (perimeter, 'perimeter')):
            visible = measures.one(cls=css)
            # The mobile label includes the unit; only the remaining visible text is numeric.
            label = visible.find(tag='span')
            text = visible.text
            if label:
                text = text.removeprefix(label[0].text).strip()
            if abs(money(calculated) - number(text)) > CENT:
                raise GlasswareError(f'Las medidas del ítem {index} no coinciden con el resumen de Glassware.')
        components, adicionales = [], []
        for frame in detail.find(tag='turbo-frame'):
            cls = frame.attrs.get('class', '').split()
            if 'item' not in cls:
                continue
            names = frame.find(cls='name')
            prices = frame.find(cls='total')
            if not any(kind in cls for kind in ('material', 'process', 'complement')):
                continue
            if not names or not prices:
                raise GlasswareError('Falta el nombre o el precio de un material, proceso o complemento.')
            name = names[0].text
            price = number(prices[0].text)
            if price < 0 or not name or len(name) > 500:
                raise GlasswareError('Material, proceso o complemento con precio o descripción inválida.')
            discount = frame.find(cls='update-prices')
            originals = frame.find(cls='subtotal')
            units = frame.find(cls='quantity')
            count = number(units[0].text.replace('Cantidad', '')) if units else None
            components.append({'id': frame.attrs.get('id'), 'descripcion': name,
                'precio': str(price), 'precio_original': str(number(originals[0].text)) if originals else str(price),
                'ajuste_visible': discount[0].text if discount else '', 'cantidad': int(count) if count is not None else None,
                'tipo': 'complemento' if 'complement' in cls else ('material' if 'material' in cls else 'proceso')})
            if 'complement' in cls:
                if count is None or count <= 0 or count > 2147483647 or count != count.to_integral_value() or len(name) > 500:
                    raise GlasswareError('Complemento con cantidad o descripción inválida.')
                if money(price*count) > Decimal('9999999999999.99'):
                    raise GlasswareError('El importe de un complemento supera el rango admitido.')
                adicionales.append(NormalizedAdicional(cantidad=int(count), descripcion=name,
                    precio_unitario=price, precio_total=money(price*count), tipo='complemento'))
        if not any(c['tipo'] == 'material' for c in components):
            raise GlasswareError('El detalle del ítem no incluye sus materiales.')
        items.append(NormalizedItem(numero_item=index, descripcion=description, material='',
            tipologia='Glassware', cantidad=int(qty), total_m2=money(area), total_ml=money(perimeter),
            total_pesos=raw_total, panos=panos, adicionales=adicionales))
        snapshots.append({'id': sid, 'componentes': components, 'medidas': details[sid]['measures'], 'importe_original': str(raw_total)})
        raw_totals.append(raw_total)
        total_area += area
        total_perim += perimeter

    if sum(it.cantidad for it in items) != expected_quantity:
        raise GlasswareError('La cantidad total no coincide con los ítems.')
    if abs(money(total_area)-expected_area) > CENT or abs(money(total_perim)-expected_perim) > CENT:
        raise GlasswareError('La superficie o el perímetro total no coincide con las medidas.')
    if sum(a.cantidad for item in items for a in item.adicionales) != expected_complements:
        raise GlasswareError('La cantidad de complementos no coincide con el total de Glassware.')
    difference = total - sum(raw_totals)
    adjustment_nodes = [p for p in resume.find(tag='p') if p.text.startswith('Ajuste:')]
    visible_adjustment = adjustment_nodes[0].text.removeprefix('Ajuste:').strip() if adjustment_nodes else ''
    if not visible_adjustment or visible_adjustment == '-':
        if difference:
            raise GlasswareError('El importe total no coincide con los ítems y Glassware no informa un ajuste general.')
    else:
        if '%' not in visible_adjustment:
            raise GlasswareError('El ajuste general de Glassware tiene un formato desconocido.')
        percentage = number(visible_adjustment)
        # The percentage is displayed with two decimals; allow only its rounding interval.
        expected = sum(raw_totals) * (1 + percentage / 100)
        tolerance = sum(raw_totals) * Decimal('0.00005') + CENT
        if abs(total-expected) > tolerance:
            raise GlasswareError('El total no se corresponde con el ajuste general informado por Glassware.')
    item_amounts = allocate(total, raw_totals)
    for item, amount in zip(items, item_amounts):
        item.total_pesos = amount
        # Complement prices retain their source values; pano prices are unknown, never invented.
    adjustment = total - sum(raw_totals)
    if adjustment:
        warnings.append('El ajuste general se distribuye proporcionalmente entre los ítems, conservando exactamente el total contratado. Los precios de componentes y complementos se conservan antes de ese ajuste.')
    # Aggregate persistence rounds each row: reconcile the cents against the item total.
    for attr in ('superficie_m2', 'perimetro_ml'):
        for item in items:
            target = item.total_m2 if attr == 'superficie_m2' else item.total_ml
            rounded = allocate(target, [getattr(p, attr) for p in item.panos])
            for pano, value in zip(item.panos, rounded):
                setattr(pano, attr, value)
    for attr, target in (('total_m2', expected_area), ('total_ml', expected_perim)):
        delta = target - sum(getattr(it, attr) for it in items)
        if delta:
            item = max(items, key=lambda it: getattr(it, attr))
            setattr(item, attr, getattr(item, attr)+delta)
            pano_attr = 'superficie_m2' if attr == 'total_m2' else 'perimetro_ml'
            pano = max(item.panos, key=lambda p: getattr(p, pano_attr))
            setattr(pano, pano_attr, getattr(pano, pano_attr)+delta)
    observations = root.find(id='observations')
    observations = observations[0].text if observations else ''
    weight = labeled(resume, 'Peso estimado:')
    if weight < 0 or weight > Decimal('99999999.99'):
        raise GlasswareError('El peso estimado supera el rango admitido.')
    budget = NormalizedPresupuesto(numero=numero, empresa=cliente, estado=state,
        peso_estimado_kg=weight,
        condiciones=f'Glassware {gid}. Importe previo al ajuste: {sum(raw_totals)}. Ajuste general: {adjustment}.\n{observations}')
    return NormalizedAcopioData(numero=numero, cliente_nombre=cliente, obra_nombre=obra,
        total_m2=expected_area, total_ml=expected_perim, total_unidades=int(expected_quantity),
        total_pesos=total, origen_datos='glassware', v_presupuesto_id=numero,
        presupuestos=[budget], items=items, warnings=warnings,
        metadata={'glassware_id': gid, 'url': source['url'], 'estado': state,
            'consultado_en': datetime.utcnow().isoformat()+'Z', 'importe_sin_ajuste': str(sum(raw_totals)),
            'ajuste_importe': str(adjustment), 'observaciones': observations, 'items': snapshots})
