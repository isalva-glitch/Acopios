"""Documentacion comercial independiente de los informes estadisticos."""
from pathlib import Path
from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, Query
from fastapi.responses import FileResponse
from pydantic import ValidationError
from sqlalchemy import or_
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session
from config import settings
from database import get_db
from models import Comprobante, TipoComprobante
from schemas.documentacion import RepartoInput, ComprobanteInput, AplicacionInput, EstadoAplicacionInput
from services import documentacion_service as service

router = APIRouter()


def get_documentacion_db(db: Session = Depends(get_db)):
    try:
        yield db
    except Exception:
        db.rollback()
        raise


@router.get('/acopios/{acopio_id}/documentacion')
def get_documentacion(acopio_id: int, db: Session = Depends(get_documentacion_db)):
    return service.snapshot(db, acopio_id)


@router.put('/acopios/{acopio_id}/documentacion/reparto')
def update_reparto(acopio_id: int, payload: RepartoInput, db: Session = Depends(get_documentacion_db)):
    return service.set_reparto(db, acopio_id, payload)


def parse_payload(payload):
    try:
        return ComprobanteInput.model_validate_json(payload)
    except ValidationError as exc:
        labels = {'numero': 'numero', 'emisor': 'emisor', 'fecha': 'fecha',
                  'importe': 'neto original', 'importe_aplicado': 'neto aplicado',
                  'importe_facturado': 'parte Facturado', 'iva': 'IVA', 'tipo': 'tipo de comprobante'}
        field = exc.errors()[0]['loc'][-1] if exc.errors()[0]['loc'] else 'datos'
        label = labels.get(field, 'datos del comprobante')
        raise HTTPException(422, f'Revise {label}: los importes deben ser validos, positivos y tener hasta dos decimales; complete los campos obligatorios')


@router.post('/acopios/{acopio_id}/documentacion/comprobantes', status_code=201)
async def create_documento(acopio_id: int, payload: str = Form(...),
                           file: UploadFile | None = File(None), db: Session = Depends(get_documentacion_db)):
    try:
        return await service.save_document(db, acopio_id, parse_payload(payload), file)
    except IntegrityError:
        db.rollback()
        raise HTTPException(409, 'El comprobante o el archivo ya existe; actualice la lista y use Asociar existente')


@router.put('/acopios/{acopio_id}/documentacion/comprobantes/{aplicacion_id}')
async def update_documento(acopio_id: int, aplicacion_id: int, payload: str = Form(...),
                           file: UploadFile | None = File(None), db: Session = Depends(get_documentacion_db)):
    try:
        return await service.save_document(db, acopio_id, parse_payload(payload), file, aplicacion_id)
    except IntegrityError:
        db.rollback()
        raise HTTPException(409, 'El numero y emisor ya corresponden a otro comprobante')


@router.post('/acopios/{acopio_id}/documentacion/asociaciones', status_code=201)
def associate_documento(acopio_id: int, payload: AplicacionInput, db: Session = Depends(get_documentacion_db)):
    return service.associate_existing(db, acopio_id, payload)


@router.patch('/acopios/{acopio_id}/documentacion/asociaciones/{aplicacion_id}')
def change_documento_state(acopio_id: int, aplicacion_id: int,
                           payload: EstadoAplicacionInput, db: Session = Depends(get_documentacion_db)):
    return service.change_state(db, acopio_id, aplicacion_id, payload.anulada)


@router.get('/documentacion/comprobantes')
def find_documentos(buscar: str = Query(default='', max_length=200), db: Session = Depends(get_documentacion_db)):
    query = db.query(Comprobante).filter(Comprobante.tipo.in_([
        TipoComprobante.ORDEN_COMPRA, TipoComprobante.FAC_ANTICIPO, TipoComprobante.FAC_MERCADERIA, TipoComprobante.RECIBO]))
    if buscar.strip():
        query = query.filter(or_(Comprobante.numero.icontains(buscar.strip(), autoescape=True),
                                 Comprobante.emisor.icontains(buscar.strip(), autoescape=True)))
    return [service.serialize_comprobante(db, c) for c in query.order_by(Comprobante.id.desc()).limit(100).all()]


@router.get('/documentacion/archivos/{comprobante_id}')
def open_documento(comprobante_id: int, db: Session = Depends(get_documentacion_db)):
    comprobante = db.query(Comprobante).filter_by(id=comprobante_id).first()
    if not comprobante or not comprobante.documento:
        raise HTTPException(404, 'PDF no adjuntado')
    document = comprobante.documento
    path = Path(document.ruta_storage).resolve()
    if not path.is_relative_to(settings.storage_path.resolve()) or not path.is_file():
        raise HTTPException(404, 'PDF no disponible en el almacenamiento')
    return FileResponse(path, media_type='application/pdf', filename=document.nombre_archivo,
                        content_disposition_type='inline')


@router.get('/acopio-paquetes/{paquete_id}/documentacion')
def get_paquete_documentacion(paquete_id: int, db: Session = Depends(get_documentacion_db)):
    return service.package_snapshot(db, paquete_id)


@router.get("/documentacion/coincidencias-numero")
def find_number(numero: str = Query(min_length=3, max_length=40), db: Session = Depends(get_documentacion_db)):
    from services.comprobante_numero import local_matches
    return local_matches(db, numero)


@router.get("/acopios/{acopio_id}/documentacion/panel")
def get_unified_panel(acopio_id: int, db: Session = Depends(get_documentacion_db)):
    from services.documentacion_panel_service import panel
    return panel(db, acopio_id)
