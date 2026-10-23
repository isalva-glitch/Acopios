"""Normalize commercial number formats without treating a short number as a global identity."""
import re
from fastapi import HTTPException
from sqlalchemy import func
from models import Comprobante, TipoComprobante
from services import documentacion_service as docs


def number_query(number):
    raw = number.strip().upper()
    branch = re.fullmatch(r"([A-Z])?\s*(\d{1,5})\s*[-/]\s*(\d{1,8})", raw)
    if branch:
        letter, point, sequence = branch.groups()
        value = (letter or "") + point.zfill(5) + sequence.zfill(8)
        return {"numero_normalizado": value, "numero_modo": "COMPLETO" if letter else "SIN_LETRA"}
    value = re.sub(r"[\s.\-/]", "", raw)
    if re.fullmatch(r"\d{3,8}", value):
        return {"numero_normalizado": value.lstrip("0") or "000", "numero_modo": "SECUENCIA"}
    if re.fullmatch(r"[A-Z]\d{9,13}", value):
        return {"numero_normalizado": value[0] + value[1:-8].zfill(5) + value[-8:], "numero_modo": "COMPLETO"}
    if re.fullmatch(r"\d{9,13}", value):
        return {"numero_normalizado": value[:-8].zfill(5) + value[-8:], "numero_modo": "SIN_LETRA"}
    raise HTTPException(422, "Ingresá al menos tres dígitos, el número completo o punto de venta y número.")


def number_matches(source, query):
    try:
        candidate = number_query(source)
    except HTTPException:
        return False
    value = candidate["numero_normalizado"]
    requested = query["numero_normalizado"]
    if query["numero_modo"] == "SECUENCIA":
        return int(value[-8:]) == int(requested)
    if query["numero_modo"] == "SIN_LETRA":
        return value.lstrip("ABCDEFGHIJKLMNOPQRSTUVWXYZ").zfill(13) == requested
    return candidate["numero_modo"] == "COMPLETO" and value == requested


def local_matches(db, number):
    query = number_query(number)
    normalized = func.upper(Comprobante.numero)
    for char in (" ", "-", "/", "."):
        normalized = func.replace(normalized, char, "")
    # Use the sequence as a bounded SQL prefilter; then compare canonical formats.
    tail = query["numero_normalizado"][-8:].lstrip("0") or "0"
    rows = db.query(Comprobante).filter(Comprobante.tipo.in_([
        TipoComprobante.FAC_ANTICIPO, TipoComprobante.FAC_MERCADERIA, TipoComprobante.RECIBO]),
        normalized.contains(tail, autoescape=True)).order_by(Comprobante.id.desc()).limit(101).all()
    result = []
    for row in rows:
        if number_matches(row.numero, query):
            item = docs.serialize_comprobante(db, row)
            item["bloqueo"] = None
            result.append(item)
    return {"resultados": result[:20], "limitado": len(rows) > 100 or len(result) > 20}
