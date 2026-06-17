"""Item-scoped reference price rules."""
from decimal import Decimal, ROUND_HALF_UP
from typing import Iterable

from sqlalchemy.orm import Session

from models import Acopio, AcopioItem, AcopioItemPrecioReferencia
from schemas.acopio_item_precio_referencia import (
    ConceptoPrecioReferenciaInput,
    ItemPreciosReferenciaInput,
)
from services.proceso_inference import PROCESS_FIELDS, PROCESS_UNITS


MONEY_QUANT = Decimal("0.01")
VALID_ORIGINS = {"autodetectado", "manual", "migrado"}


def _to_decimal(value) -> Decimal:
    if value is None:
        return Decimal("0")
    if isinstance(value, Decimal):
        return value
    return Decimal(str(value))


def _to_price_or_none(value) -> Decimal | None:
    if value is None:
        return None
    return _to_decimal(value).quantize(MONEY_QUANT, rounding=ROUND_HALF_UP)


def _global_price_for(acopio: Acopio, concepto: str) -> Decimal | None:
    precios = acopio.precios_referencia
    if not precios:
        return None
    return _to_price_or_none(getattr(precios, concepto, None))


def get_item_enabled_concepts(item: AcopioItem) -> list[str]:
    """Return concepts currently enabled by persisted item process flags."""
    return [
        field
        for field in PROCESS_FIELDS
        if bool(getattr(item, f"proceso_{field}", False))
    ]


def is_reference_price_missing(record: AcopioItemPrecioReferencia | None) -> bool:
    """Return true when a record cannot be used as a completed price."""
    if record is None or not record.habilitado:
        return True
    if record.precio_actual is None:
        return True

    precio_actual = _to_decimal(record.precio_actual)
    return precio_actual == 0 and record.origen != "manual"


def _estado_item(conceptos: list[AcopioItemPrecioReferencia]) -> str:
    enabled = [concepto for concepto in conceptos if concepto.habilitado]
    if not enabled:
        return "sin_conceptos"
    if any(is_reference_price_missing(concepto) for concepto in enabled):
        return "incompleto"
    return "completo"


def _sort_items(items: Iterable[AcopioItem]) -> list[AcopioItem]:
    return sorted(
        items,
        key=lambda item: (
            item.numero_item if item.numero_item is not None else 0,
            item.id or 0,
        ),
    )


def sync_item_reference_prices(
    db: Session,
    acopio: Acopio,
    item: AcopioItem,
    *,
    use_global_fallback: bool,
) -> bool:
    """
    Synchronize persisted rows with the item process flags.

    New rows created during migration compatibility can copy the legacy global
    price. New rows created after a manual process toggle stay pending.
    """
    changed = False
    enabled_concepts = set(get_item_enabled_concepts(item))
    records = {
        record.concepto: record
        for record in db.query(AcopioItemPrecioReferencia)
        .filter(AcopioItemPrecioReferencia.acopio_item_id == item.id)
        .all()
    }

    for concepto in enabled_concepts:
        unidad = PROCESS_UNITS[concepto]
        record = records.get(concepto)
        if record:
            if not record.habilitado:
                record.habilitado = True
                changed = True
            if record.unidad != unidad:
                record.unidad = unidad
                changed = True
            if record.acopio_id != acopio.id:
                record.acopio_id = acopio.id
                changed = True
            continue

        fallback = _global_price_for(acopio, concepto) if use_global_fallback else None
        origin = "migrado" if fallback is not None and use_global_fallback else "autodetectado"
        db.add(AcopioItemPrecioReferencia(
            acopio_id=acopio.id,
            acopio_item_id=item.id,
            concepto=concepto,
            unidad=unidad,
            precio_base=fallback,
            precio_actual=fallback,
            habilitado=True,
            origen=origin,
        ))
        changed = True

    for concepto, record in records.items():
        if concepto not in PROCESS_FIELDS:
            continue
        if concepto not in enabled_concepts and record.habilitado:
            record.habilitado = False
            changed = True

    if changed:
        db.flush()
    return changed


def ensure_acopio_item_reference_prices(
    db: Session,
    acopio: Acopio,
    *,
    use_global_fallback: bool = True,
) -> bool:
    """Ensure every enabled item concept has one persisted reference-price row."""
    changed = False
    for item in acopio.items:
        changed = sync_item_reference_prices(
            db,
            acopio,
            item,
            use_global_fallback=use_global_fallback,
        ) or changed
    return changed


def build_items_reference_prices_matrix(db: Session, acopio: Acopio) -> dict:
    """Return the item reference-price matrix consumed by the frontend."""
    ensure_acopio_item_reference_prices(db, acopio)

    records = db.query(AcopioItemPrecioReferencia).filter(
        AcopioItemPrecioReferencia.acopio_id == acopio.id,
    ).all()
    records_by_item = {}
    for record in records:
        records_by_item.setdefault(record.acopio_item_id, {})[record.concepto] = record

    response_items = []
    for item in _sort_items(acopio.items):
        enabled_concepts = set(get_item_enabled_concepts(item))
        item_records = records_by_item.get(item.id, {})
        conceptos = [
            item_records[concepto]
            for concepto in PROCESS_FIELDS
            if concepto in enabled_concepts and concepto in item_records
        ]
        response_items.append({
            "item_id": item.id,
            "numero_item": str(item.numero_item or item.id),
            "descripcion": item.descripcion,
            "cantidad": item.cantidad or 0,
            "total_m2": _to_decimal(item.total_m2),
            "total_ml": _to_decimal(item.total_ml),
            "total_pesos": _to_decimal(item.total_pesos),
            "conceptos": conceptos,
            "estado_precios_referencia": _estado_item(conceptos),
        })

    return {
        "acopio_id": acopio.id,
        "items": response_items,
    }


def _validate_input_concept(
    item: AcopioItem,
    payload: ConceptoPrecioReferenciaInput,
) -> tuple[str, Decimal | None, Decimal | None]:
    concepto = payload.concepto
    if concepto not in PROCESS_FIELDS:
        raise ValueError(f"Concepto de precio de referencia desconocido: {concepto}")

    enabled_concepts = set(get_item_enabled_concepts(item))
    if concepto not in enabled_concepts:
        if payload.habilitado:
            raise ValueError(
                f"El concepto {concepto} no esta habilitado para el item {item.numero_item or item.id}."
            )
        return concepto, None, None

    precio_base = _to_price_or_none(payload.precio_base)
    precio_actual = _to_price_or_none(payload.precio_actual)

    for label, value in (("precio_base", precio_base), ("precio_actual", precio_actual)):
        if value is not None and value < 0:
            raise ValueError(f"{label} no puede ser negativo para {concepto}.")

    if precio_actual is None:
        raise ValueError(
            f"El concepto {concepto} del item {item.numero_item or item.id} requiere precio actual."
        )
    if precio_actual == 0 and not payload.confirmar_cero:
        raise ValueError(
            f"Confirme explicitamente el precio 0 para {concepto} del item {item.numero_item or item.id}."
        )

    return concepto, precio_base, precio_actual


def _records_for_acopio(db: Session, acopio_id: int) -> dict[tuple[int, str], AcopioItemPrecioReferencia]:
    records = db.query(AcopioItemPrecioReferencia).filter(
        AcopioItemPrecioReferencia.acopio_id == acopio_id,
    ).all()
    return {
        (record.acopio_item_id, record.concepto): record
        for record in records
    }


def save_item_reference_prices(
    db: Session,
    acopio: Acopio,
    items_payload: list[ItemPreciosReferenciaInput],
) -> dict:
    """Persist editable item reference prices and return the refreshed matrix."""
    ensure_acopio_item_reference_prices(db, acopio, use_global_fallback=True)
    item_map = {item.id: item for item in acopio.items}
    records = _records_for_acopio(db, acopio.id)

    for item_payload in items_payload:
        item = item_map.get(item_payload.item_id)
        if not item:
            raise ValueError(f"El item {item_payload.item_id} no pertenece al acopio.")

        for concepto_payload in item_payload.conceptos:
            concepto, precio_base, precio_actual = _validate_input_concept(item, concepto_payload)
            key = (item.id, concepto)
            record = records.get(key)

            if concepto not in get_item_enabled_concepts(item):
                if record:
                    record.habilitado = False
                continue

            if not record:
                record = AcopioItemPrecioReferencia(
                    acopio_id=acopio.id,
                    acopio_item_id=item.id,
                    concepto=concepto,
                    unidad=concepto_payload.unidad or PROCESS_UNITS[concepto],
                    origen="manual",
                )
                db.add(record)
                records[key] = record

            changed_price = (
                record.precio_base != precio_base
                or record.precio_actual != precio_actual
            )
            record.unidad = concepto_payload.unidad or PROCESS_UNITS[concepto]
            record.precio_base = precio_base
            record.precio_actual = precio_actual
            record.habilitado = True
            if changed_price or record.origen not in VALID_ORIGINS:
                record.origen = "manual"

    db.flush()
    return build_items_reference_prices_matrix(db, acopio)
