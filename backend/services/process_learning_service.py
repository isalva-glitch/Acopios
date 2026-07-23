"""Supervised learning support for process inference corrections."""
from decimal import Decimal
from typing import Iterable

from sqlalchemy.orm import Session

from models import AcopioItem, CorreccionProceso, ReglaProceso
from services.proceso_inference import (
    PROCESS_FIELDS,
    infer_item_processes_from_texts,
    normalize_process_text,
)


def process_flags_from_item(item: AcopioItem) -> dict[str, bool]:
    return {
        field: bool(getattr(item, f"proceso_{field}", False))
        for field in PROCESS_FIELDS
    }


def item_learning_text(item: AcopioItem) -> str:
    parts: Iterable[object] = (
        item.descripcion,
        item.material,
        item.tipologia,
        *(pano.denominacion for pano in item.panos),
        *(adicional.descripcion for adicional in item.adicionales),
    )
    return " ".join(str(part or "") for part in parts).strip()


def normalize_learning_texts(texts: Iterable[object]) -> str:
    return normalize_process_text(" ".join(str(text or "") for text in texts))


def _approved_rules_for_text(db: Session, normalized_text: str) -> list[ReglaProceso]:
    if not normalized_text:
        return []
    return db.query(ReglaProceso).filter(
        ReglaProceso.estado == "aprobada",
        ReglaProceso.alcance == "item_text_exact",
        ReglaProceso.tipo_patron == "texto_normalizado",
        ReglaProceso.patron == normalized_text,
    ).order_by(ReglaProceso.prioridad.asc(), ReglaProceso.id.asc()).all()


def apply_approved_process_rules(
    db: Session,
    texts: Iterable[object],
    base_flags: dict[str, bool] | None = None,
) -> tuple[dict[str, bool], list[dict]]:
    normalized_text = normalize_learning_texts(texts)
    flags = dict(base_flags or infer_item_processes_from_texts(texts))
    applied = []

    for rule in _approved_rules_for_text(db, normalized_text):
        before = bool(flags.get(rule.proceso))
        if rule.accion == "activar":
            flags[rule.proceso] = True
        elif rule.accion == "desactivar":
            flags[rule.proceso] = False
        else:
            continue

        after = bool(flags.get(rule.proceso))
        applied.append({
            "regla_id": rule.id,
            "proceso": rule.proceso,
            "accion": rule.accion,
            "antes": before,
            "despues": after,
        })

    return flags, applied


def infer_item_processes_with_learning(db: Session, texts: Iterable[object]) -> dict[str, bool]:
    flags, _applied = apply_approved_process_rules(db, texts)
    return flags


def _changed_processes(before: dict[str, bool], after: dict[str, bool]) -> dict:
    return {
        field: {"antes": bool(before.get(field)), "despues": bool(after.get(field))}
        for field in PROCESS_FIELDS
        if bool(before.get(field)) != bool(after.get(field))
    }


def _confidence_from_support(support_count: int) -> Decimal:
    # Conservative score for proposed rules. Approval remains manual.
    value = min(Decimal("0.95"), Decimal("0.45") + (Decimal(support_count) * Decimal("0.10")))
    return value.quantize(Decimal("0.0001"))


def _example_for_rule(correction: CorreccionProceso, item: AcopioItem) -> dict:
    return {
        "correccion_id": correction.id,
        "acopio_id": correction.acopio_id,
        "acopio_item_id": correction.acopio_item_id,
        "numero_item": item.numero_item,
        "descripcion": item.descripcion,
    }


def _upsert_proposed_rules(db: Session, correction: CorreccionProceso, item: AcopioItem) -> list[ReglaProceso]:
    rules = []
    pattern = correction.texto_normalizado
    if not pattern:
        return rules

    for field, change in correction.cambios.items():
        action = "activar" if bool(change["despues"]) else "desactivar"
        rule = db.query(ReglaProceso).filter(
            ReglaProceso.patron == pattern,
            ReglaProceso.proceso == field,
            ReglaProceso.accion == action,
            ReglaProceso.alcance == "item_text_exact",
        ).first()

        example = _example_for_rule(correction, item)
        if rule:
            rule.soporte_count = int(rule.soporte_count or 0) + 1
            existing_examples = list(rule.ejemplos or [])
            if not any(current.get("correccion_id") == correction.id for current in existing_examples):
                existing_examples.append(example)
            rule.ejemplos = existing_examples[-10:]
            rule.confianza = _confidence_from_support(rule.soporte_count)
        else:
            rule = ReglaProceso(
                patron=pattern,
                tipo_patron="texto_normalizado",
                proceso=field,
                accion=action,
                alcance="item_text_exact",
                estado="propuesta",
                prioridad=100,
                soporte_count=1,
                confianza=_confidence_from_support(1),
                ejemplos=[example],
                creada_desde_correccion_id=correction.id,
            )
            db.add(rule)
        rules.append(rule)

    return rules


def register_item_process_correction(
    db: Session,
    item: AcopioItem,
    before: dict[str, bool],
    after: dict[str, bool],
    origin: str = "manual",
) -> CorreccionProceso | None:
    changes = _changed_processes(before, after)
    if not changes:
        return None

    original_text = item_learning_text(item)
    correction = CorreccionProceso(
        acopio_id=item.acopio_id,
        acopio_item_id=item.id,
        origen=origin,
        estado="registrada",
        texto_original=original_text,
        texto_normalizado=normalize_process_text(original_text),
        procesos_antes=before,
        procesos_despues=after,
        cambios=changes,
    )
    db.add(correction)
    db.flush()
    _upsert_proposed_rules(db, correction, item)
    return correction


def correction_to_dict(correction: CorreccionProceso) -> dict:
    return {
        "id": correction.id,
        "acopio_id": correction.acopio_id,
        "acopio_item_id": correction.acopio_item_id,
        "pedido_id": correction.pedido_id,
        "origen": correction.origen,
        "estado": correction.estado,
        "texto_original": correction.texto_original,
        "texto_normalizado": correction.texto_normalizado,
        "procesos_antes": correction.procesos_antes,
        "procesos_despues": correction.procesos_despues,
        "cambios": correction.cambios,
        "created_at": correction.created_at.isoformat() if correction.created_at else None,
    }


def rule_to_dict(rule: ReglaProceso) -> dict:
    return {
        "id": rule.id,
        "patron": rule.patron,
        "tipo_patron": rule.tipo_patron,
        "proceso": rule.proceso,
        "accion": rule.accion,
        "alcance": rule.alcance,
        "estado": rule.estado,
        "prioridad": rule.prioridad,
        "soporte_count": rule.soporte_count,
        "confianza": float(rule.confianza or 0),
        "ejemplos": rule.ejemplos,
        "creada_desde_correccion_id": rule.creada_desde_correccion_id,
        "created_at": rule.created_at.isoformat() if rule.created_at else None,
    }


def set_rule_state(db: Session, rule: ReglaProceso, state: str) -> ReglaProceso:
    if state not in {"propuesta", "aprobada", "desactivada"}:
        raise ValueError(f"Estado de regla invalido: {state}")
    rule.estado = state
    db.flush()
    return rule


def simulate_rule(db: Session, rule: ReglaProceso, limit: int = 100) -> dict:
    affected = []
    query = db.query(AcopioItem).order_by(AcopioItem.id.asc())
    for item in query.all():
        texts = [
            item.descripcion,
            item.material,
            item.tipologia,
            *(pano.denominacion for pano in item.panos),
            *(adicional.descripcion for adicional in item.adicionales),
        ]
        normalized_text = normalize_learning_texts(texts)
        if rule.tipo_patron != "texto_normalizado" or rule.alcance != "item_text_exact":
            continue
        if normalized_text != rule.patron:
            continue

        before = infer_item_processes_from_texts(texts)
        after = dict(before)
        if rule.accion == "activar":
            after[rule.proceso] = True
        elif rule.accion == "desactivar":
            after[rule.proceso] = False
        else:
            continue

        if before == after:
            continue

        affected.append({
            "acopio_id": item.acopio_id,
            "acopio_item_id": item.id,
            "numero_item": item.numero_item,
            "descripcion": item.descripcion,
            "proceso": rule.proceso,
            "antes": before[rule.proceso],
            "despues": after[rule.proceso],
        })
        if len(affected) >= limit:
            break

    return {
        "regla": rule_to_dict(rule),
        "affected_count": len(affected),
        "affected_items": affected,
    }
