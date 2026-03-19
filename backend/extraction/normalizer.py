"""Data normalization functions."""
from typing import Dict, Any, List
from decimal import Decimal
from datetime import datetime, date
from extraction.helpers import parse_spanish_number, clean_text
import re


def normalize_date(date_str: str) -> str:
    """
    Normalize date string to ISO format (YYYY-MM-DD).
    
    Supports formats:
    - DD/MM/YYYY
    - DD-MM-YYYY
    - YYYY-MM-DD
    """
    if not date_str:
        return datetime.now().strftime("%Y-%m-%d")
    
    date_str = clean_text(date_str)
    
    # Try different formats
    formats = [
        "%d/%m/%Y",
        "%d-%m-%Y",
        "%Y-%m-%d",
        "%d/%m/%y",
        "%d-%m-%y",
    ]
    
    for fmt in formats:
        try:
            dt = datetime.strptime(date_str, fmt)
            return dt.strftime("%Y-%m-%d")
        except ValueError:
            continue
    
    # If all fail, return current date
    return datetime.now().strftime("%Y-%m-%d")


def normalize_presupuesto_number(numero: str) -> str:
    """Normalize presupuesto number."""
    if not numero:
        return ""
    
    # Extract just the number part
    numero = clean_text(numero)
    # Remove common prefixes
    numero = re.sub(r"^(Pres\.|Presupuesto|#|Nº|N°|Num\.?)\s*", "", numero, flags=re.IGNORECASE)
    return numero.strip()


def normalize_item_row(row: Dict[str, Any]) -> Dict[str, Any]:
    """
    Normalize an item row from consolidated table.
    
    Expected columns: descripcion, material, tipologia, cantidad, m2, ml, total
    """
    normalized = {}
    
    # Clean text fields
    for field in ["descripcion", "material", "tipologia"]:
        normalized[field] = clean_text(row.get(field, ""))
    
    # Parse numeric fields
    normalized["cantidad"] = int(parse_spanish_number(row.get("cantidad", 0)))
    normalized["total_m2"] = parse_spanish_number(row.get("m2", 0))
    normalized["total_ml"] = parse_spanish_number(row.get("ml", 0))
    normalized["total_pesos"] = parse_spanish_number(row.get("total", 0))
    
    return normalized


def normalize_pano_row(row: Dict[str, Any], item_index: int) -> Dict[str, Any]:
    """
    Normalize a paño row from detailed table.
    
    Expected columns: cantidad, ancho, alto, superficie_m2, perimetro_ml, precio_unitario, precio_total
    """
    normalized = {
        "item_index": item_index
    }
    
    # Parse numeric fields
    normalized["cantidad"] = int(parse_spanish_number(row.get("cantidad", 1)))
    normalized["ancho"] = parse_spanish_number(row.get("ancho", 0))
    normalized["alto"] = parse_spanish_number(row.get("alto", 0))
    normalized["superficie_m2"] = parse_spanish_number(row.get("superficie", row.get("superficie_m2", 0)))
    normalized["perimetro_ml"] = parse_spanish_number(row.get("perimetro", row.get("perimetro_ml", 0)))
    normalized["precio_unitario"] = parse_spanish_number(row.get("precio_unitario", row.get("unitario", 0)))
    normalized["precio_total"] = parse_spanish_number(row.get("precio_total", row.get("total", 0)))
    
    return normalized


def normalize_totals(totals: Dict[str, Any]) -> Dict[str, Decimal]:
    """Normalize totals from PDF."""
    return {
        "total_m2": parse_spanish_number(totals.get("m2", totals.get("total_m2", 0))),
        "total_ml": parse_spanish_number(totals.get("ml", totals.get("total_ml", 0))),
        "total_pesos": parse_spanish_number(totals.get("pesos", totals.get("total", totals.get("total_pesos", 0)))),
    }
