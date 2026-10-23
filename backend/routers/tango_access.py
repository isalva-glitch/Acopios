"""Independent read/review panel backed by the Windows Access connector."""
from typing import Literal
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import Response
from pydantic import BaseModel, ConfigDict, Field
from schemas.documentacion import AplicacionInput
from sqlalchemy.orm import Session
from routers.documentacion import get_documentacion_db
from models.tango_registro import TangoRegistro
from services import tango_service as service
from services.tango_access_bridge import request_access

router = APIRouter(prefix="/acopios/{acopio_id}/tango", tags=["Tango Access"])


class ConsultaInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    ampliar: bool = False


class RevisionInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    estado: Literal["PENDIENTE", "CONSERVADO", "DESCARTADO"]


@router.get("")
def get_panel(acopio_id: int, db: Session = Depends(get_documentacion_db)):
    return service.snapshot(db, acopio_id)


@router.post("/consultar")
async def consult(acopio_id: int, payload: ConsultaInput, db: Session = Depends(get_documentacion_db)):
    return await service.consult(db, acopio_id, payload.ampliar)


@router.patch("/registros/{record_id}")
def review(acopio_id: int, record_id: int, payload: RevisionInput, db: Session = Depends(get_documentacion_db)):
    return service.review(db, acopio_id, record_id, payload.estado)


@router.post("/descartar-pendientes")
def discard(acopio_id: int, db: Session = Depends(get_documentacion_db)):
    return service.discard_pending(db, acopio_id)


@router.get("/registros/{record_id}/pdf")
async def pdf(acopio_id: int, record_id: int, db: Session = Depends(get_documentacion_db)):
    record = db.query(TangoRegistro).filter_by(id=record_id, acopio_id=acopio_id).first()
    if not record:
        raise HTTPException(404, "Registro no encontrado en este acopio")
    content = await request_access("pdf", {"empresa": record.empresa, "origen_id": record.origen_id})
    return Response(content, media_type="application/pdf",
                    headers={"Content-Disposition": 'inline; filename="comprobante-tango.pdf"'})

class RevisionAplicacionInput(AplicacionInput):
    comprobante_id: None = None
    tipo_factura: Literal["FAC_ANTICIPO", "FAC_MERCADERIA"] | None = None


@router.get("/asociables")
def asociables(acopio_id: int, db: Session = Depends(get_documentacion_db)):
    from services import tango_asociacion_service as association
    return association.choices(db, acopio_id)


@router.post("/registros/{record_id}/asociar", status_code=201)
async def associate(acopio_id: int, record_id: int, payload: RevisionAplicacionInput,
                    db: Session = Depends(get_documentacion_db)):
    from services import tango_asociacion_service as association
    from sqlalchemy.exc import IntegrityError
    try:
        return await association.associate(db, acopio_id, record_id, payload)
    except IntegrityError:
        db.rollback()
        raise HTTPException(409, "El comprobante ya fue incorporado. Actualizá la lista para asociarlo.")


class NumeroInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    numero: str = Field(min_length=3, max_length=40)


@router.post("/buscar-numero")
async def search_number(acopio_id: int, payload: NumeroInput, db: Session = Depends(get_documentacion_db)):
    from services import tango_asociacion_service as association
    from services.comprobante_numero import number_matches, number_query
    query = number_query(payload.numero)
    result = await service.consult(db, acopio_id, number=payload.numero)
    panel = association.choices(db, acopio_id)
    panel["resultados"] = [r for r in panel["resultados"] if number_matches(r["numero"], query)]
    panel["avisos"] = result["consulta"]["avisos"]
    return panel
