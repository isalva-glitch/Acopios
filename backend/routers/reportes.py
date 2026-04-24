"""Reportes router."""
from fastapi import APIRouter, Depends, Response
from sqlalchemy.orm import Session
from typing import List
from decimal import Decimal
from datetime import date, timedelta
import csv
import io

from database import get_db
from models import Acopio, Imputacion, EstadoAcopio

router = APIRouter()


@router.get("/acopios-activos")
async def acopios_activos(
    format: str = "json",
    db: Session = Depends(get_db)
):
    """
    Get list of active acopios (with saldo > 0).
    
    format: json or csv
    """
    acopios = db.query(Acopio).filter(
        (Acopio.saldo_m2 > 0) | (Acopio.saldo_ml > 0) | (Acopio.saldo_pesos > 0)
    ).all()
    
    data = [
        {
            "id": a.id,
            "numero": a.numero,
            "obra": a.obra.nombre if a.obra else "Presupuesto Externo (SPF)",
            "cliente": a.obra.cliente.nombre if a.obra else f"SPF ID: {a.cliente_id}",
            "fecha_alta": a.fecha_alta.isoformat() if a.fecha_alta else "",
            "estado": a.estado.value if hasattr(a.estado, 'value') else str(a.estado),
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
    imputaciones = db.query(Imputacion).filter(
        Imputacion.es_excedente == True
    ).all()
    
    data = [
        {
            "id": imp.id,
            "pedido_numero": imp.pedido.numero,
            "acopio_numero": imp.acopio.numero,
            "obra": imp.pedido.obra.nombre if imp.pedido and imp.pedido.obra else "Desconocida",
            "cantidad_m2": float(imp.cantidad_m2 or 0),
            "cantidad_ml": float(imp.cantidad_ml or 0),
            "cantidad_pesos": float(imp.cantidad_pesos or 0),
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
    db: Session = Depends(get_db)
):
    """
    Get acopios with precio vencimiento within N days.
    
    format: json or csv
    """
    fecha_limite = date.today() + timedelta(days=dias)
    
    acopios = db.query(Acopio).filter(
        Acopio.fecha_vencimiento_precio != None,
        Acopio.fecha_vencimiento_precio <= fecha_limite,
        Acopio.estado != EstadoAcopio.CONSUMIDO
    ).all()
    
    data = [
        {
            "id": a.id,
            "numero": a.numero,
            "obra": a.obra.nombre if a.obra else "Presupuesto Externo (SPF)",
            "cliente": a.obra.cliente.nombre if a.obra else f"SPF ID: {a.cliente_id}",
            "fecha_vencimiento": a.fecha_vencimiento_precio.isoformat() if a.fecha_vencimiento_precio else None,
            "dias_restantes": (a.fecha_vencimiento_precio - date.today()).days if a.fecha_vencimiento_precio else None,
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
    
    # Create CSV in memory
    output = io.StringIO()
    writer = csv.DictWriter(output, fieldnames=data[0].keys())
    writer.writeheader()
    writer.writerows(data)
    
    # Return as response
    return Response(
        content=output.getvalue(),
        media_type="text/csv",
        headers={"Content-Disposition": f"attachment; filename={filename}"}
    )
