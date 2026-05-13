"""Compensation summary for acopio detail."""
from decimal import Decimal, ROUND_HALF_UP
from typing import Optional

from sqlalchemy.orm import Session

from models import Acopio
from services.proceso_inference import PROCESS_FIELDS, PROCESS_UNITS


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

    precios = acopio.precios_referencia
    total_positivo = Decimal("0")
    total_negativo = Decimal("0")
    rows = []

    for field in PROCESS_FIELDS:
        unidad = PROCESS_UNITS[field]
        cantidad_acopio = _round_qty(acopio_totals[field])
        cantidad_pedidos = _round_qty(pedido_totals[field])
        diferencia = _round_qty(cantidad_acopio - cantidad_pedidos)
        precio = _to_decimal(getattr(precios, field, 0) if precios else 0)
        importe = _round_money(diferencia * precio)

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

        precio_faltante = diferencia != 0 and precio == 0
        if precio_faltante:
            warnings.append(
                f"Falta precio de referencia para {PROCESS_LABELS[field]}."
            )

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

