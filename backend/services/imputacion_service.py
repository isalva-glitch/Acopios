"""Imputacion service with business logic."""
from typing import Iterable, Optional, Tuple
from sqlalchemy.orm import Session
from decimal import Decimal, ROUND_HALF_UP

from models import Imputacion, ImputacionProceso, Acopio, AcopioItem, Pedido
from config import settings
from services.proceso_inference import PROCESS_FIELDS, PROCESS_UNITS

MONEY_QUANT = Decimal("0.01")


def _to_decimal(value) -> Decimal:
    if value is None:
        return Decimal("0")
    if isinstance(value, Decimal):
        return value
    return Decimal(str(value))


def _money(value) -> Decimal:
    return _to_decimal(value).quantize(MONEY_QUANT, rounding=ROUND_HALF_UP)


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
) -> Tuple[bool, str, Optional[str]]:
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
    excedente_tipo = "NONE"
    warnings = []
    
    if cantidad_m2 > acopio.saldo_m2:
        is_excedente = True
        warnings.append(f"m2: consumo {cantidad_m2} excede saldo {acopio.saldo_m2}")
    
    if cantidad_ml > acopio.saldo_ml:
        is_excedente = True
        warnings.append(f"ml: consumo {cantidad_ml} excede saldo {acopio.saldo_ml}")
    
    if _money(cantidad_pesos) > _money(acopio.saldo_pesos):
        is_excedente = True
        warnings.append(f"pesos: consumo {cantidad_pesos} excede saldo {acopio.saldo_pesos}")
        
    if cantidad_unidades > acopio.saldo_unidades:
        is_excedente = True
        warnings.append(f"unidades: consumo {cantidad_unidades} excede saldo {acopio.saldo_unidades}")
    
    if is_excedente:
        excedente_tipo = "ACOPIO"
        
    # If item specified, also check item saldos
    if acopio_item_id:
        item = db.query(AcopioItem).filter(AcopioItem.id == acopio_item_id).first()
        if item:
            item_excedente = False
            if cantidad_m2 > item.saldo_m2:
                item_excedente = True
                warnings.append(f"Item {item.descripcion}: m2 excede saldo")
            if cantidad_ml > item.saldo_ml:
                item_excedente = True
                warnings.append(f"Item {item.descripcion}: ml excede saldo")
            if _money(cantidad_pesos) > _money(item.saldo_pesos):
                item_excedente = True
                warnings.append(f"Item {item.descripcion}: pesos excede saldo")
            if cantidad_unidades > item.saldo_cantidad:
                item_excedente = True
                warnings.append(f"Item {item.descripcion}: unidades excede saldo")
            
            if item_excedente:
                is_excedente = True
                if excedente_tipo == "NONE":
                    excedente_tipo = "ITEM"
    
    warning_msg = "; ".join(warnings) if warnings else None
    
    return is_excedente, excedente_tipo, warning_msg


def imputar_consumo(
    db: Session,
    pedido_id: int,
    acopio_id: int,
    acopio_item_id: Optional[int],
    cantidad_m2: Decimal,
    cantidad_ml: Decimal,
    cantidad_pesos: Decimal,
    cantidad_unidades: int,
    procesos: Optional[Iterable[dict]] = None,
    pedido_item_descripcion: Optional[str] = None,
    composicion_normalizada: Optional[str] = None,
    composicion_match_estado: Optional[str] = None,
    composicion_match_score: Optional[Decimal] = None,
    composicion_advertencia: Optional[str] = None,
) -> Tuple[Imputacion, Optional[str]]:
    """
    Create imputacion and update saldos.
    
    Returns:
        (imputacion, warning_message)
        
    Raises:
        ValueError if BLOCK policy and excedente detected
    """
    # Check for excedente
    is_excedente, excedente_tipo, warning = check_excedente(
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
        es_excedente=is_excedente,
        excedente_tipo=excedente_tipo if is_excedente else "NONE",
        excedente_motivo=warning if is_excedente else None,
        pedido_item_descripcion=pedido_item_descripcion,
        composicion_normalizada=composicion_normalizada,
        composicion_match_estado=composicion_match_estado,
        composicion_match_score=composicion_match_score,
        composicion_advertencia=composicion_advertencia,
    )
    
    db.add(imputacion)
    db.flush()

    if procesos:
        for proceso in procesos:
            proceso_key = proceso.get("proceso")
            if proceso_key not in PROCESS_FIELDS:
                continue

            unidad = proceso.get("unidad") or PROCESS_UNITS[proceso_key]
            if unidad != PROCESS_UNITS[proceso_key]:
                continue

            cantidad = Decimal(str(proceso.get("cantidad") or 0))
            if cantidad == 0:
                continue

            db.add(ImputacionProceso(
                imputacion_id=imputacion.id,
                proceso=proceso_key,
                unidad=unidad,
                cantidad=cantidad,
                origen=proceso.get("origen") or "snapshot_spf",
            ))

    db.commit()
    db.refresh(imputacion)
    
    # Update saldos
    from services.acopio_service import update_saldos
    update_saldos(db, acopio_id)
    
    # Return warning if WARN policy
    return_warning = warning if (is_excedente and policy == ExcedentePolicy.WARN) else None
    
    return imputacion, return_warning


def imputar_consumos(
    db: Session,
    consumos: Iterable[dict],
) -> Tuple[list[Imputacion], list[str]]:
    """
    Create several imputation rows atomically.

    Used when a pedido SPF contains several item compositions that must be
    assigned to acopio items independently.
    """
    consumos = list(consumos)
    if not consumos:
        return [], []

    warnings: list[str] = []
    excedente_flags: list[bool] = []
    excedente_tipos: list[str] = []
    excedente_motivos: list[str] = []

    def add_warning(message: Optional[str]) -> None:
        if message and message not in warnings:
            warnings.append(message)

    def add_to_bucket(bucket: dict, consumo: dict, index: int) -> None:
        bucket["indices"].append(index)
        bucket["m2"] += _to_decimal(consumo["cantidad_m2"])
        bucket["ml"] += _to_decimal(consumo["cantidad_ml"])
        bucket["pesos"] += _to_decimal(consumo["cantidad_pesos"])
        bucket["unidades"] += int(consumo["cantidad_unidades"] or 0)

    def mark_excedente(indices: list[int], message: str, tipo: str) -> None:
        for index in indices:
            excedente_flags[index] = True
            if excedente_tipos[index] == "NONE" or (excedente_tipos[index] == "ITEM" and tipo == "ACOPIO"):
                excedente_tipos[index] = tipo
            
            # Append reason
            current_motivos = excedente_motivos[index].split("; ") if excedente_motivos[index] else []
            if message not in current_motivos:
                current_motivos.append(message)
                excedente_motivos[index] = "; ".join(current_motivos)
                
        add_warning(message)

    for consumo in consumos:
        is_excedente, excedente_tipo, warning = check_excedente(
            db,
            consumo["acopio_id"],
            consumo.get("acopio_item_id"),
            consumo["cantidad_m2"],
            consumo["cantidad_ml"],
            consumo["cantidad_pesos"],
            consumo["cantidad_unidades"],
        )
        excedente_flags.append(is_excedente)
        excedente_tipos.append(excedente_tipo if is_excedente else "NONE")
        excedente_motivos.append(warning if is_excedente else "")
        add_warning(warning)

    totals_by_acopio: dict[int, dict] = {}
    totals_by_item: dict[int, dict] = {}
    for index, consumo in enumerate(consumos):
        acopio_bucket = totals_by_acopio.setdefault(
            consumo["acopio_id"],
            {"indices": [], "m2": Decimal("0"), "ml": Decimal("0"), "pesos": Decimal("0"), "unidades": 0},
        )
        add_to_bucket(acopio_bucket, consumo, index)

        acopio_item_id = consumo.get("acopio_item_id")
        if acopio_item_id:
            item_bucket = totals_by_item.setdefault(
                acopio_item_id,
                {"indices": [], "m2": Decimal("0"), "ml": Decimal("0"), "pesos": Decimal("0"), "unidades": 0},
            )
            add_to_bucket(item_bucket, consumo, index)

    for acopio_id, bucket in totals_by_acopio.items():
        acopio = db.query(Acopio).filter(Acopio.id == acopio_id).first()
        if not acopio:
            continue

        if bucket["m2"] > _to_decimal(acopio.saldo_m2):
            mark_excedente(
                bucket["indices"],
                f"Acopio {acopio_id}: consumo acumulado m2 {bucket['m2']} excede saldo {acopio.saldo_m2}",
                "ACOPIO"
            )
        if bucket["ml"] > _to_decimal(acopio.saldo_ml):
            mark_excedente(
                bucket["indices"],
                f"Acopio {acopio_id}: consumo acumulado ml {bucket['ml']} excede saldo {acopio.saldo_ml}",
                "ACOPIO"
            )
        if _money(bucket["pesos"]) > _money(acopio.saldo_pesos):
            mark_excedente(
                bucket["indices"],
                f"Acopio {acopio_id}: consumo acumulado pesos {bucket['pesos']} excede saldo {acopio.saldo_pesos}",
                "ACOPIO"
            )
        if bucket["unidades"] > int(acopio.saldo_unidades or 0):
            mark_excedente(
                bucket["indices"],
                f"Acopio {acopio_id}: consumo acumulado unidades {bucket['unidades']} excede saldo {acopio.saldo_unidades}",
                "ACOPIO"
            )

    for item_id, bucket in totals_by_item.items():
        item = db.query(AcopioItem).filter(AcopioItem.id == item_id).first()
        if not item:
            continue

        item_label = item.descripcion or item_id
        if bucket["m2"] > _to_decimal(item.saldo_m2):
            mark_excedente(
                bucket["indices"],
                f"Item {item_label}: consumo acumulado m2 {bucket['m2']} excede saldo {item.saldo_m2}",
                "ITEM"
            )
        if bucket["ml"] > _to_decimal(item.saldo_ml):
            mark_excedente(
                bucket["indices"],
                f"Item {item_label}: consumo acumulado ml {bucket['ml']} excede saldo {item.saldo_ml}",
                "ITEM"
            )
        if _money(bucket["pesos"]) > _money(item.saldo_pesos):
            mark_excedente(
                bucket["indices"],
                f"Item {item_label}: consumo acumulado pesos {bucket['pesos']} excede saldo {item.saldo_pesos}",
                "ITEM"
            )
        if bucket["unidades"] > int(item.saldo_cantidad or 0):
            mark_excedente(
                bucket["indices"],
                f"Item {item_label}: consumo acumulado unidades {bucket['unidades']} excede saldo {item.saldo_cantidad}",
                "ITEM"
            )

    policy = settings.excedente_policy
    if any(excedente_flags) and policy == ExcedentePolicy.BLOCK:
        raise ValueError(f"Imputacion bloqueada por excedente: {'; '.join(warnings)}")

    imputaciones: list[Imputacion] = []
    for i, consumo in enumerate(consumos):
        is_excedente = excedente_flags[i]
        imputacion = Imputacion(
            pedido_id=consumo["pedido_id"],
            acopio_id=consumo["acopio_id"],
            acopio_item_id=consumo.get("acopio_item_id"),
            cantidad_m2=consumo["cantidad_m2"],
            cantidad_ml=consumo["cantidad_ml"],
            cantidad_pesos=consumo["cantidad_pesos"],
            cantidad_unidades=consumo["cantidad_unidades"],
            es_excedente=is_excedente,
            excedente_tipo=excedente_tipos[i],
            excedente_motivo=excedente_motivos[i] if is_excedente and excedente_motivos[i] else None,
            pedido_item_descripcion=consumo.get("pedido_item_descripcion"),
            composicion_normalizada=consumo.get("composicion_normalizada"),
            composicion_match_estado=consumo.get("composicion_match_estado"),
            composicion_match_score=consumo.get("composicion_match_score"),
            composicion_advertencia=consumo.get("composicion_advertencia"),
        )
        db.add(imputacion)
        db.flush()

        for proceso in consumo.get("procesos") or []:
            proceso_key = proceso.get("proceso")
            if proceso_key not in PROCESS_FIELDS:
                continue

            unidad = proceso.get("unidad") or PROCESS_UNITS[proceso_key]
            if unidad != PROCESS_UNITS[proceso_key]:
                continue

            cantidad = Decimal(str(proceso.get("cantidad") or 0))
            if cantidad == 0:
                continue

            db.add(ImputacionProceso(
                imputacion_id=imputacion.id,
                proceso=proceso_key,
                unidad=unidad,
                cantidad=cantidad,
                origen=proceso.get("origen") or "composicion_pedido",
            ))

        imputaciones.append(imputacion)

    db.commit()
    for imputacion in imputaciones:
        db.refresh(imputacion)

    from services.acopio_service import update_saldos
    for acopio_id in {imputacion.acopio_id for imputacion in imputaciones}:
        update_saldos(db, acopio_id)

    return_warnings = warnings if (any(excedente_flags) and policy == ExcedentePolicy.WARN) else []
    return imputaciones, return_warnings


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
