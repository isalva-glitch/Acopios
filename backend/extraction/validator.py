"""Validation functions for extracted data."""
from typing import Dict, Any, List
from decimal import Decimal
import jsonschema
import json
from pathlib import Path
from extraction.helpers import calculate_m2, calculate_perimeter_ml, is_within_tolerance
from config import settings


def load_json_schema() -> dict:
    """Load the JSON schema for validation."""
    schema_path = Path(__file__).parent.parent / "schemas" / "acopio_package_schema.json"
    with open(schema_path, "r", encoding="utf-8") as f:
        return json.load(f)


def validate_against_schema(package: dict) -> tuple[bool, List[str]]:
    """
    Validate package against JSON Schema.
    
    Returns:
        (is_valid, error_messages)
    """
    try:
        schema = load_json_schema()
        jsonschema.validate(instance=package, schema=schema)
        return True, []
    except jsonschema.exceptions.ValidationError as e:
        return False, [str(e)]
    except Exception as e:
        return False, [f"Schema validation error: {str(e)}"]


def validate_pano_calculations(
    pano: Dict[str, Any],
    warnings: List[Dict[str, Any]]
) -> None:
    """
    Validate paño calculations (m2 and ml).
    
    Adds warnings if calculations don't match within tolerance.
    """
    ancho = Decimal(str(pano["ancho"]))
    alto = Decimal(str(pano["alto"]))
    cantidad = Decimal(str(pano.get("cantidad", 1)))
    superficie_declared = Decimal(str(pano["superficie_m2"]))
    perimetro_declared = Decimal(str(pano["perimetro_ml"]))
    
    # Calculate expected values (helpers now convert mm to m)
    # Area = (width * height / 1M) * quantity
    superficie_calculated = calculate_m2(ancho, alto) * cantidad
    
    # Perimeter = (2 * (width + height) / 1000) * quantity
    perimetro_calculated = calculate_perimeter_ml(ancho, alto) * cantidad
    
    # Check m2
    if not is_within_tolerance(superficie_declared, superficie_calculated, settings.pdf_tolerance_percentage):
        warnings.append({
            "level": "WARNING",
            "message": f"Superficie m2 no coincide para paño {ancho}x{alto} (cant: {cantidad})",
            "field": "superficie_m2",
            "expected": float(superficie_calculated),
            "actual": float(superficie_declared),
            "tolerance": settings.pdf_tolerance_percentage
        })
    
    # Check ml
    if not is_within_tolerance(perimetro_declared, perimetro_calculated, settings.pdf_tolerance_percentage):
        warnings.append({
            "level": "WARNING",
            "message": f"Perímetro ml no coincide para paño {ancho}x{alto} (cant: {cantidad})",
            "field": "perimetro_ml",
            "expected": float(perimetro_calculated),
            "actual": float(perimetro_declared),
            "tolerance": settings.pdf_tolerance_percentage
        })


def validate_item_totals(
    item: Dict[str, Any],
    panos: List[Dict[str, Any]],
    item_index: int,
    warnings: List[Dict[str, Any]]
) -> None:
    """
    Validate item totals against sum of paños.
    
    Adds warnings if totals don't match within tolerance.
    """
    # Get paños for this item
    item_panos = [p for p in panos if p.get("item_index") == item_index]
    
    if not item_panos:
        return
    
    # Calculate sums from paños
    sum_m2 = sum(Decimal(str(p["superficie_m2"])) for p in item_panos)
    sum_ml = sum(Decimal(str(p["perimetro_ml"])) for p in item_panos)
    sum_pesos = sum(Decimal(str(p["precio_total"])) for p in item_panos)
    
    # Get declared totals
    item_m2 = Decimal(str(item["total_m2"]))
    item_ml = Decimal(str(item["total_ml"]))
    item_pesos = Decimal(str(item["total_pesos"]))
    
    # Validate m2
    if not is_within_tolerance(item_m2, sum_m2, settings.pdf_tolerance_percentage):
        warnings.append({
            "level": "WARNING",
            "message": f"Total m2 del item '{item['descripcion']}' no coincide con suma de paños",
            "field": "total_m2",
            "expected": float(sum_m2),
            "actual": float(item_m2),
            "tolerance": settings.pdf_tolerance_percentage
        })
    
    # Validate ml
    if not is_within_tolerance(item_ml, sum_ml, settings.pdf_tolerance_percentage):
        warnings.append({
            "level": "WARNING",
            "message": f"Total ml del item '{item['descripcion']}' no coincide con suma de paños",
            "field": "total_ml",
            "expected": float(sum_ml),
            "actual": float(item_ml),
            "tolerance": settings.pdf_tolerance_percentage
        })
    
    # Validate pesos
    if not is_within_tolerance(item_pesos, sum_pesos, settings.pdf_tolerance_percentage):
        warnings.append({
            "level": "WARNING",
            "message": f"Total pesos del item '{item['descripcion']}' no coincide con suma de paños",
            "field": "total_pesos",
            "expected": float(sum_pesos),
            "actual": float(item_pesos),
            "tolerance": settings.pdf_tolerance_percentage
        })


def validate_acopio_totals(
    acopio: Dict[str, Any],
    items: List[Dict[str, Any]],
    warnings: List[Dict[str, Any]]
) -> None:
    """
    Validate acopio totals against sum of items.
    
    Adds warnings if totals don't match within tolerance.
    """
    # Calculate sums from items
    sum_m2 = sum(Decimal(str(item["total_m2"])) for item in items)
    sum_ml = sum(Decimal(str(item["total_ml"])) for item in items)
    sum_pesos = sum(Decimal(str(item["total_pesos"])) for item in items)
    
    # Get declared totals
    acopio_m2 = Decimal(str(acopio.get("total_m2", 0)))
    acopio_ml = Decimal(str(acopio.get("total_ml", 0)))
    acopio_pesos = Decimal(str(acopio.get("total_pesos", 0)))
    
    # Validate m2
    if not is_within_tolerance(acopio_m2, sum_m2, settings.pdf_tolerance_percentage):
        warnings.append({
            "level": "ERROR",
            "message": "Total m2 del acopio no coincide con suma de items",
            "field": "total_m2",
            "expected": float(sum_m2),
            "actual": float(acopio_m2),
            "tolerance": settings.pdf_tolerance_percentage
        })
    
    # Validate ml
    if not is_within_tolerance(acopio_ml, sum_ml, settings.pdf_tolerance_percentage):
        warnings.append({
            "level": "ERROR",
            "message": "Total ml del acopio no coincide con suma de items",
            "field": "total_ml",
            "expected": float(sum_ml),
            "actual": float(acopio_ml),
            "tolerance": settings.pdf_tolerance_percentage
        })
    
    # Validate pesos
    if not is_within_tolerance(acopio_pesos, sum_pesos, settings.pdf_tolerance_percentage):
        warnings.append({
            "level": "ERROR",
            "message": "Total pesos del acopio no coincide con suma de items",
            "field": "total_pesos",
            "expected": float(sum_pesos),
            "actual": float(acopio_pesos),
            "tolerance": settings.pdf_tolerance_percentage
        })


def validate_package(package: dict) -> List[Dict[str, Any]]:
    """
    Validate entire package.
    
    Returns list of warnings.
    """
    warnings = []
    
    # Validate against JSON Schema
    is_valid, schema_errors = validate_against_schema(package)
    if not is_valid:
        for error in schema_errors:
            warnings.append({
                "level": "ERROR",
                "message": f"JSON Schema validation error: {error}",
                "field": "schema"
            })
        return warnings
    
    # Validate paño calculations
    for pano in package.get("panos", []):
        validate_pano_calculations(pano, warnings)
    
    # Validate item totals
    items = package.get("items", [])
    panos = package.get("panos", [])
    for idx, item in enumerate(items):
        validate_item_totals(item, panos, idx + 1, warnings)
    
    # Validate acopio totals
    acopio = package.get("acopio", {})
    validate_acopio_totals(acopio, items, warnings)
    
    return warnings
