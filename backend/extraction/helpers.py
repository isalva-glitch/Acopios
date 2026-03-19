"""Helper functions for PDF extraction."""
import re
from typing import Any, Optional
from decimal import Decimal


def clean_text(text: Optional[str]) -> str:
    """Clean and normalize text."""
    if not text:
        return ""
    # Remove extra whitespace
    text = " ".join(text.split())
    return text.strip()


def extract_number_from_text(text: str, pattern: str = r"[\d.,]+") -> Optional[str]:
    """Extract first number from text."""
    match = re.search(pattern, text)
    if match:
        return match.group(0)
    return None


def parse_spanish_number(value: Any) -> Decimal:
    """
    Parse Spanish formatted number (12.345,67) to Decimal.
    
    Args:
        value: Number as string or float
        
    Returns:
        Decimal representation
    """
    if value is None or value == "":
        return Decimal("0")
    
    if isinstance(value, (int, float, Decimal)):
        return Decimal(str(value))
    
    # Convert to string and clean
    value_str = str(value).strip()
    
    # Remove currency symbols
    value_str = value_str.replace("$", "").replace("€", "").strip()
    
    # Spanish format: 12.345,67 -> 12345.67
    # Check if comma is decimal separator (Spanish format)
    if "," in value_str and "." in value_str:
        # Both present: dot is thousands separator
        value_str = value_str.replace(".", "")
        value_str = value_str.replace(",", ".")
    elif "," in value_str:
        # Only comma: it's decimal separator
        value_str = value_str.replace(",", ".")
    # else: only dot or neither - assume English format
    
    try:
        return Decimal(value_str)
    except:
        return Decimal("0")


def calculate_m2(ancho: Decimal, alto: Decimal) -> Decimal:
    """
    Calculate square meters from millimeters.
    
    Args:
        ancho: Width in mm
        alto: Height in mm
        
    Returns:
        Area in m2
    """
    return (ancho * alto) / Decimal("1000000")


def calculate_perimeter_ml(ancho: Decimal, alto: Decimal) -> Decimal:
    """
    Calculate perimeter in linear meters from millimeters.
    
    Args:
        ancho: Width in mm
        alto: Height in mm
        
    Returns:
        Perimeter in ml
    """
    return (Decimal("2") * (ancho + alto)) / Decimal("1000")


def is_within_tolerance(value1: Decimal, value2: Decimal, tolerance_percent: float = 0.5) -> bool:
    """
    Check if two values are within tolerance percentage.
    
    Args:
        value1: First value
        value2: Second value
        tolerance_percent: Tolerance percentage (default 0.5%)
        
    Returns:
        True if within tolerance
    """
    if value2 == 0:
        return value1 == 0
    
    diff_percent = abs((value1 - value2) / value2 * 100)
    return diff_percent <= Decimal(str(tolerance_percent))
