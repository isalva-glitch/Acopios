"""Manual commercial documents, kept independent from operational consumption."""
from decimal import Decimal, ROUND_HALF_UP
from pathlib import Path
import hashlib
from fastapi import HTTPException, UploadFile
from sqlalchemy import func
from sqlalchemy.orm import Session
from config import settings
from models import Acopio, AcopioPaquete, Comprobante, TipoComprobante, AfectacionAcopio, Documento

CENT = Decimal('0.01')
ZERO = Decimal('0.00')
TYPES = {'ORDEN_COMPRA', 'FAC_ANTICIPO', 'FAC_MERCADERIA', 'RECIBO'}
INVOICE_TYPES = {'FAC_ANTICIPO', 'FAC_MERCADERIA'}
MAX_PDF = 20 * 1024 * 1024


def money(value):
    return Decimal(str(value or 0)).quantize(CENT, rounding=ROUND_HALF_UP)


def kind(comprobante):
    return comprobante.tipo.value if hasattr(comprobante.tipo, 'value') else comprobante.tipo


def get_acopio(db, acopio_id, lock=False):
    query = db.query(Acopio).filter(Acopio.id == acopio_id)
    acopio = (query.with_for_update() if lock else query).first()
    if not acopio:
        raise HTTPException(404, 'Acopio no encontrado')
    return acopio


def get_aplicacion(db, acopio_id, aplicacion_id):
    row = db.query(AfectacionAcopio).filter_by(id=aplicacion_id, acopio_id=acopio_id).first()
    if not row:
        raise HTTPException(404, 'Asociacion no encontrada en este acopio')
    return row


def active_query(db):
    return db.query(AfectacionAcopio).filter(AfectacionAcopio.anulada.is_(False))


def serialize_comprobante(db, comprobante):
    aplicado = money(db.query(func.sum(AfectacionAcopio.importe)).filter(
        AfectacionAcopio.comprobante_id == comprobante.id,
        AfectacionAcopio.anulada.is_(False),
    ).scalar())
    doc = comprobante.documento
    return {
        'id': comprobante.id, 'tipo': kind(comprobante), 'numero': comprobante.numero,
        'emisor': comprobante.emisor, 'fecha': comprobante.fecha.isoformat(),
        'importe': float(comprobante.importe),
        'iva': float(comprobante.iva) if comprobante.iva is not None else None,
        'total': float(comprobante.importe + comprobante.iva) if comprobante.iva is not None else None,
        'descripcion': comprobante.descripcion,
        'origen_tango': {'empresa': comprobante.origen_tango.empresa,
                         'origen_id': comprobante.origen_tango.origen_id,
                         'origen_tipo': comprobante.origen_tango.origen_tipo,
                         'bruto_original': comprobante.origen_tango.datos['total']} if comprobante.origen_tango else None,
        'compartido': db.query(AfectacionAcopio).filter_by(comprobante_id=comprobante.id).count() > 1,
        'aplicado': float(aplicado), 'disponible': float(money(comprobante.importe) - aplicado),
        'archivo': {'nombre': doc.nombre_archivo,
                    'url': f'/documentacion/archivos/{comprobante.id}',
                    'disponible': Path(doc.ruta_storage).is_file()} if doc else None,
    }


def validate_application(db, acopio, comprobante, payload, current=None):
    importe = money(payload.importe_aplicado)
    facturado = money(payload.importe_facturado)
    tipo = kind(comprobante)
    if tipo not in TYPES:
        raise HTTPException(422, 'Tipo de comprobante no habilitado para esta documentacion')
    if comprobante.origen_tango:
        company = comprobante.origen_tango.empresa
        if (company == 'VIVIANA' and facturado != ZERO) or (company == 'FONTELA' and facturado != importe):
            raise HTTPException(422, 'La parte debe coincidir con la empresa de origen de Tango')
        if not current and active_query(db).filter_by(acopio_id=acopio.id, comprobante_id=comprobante.id).first():
            raise HTTPException(409, 'El comprobante de Tango ya esta asociado a este acopio')
    if facturado > importe:
        raise HTTPException(422, 'La parte facturada no puede superar el importe aplicado')
    if acopio.porcentaje_facturado is None:
        raise HTTPException(422, 'Defina primero el reparto Facturado / Viviana del acopio')
    if acopio.porcentaje_facturado == 0 and facturado > 0:
        raise HTTPException(422, 'Este acopio esta definido 100% Viviana')
    if acopio.porcentaje_facturado == 100 and facturado != importe:
        raise HTTPException(422, 'Este acopio esta definido 100% Facturado')
    if tipo in INVOICE_TYPES and facturado != importe:
        raise HTTPException(422, 'La factura corresponde completamente a Facturado')
    if tipo == 'RECIBO' and facturado not in (ZERO, importe):
        raise HTTPException(422, 'Asocie el recibo a Facturado o a Viviana')
    used = active_query(db).filter(AfectacionAcopio.comprobante_id == comprobante.id)
    if current:
        used = used.filter(AfectacionAcopio.id != current.id)
    total_usado = sum((money(row.importe) for row in used.all()), ZERO)
    if total_usado + importe > money(comprobante.importe):
        raise HTTPException(422, 'La suma aplicada a los acopios supera el neto del comprobante')
    if payload.referencia_id:
        reference = get_aplicacion(db, acopio.id, payload.referencia_id)
        expected = {'ORDEN_COMPRA'} if tipo in INVOICE_TYPES else INVOICE_TYPES
        if tipo == 'ORDEN_COMPRA' or reference.anulada or kind(reference.comprobante) not in expected:
            raise HTTPException(422, 'La referencia debe ser una OC activa para la factura, o una factura de anticipo o mercaderia activa para el recibo')
        if current and current.id == reference.id:
            raise HTTPException(422, 'Un comprobante no puede referenciarse a si mismo')
        if tipo == 'RECIBO' and facturado != importe:
            raise HTTPException(422, 'Solo el recibo Facturado puede vincularse a una factura')


def set_application(row, payload):
    row.importe = money(payload.importe_aplicado)
    row.importe_facturado = money(payload.importe_facturado)
    row.referencia_id = payload.referencia_id


async def attach_pdf(db, comprobante, file: UploadFile | None):
    if file is None:
        return
    name = (file.filename or '').replace('\\', '/').split('/')[-1]
    content = await file.read(MAX_PDF + 1)
    if len(name) > 500:
        raise HTTPException(422, 'El nombre del PDF no puede superar 500 caracteres')
    if not name.lower().endswith('.pdf') or not content.startswith(b'%PDF-'):
        raise HTTPException(422, 'Seleccione un archivo PDF valido')
    if len(content) > MAX_PDF:
        raise HTTPException(422, 'El PDF no puede superar 20 MB')
    digest = hashlib.sha256(content).hexdigest()
    doc = db.query(Documento).filter_by(hash=digest).first()
    if doc:
        target = Path(doc.ruta_storage).resolve()
        root = settings.storage_path.resolve()
        if not target.is_relative_to(root):
            raise HTTPException(422, 'El archivo existente esta fuera del almacenamiento configurado')
    else:
        target = settings.storage_path.resolve() / f'{digest}.pdf'
        doc = Documento(entidad_tipo='comprobante', entidad_id=str(comprobante.id),
                        tipo_documento='respaldo_comercial', nombre_archivo=name,
                        hash=digest, ruta_storage=str(target))
        db.add(doc)
    target.parent.mkdir(parents=True, exist_ok=True)
    if not target.is_file():
        target.write_bytes(content)
    db.flush()
    comprobante.documento_id = doc.id


def metadata_from_input(comprobante, payload):
    comprobante.tipo = TipoComprobante(payload.tipo)
    comprobante.numero = payload.numero
    comprobante.emisor = payload.emisor
    comprobante.fecha = payload.fecha
    comprobante.importe = money(payload.importe)
    comprobante.iva = money(payload.iva) if payload.iva is not None else None
    comprobante.descripcion = payload.descripcion


async def save_document(db, acopio_id, payload, file=None, aplicacion_id=None):
    acopio = get_acopio(db, acopio_id, lock=True)
    row = get_aplicacion(db, acopio_id, aplicacion_id) if aplicacion_id else None
    if row and row.anulada:
        raise HTTPException(422, 'Restaure la asociacion antes de editarla')
    if row:
        comprobante = db.query(Comprobante).filter_by(id=row.comprobante_id).with_for_update().one()
        if payload.tipo != kind(comprobante):
            raise HTTPException(422, 'El tipo no se puede cambiar; anule la asociacion y cargue el comprobante correcto')
        others = db.query(AfectacionAcopio).filter(
            AfectacionAcopio.comprobante_id == comprobante.id,
            AfectacionAcopio.id != row.id,
        ).count()
        shared_fields = ('numero', 'emisor', 'fecha', 'importe', 'iva', 'descripcion')
        if (others or comprobante.origen_tango) and any(getattr(comprobante, field) != getattr(payload, field) for field in shared_fields):
            raise HTTPException(409, 'El comprobante es compartido: conserve sus datos originales y edite solo la aplicacion')
    else:
        comprobante = Comprobante()
        db.add(comprobante)
    metadata_from_input(comprobante, payload)
    # Avoid flushing invalid or duplicate metadata before application validation.
    with db.no_autoflush:
        validate_application(db, acopio, comprobante, payload, row)
        duplicate = db.query(Comprobante).filter_by(numero=payload.numero, emisor=payload.emisor)
        if payload.tipo in INVOICE_TYPES:
            duplicate = duplicate.filter(Comprobante.tipo.in_([TipoComprobante(t) for t in INVOICE_TYPES]))
        else:
            duplicate = duplicate.filter(Comprobante.tipo == comprobante.tipo)
        if row:
            duplicate = duplicate.filter(Comprobante.id != comprobante.id)
        if duplicate.first():
            raise HTTPException(409, 'El comprobante ya existe. Use Asociar existente para distribuirlo')
    db.flush()
    if row is None:
        row = AfectacionAcopio(acopio_id=acopio_id, comprobante_id=comprobante.id)
        db.add(row)
    set_application(row, payload)
    await attach_pdf(db, comprobante, file)
    db.commit()
    return snapshot(db, acopio_id)


def associate_existing(db, acopio_id, payload):
    acopio = get_acopio(db, acopio_id, lock=True)
    comprobante = db.query(Comprobante).filter_by(id=payload.comprobante_id).with_for_update().first()
    if not comprobante:
        raise HTTPException(404, 'Comprobante no encontrado')
    validate_application(db, acopio, comprobante, payload)
    row = AfectacionAcopio(acopio_id=acopio_id, comprobante_id=comprobante.id)
    set_application(row, payload)
    db.add(row)
    db.commit()
    return snapshot(db, acopio_id)


def change_state(db, acopio_id, aplicacion_id, anulada):
    acopio = get_acopio(db, acopio_id, lock=True)
    row = get_aplicacion(db, acopio_id, aplicacion_id)
    db.query(Comprobante).filter_by(id=row.comprobante_id).with_for_update().one()
    if anulada and active_query(db).filter(AfectacionAcopio.referencia_id == row.id).count():
        raise HTTPException(422, 'Primero desvincule o anule los comprobantes que referencian esta asociacion')
    if not anulada:
        from schemas.documentacion import AplicacionInput
        if row.importe_facturado is None:
            raise HTTPException(422, 'La asociacion historica requiere clasificacion')
        validate_application(db, acopio, row.comprobante, AplicacionInput(
            importe_aplicado=row.importe, importe_facturado=row.importe_facturado,
            referencia_id=row.referencia_id), row)
    row.anulada = anulada
    db.commit()
    return snapshot(db, acopio_id)


def set_reparto(db, acopio_id, payload):
    acopio = get_acopio(db, acopio_id, lock=True)
    rows = active_query(db).filter_by(acopio_id=acopio_id).all()
    pct = payload.porcentaje_facturado
    if rows and pct is None:
        raise HTTPException(422, 'No se puede quitar el reparto mientras hay documentos activos')
    if pct in (Decimal('0'), Decimal('100')):
        for row in rows:
            if row.importe_facturado is None:
                continue
            if (pct == 0 and row.importe_facturado > 0) or (pct == 100 and row.importe_facturado != row.importe):
                raise HTTPException(422, 'El reparto contradice documentos activos; corrija sus aplicaciones primero')
    acopio.porcentaje_facturado = pct
    db.commit()
    return snapshot(db, acopio_id)


def oc_control(active, reference):
    invoices = [r for r in active if r.referencia_id == reference.id and kind(r.comprobante) in INVOICE_TYPES]
    if len({kind(r.comprobante) for r in invoices}) > 1:
        # Advance and merchandise invoices can describe the same agreement.
        # Do not add them until the application of advances has been reviewed.
        return 'REVISAR_ANTICIPOS', None
    amount = sum((money(r.importe) for r in invoices), ZERO)
    difference = money(reference.importe_facturado) - amount
    return ('PENDIENTE_FACTURA' if not invoices else 'COINCIDENTE' if difference == 0 else 'CON_DIFERENCIA'), difference


def snapshot(db: Session, acopio_id):
    acopio = get_acopio(db, acopio_id)
    rows = db.query(AfectacionAcopio).filter_by(acopio_id=acopio_id).order_by(AfectacionAcopio.id).all()
    active = [r for r in rows if not r.anulada]
    result = []
    totals = {'oc_facturado': ZERO, 'oc_viviana': ZERO, 'anticipos_facturados': ZERO,
              'cobrado_facturado': ZERO, 'cobrado_viviana': ZERO, 'mercaderia_documentada': ZERO}
    alerts = []
    for row in rows:
        comp = row.comprobante
        tipo = kind(comp)
        fact = money(row.importe_facturado) if row.importe_facturado is not None else None
        viviana = money(row.importe) - fact if fact is not None else None
        status = 'ANULADA' if row.anulada else 'REGISTRADO'
        difference = None
        if not row.anulada:
            if fact is None:
                status = 'SIN_CLASIFICAR'
            elif tipo == 'ORDEN_COMPRA' and fact > 0:
                status, difference = oc_control(active, row)
                if status == 'REVISAR_ANTICIPOS':
                    alerts.append(f'{comp.numero}: hay facturas de anticipo y de mercaderia; revise la aplicacion de anticipos antes de consolidar.')
            elif tipo in INVOICE_TYPES:
                reference = next((r for r in active if r.id == row.referencia_id), None)
                if not reference or reference.importe_facturado is None:
                    status = 'PENDIENTE_OC'
                else:
                    status, difference = oc_control(active, reference)
            if fact is not None:
                if tipo == 'ORDEN_COMPRA':
                    totals['oc_facturado'] += fact
                    totals['oc_viviana'] += viviana
                elif tipo == 'FAC_ANTICIPO':
                    totals['anticipos_facturados'] += money(row.importe)
                elif tipo == 'FAC_MERCADERIA':
                    totals['mercaderia_documentada'] += money(row.importe)
                elif tipo == 'RECIBO':
                    totals['cobrado_facturado'] += fact
                    totals['cobrado_viviana'] += viviana
                    if row.referencia_id:
                        reference = next((r for r in active if r.id == row.referencia_id), None)
                        # All receipts referring to the same invoice, not receipts referring to this receipt.
                        paid = sum((money(r.importe) for r in active
                                    if r.referencia_id == row.referencia_id and kind(r.comprobante) == 'RECIBO'), ZERO)
                        if reference and paid > money(reference.importe):
                            status = 'COBRO_EXCEDIDO'
        data = serialize_comprobante(db, comp)
        if not row.anulada and (not data['archivo'] or not data['archivo']['disponible']):
            alerts.append(f'{comp.numero}: falta el PDF')
        result.append({'id': row.id, 'comprobante': data, 'importe_aplicado': float(row.importe),
                       'importe_facturado': float(fact) if fact is not None else None,
                       'importe_viviana': float(viviana) if viviana is not None else None,
                       'referencia_id': row.referencia_id, 'anulada': row.anulada,
                       'estado': status, 'diferencia': float(difference) if difference is not None else None})
    pct = acopio.porcentaje_facturado
    expected_f = money(money(acopio.total_pesos) * pct / 100) if pct is not None else None
    expected_v = money(acopio.total_pesos) - expected_f if expected_f is not None else None
    if pct is None:
        alerts.append('Reparto Facturado / Viviana por definir')
    else:
        if totals['anticipos_facturados'] > expected_f:
            alerts.append('Los anticipos facturados superan la parte Facturado acordada')
        if totals['mercaderia_documentada'] > expected_f:
            alerts.append('Las facturas de mercaderia documentadas superan la parte Facturado acordada')
        if totals['cobrado_facturado'] > expected_f or totals['cobrado_viviana'] > expected_v:
            alerts.append('Los cobros superan el importe acordado de una de las partes')
        if totals['oc_facturado'] > expected_f or totals['oc_viviana'] > expected_v:
            alerts.append('Las ordenes de compra superan el importe acordado de una de las partes')
    return {
        'acopio_id': acopio.id, 'numero': acopio.numero,
        'total_neto': float(acopio.total_pesos),
        'porcentaje_facturado': float(pct) if pct is not None else None,
        'porcentaje_viviana': float(100 - pct) if pct is not None else None,
        'acordado_facturado': float(expected_f) if expected_f is not None else None,
        'acordado_viviana': float(expected_v) if expected_v is not None else None,
        'totales': {key: float(value) for key, value in totals.items()},
        'documentos': result, 'alertas': alerts,
    }


def package_snapshot(db, paquete_id):
    paquete = db.query(AcopioPaquete).filter_by(id=paquete_id).first()
    if not paquete:
        raise HTTPException(404, 'Paquete no encontrado')
    snapshots = [snapshot(db, a.id) for a in paquete.acopios]
    keys = ('oc_facturado', 'oc_viviana', 'anticipos_facturados', 'cobrado_facturado', 'cobrado_viviana', 'mercaderia_documentada')
    return {'paquete_id': paquete_id, 'acopios': snapshots,
            'sin_clasificar': sum(s['porcentaje_facturado'] is None for s in snapshots),
            'totales': {key: float(sum((money(s['totales'][key]) for s in snapshots), ZERO)) for key in keys}}
