"""Compensation summary for acopio detail."""
from decimal import Decimal, ROUND_HALF_UP
from typing import Optional

from sqlalchemy.orm import Session

from models import Acopio, AcopioItemPrecioReferencia
from services.item_precios_referencia_service import (
    ensure_acopio_item_reference_prices,
    is_reference_price_missing,
)
from services.proceso_inference import (
    PROCESS_FIELDS,
    PROCESS_UNITS,
    has_structural_offset_camera_text,
)


MONEY_QUANT = Decimal("0.01")
QTY_QUANT = Decimal("0.0001")

PROCESS_LABELS = {
    "vidrio_exterior": "Vidrio Exterior",
    "vidrio_interior": "Vidrio Interior",
    "camara_estructural": "Camara Estructural",
    "pulido": "Pulido",
    "fason_templado_exterior": "Fason Templado Exterior",
    "pegado_bastidor": "Pegado a Bastidor",
    "camara_normal": "Camara Normal",
    "opacificado_perimetral": "Opacificado Perimetral",
    "opacificado_total": "Opacificado Total",
    "camara_offset": "Camara Offset",
}


def _to_decimal(value) -> Decimal:
    if value is None:
        return Decimal("0")
    if isinstance(value, Decimal):
        return value
    return Decimal(str(value))


def _round_money(value: Decimal) -> Decimal:
    return value.quantize(MONEY_QUANT, rounding=ROUND_HALF_UP)


def _round_qty(value: Decimal) -> Decimal:
    return value.quantize(QTY_QUANT, rounding=ROUND_HALF_UP)


def _as_float(value: Decimal) -> float:
    return float(value)


def _empty_process_totals() -> dict:
    return {field: Decimal("0") for field in PROCESS_FIELDS}


def _build_acopio_process_totals(acopio: Acopio) -> tuple[dict, dict]:
    """Sum process quantities from acopio items that have the process checked."""
    totals = _empty_process_totals()
    detail = {field: [] for field in PROCESS_FIELDS}

    for item in acopio.items:
        for field in PROCESS_FIELDS:
            if not bool(getattr(item, f"proceso_{field}", False)):
                continue

            unidad = PROCESS_UNITS[field]
            cantidad = _to_decimal(item.total_m2 if unidad == "m2" else item.total_ml)
            totals[field] += cantidad
            if cantidad != 0:
                detail[field].append({
                    "item_id": item.id,
                    "descripcion": item.descripcion,
                    "cantidad": _as_float(_round_qty(cantidad)),
                })

    return totals, detail


def _build_acopio_item_process_totals(acopio: Acopio) -> dict:
    """Sum acopio process quantities by item and concept."""
    totals = {}
    for item in acopio.items:
        for field in PROCESS_FIELDS:
            if not bool(getattr(item, f"proceso_{field}", False)):
                continue

            unidad = PROCESS_UNITS[field]
            cantidad = _to_decimal(item.total_m2 if unidad == "m2" else item.total_ml)
            totals[(item.id, field)] = totals.get((item.id, field), Decimal("0")) + cantidad

    return totals


def _snapshot_processes_for_compensacion(imputacion) -> list:
    procesos = list(imputacion.procesos or [])
    if not procesos:
        return procesos

    has_offset_snapshot = any(
        proceso.proceso == "camara_offset"
        for proceso in procesos
    )
    if has_offset_snapshot and has_structural_offset_camera_text(imputacion.pedido_item_descripcion):
        return [
            proceso
            for proceso in procesos
            if proceso.proceso != "camara_estructural"
        ]

    return procesos


def _add_item_process_total(totals: dict, item_id: int, field: str, cantidad: Decimal) -> None:
    if item_id is None or cantidad == 0:
        return
    key = (item_id, field)
    totals[key] = totals.get(key, Decimal("0")) + cantidad


def _item_process_qty(item, field: str) -> Decimal:
    unidad = PROCESS_UNITS[field]
    return _to_decimal(item.total_m2 if unidad == "m2" else item.total_ml)


def _distribute_snapshot_process_to_items(
    acopio: Acopio,
    totals: dict,
    field: str,
    cantidad: Decimal,
    target_item_id: int | None,
    warnings: list[str],
) -> None:
    item_map = {item.id: item for item in acopio.items}
    if target_item_id and target_item_id in item_map:
        _add_item_process_total(totals, target_item_id, field, cantidad)
        return

    candidates = [
        item
        for item in acopio.items
        if bool(getattr(item, f"proceso_{field}", False))
    ]
    if not candidates:
        warnings.append(
            f"No hay item habilitado para asignar el proceso '{field}' de pedidos imputados."
        )
        return

    total_qty = sum((_item_process_qty(item, field) for item in candidates), Decimal("0"))
    if total_qty == 0:
        warnings.append(
            f"No se pudo prorratear el proceso '{field}' porque los items habilitados no tienen cantidad."
        )
        return

    for item in candidates:
        item_qty = _item_process_qty(item, field)
        _add_item_process_total(
            totals,
            item.id,
            field,
            _round_qty(cantidad * item_qty / total_qty),
        )


def _build_pedido_process_totals(acopio: Acopio, warnings: list[str]) -> tuple[dict, dict]:
    """
    Calculate process quantities consumed by each imputacion using proration.

    For each acopio item that has a process marked, and for each imputacion
    linked to that item, we prorate the process quantity proportionally:

        pedido_proceso_qty = (pedido_qty_in_process_unit / item_total_qty_in_process_unit)
                             * item_process_qty

    This avoids re-inferring processes from SPF text (which lacks process info)
    and correctly attributes process quantities based on physical consumption.

    Imputaciones without a specific acopio_item_id are prorated against the
    whole acopio totals as a fallback.
    """
    totals = _empty_process_totals()
    detail = {field: [] for field in PROCESS_FIELDS}

    # Build a lookup: item_id -> item object, for quick access
    item_map = {item.id: item for item in acopio.items}

    # Compute acopio-level totals per unit for the whole-acopio fallback
    acopio_total_m2 = sum(_to_decimal(it.total_m2) for it in acopio.items)
    acopio_total_ml = sum(_to_decimal(it.total_ml) for it in acopio.items)

    for imputacion in acopio.imputaciones:
        pedido_id = imputacion.pedido_id
        pedido_numero = imputacion.pedido.numero if imputacion.pedido else str(pedido_id)

        procesos_snapshot = _snapshot_processes_for_compensacion(imputacion)
        if procesos_snapshot:
            for proceso in procesos_snapshot:
                field = proceso.proceso
                if field not in PROCESS_FIELDS:
                    warnings.append(f"Proceso desconocido en imputacion {imputacion.id}: {field}")
                    continue

                cantidad = _round_qty(_to_decimal(proceso.cantidad))
                if cantidad == 0:
                    continue

                totals[field] += cantidad
                detail[field].append({
                    "imputacion_id": imputacion.id,
                    "pedido_id": pedido_id,
                    "pedido_numero": pedido_numero,
                    "cantidad": _as_float(cantidad),
                    "origen": proceso.origen or "composicion_pedido",
                })
            continue

        imp_m2 = _to_decimal(imputacion.cantidad_m2)
        imp_ml = _to_decimal(imputacion.cantidad_ml)

        # Determine which items contribute to this imputacion
        if imputacion.acopio_item_id and imputacion.acopio_item_id in item_map:
            # Imputacion is linked to a specific item → prorate against that item
            contributing_items = [(item_map[imputacion.acopio_item_id], imp_m2, imp_ml)]
        else:
            # No specific item link → distribute proportionally across all items
            # using the imputacion totals vs acopio totals ratio
            contributing_items = [
                (
                    item,
                    # Share of this imputacion's m2/ml attributable to this item
                    (imp_m2 * _to_decimal(item.total_m2) / acopio_total_m2)
                    if acopio_total_m2 != 0 else Decimal("0"),
                    (imp_ml * _to_decimal(item.total_ml) / acopio_total_ml)
                    if acopio_total_ml != 0 else Decimal("0"),
                )
                for item in acopio.items
            ]

        for item, item_imp_m2, item_imp_ml in contributing_items:
            item_total_m2 = _to_decimal(item.total_m2)
            item_total_ml = _to_decimal(item.total_ml)

            for field in PROCESS_FIELDS:
                if not bool(getattr(item, f"proceso_{field}", False)):
                    continue

                unidad = PROCESS_UNITS[field]
                item_process_qty = item_total_m2 if unidad == "m2" else item_total_ml
                imp_qty_for_unit = item_imp_m2 if unidad == "m2" else item_imp_ml
                item_total_for_unit = item_total_m2 if unidad == "m2" else item_total_ml

                if item_total_for_unit == 0:
                    warnings.append(
                        f"Item {item.id} tiene proceso '{field}' activo pero su total en {unidad} es 0."
                    )
                    continue

                # Prorate: how much of the process quantity does this imputacion consume?
                ratio = imp_qty_for_unit / item_total_for_unit
                cantidad = _round_qty(ratio * item_process_qty)

                if cantidad == 0:
                    continue

                totals[field] += cantidad
                detail[field].append({
                    "imputacion_id": imputacion.id,
                    "pedido_id": pedido_id,
                    "pedido_numero": pedido_numero,
                    "cantidad": _as_float(cantidad),
                    "origen": "prorrateado",
                })

    return totals, detail


def _build_pedido_item_process_totals(acopio: Acopio, warnings: list[str]) -> dict:
    """Calculate consumed process quantities by item and concept."""
    totals = {}
    item_map = {item.id: item for item in acopio.items}
    acopio_total_m2 = sum(_to_decimal(it.total_m2) for it in acopio.items)
    acopio_total_ml = sum(_to_decimal(it.total_ml) for it in acopio.items)

    for imputacion in acopio.imputaciones:
        procesos_snapshot = _snapshot_processes_for_compensacion(imputacion)
        if procesos_snapshot:
            for proceso in procesos_snapshot:
                field = proceso.proceso
                if field not in PROCESS_FIELDS:
                    continue
                cantidad = _round_qty(_to_decimal(proceso.cantidad))
                if cantidad == 0:
                    continue
                _distribute_snapshot_process_to_items(
                    acopio,
                    totals,
                    field,
                    cantidad,
                    imputacion.acopio_item_id,
                    warnings,
                )
            continue

        imp_m2 = _to_decimal(imputacion.cantidad_m2)
        imp_ml = _to_decimal(imputacion.cantidad_ml)

        if imputacion.acopio_item_id and imputacion.acopio_item_id in item_map:
            contributing_items = [(item_map[imputacion.acopio_item_id], imp_m2, imp_ml)]
        else:
            contributing_items = [
                (
                    item,
                    (imp_m2 * _to_decimal(item.total_m2) / acopio_total_m2)
                    if acopio_total_m2 != 0 else Decimal("0"),
                    (imp_ml * _to_decimal(item.total_ml) / acopio_total_ml)
                    if acopio_total_ml != 0 else Decimal("0"),
                )
                for item in acopio.items
            ]

        for item, item_imp_m2, item_imp_ml in contributing_items:
            item_total_m2 = _to_decimal(item.total_m2)
            item_total_ml = _to_decimal(item.total_ml)

            for field in PROCESS_FIELDS:
                if not bool(getattr(item, f"proceso_{field}", False)):
                    continue

                unidad = PROCESS_UNITS[field]
                item_process_qty = item_total_m2 if unidad == "m2" else item_total_ml
                imp_qty_for_unit = item_imp_m2 if unidad == "m2" else item_imp_ml
                item_total_for_unit = item_total_m2 if unidad == "m2" else item_total_ml

                if item_total_for_unit == 0:
                    continue

                cantidad = _round_qty((imp_qty_for_unit / item_total_for_unit) * item_process_qty)
                _add_item_process_total(totals, item.id, field, cantidad)

    return totals


def _build_item_price_records(db: Session, acopio: Acopio) -> dict:
    ensure_acopio_item_reference_prices(db, acopio, use_global_fallback=True)
    records = db.query(AcopioItemPrecioReferencia).filter(
        AcopioItemPrecioReferencia.acopio_id == acopio.id,
    ).all()
    return {
        (record.acopio_item_id, record.concepto): record
        for record in records
    }


def _build_item_valuation(
    acopio: Acopio,
    field: str,
    acopio_item_totals: dict,
    pedido_item_totals: dict,
    price_records: dict,
    warnings: list[str],
) -> tuple[Decimal, bool, list[dict]]:
    importe_total = Decimal("0")
    precio_faltante = False
    detail = []

    for item in acopio.items:
        if not bool(getattr(item, f"proceso_{field}", False)):
            continue

        cantidad_acopio = _round_qty(acopio_item_totals.get((item.id, field), Decimal("0")))
        cantidad_pedidos = _round_qty(pedido_item_totals.get((item.id, field), Decimal("0")))
        diferencia = _round_qty(cantidad_acopio - cantidad_pedidos)
        record = price_records.get((item.id, field))
        missing = diferencia != 0 and is_reference_price_missing(record)
        precio = Decimal("0") if missing or record is None else _to_decimal(record.precio_actual)
        importe = _round_money(diferencia * precio)

        if missing:
            precio_faltante = True
            item_label = item.numero_item if item.numero_item is not None else item.id
            warnings.append(
                f"Falta precio de referencia para {PROCESS_LABELS[field]} en item {item_label}."
            )
        else:
            importe_total += importe

        if diferencia != 0 or record is not None:
            detail.append({
                "item_id": item.id,
                "descripcion": item.descripcion,
                "cantidad_acopio": _as_float(cantidad_acopio),
                "cantidad_pedidos": _as_float(cantidad_pedidos),
                "diferencia": _as_float(diferencia),
                "precio_referencia": _as_float(_round_money(precio)),
                "importe": _as_float(importe),
                "precio_faltante": missing,
            })

    return _round_money(importe_total), precio_faltante, detail


def build_resumen_compensacion(
    db: Session,
    acopio_id: int,
    spf_db: Optional[Session] = None,
) -> Optional[dict]:
    """Build the commercial compensation summary for an acopio."""
    acopio = db.query(Acopio).filter(Acopio.id == acopio_id).first()
    if not acopio:
        return None

    warnings: list[str] = []
    acopio_totals, acopio_detail = _build_acopio_process_totals(acopio)
    pedido_totals, pedido_detail = _build_pedido_process_totals(acopio, warnings)
    acopio_item_totals = _build_acopio_item_process_totals(acopio)
    pedido_item_totals = _build_pedido_item_process_totals(acopio, warnings)
    price_records = _build_item_price_records(db, acopio)

    total_positivo = Decimal("0")
    total_negativo = Decimal("0")
    rows = []

    for field in PROCESS_FIELDS:
        unidad = PROCESS_UNITS[field]
        cantidad_acopio = _round_qty(acopio_totals[field])
        cantidad_pedidos = _round_qty(pedido_totals[field])
        diferencia = _round_qty(cantidad_acopio - cantidad_pedidos)
        importe, precio_faltante, items_valorizacion = _build_item_valuation(
            acopio,
            field,
            acopio_item_totals,
            pedido_item_totals,
            price_records,
            warnings,
        )
        precio = _round_money(importe / diferencia) if diferencia != 0 else Decimal("0")

        if importe > 0:
            total_positivo += importe
        elif importe < 0:
            total_negativo += importe

        if diferencia > 0:
            estado = "sobrante_acopio"
        elif diferencia < 0:
            estado = "excedente_pedido"
        else:
            estado = "compensado"

        rows.append({
            "proceso": field,
            "label": PROCESS_LABELS[field],
            "unidad": unidad,
            "cantidad_acopio": _as_float(cantidad_acopio),
            "cantidad_pedidos": _as_float(cantidad_pedidos),
            "diferencia": _as_float(diferencia),
            "precio_referencia": _as_float(_round_money(precio)),
            "importe": _as_float(importe),
            "estado": estado,
            "precio_faltante": precio_faltante,
            "items_acopio": acopio_detail[field],
            "pedidos": pedido_detail[field],
            "items_valorizacion": items_valorizacion,
        })

    saldo = _round_money(total_positivo + total_negativo)

    return {
        "acopio_id": acopio.id,
        "numero": acopio.numero,
        "v_presupuesto_id": acopio.v_presupuesto_id,
        "totals": {
            "positivo": _as_float(_round_money(total_positivo)),
            "negativo": _as_float(_round_money(total_negativo)),
            "saldo": _as_float(saldo),
        },
        "rows": rows,
        "warnings": warnings,
    }
