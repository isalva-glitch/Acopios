"""Glassware import: review first, confirm an immutable server-side preview."""
from datetime import datetime, timedelta
import hashlib
import json
from uuid import uuid4
from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field, ValidationError, ConfigDict, StrictBool
from sqlalchemy import func, text
from sqlalchemy.orm import Session
from database import get_db
from models import Acopio
from models.glassware_import import GlasswareImport
from services.acopio_creation_models import NormalizedAcopioData
from services import acopio_service  # Initialize the existing creation-service import cycle in its established order.
from services.acopio_creation_service import AcopioCreationService
from integrations.glassware.parser import parse_budget, GlasswareError

router = APIRouter(prefix='/integrations/glassware', tags=['Glassware'])


class ItemSource(BaseModel):
    model_config = ConfigDict(extra='forbid')
    id: str = Field(pattern=r'^[1-9]\d{0,15}$')
    html: str = Field(max_length=1000000)
    measures: list[list] = Field(min_length=1, max_length=5000)


class BudgetSource(BaseModel):
    model_config = ConfigDict(extra='forbid')
    url: str = Field(max_length=200)
    budget_html: str = Field(max_length=2000000)
    items: list[ItemSource] = Field(min_length=1, max_length=200)


class Confirmation(BaseModel):
    model_config = ConfigDict(extra='forbid')
    preview_id: str = Field(min_length=36, max_length=36)
    aprobacion_verificada: StrictBool = False


def existing(db, numero):
    key = numero.lstrip('0') or '0'
    return db.query(Acopio).filter(
        (func.ltrim(Acopio.numero, '0') == key) |
        (func.ltrim(Acopio.v_presupuesto_id, '0') == key)).first()


@router.post('/preview')
async def preview(request: Request, db: Session = Depends(get_db)):
    body = bytearray()
    async for chunk in request.stream():
        body.extend(chunk)
        if len(body) > 8_000_000:
            raise HTTPException(413, 'El presupuesto supera el tamaño admitido.')
    try:
        source = BudgetSource.model_validate_json(body)
        data = parse_budget(source.model_dump())
    except (ValidationError, ValueError, KeyError, TypeError, IndexError, RecursionError) as exc:
        message = str(exc) if isinstance(exc, GlasswareError) else 'La respuesta del conector está incompleta o tiene un formato inválido.'
        raise HTTPException(422, message) from exc
    if existing(db, data.numero):
        raise HTTPException(409, f'Ya existe un acopio para el presupuesto {data.numero}.')
    row = GlasswareImport(token=str(uuid4()), glassware_id=data.metadata['glassware_id'],
        numero=data.numero, datos=data.model_dump(mode='json'))
    db.add(row)
    db.commit()
    return {'preview_id': row.token, 'data': row.datos}


@router.get('/preview/{preview_id}')
def get_preview(preview_id: str, db: Session = Depends(get_db)):
    row = db.query(GlasswareImport).filter_by(token=preview_id).first()
    if not row:
        raise HTTPException(404, 'No se encontró la vista previa.')
    if row.created_at < datetime.utcnow()-timedelta(hours=2) or row.acopio_id or row.confirmado_en:
        raise HTTPException(409, 'La vista previa venció o ya fue confirmada. Volvé a consultar Glassware.')
    return {'preview_id': row.token, 'data': row.datos}


@router.post('/confirm')
def confirm(payload: Confirmation, db: Session = Depends(get_db)):
    try:
        row = db.query(GlasswareImport).filter_by(token=payload.preview_id).with_for_update().first()
        if not row:
            raise HTTPException(404, 'No se encontró la vista previa. Volvé a consultar Glassware.')
        if row.acopio_id:
            if not db.get(Acopio, row.acopio_id):
                raise HTTPException(409, 'El acopio de esta importación fue eliminado. Consultá de nuevo para iniciar otra alta.')
            return {'acopio_id': row.acopio_id, 'numero': row.numero, 'already_created': True}
        if row.confirmado_en:
            raise HTTPException(409, 'Esta vista previa ya fue utilizada. Volvé a consultar Glassware.')
        if row.created_at < datetime.utcnow()-timedelta(hours=2):
            raise HTTPException(409, 'La vista previa venció. Volvé a consultar Glassware.')
        if db.bind.dialect.name == 'postgresql':
            lock = int.from_bytes(hashlib.sha256(row.numero.encode()).digest()[:8], 'big', signed=True)
            db.execute(text('SELECT pg_advisory_xact_lock(:key)'), {'key': lock})
        if existing(db, row.numero):
            raise HTTPException(409, f'Ya existe un acopio para el presupuesto {row.numero}.')
        data = NormalizedAcopioData.model_validate(row.datos)
        if data.metadata.get('estado') not in {'Aceptado', 'Parcial'}:
            raise HTTPException(409, 'La aprobación del presupuesto no es válida. Volvé a consultar Glassware.')
        if data.metadata.get('estado') != 'Aceptado' and not payload.aprobacion_verificada:
            raise HTTPException(409, 'Verificá que el presupuesto está aprobado por el total antes de crear el acopio.')
        if payload.aprobacion_verificada:
            data.metadata['aprobacion_verificada'] = True
            data.metadata['aprobacion_verificada_en'] = datetime.utcnow().isoformat()+'Z'
            row.datos = data.model_dump(mode='json')
        acopio = AcopioCreationService.persist_from_normalized_data(db, data, commit=False)
        row.acopio_id = acopio.id
        row.confirmado_en = datetime.utcnow()
        db.commit()
        return {'acopio_id': acopio.id, 'numero': acopio.numero, 'already_created': False}
    except Exception:
        db.rollback()
        raise
