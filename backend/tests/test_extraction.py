"""Tests for PDF extraction."""
import pytest
from pathlib import Path
from decimal import Decimal
from extraction import extract_standard_budget_pdf
from extraction.validator import validate_against_schema


# Path to fixture PDFs
FIXTURES_PATH = Path(__file__).parent / "fixtures" / "budget_fixture.pdf"


@pytest.mark.skipif(not FIXTURES_PATH.exists(), reason="Fixture PDF not found")
def test_extract_standard_pdf():
    """Test extraction of standard PDF."""
    package = extract_standard_budget_pdf(str(FIXTURES_PATH))
    
    # Verify package structure
    assert "meta" in package
    assert "acopio" in package
    assert "presupuestos" in package
    assert "items" in package
    assert "panos" in package
    assert "warnings" in package
    
    # Verify meta
    assert package["meta"]["pdf_filename"] is not None
    assert package["meta"]["pdf_hash"] is not None
    
    # Verify acopio
    assert package["acopio"]["cliente"] != ""
    assert "obra" in package["acopio"]


@pytest.mark.skipif(not FIXTURES_PATH.exists(), reason="Fixture PDF not found")
def test_extraction_validates_against_schema():
    """Test that extracted package validates against JSON schema."""
    package = extract_standard_budget_pdf(str(FIXTURES_PATH))
    
    is_valid, errors = validate_against_schema(package)
    
    if not is_valid:
        print("Validation errors:", errors)
    
    assert is_valid, f"Package validation failed: {errors}"


@pytest.mark.skipif(not FIXTURES_PATH.exists(), reason="Fixture PDF not found")
def test_extraction_totals():
    """Test that totals are calculated correctly."""
    package = extract_standard_budget_pdf(str(FIXTURES_PATH))
    
    # Check that totals exist
    assert "total_m2" in package["acopio"]
    assert "total_ml" in package["acopio"]
    assert "total_pesos" in package["acopio"]
    
    # Totals should be numeric
    assert isinstance(package["acopio"]["total_m2"], (int, float, Decimal))
    assert isinstance(package["acopio"]["total_ml"], (int, float, Decimal))
    assert isinstance(package["acopio"]["total_pesos"], (int, float, Decimal))
    
    # Totals should be non-negative
    assert package["acopio"]["total_m2"] >= 0
    assert package["acopio"]["total_ml"] >= 0
    assert package["acopio"]["total_pesos"] >= 0
