"""Interpret item details and infer reference-price process flags."""
import re
import unicodedata
from typing import Iterable, Mapping


PROCESS_FIELDS = (
    "vidrio_exterior",
    "vidrio_interior",
    "camara_estructural",
    "pulido",
    "fason_templado_exterior",
    "pegado_bastidor",
    "camara_normal",
    "opacificado_perimetral",
    "opacificado_total",
    "camara_offset",
)

PROCESS_UNITS = {
    "vidrio_exterior": "m2",
    "vidrio_interior": "m2",
    "camara_estructural": "ml",
    "pulido": "ml",
    "fason_templado_exterior": "m2",
    "pegado_bastidor": "ml",
    "camara_normal": "ml",
    "opacificado_perimetral": "ml",
    "opacificado_total": "m2",
    "camara_offset": "ml",
}

_PROCESS_PATTERNS: Mapping[str, tuple[str, ...]] = {
    "vidrio_exterior": (
        r"\bvidrio\s+ext(?:erior)?\b",
        r"\bvidrio\s+exterior\b",
        r"\bvid\s+ext(?:erior)?\b",
        r"\bv\s+ext(?:erior)?\b",
        r"\beclipse\b",
        r"\beclip\b",
    ),
    "vidrio_interior": (
        r"\bvidrio\s+int(?:erior)?\b",
        r"\bvidrio\s+interior\b",
        r"\bvid\s+int(?:erior)?\b",
        r"\bv\s+int(?:erior)?\b",
        r"\blam\s+3\s+3\b",
        r"\blaminado\s+3\s+3\b",
    ),
    "camara_estructural": (
        r"\bcamara\s+estructural(?!\s+offset)\b",
        r"\bcamara\s+extructural(?!\s+offset)\b",
        r"\bcamara\s+\d+\s+(?:mm\s+)?estructural(?!\s+offset)\b",
        r"\bcamara\s+\d+\s+(?:mm\s+)?extructural(?!\s+offset)\b",
        r"\bsellado\s+estructural\b",
        r"\bsellado\s+extructural\b",
        r"\bsilicona\s+estructural\b",
        r"\bsilicona\s+extructural\b",
    ),
    "pulido": (
        r"\bpulido\b",
        r"\bpulidos\b",
        r"\bpulir\b",
        r"\bcanto\s+pulido\b",
        r"\bbordes\s+pulidos\b",
        r"\bbp\b",
        r"\bbpsb\b",
    ),
    "fason_templado_exterior": (
        r"\bfason\s+templado\s+exterior\b",
        r"\bfason\s+templado\b",
        r"\bfason\s+temp\b",
        r"\bfason\s+ext(?:erior)?\b",
        r"\btemplad[oa]s?\b",
        r"\btemp\b",
        r"\btem\b",
    ),
    "pegado_bastidor": (
        r"\bpegad[oa]\s+(?:a\s+)?bastidor\b",
        r"\bpegad[oa]\s+estructural\b",
        r"\bpegad[oa]\s+extructural\b",
        r"\bbastidor\b",
    ),
    "opacificado_perimetral": (
        r"\bopacificado\s+perimetral\b",
        r"\bopacado\s+perimetral\b",
        r"\bopac(?:if)?\s+perimetral\b",
        r"\bserigraf(?:ia|iado)\s+perimetral\b",
        r"\bopacificado\b.*\bbandas?\b",
        r"\bopacificado\b.*\bparcial(?:es)?\b",
        r"\bopacado\b.*\bbandas?\b",
        r"\bopacado\b.*\bparcial(?:es)?\b",
    ),
    "opacificado_total": (
        r"\bopacificado\s+total\b",
        r"\bopacado\s+total\b",
        r"\bopac(?:if)?\s+total\b",
        r"\bserigraf(?:ia|iado)\s+total\b",
    ),
    "camara_offset": (
        r"\bcamara\s+offset\b",
        r"\boffset\b",
    ),
}

_DVH_PATTERNS = (
    r"\bdvh\b",
    r"\bdoble\s+vidriado\b",
    r"\bdoble\s+vidrio\b",
)

_CAMARA_NORMAL_EXPLICIT_PATTERNS = (
    r"\bcamara\s+normal\b",
)

_CAMARA_NORMAL_GENERIC_PATTERNS = (
    r"\bcamara\b",
    *_DVH_PATTERNS,
)

_STRUCTURAL_OFFSET_CAMERA_PATTERNS = (
    r"\bcamara\s+(?:\d+\s+(?:mm\s+)?)?estructural\s+offset\b",
    r"\bcamara\s+(?:\d+\s+(?:mm\s+)?)?extructural\s+offset\b",
)


def normalize_process_text(value: object) -> str:
    if value is None:
        return ""

    text = str(value)
    text = unicodedata.normalize("NFKD", text)
    text = "".join(char for char in text if not unicodedata.combining(char))
    text = text.lower()
    text = re.sub(r"[^a-z0-9]+", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def has_structural_offset_camera_text(value: object) -> bool:
    """Return true when a camera is described as the Offset variant."""
    normalized = normalize_process_text(value)
    return any(
        re.search(pattern, normalized)
        for pattern in _STRUCTURAL_OFFSET_CAMERA_PATTERNS
    )


def infer_item_processes_from_texts(texts: Iterable[object]) -> dict:
    normalized = normalize_process_text(" ".join(str(text or "") for text in texts))
    inferred = {field: False for field in PROCESS_FIELDS}

    for field, patterns in _PROCESS_PATTERNS.items():
        inferred[field] = any(re.search(pattern, normalized) for pattern in patterns)

    has_dvh = any(
        re.search(pattern, normalized)
        for pattern in _DVH_PATTERNS
    )
    if has_dvh:
        inferred["vidrio_exterior"] = True
        inferred["vidrio_interior"] = True

    has_explicit_normal_camera = any(
        re.search(pattern, normalized)
        for pattern in _CAMARA_NORMAL_EXPLICIT_PATTERNS
    )
    has_generic_normal_camera = any(
        re.search(pattern, normalized)
        for pattern in _CAMARA_NORMAL_GENERIC_PATTERNS
    )
    inferred["camara_normal"] = (
        has_explicit_normal_camera
        or (
            has_generic_normal_camera
            and not inferred["camara_estructural"]
            and not inferred["camara_offset"]
        )
    )

    has_generic_opacificado = any(
        re.search(pattern, normalized)
        for pattern in (
            r"\bopacificado\b",
            r"\bopacado\b",
            r"\bopac\b",
            r"\bserigraf(?:ia|iado)\b",
        )
    )
    if has_generic_opacificado and not inferred["opacificado_perimetral"]:
        inferred["opacificado_total"] = True

    # Vidrio monolítico: sin vidrio interior/exterior explícito, sin DVH, sin cámara
    # y sin laminado → asignar vidrio_interior=True por defecto para contabilizar m².
    # Ejemplo: "Mirage 5 mm. Incoloro con Borde Pulido" → vidrio_interior=True
    has_laminado = bool(re.search(r"\blam(?:inado)?\s*\d", normalized))
    is_monolitico = (
        not inferred["vidrio_interior"]
        and not inferred["vidrio_exterior"]
        and not has_dvh
        and not inferred["camara_normal"]
        and not inferred["camara_estructural"]
        and not inferred["camara_offset"]
        and not has_laminado
    )
    if is_monolitico:
        inferred["vidrio_interior"] = True

    return inferred


def infer_normalized_item_processes(item) -> dict:
    texts = [
        item.descripcion,
        item.material,
        item.tipologia,
        *(pano.denominacion for pano in item.panos),
        *(adicional.descripcion for adicional in item.adicionales),
    ]
    return infer_item_processes_from_texts(texts)
