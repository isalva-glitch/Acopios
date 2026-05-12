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
    ),
    "vidrio_interior": (
        r"\bvidrio\s+int(?:erior)?\b",
        r"\bvidrio\s+interior\b",
        r"\bvid\s+int(?:erior)?\b",
        r"\bv\s+int(?:erior)?\b",
    ),
    "camara_estructural": (
        r"\bcamara\s+estructural\b",
        r"\bsellado\s+estructural\b",
        r"\bsilicona\s+estructural\b",
    ),
    "pulido": (
        r"\bpulido\b",
        r"\bpulir\b",
        r"\bcanto\s+pulido\b",
    ),
    "fason_templado_exterior": (
        r"\bfason\s+templado\s+exterior\b",
        r"\bfason\s+templado\b",
        r"\bfason\s+temp\b",
        r"\bfason\s+ext(?:erior)?\b",
        r"\btemplad[oa]s?\b",
        r"\btemp\b",
    ),
    "pegado_bastidor": (
        r"\bpegad[oa]\s+(?:a\s+)?bastidor\b",
        r"\bbastidor\b",
    ),
    "opacificado_perimetral": (
        r"\bopacificado\s+perimetral\b",
        r"\bopacado\s+perimetral\b",
        r"\bopac(?:if)?\s+perimetral\b",
        r"\bserigraf(?:ia|iado)\s+perimetral\b",
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


def normalize_process_text(value: object) -> str:
    if value is None:
        return ""

    text = str(value)
    text = unicodedata.normalize("NFKD", text)
    text = "".join(char for char in text if not unicodedata.combining(char))
    text = text.lower()
    text = re.sub(r"[^a-z0-9]+", " ", text)
    return re.sub(r"\s+", " ", text).strip()


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
