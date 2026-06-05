"""Normalize and match item compositions independent of wording/order."""
from dataclasses import dataclass
from decimal import Decimal
import re
from typing import Iterable, Sequence

from services.proceso_inference import (
    PROCESS_FIELDS,
    has_structural_offset_camera_text,
    infer_item_processes_from_texts,
    normalize_process_text,
)


MATCH_EXACT = "exacta"
MATCH_EQUIVALENT = "equivalente"
MATCH_CHANGED = "cambio_composicion"
MATCH_NONE = "sin_correspondencia"

_COMPONENT_PATTERNS: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("vidrio_eclipse", (r"\beclip(?:se)?\b", r"\badv(?:antage)?\b", r"\bgrey\b")),
    ("vidrio_incoloro", (r"\bincolor[oa]\b",)),
    ("vidrio_float", (r"\bfloat\b",)),
    ("laminado_3_3", (r"\blam(?:inado)?\s*3\s*3\b", r"\b3\s*3\b")),
    ("camara_12", (r"\bcamara\s*12\b",)),
    ("camara_12_estructural", (r"\bcamara\s*12\s*(?:mm\s*)?estructural(?!\s*offset)\b",)),
    ("camara_12_offset", (r"\bcamara\s*12\s*(?:mm\s*)?(?:estructural\s*)?offset\b",)),
    ("templado_6", (r"\btemp(?:lado)?(?:\s+(?:float|de))?\s*6\b", r"\btemplado\s+float\s+6\b")),
    ("borde_pulido", (r"\bborde\s+pulido\b", r"\bbordes\s+pulidos\b", r"\bbp\b", r"\bbpsb\b")),
    ("pegado_estructural", (r"\bpegad[oa]\s+(?:estructural|extructural)\b",)),
    ("pegado_bastidor", (r"\bpegad[oa]\s+(?:a\s+)?bastidor\b", r"\bbastidor(?:es)?\b", r"\bbastidos\b")),
    ("opacificado_total", (r"\bopacificado\b", r"\bopacado\b", r"\bserigraf(?:ia|iado)\b")),
    ("opacificado_perimetral", (r"\bopacificado\s+perimetral\b", r"\bopacado\s+perimetral\b")),
)

_STOPWORDS = {
    "con",
    "de",
    "del",
    "la",
    "el",
    "en",
    "mm",
    "mas",
    "color",
    "provisto",
    "provistos",
    "por",
    "cliente",
    "item",
    "inc",
    "sin",
    "brillo",
    "recto",
    "banda",
    "bandas",
    "parcial",
    "parciales",
    "opacificado",
    "opacado",
    "perimetral",
}

_MATERIAL_COMPONENTS = {
    "vidrio_eclipse",
    "vidrio_incoloro",
    "vidrio_float",
    "laminado_3_3",
    "templado_6",
}

_COMPONENT_LABELS = {
    "vidrio_eclipse": "Eclipse Advantage Grey",
    "vidrio_incoloro": "Incoloro",
    "vidrio_float": "Float",
    "laminado_3_3": "Laminado 3+3",
    "templado_6": "Templado 6",
}

_OPACIFICADO_PARCIAL_PATTERNS = (
    r"\bopacificado\s+perimetral\b",
    r"\bopacado\s+perimetral\b",
    r"\bopacificado\b.*\bbandas?\b",
    r"\bopacificado\b.*\bparcial(?:es)?\b",
    r"\bopacado\b.*\bbandas?\b",
    r"\bopacado\b.*\bparcial(?:es)?\b",
    r"\bopac(?:if)?\s+perimetral\b",
    r"\bserigraf(?:ia|iado)\s+perimetral\b",
)


@dataclass(frozen=True)
class ComposicionNormalizada:
    """Canonical representation used to compare acopio and pedido items."""

    texto_normalizado: str
    componentes: tuple[str, ...]
    procesos: dict[str, bool]
    firma: str


@dataclass(frozen=True)
class ComposicionMatch:
    """Best match for a pedido item against acopio items."""

    item: object | None
    estado: str
    score: Decimal
    advertencia: str | None
    diferencias_procesos: tuple[str, ...]


def _joined_text(texts: Iterable[object]) -> str:
    return " ".join(str(text or "") for text in texts)


def _canonical_text(texts: Iterable[object]) -> str:
    text = normalize_process_text(_joined_text(texts))
    replacements = {
        "extructural": "estructural",
        "bastidos": "bastidor",
        "bastidores": "bastidor",
        "adv grey": "advantage grey",
        "eclip adv": "eclipse advantage",
        "tem ": "templado ",
        "temp ": "templado ",
    }
    for source, target in replacements.items():
        text = text.replace(source, target)
    return re.sub(r"\s+", " ", text).strip()


def _is_noise_token(token: str) -> bool:
    if token == "pdf" or token in _STOPWORDS:
        return True

    # Panel/zone labels from presupuestos and pedidos are not composition.
    # Examples seen in SPF/PDF data: PA13, PFA2, PF07, CW3B, CE3B, VF7, SP1.
    if re.match(r"^[a-z]{1,4}\d+[a-z]?$", token):
        return True

    # Edge/profile codes like 4A10 should not drive material matching either.
    if re.match(r"^\d+[a-z]\d+$", token):
        return True

    return False


def _extract_components(text: str, procesos: dict[str, bool]) -> tuple[str, ...]:
    components: set[str] = set()
    for component, patterns in _COMPONENT_PATTERNS:
        if any(re.search(pattern, text) for pattern in patterns):
            components.add(component)

    if any(re.search(pattern, text) for pattern in _OPACIFICADO_PARCIAL_PATTERNS):
        components.discard("opacificado_total")
        components.add("opacificado_perimetral")

    if has_structural_offset_camera_text(text):
        components.discard("camara_12_estructural")

    for field, active in procesos.items():
        if active:
            components.add(f"proceso:{field}")

    # Keep meaningful residual terms so unknown compositions still get a stable key.
    for token in re.findall(r"\b[a-z0-9]{3,}\b", text):
        if _is_noise_token(token) or re.match(r"^\d+$", token):
            continue
        components.add(f"term:{token}")

    return tuple(sorted(components))


def _material_components(components: Sequence[str]) -> set[str]:
    return {component for component in components if component in _MATERIAL_COMPONENTS}


def _format_components(components: Sequence[str]) -> str:
    if not components:
        return "sin componente canonico"
    return ", ".join(_COMPONENT_LABELS.get(component, component) for component in components)


def _material_change_warning(
    acopio_comp: ComposicionNormalizada,
    pedido_comp: ComposicionNormalizada,
) -> str | None:
    acopio_material = _material_components(acopio_comp.componentes)
    pedido_material = _material_components(pedido_comp.componentes)
    removed = tuple(sorted(acopio_material - pedido_material))
    added = tuple(sorted(pedido_material - acopio_material))
    if not removed and not added:
        return None

    return (
        "Evento de cambio de material detectado: contratado "
        f"{_format_components(removed)}; pedido {_format_components(added)}."
    )


def normalizar_composicion(texts: Iterable[object]) -> ComposicionNormalizada:
    """Build a canonical, order-independent composition signature."""
    original_text = _joined_text(texts)
    text = _canonical_text([original_text])
    procesos = infer_item_processes_from_texts([text])
    components = _extract_components(text, procesos)
    return ComposicionNormalizada(
        texto_normalizado=text,
        componentes=components,
        procesos=procesos,
        firma="|".join(components),
    )


def normalizar_item_acopio(item) -> ComposicionNormalizada:
    return normalizar_composicion([
        item.descripcion,
        item.material,
        item.tipologia,
        *(pano.denominacion for pano in item.panos),
        *(adicional.descripcion for adicional in item.adicionales),
    ])


def composicion_desde_payload(payload: dict) -> ComposicionNormalizada:
    """Rebuild a normalized composition received from an integration payload."""
    composicion = payload.get("composicion") if payload else None
    if not composicion:
        return normalizar_composicion([payload.get("descripcion") if payload else ""])

    procesos = {
        field: bool((composicion.get("procesos") or {}).get(field))
        for field in PROCESS_FIELDS
    }
    componentes = tuple(sorted(composicion.get("componentes") or []))
    firma = composicion.get("firma") or "|".join(componentes)
    return ComposicionNormalizada(
        texto_normalizado=composicion.get("normalizada") or "",
        componentes=componentes,
        procesos=procesos,
        firma=firma,
    )


def preview_match_items(acopio_items: Iterable[object], pedido_items: Iterable[dict]) -> list[dict]:
    """Return item-level composition match diagnostics for a pedido."""
    result = []
    for pedido_item in pedido_items:
        pedido_comp = composicion_desde_payload(pedido_item)
        match = encontrar_item_por_composicion(acopio_items, pedido_comp)
        result.append({
            "pedido_item_id": pedido_item.get("id"),
            "pedido_item_descripcion": pedido_item.get("descripcion"),
            "acopio_item_id": match.item.id if match.item else None,
            "acopio_item_descripcion": match.item.descripcion if match.item else None,
            "estado": match.estado,
            "score": float(match.score),
            "advertencia": match.advertencia,
            "diferencias_procesos": list(match.diferencias_procesos),
        })
    return result


def _jaccard(left: Sequence[str], right: Sequence[str]) -> Decimal:
    left_set = set(left)
    right_set = set(right)
    if not left_set and not right_set:
        return Decimal("1")
    union = left_set | right_set
    if not union:
        return Decimal("0")
    return Decimal(len(left_set & right_set)) / Decimal(len(union))


def _process_differences(left: dict[str, bool], right: dict[str, bool]) -> tuple[str, ...]:
    return tuple(
        field
        for field in PROCESS_FIELDS
        if bool(left.get(field)) != bool(right.get(field))
    )


def comparar_composiciones(
    acopio_comp: ComposicionNormalizada,
    pedido_comp: ComposicionNormalizada,
) -> tuple[Decimal, tuple[str, ...]]:
    component_score = _jaccard(acopio_comp.componentes, pedido_comp.componentes)
    process_diffs = _process_differences(acopio_comp.procesos, pedido_comp.procesos)
    process_score = (
        Decimal(len(PROCESS_FIELDS) - len(process_diffs))
        / Decimal(len(PROCESS_FIELDS))
    )
    score = (component_score * Decimal("0.55")) + (process_score * Decimal("0.45"))
    return score.quantize(Decimal("0.0001")), process_diffs


def encontrar_item_por_composicion(items: Iterable[object], pedido_comp: ComposicionNormalizada) -> ComposicionMatch:
    """Find the acopio item that best matches a pedido item by composition."""
    best_item = None
    best_score = Decimal("-1")
    best_diffs: tuple[str, ...] = ()
    best_comp: ComposicionNormalizada | None = None
    best_exact = False
    best_key: tuple[int, int, int, Decimal] | None = None

    for item in items:
        acopio_comp = normalizar_item_acopio(item)
        score, diffs = comparar_composiciones(acopio_comp, pedido_comp)
        exact = False
        if acopio_comp.firma == pedido_comp.firma:
            score = Decimal("1.0000")
            diffs = ()
            exact = True

        candidate_key = (
            1 if exact else 0,
            1 if not diffs and score >= Decimal("0.6500") else 0,
            -len(diffs),
            score,
        )

        if best_key is None or candidate_key > best_key:
            best_item = item
            best_score = score
            best_diffs = diffs
            best_comp = acopio_comp
            best_exact = exact
            best_key = candidate_key

    if best_item is None or best_score < Decimal("0.4500"):
        return ComposicionMatch(
            item=None,
            estado=MATCH_NONE,
            score=Decimal("0"),
            advertencia="No se encontro un item del acopio con composicion compatible.",
            diferencias_procesos=(),
        )

    material_warning = (
        _material_change_warning(best_comp, pedido_comp)
        if best_comp is not None else None
    )

    if material_warning and not best_diffs and best_score >= Decimal("0.6500"):
        return ComposicionMatch(
            item=best_item,
            estado=MATCH_CHANGED,
            score=best_score,
            advertencia=material_warning,
            diferencias_procesos=(),
        )

    if best_exact or (best_score >= Decimal("0.9000") and not best_diffs):
        return ComposicionMatch(
            item=best_item,
            estado=MATCH_EXACT,
            score=best_score,
            advertencia=None,
            diferencias_procesos=(),
        )

    if not best_diffs and best_score >= Decimal("0.7000"):
        return ComposicionMatch(
            item=best_item,
            estado=MATCH_EQUIVALENT,
            score=best_score,
            advertencia=None,
            diferencias_procesos=(),
        )

    if material_warning and best_score >= Decimal("0.6500"):
        warning = material_warning
        if best_diffs:
            warning += f" Diferencias de procesos: {', '.join(best_diffs)}."
        return ComposicionMatch(
            item=best_item,
            estado=MATCH_CHANGED,
            score=best_score,
            advertencia=warning,
            diferencias_procesos=best_diffs,
        )

    if best_diffs:
        warning = (
            "La composicion del pedido difiere de la composicion del acopio "
            f"en: {', '.join(best_diffs)}."
        )
    else:
        warning = (
            "La composicion del pedido difiere de la composicion del acopio "
            "en los componentes de material."
        )
    return ComposicionMatch(
        item=best_item,
        estado=MATCH_CHANGED,
        score=best_score,
        advertencia=warning,
        diferencias_procesos=best_diffs,
    )
