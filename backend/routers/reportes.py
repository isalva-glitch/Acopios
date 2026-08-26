"""Reportes router."""
from fastapi import APIRouter, Depends, Response
from sqlalchemy.orm import Session
from typing import List, Optional
from decimal import Decimal
from datetime import date, timedelta
import csv
import io

from database import get_db
from models import Acopio, Imputacion, EstadoAcopio
from services.imputacion_service import recalculate_excedentes_for_acopios

router = APIRouter()


@router.get("/acopios-activos")
async def acopios_activos(
    format: str = "json",
    incluir_paquetes: bool = True,
    db: Session = Depends(get_db)
):
    """
    Get list of active acopios (with saldo > 0).
    
    format: json or csv
    incluir_paquetes: If False, filters out acopios that belong to a package.
    """
    query = db.query(Acopio).filter(
        (Acopio.saldo_m2 > 0) | (Acopio.saldo_ml > 0) | (Acopio.saldo_pesos > 0)
    )
    
    if not incluir_paquetes:
        query = query.filter(Acopio.paquete_id.is_(None))
        
    acopios = query.all()
    
    data = [
        {
            "id": a.id,
            "numero": a.numero,
            "obra": a.obra.nombre if a.obra else "Presupuesto Externo (SPF)",
            "cliente": a.obra.cliente.nombre if a.obra and a.obra.cliente else (f"SPF ID: {a.cliente_id}" if a.cliente_id else "-"),
            "fecha_alta": a.fecha_alta.isoformat() if a.fecha_alta else "",
            "fecha_vencimiento_precio": a.fecha_vencimiento_precio.isoformat() if a.fecha_vencimiento_precio else None,
            "dias_restantes": (a.fecha_vencimiento_precio - date.today()).days if a.fecha_vencimiento_precio else None,
            "estado": a.estado.value if hasattr(a.estado, 'value') else str(a.estado),
            "es_paquete": a.paquete_id is not None,
            "paquete_id": a.paquete_id,
            "paquete_nombre": a.paquete.nombre if a.paquete else None,
            "paquete_numero": a.paquete.numero if a.paquete else None,
            "tipo_origen": "Paquete" if a.paquete_id else "Acopio Individual",
            "total_m2": float(a.total_m2 or 0),
            "total_ml": float(a.total_ml or 0),
            "total_pesos": float(a.total_pesos or 0),
            "saldo_m2": float(a.saldo_m2 or 0),
            "saldo_ml": float(a.saldo_ml or 0),
            "saldo_pesos": float(a.saldo_pesos or 0)
        }
        for a in acopios
    ]
    
    if format == "csv":
        return generate_csv_response(data, "acopios_activos.csv")
    
    return {"acopios": data, "count": len(data)}


@router.get("/excedentes")
async def excedentes(
    format: str = "json",
    db: Session = Depends(get_db)
):
    """
    Get list of imputaciones marked as excedente.
    
    format: json or csv
    """
    acopio_ids = [
        row[0]
        for row in db.query(Imputacion.acopio_id)
        .distinct()
        .all()
    ]
    recalculate_excedentes_for_acopios(db, acopio_ids)

    imputaciones = db.query(Imputacion).filter(
        Imputacion.es_excedente == True
    ).all()
    
    data = [
        {
            "id": imp.id,
            "pedido_numero": imp.pedido.numero if imp.pedido else "-",
            "acopio_numero": imp.acopio.numero if imp.acopio else "-",
            "obra": imp.pedido.obra.nombre if imp.pedido and imp.pedido.obra else (imp.acopio.obra.nombre if imp.acopio and imp.acopio.obra else "Desconocida"),
            "cliente": (
                imp.pedido.obra.cliente.nombre if imp.pedido and imp.pedido.obra and imp.pedido.obra.cliente
                else (imp.acopio.obra.cliente.nombre if imp.acopio and imp.acopio.obra and imp.acopio.obra.cliente else "-")
            ),
            "es_paquete": imp.acopio.paquete_id is not None if imp.acopio else False,
            "paquete_nombre": imp.acopio.paquete.nombre if imp.acopio and imp.acopio.paquete else None,
            "tipo_origen": "Paquete" if (imp.acopio and imp.acopio.paquete_id) else "Acopio Individual",
            "cantidad_m2": float(imp.cantidad_m2 or 0),
            "cantidad_ml": float(imp.cantidad_ml or 0),
            "cantidad_pesos": float(imp.cantidad_pesos or 0),
            "excedente_tipo": imp.excedente_tipo or "Consumo Excedente",
            "excedente_motivo": imp.excedente_motivo or "-",
            "fecha": imp.created_at.isoformat() if imp.created_at else ""
        }
        for imp in imputaciones
    ]
    
    if format == "csv":
        return generate_csv_response(data, "excedentes.csv")
    
    return {"excedentes": data, "count": len(data)}


@router.get("/vencimientos-precio")
async def vencimientos_precio(
    dias: int = 30,
    format: str = "json",
    incluir_paquetes: bool = True,
    db: Session = Depends(get_db)
):
    """
    Get acopios with precio vencimiento within N days.
    
    format: json or csv
    """
    fecha_limite = date.today() + timedelta(days=dias)
    
    query = db.query(Acopio).filter(
        Acopio.fecha_vencimiento_precio != None,
        Acopio.fecha_vencimiento_precio <= fecha_limite,
        Acopio.estado != EstadoAcopio.CONSUMIDO
    )
    
    if not incluir_paquetes:
        query = query.filter(Acopio.paquete_id.is_(None))
        
    acopios = query.all()
    
    data = [
        {
            "id": a.id,
            "numero": a.numero,
            "obra": a.obra.nombre if a.obra else "Presupuesto Externo (SPF)",
            "cliente": a.obra.cliente.nombre if a.obra and a.obra.cliente else (f"SPF ID: {a.cliente_id}" if a.cliente_id else "-"),
            "estado": a.estado.value if hasattr(a.estado, 'value') else str(a.estado),
            "es_paquete": a.paquete_id is not None,
            "paquete_id": a.paquete_id,
            "paquete_nombre": a.paquete.nombre if a.paquete else None,
            "paquete_numero": a.paquete.numero if a.paquete else None,
            "tipo_origen": "Paquete" if a.paquete_id else "Acopio Individual",
            "fecha_vencimiento": a.fecha_vencimiento_precio.isoformat() if a.fecha_vencimiento_precio else None,
            "dias_restantes": (a.fecha_vencimiento_precio - date.today()).days if a.fecha_vencimiento_precio else None,
            "total_m2": float(a.total_m2 or 0),
            "total_ml": float(a.total_ml or 0),
            "total_pesos": float(a.total_pesos or 0),
            "saldo_m2": float(a.saldo_m2 or 0),
            "saldo_ml": float(a.saldo_ml or 0),
            "saldo_pesos": float(a.saldo_pesos or 0)
        }
        for a in acopios
    ]
    
    if format == "csv":
        return generate_csv_response(data, "vencimientos_precio.csv")
    
    return {"vencimientos": data, "count": len(data)}


def generate_csv_response(data: List[dict], filename: str) -> Response:
    """Generate CSV response from data."""
    if not data:
        return Response(content="", media_type="text/csv")
    
    output = io.StringIO()
    writer = csv.DictWriter(output, fieldnames=data[0].keys())
    writer.writeheader()
    writer.writerows(data)
    
    return Response(
        content=output.getvalue(),
        media_type="text/csv",
        headers={"Content-Disposition": f"attachment; filename={filename}"}
    )
