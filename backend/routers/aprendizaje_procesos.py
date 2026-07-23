"""Process-learning inspection endpoints."""
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from database import get_db
from models import CorreccionProceso, ReglaProceso
from services.process_learning_service import (
    correction_to_dict,
    rule_to_dict,
    set_rule_state,
    simulate_rule,
)


router = APIRouter()


@router.get("/correcciones")
async def list_process_corrections(
    estado: str | None = None,
    acopio_id: int | None = None,
    acopio_item_id: int | None = None,
    limit: int = Query(default=100, ge=1, le=500),
    db: Session = Depends(get_db),
):
    query = db.query(CorreccionProceso)
    if estado:
        query = query.filter(CorreccionProceso.estado == estado)
    if acopio_id:
        query = query.filter(CorreccionProceso.acopio_id == acopio_id)
    if acopio_item_id:
        query = query.filter(CorreccionProceso.acopio_item_id == acopio_item_id)

    rows = query.order_by(CorreccionProceso.created_at.desc(), CorreccionProceso.id.desc()).limit(limit).all()
    return [correction_to_dict(row) for row in rows]


@router.get("/reglas")
async def list_process_rules(
    estado: str | None = "propuesta",
    proceso: str | None = None,
    limit: int = Query(default=100, ge=1, le=500),
    db: Session = Depends(get_db),
):
    query = db.query(ReglaProceso)
    if estado:
        query = query.filter(ReglaProceso.estado == estado)
    if proceso:
        query = query.filter(ReglaProceso.proceso == proceso)

    rows = query.order_by(
        ReglaProceso.soporte_count.desc(),
        ReglaProceso.confianza.desc(),
        ReglaProceso.created_at.desc(),
        ReglaProceso.id.desc(),
    ).limit(limit).all()
    return [rule_to_dict(row) for row in rows]


def _get_rule_or_404(db: Session, regla_id: int) -> ReglaProceso:
    rule = db.query(ReglaProceso).filter(ReglaProceso.id == regla_id).first()
    if not rule:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Regla de proceso no encontrada",
        )
    return rule


@router.post("/reglas/{regla_id}/simular")
async def simulate_process_rule(
    regla_id: int,
    limit: int = Query(default=100, ge=1, le=500),
    db: Session = Depends(get_db),
):
    rule = _get_rule_or_404(db, regla_id)
    return simulate_rule(db, rule, limit=limit)


@router.post("/reglas/{regla_id}/aprobar")
async def approve_process_rule(
    regla_id: int,
    db: Session = Depends(get_db),
):
    rule = _get_rule_or_404(db, regla_id)
    set_rule_state(db, rule, "aprobada")
    db.commit()
    db.refresh(rule)
    return rule_to_dict(rule)


@router.post("/reglas/{regla_id}/desactivar")
async def deactivate_process_rule(
    regla_id: int,
    db: Session = Depends(get_db),
):
    rule = _get_rule_or_404(db, regla_id)
    set_rule_state(db, rule, "desactivada")
    db.commit()
    db.refresh(rule)
    return rule_to_dict(rule)
