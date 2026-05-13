"""Compensation summary for acopio detail."""
from decimal import Decimal, ROUND_HALF_UP
from typing import Optional

from sqlalchemy.orm import Session

from integrations.spf import services as spf_services
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


def _snapshot_process_rows(imputacion) -> Optional[list[dict]]:
    if not imputacion.procesos:
        return None

    return [
        {
            "proceso": proceso.proceso,
            "unidad": proceso.unidad,
            "cantidad": proceso.cantidad,
            "origen": proceso.origen,
        }
        for proceso in imputacion.procesos
    ]


def _spf_process_rows(spf_db: Optional[Session], imputacion, warnings: list[str]) -> list[dict]:
    pedido_numero = imputacion.pedido.numero if imputacion.pedido else None
    if not spf_db or not pedido_numero:
        warnings.append(
            f"La imputacion {imputacion.id} no tiene desglose por proceso guardado."
        )
        return []

    try:
        spf_pedido = spf_services.get_pedido_for_imputation(spf_db, str(pedido_numero))
    except Exception as exc:
        warnings.append(
            f"No se pudo recalcular el pedido {pedido_numero} desde SPF: {exc}"
        )
        return []

    if not spf_pedido:
        warnings.append(f"No se encontro el pedido {pedido_numero} en SPF.")
        return []

    procesos = spf_pedido.get("procesos") or []
    if not procesos:
        warnings.append(f"El pedido {pedido_numero} no tiene procesos detectados.")
    return procesos


def build_resumen_compensacion(
    db: Session,
    acopio_id: int,
    spf_db: Optional[Session] = None,
) -> Optional[dict]:
    """Build the commercial compensation summary for an acopio."""
    acopio = db.query(Acopio).filter(Acopio.id == acopio_id).first()
    if not acopio:
        return None

    warnings = []
    acopio_totals, acopio_detail = _build_acopio_process_totals(acopio)
    pedido_totals = _empty_process_totals()
    pedido_detail = {field: [] for field in PROCESS_FIELDS}

    for imputacion in acopio.imputaciones:
        rows = _snapshot_process_rows(imputacion)
        source = "snapshot"
        if rows is None:
            rows = _spf_process_rows(spf_db, imputacion, warnings)
            source = "spf"

        for row in rows:
            field = row.get("proceso")
            if field not in PROCESS_FIELDS:
                warnings.append(f"Proceso desconocido en imputacion {imputacion.id}: {field}")
                continue

            unidad = row.get("unidad") or PROCESS_UNITS[field]
            if unidad != PROCESS_UNITS[field]:
                warnings.append(
                    f"Unidad invalida para {field} en imputacion {imputacion.id}: {unidad}"
                )
                continue

            cantidad = _to_decimal(row.get("cantidad"))
            pedido_totals[field] += cantidad
            if cantidad != 0:
                pedido_detail[field].append({
                    "imputacion_id": imputacion.id,
                    "pedido_id": imputacion.pedido_id,
                    "pedido_numero": imputacion.pedido.numero if imputacion.pedido else None,
                    "cantidad": _as_float(_round_qty(cantidad)),
                    "origen": row.get("origen") or source,
                })

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
