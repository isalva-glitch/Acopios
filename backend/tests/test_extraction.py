"""Tests for PDF extraction — original + expanded suite."""
import pytest
from pathlib import Path
from decimal import Decimal

from extraction import extract_standard_budget_pdf
from extraction.validator import validate_against_schema
from extraction.pdf_parser import (
    extract_pages,
    parse_header,
    parse_general_totals,
    parse_consolidated,
    parse_detailed,
)

# ─────────────────────────────────────────────────────────────────────────────
# Fixture paths
# ─────────────────────────────────────────────────────────────────────────────

FIXTURES = Path(__file__).parent / "fixtures"
PDF_FIXTURE   = FIXTURES / "budget_fixture.pdf"    # same as sample.pdf (#000208195)
PDF_208195    = FIXTURES / "budget_208195.pdf"      # #000208195 EDILIZIA / ROSFAR VIDRIOS
PDF_212248    = FIXTURES / "budget_212248.pdf"      # #000212248 Ing. Rinaldi / OBRA ESPAÑA 257


def _skip_if_missing(path: Path):
    return pytest.mark.skipif(not path.exists(), reason=f"Fixture not found: {path.name}")


# ─────────────────────────────────────────────────────────────────────────────
# Original tests (kept intact)
# ─────────────────────────────────────────────────────────────────────────────

@_skip_if_missing(PDF_FIXTURE)
def test_extract_standard_pdf():
    """Package structure is present."""
    package = extract_standard_budget_pdf(str(PDF_FIXTURE))
    assert "meta"          in package
    assert "acopio"        in package
    assert "presupuestos"  in package
    assert "items"         in package
    assert "panos"         in package
    assert "warnings"      in package
    assert package["meta"]["pdf_filename"] is not None
    assert package["meta"]["pdf_hash"]     is not None
    assert package["acopio"]["cliente"]    != ""
    assert "obra" in package["acopio"]


@_skip_if_missing(PDF_FIXTURE)
def test_extraction_validates_against_schema():
    """Extracted package validates against JSON schema."""
    package = extract_standard_budget_pdf(str(PDF_FIXTURE))
    is_valid, errors = validate_against_schema(package)
    assert is_valid, f"Schema validation failed: {errors}"


@_skip_if_missing(PDF_FIXTURE)
def test_extraction_totals():
    """Totals exist, are numeric, and non-negative."""
    package = extract_standard_budget_pdf(str(PDF_FIXTURE))
    acopio = package["acopio"]
    for field in ("total_m2", "total_ml", "total_pesos"):
        assert field in acopio
        assert isinstance(acopio[field], (int, float, Decimal))
        assert acopio[field] >= 0


# ─────────────────────────────────────────────────────────────────────────────
# New: parse_header — per PDF
# ─────────────────────────────────────────────────────────────────────────────

@_skip_if_missing(PDF_208195)
def test_parse_header_208195():
    """#000208195 — cliente=EDILIZIA, obra=ROSFAR VIDRIOS."""
    pages = extract_pages(str(PDF_208195))
    h = parse_header(pages)
    assert "EDILIZIA" in h["cliente"].upper()
    assert "ROSFAR" in h["obra"].upper() or "VIDRIOS" in h["obra"].upper()
    assert h["presupuesto_numero"] == "000208195"


@_skip_if_missing(PDF_212248)
def test_parse_header_212248():
    """#000212248 — cliente=Ing. Rinaldi, obra contains ESPAÑA/257."""
    pages = extract_pages(str(PDF_212248))
    h = parse_header(pages)
    assert "RINALDI" in h["cliente"].upper() or "ING" in h["cliente"].upper()
    assert "ESPAÑA" in h["obra"].upper() or "257" in h["obra"]
    assert h["presupuesto_numero"] == "000212248"


@_skip_if_missing(PDF_208195)
def test_parse_header_no_null_fields():
    """Header never returns None values — always strings."""
    pages = extract_pages(str(PDF_208195))
    h = parse_header(pages)
    for key, val in h.items():
        assert val is not None, f"Field '{key}' is None"
        assert isinstance(val, str), f"Field '{key}' is not str"


# ─────────────────────────────────────────────────────────────────────────────
# New: parse_general_totals
# ─────────────────────────────────────────────────────────────────────────────

@_skip_if_missing(PDF_208195)
def test_parse_totals_208195():
    """#000208195 — m2=112.27, ml=370.86."""
    pages = extract_pages(str(PDF_208195))
    t = parse_general_totals(pages)
    m2    = float(str(t["m2"]).replace(",", "."))
    ml    = float(str(t["ml"]).replace(",", "."))
    assert abs(m2  - 112.27) < 1.0, f"m2 mismatch: {m2}"
    assert abs(ml  - 370.86) < 1.0, f"ml mismatch: {ml}"


@_skip_if_missing(PDF_212248)
def test_parse_totals_212248():
    """#000212248 — m2=101.47, ml=325.6."""
    pages = extract_pages(str(PDF_212248))
    t = parse_general_totals(pages)
    m2 = float(str(t["m2"]).replace(",", "."))
    ml = float(str(t["ml"]).replace(",", "."))
    assert abs(m2 - 101.47) < 1.0, f"m2 mismatch: {m2}"
    assert abs(ml - 325.6)  < 1.0, f"ml mismatch: {ml}"


# ─────────────────────────────────────────────────────────────────────────────
# New: parse_consolidated — item count
# ─────────────────────────────────────────────────────────────────────────────

@_skip_if_missing(PDF_208195)
def test_parse_consolidated_item_count_208195():
    """#000208195 has 4 items in consolidated table."""
    pages = extract_pages(str(PDF_208195))
    items = parse_consolidated(pages)
    assert len(items) == 4, f"Expected 4 items, got {len(items)}"


@_skip_if_missing(PDF_212248)
def test_parse_consolidated_item_count_212248():
    """#000212248 has 1 item in consolidated table."""
    pages = extract_pages(str(PDF_212248))
    items = parse_consolidated(pages)
    assert len(items) == 1, f"Expected 1 item, got {len(items)}"


@_skip_if_missing(PDF_208195)
def test_parse_consolidated_item_fields():
    """Consolidated items have required fields and non-empty descripcion."""
    pages = extract_pages(str(PDF_208195))
    items = parse_consolidated(pages)
    assert items, "No items extracted"
    for item in items:
        assert "descripcion" in item
        assert item["descripcion"], "Empty descripcion in item"
        assert "cantidad"    in item
        assert "total_pesos" in item


# ─────────────────────────────────────────────────────────────────────────────
# New: parse_detailed — paño count and item assignment
# ─────────────────────────────────────────────────────────────────────────────

@_skip_if_missing(PDF_208195)
def test_parse_detailed_pano_count_208195():
    """#000208195 — 74 total paños across all items."""
    pages = extract_pages(str(PDF_208195))
    panos = parse_detailed(pages)
    total = sum(p["cantidad"] for p in panos)
    assert total == 74, f"Expected 74 paños, got {total}"


@_skip_if_missing(PDF_212248)
def test_parse_detailed_pano_count_212248():
    """#000212248 — 54 paños (1 item)."""
    pages = extract_pages(str(PDF_212248))
    panos = parse_detailed(pages)
    total = sum(p["cantidad"] for p in panos)
    assert total == 54, f"Expected 54 paños, got {total}"


@_skip_if_missing(PDF_208195)
def test_state_machine_item_assignment():
    """State machine assigns paños to correct item_index."""
    pages = extract_pages(str(PDF_208195))
    panos = parse_detailed(pages)

    # item 1: 15 paños, item 2: 37, item 3: 18, item 4: 4
    expected = {1: 15, 2: 37, 3: 18, 4: 4}
    for item_idx, expected_qty in expected.items():
        item_panos = [p for p in panos if p.get("item_index") == item_idx]
        actual_qty = sum(p["cantidad"] for p in item_panos)
        assert actual_qty == expected_qty, (
            f"Item {item_idx}: expected {expected_qty} paños, got {actual_qty}"
        )


# ─────────────────────────────────────────────────────────────────────────────
# New: null-tolerance — extraction never raises on valid PDFs
# ─────────────────────────────────────────────────────────────────────────────

@_skip_if_missing(PDF_208195)
def test_null_tolerant_extraction_208195():
    """extract_standard_budget_pdf does not raise and returns a package."""
    package = extract_standard_budget_pdf(str(PDF_208195))
    assert package is not None
    assert isinstance(package, dict)
    # All optional string fields tolerate empty string (not None)
    acopio = package["acopio"]
    for field in ("obra", "cliente", "numero"):
        assert acopio.get(field) is not None, f"acopio.{field} is None"


@_skip_if_missing(PDF_212248)
def test_null_tolerant_extraction_212248():
    """extract_standard_budget_pdf does not raise on #000212248."""
    package = extract_standard_budget_pdf(str(PDF_212248))
    assert package is not None
    assert isinstance(package, dict)
    acopio = package["acopio"]
    for field in ("obra", "cliente", "numero"):
        assert acopio.get(field) is not None, f"acopio.{field} is None"
