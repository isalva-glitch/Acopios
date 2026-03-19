"""Acopio service with business logic."""
from typing import Dict, Any, Optional
from sqlalchemy.orm import Session
from datetime import date
from decimal import Decimal

from models import (
    Cliente, Obra, Acopio, Presupuesto, AcopioItem, AcopioItemPano,
    Documento, ExtraccionIA, EstadoAcopio
)


def get_or_create_cliente(db: Session, nombre: str) -> Cliente:
    """Get existing cliente or create new one."""
    cliente = db.query(Cliente).filter(Cliente.nombre == nombre).first()
    if not cliente:
        cliente = Cliente(nombre=nombre)
        db.add(cliente)
        db.flush()
    return cliente


def get_or_create_obra(db: Session, nombre: str, cliente_id: int) -> Obra:
    """Get existing obra or create new one."""
    obra = db.query(Obra).filter(
        Obra.nombre == nombre,
        Obra.cliente_id == cliente_id
    ).first()
    if not obra:
        obra = Obra(nombre=nombre, cliente_id=cliente_id)
        db.add(obra)
        db.flush()
    return obra


def create_from_extraction(db: Session, extraction_package: Dict[str, Any]) -> Acopio:
    """
    Create acopio and related entities from extraction package.
    
    Args:
        db: Database session
        extraction_package: Validated extraction package from PDF
        
    Returns:
        Created Acopio instance
    """
    # Get or create cliente
    cliente_nombre = extraction_package["acopio"]["cliente"]
    cliente = get_or_create_cliente(db, cliente_nombre)
    
    # Get or create obra
    obra_nombre = extraction_package["acopio"]["obra"]
    obra = get_or_create_obra(db, obra_nombre, cliente.id)
    
    # Create acopio
    acopio_data = extraction_package["acopio"]
    total_m2 = Decimal(str(acopio_data.get("total_m2", 0)))
    total_ml = Decimal(str(acopio_data.get("total_ml", 0)))
    total_pesos = Decimal(str(acopio_data.get("total_pesos", 0)))
    
    total_unidades = sum(item.get("cantidad", 0) for item in extraction_package.get("items", []))
    
    acopio = Acopio(
        obra_id=obra.id,
        numero=acopio_data.get("numero", ""),
        fecha_alta=date.fromisoformat(acopio_data["fecha_alta"]),
        estado=EstadoAcopio.ACTIVO,
        total_m2=total_m2,
        total_ml=total_ml,
        total_pesos=total_pesos,
        total_unidades=total_unidades,
        saldo_m2=total_m2,  # Initially, saldo = total
        saldo_ml=total_ml,
        saldo_pesos=total_pesos,
        saldo_unidades=total_unidades
    )
    db.add(acopio)
    db.flush()
    
    # Create presupuestos
    for pres_data in extraction_package.get("presupuestos", []):
        presupuesto = Presupuesto(
            acopio_id=acopio.id,
            numero=pres_data["numero"],
            fecha=date.fromisoformat(pres_data["fecha"]),
            condiciones=pres_data.get("condiciones", ""),
            estado=pres_data.get("estado", "")
        )
        db.add(presupuesto)
    
    # Create items
    for idx, item_data in enumerate(extraction_package.get("items", [])):
        item_m2 = Decimal(str(item_data.get("total_m2", 0)))
        item_ml = Decimal(str(item_data.get("total_ml", 0)))
        item_pesos = Decimal(str(item_data.get("total_pesos", 0)))
        
        item = AcopioItem(
            acopio_id=acopio.id,
            descripcion=item_data["descripcion"],
            material=item_data.get("material", ""),
            tipologia=item_data.get("tipologia", ""),
            cantidad=item_data.get("cantidad", 0),
            total_m2=item_m2,
            total_ml=item_ml,
            total_pesos=item_pesos,
            saldo_m2=item_m2,
            saldo_ml=item_ml,
            saldo_pesos=item_pesos,
            saldo_cantidad=item_data.get("cantidad", 0)
        )
        db.add(item)
        db.flush()
        
        # Create paños for this item
        for pano_data in extraction_package.get("panos", []):
            if pano_data.get("item_index") == idx:
                pano = AcopioItemPano(
                    item_id=item.id,
                    cantidad=pano_data["cantidad"],
                    ancho=Decimal(str(pano_data["ancho"])),
                    alto=Decimal(str(pano_data["alto"])),
                    superficie_m2=Decimal(str(pano_data["superficie_m2"])),
                    perimetro_ml=Decimal(str(pano_data["perimetro_ml"])),
                    precio_unitario=Decimal(str(pano_data.get("precio_unitario", 0))),
                    precio_total=Decimal(str(pano_data.get("precio_total", 0)))
                )
                db.add(pano)
    
    # Create documento
    for doc_data in extraction_package.get("documentos", []):
        documento = Documento(
            entidad_tipo="acopio",
            entidad_id=str(acopio.id),
            tipo_documento=doc_data["tipo_documento"],
            nombre_archivo=doc_data["nombre_archivo"],
            hash=doc_data["hash"],
            ruta_storage=f"/app/storage/{doc_data['hash']}.pdf"
        )
        db.add(documento)
        db.flush()
        
        # Create extraccion_ia
        extraccion = ExtraccionIA(
            documento_id=documento.id,
            contenido_extraido=extraction_package,
            warnings=extraction_package.get("warnings", []),
            validado=len([w for w in extraction_package.get("warnings", []) if w["level"] == "ERROR"]) == 0,
            fecha_extraccion=extraction_package["meta"]["extraction_date"]
        )
        db.add(extraccion)
    
    db.commit()
    db.refresh(acopio)
    
    return acopio


def create_from_spf(db: Session, spf_details: Dict[str, Any]) -> Acopio:
    """
    Create acopio from SPF database details.
    
    Args:
        db: Database session for local DB
        spf_details: Dictionary retrieved from SPF integration service
        
    Returns:
        Created Acopio instance
    """
    # Get or create cliente
    cliente_nombre = spf_details.get("cliente_nombre", "Desconocido")
    cliente = get_or_create_cliente(db, cliente_nombre)
    
    # We leave obra as null or create a default one since SPF does not have 'Obra'
    # By requirements, obra_id is nullable now.
    
    total_m2 = Decimal(str(spf_details.get("total_m2", 0)))
    total_ml = Decimal(str(spf_details.get("total_ml", 0)))
    total_pesos = Decimal(str(spf_details.get("total_pesos", 0)))
    
    total_unidades = sum(item.get("cantidad", 0) for item in spf_details.get("items", []))
    
    acopio = Acopio(
        numero=spf_details.get("v_presupuesto_id", ""),
        fecha_alta=date.today(),
        estado=EstadoAcopio.ACTIVO,
        total_m2=total_m2,
        total_ml=total_ml,
        total_pesos=total_pesos,
        total_unidades=total_unidades,
        saldo_m2=total_m2,
        saldo_ml=total_ml,
        saldo_pesos=total_pesos,
        saldo_unidades=total_unidades,
        v_presupuesto_id=spf_details.get("v_presupuesto_id"),
        origen_datos="spf_production",
        cliente_id=spf_details.get("cliente_id"),
        obra_id=None
    )
    db.add(acopio)
    db.flush()
    
    # Create items with their specific quantities and measurements
    for item_data in spf_details.get("items", []):
        item_m2 = Decimal(str(item_data.get("total_m2", 0)))
        item_ml = Decimal(str(item_data.get("total_ml", 0)))
        item_pesos = Decimal(str(item_data.get("total_pesos", 0)))
        
        item = AcopioItem(
            acopio_id=acopio.id,
            descripcion=item_data["descripcion"],
            material="",
            tipologia="SPF",
            cantidad=item_data.get("cantidad", 0),
            total_m2=item_m2,
            total_ml=item_ml,
            total_pesos=item_pesos,
            saldo_m2=item_m2,
            saldo_ml=item_ml,
            saldo_pesos=item_pesos
        )
        db.add(item)
        db.flush()
        
        # Create paños for this item
        for pano_data in item_data.get("panos", []):
            pano = AcopioItemPano(
                item_id=item.id,
                cantidad=pano_data["cantidad"],
                ancho=Decimal(str(pano_data["ancho"])),
                alto=Decimal(str(pano_data["alto"])),
                superficie_m2=Decimal(str(pano_data["superficie_m2"])),
                perimetro_ml=Decimal(str(pano_data["perimetro_ml"])),
                precio_unitario=Decimal(str(pano_data["precio_unitario"])),
                precio_total=Decimal(str(pano_data["precio_total"]))
            )
            db.add(pano)
    
    db.commit()
    db.refresh(acopio)
    return acopio



def update_saldos(db: Session, acopio_id: int) -> None:
    """Recalculate and update saldos for acopio and items."""
    from sqlalchemy import func
    from models import Imputacion
    
    acopio = db.query(Acopio).filter(Acopio.id == acopio_id).first()
    if not acopio:
        return
    
    # Calculate total consumed
    total_consumed = db.query(
        func.sum(Imputacion.cantidad_m2).label("m2"),
        func.sum(Imputacion.cantidad_ml).label("ml"),
        func.sum(Imputacion.cantidad_pesos).label("pesos"),
        func.sum(Imputacion.cantidad_unidades).label("unidades")
    ).filter(Imputacion.acopio_id == acopio_id).first()
    
    consumed_m2 = total_consumed.m2 or Decimal("0")
    consumed_ml = total_consumed.ml or Decimal("0")
    consumed_pesos = total_consumed.pesos or Decimal("0")
    consumed_unidades = total_consumed.unidades or 0
    
    # Update acopio saldos
    acopio.saldo_m2 = acopio.total_m2 - consumed_m2
    acopio.saldo_ml = acopio.total_ml - consumed_ml
    acopio.saldo_pesos = acopio.total_pesos - consumed_pesos
    acopio.saldo_unidades = acopio.total_unidades - int(consumed_unidades)
    
    # Update estado based on saldo
    if acopio.saldo_m2 <= 0 and acopio.saldo_ml <= 0 and acopio.saldo_pesos <= 0 and acopio.saldo_unidades <= 0:
        acopio.estado = EstadoAcopio.CONSUMIDO
    elif acopio.saldo_m2 < acopio.total_m2 or acopio.saldo_ml < acopio.total_ml or acopio.saldo_pesos < acopio.total_pesos:
        acopio.estado = EstadoAcopio.PARCIALMENTE_CONSUMIDO
    else:
        acopio.estado = EstadoAcopio.ACTIVO
    
    # Update item saldos
    for item in acopio.items:
        item_consumed = db.query(
            func.sum(Imputacion.cantidad_m2).label("m2"),
            func.sum(Imputacion.cantidad_ml).label("ml"),
            func.sum(Imputacion.cantidad_pesos).label("pesos"),
            func.sum(Imputacion.cantidad_unidades).label("unidades")
        ).filter(Imputacion.acopio_item_id == item.id).first()
        
        item_consumed_m2 = item_consumed.m2 or Decimal("0")
        item_consumed_ml = item_consumed.ml or Decimal("0")
        item_consumed_pesos = item_consumed.pesos or Decimal("0")
        item_consumed_unidades = item_consumed.unidades or 0
        
        item.saldo_m2 = item.total_m2 - item_consumed_m2
        item.saldo_ml = item.total_ml - item_consumed_ml
        item.saldo_pesos = item.total_pesos - item_consumed_pesos
        item.saldo_cantidad = item.cantidad - int(item_consumed_unidades)
    
    db.commit()
