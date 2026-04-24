"""Imputacion service with business logic."""
from typing import Optional, Tuple
from sqlalchemy.orm import Session
from decimal import Decimal

from models import Imputacion, Acopio, AcopioItem, Pedido
from config import settings


class ExcedentePolicy:
    """Excedente handling policies."""
    BLOCK = "BLOCK"
    WARN = "WARN"
    ALLOW = "ALLOW"


def check_excedente(
    db: Session,
    acopio_id: int,
    acopio_item_id: Optional[int],
    cantidad_m2: Decimal,
    cantidad_ml: Decimal,
    cantidad_pesos: Decimal,
    cantidad_unidades: int
) -> Tuple[bool, Optional[str]]:
    """
    Check if imputacion would create excedente.
    
    Returns:
        (is_excedente, warning_message)
    """
    # Get acopio
    acopio = db.query(Acopio).filter(Acopio.id == acopio_id).first()
    if not acopio:
        return False, "Acopio not found"
    
    # Check against acopio saldos
    is_excedente = False
    warnings = []
    
    if cantidad_m2 > acopio.saldo_m2:
        is_excedente = True
        warnings.append(f"m2: consumo {cantidad_m2} excede saldo {acopio.saldo_m2}")
    
    if cantidad_ml > acopio.saldo_ml:
        is_excedente = True
        warnings.append(f"ml: consumo {cantidad_ml} excede saldo {acopio.saldo_ml}")
    
    if cantidad_pesos > acopio.saldo_pesos:
        is_excedente = True
        warnings.append(f"pesos: consumo {cantidad_pesos} excede saldo {acopio.saldo_pesos}")
        
    if cantidad_unidades > acopio.saldo_unidades:
        is_excedente = True
        warnings.append(f"unidades: consumo {cantidad_unidades} excede saldo {acopio.saldo_unidades}")
    
    # If item specified, also check item saldos
    if acopio_item_id:
        item = db.query(AcopioItem).filter(AcopioItem.id == acopio_item_id).first()
        if item:
            if cantidad_m2 > item.saldo_m2:
                is_excedente = True
                warnings.append(f"Item {item.descripcion}: m2 excede saldo")
            if cantidad_ml > item.saldo_ml:
                is_excedente = True
                warnings.append(f"Item {item.descripcion}: ml excede saldo")
            if cantidad_pesos > item.saldo_pesos:
                is_excedente = True
                warnings.append(f"Item {item.descripcion}: pesos excede saldo")
            if cantidad_unidades > item.saldo_cantidad:
                is_excedente = True
                warnings.append(f"Item {item.descripcion}: unidades excede saldo")
    
    warning_msg = "; ".join(warnings) if warnings else None
    
    return is_excedente, warning_msg


def imputar_consumo(
    db: Session,
    pedido_id: int,
    acopio_id: int,
    acopio_item_id: Optional[int],
    cantidad_m2: Decimal,
    cantidad_ml: Decimal,
    cantidad_pesos: Decimal,
    cantidad_unidades: int
) -> Tuple[Imputacion, Optional[str]]:
    """
    Create imputacion and update saldos.
    
    Returns:
        (imputacion, warning_message)
        
    Raises:
        ValueError if BLOCK policy and excedente detected
    """
    # Check for excedente
    is_excedente, warning = check_excedente(
        db, acopio_id, acopio_item_id, cantidad_m2, cantidad_ml, cantidad_pesos, cantidad_unidades
    )
    
    # Apply policy
    policy = settings.excedente_policy
    
    if is_excedente and policy == ExcedentePolicy.BLOCK:
        raise ValueError(f"Imputación bloqueada por excedente: {warning}")
    
    # Create imputacion
    imputacion = Imputacion(
        pedido_id=pedido_id,
        acopio_id=acopio_id,
        acopio_item_id=acopio_item_id,
        cantidad_m2=cantidad_m2,
        cantidad_ml=cantidad_ml,
        cantidad_pesos=cantidad_pesos,
        cantidad_unidades=cantidad_unidades,
        es_excedente=is_excedente
    )
    
    db.add(imputacion)
    db.commit()
    db.refresh(imputacion)
    
    # Update saldos
    from services.acopio_service import update_saldos
    update_saldos(db, acopio_id)
    
    # Return warning if WARN policy
    return_warning = warning if (is_excedente and policy == ExcedentePolicy.WARN) else None
    
    return imputacion, return_warning


def anular_imputacion(db: Session, imputacion_id: int) -> dict:
    """
    Anula (elimina) una imputación y recalcula los saldos del acopio.

    Returns:
        dict with acopio_id affected

    Raises:
        ValueError if imputacion not found
    """
    from models import Imputacion
    from services.acopio_service import update_saldos

    imputacion = db.query(Imputacion).filter(Imputacion.id == imputacion_id).first()
    if not imputacion:
        raise ValueError(f"Imputación {imputacion_id} no encontrada")

    acopio_id = imputacion.acopio_id

    db.delete(imputacion)
    db.commit()

    # Recalculate saldos based on remaining imputaciones
    update_saldos(db, acopio_id)

    return {"acopio_id": acopio_id}
