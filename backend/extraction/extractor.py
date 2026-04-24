"""
Main PDF extraction module.

Public API (unchanged):
    extract_standard_budget_pdf(pdf_path)  -> package dict
    extract_with_pdfplumber(pdf_path)      -> intermediate dict

Internal helpers kept for backward compatibility but now delegate to pdf_parser.
"""
from typing import Dict, Any, List, Optional
from pathlib import Path
from datetime import datetime
import pdfplumber
import hashlib
import re
from decimal import Decimal

from extraction.helpers import clean_text, parse_spanish_number
from extraction.normalizer import (
    normalize_date,
    normalize_presupuesto_number,
    normalize_item_row,
    normalize_pano_row,
    normalize_totals,
)
from extraction.validator import validate_package
from extraction import pdf_parser
from extraction.pdf_parser import (
    PageData,
    extract_pages,
    parse_header,
    parse_general_totals,
    parse_consolidated,
    parse_detailed,
)


# ─────────────────────────────────────────────────────────────────────────────
# Backward-compat: raw data helper (used by tests / legacy callers)
# ─────────────────────────────────────────────────────────────────────────────

def extract_raw_data_from_pdf(pdf_path: str) -> Dict[str, Any]:
    """
    Backward-compatible helper.
    Returns the same shape as before: {text_lines, tables}.
    Internally delegates to pdf_parser.extract_pages.
    """
    pages = extract_pages(pdf_path)
    raw_data: Dict[str, Any] = {"text_lines": [], "tables": []}

    if pages:
        raw_data["text_lines"] = pages[0].text.split("\n") if pages[0].text else []

    for page in pages:
        for t_idx, table in enumerate(page.tables):
            raw_data["tables"].append({
                "page_idx": page.page_idx,
                "table_idx": t_idx,
                "data": table,
            })

    return raw_data


# ─────────────────────────────────────────────────────────────────────────────
# Core extraction pipeline
# ─────────────────────────────────────────────────────────────────────────────

def extract_with_pdfplumber(pdf_path: str) -> Dict[str, Any]:
    """
    Main extraction pipeline. Returns intermediate dict:
        {header, items, panos, totals}

    Now delegates each stage to pdf_parser functions.
    """
    pages = extract_pages(pdf_path)

    result = {
        "header": parse_header(pages),
        "items":  parse_consolidated(pages),
        "panos":  parse_detailed(pages),
        "totals": parse_general_totals(pages),
    }

    return result


# ─────────────────────────────────────────────────────────────────────────────
# Backward-compat thin wrappers (kept so existing imports don't break)
# ─────────────────────────────────────────────────────────────────────────────

def extract_header_from_text(
    text: str,
    raw_data: Optional[Dict[str, Any]] = None,
) -> Dict[str, str]:
    """
    Backward-compat wrapper.
    Rebuilds a minimal PageData from the text + optional raw_data tables
    and delegates to pdf_parser.parse_header.
    """
    tables: List[List[List[str]]] = []
    if raw_data:
        for t_info in raw_data.get("tables", []):
            if t_info.get("page_idx") == 0:
                tables.append(t_info["data"])

    page = PageData(page_idx=0, text=text, tables=tables)
    return parse_header([page])


def extract_items_from_table(table: List[List[str]]) -> List[Dict[str, Any]]:
    """Backward-compat: parse a single items table."""
    page = PageData(page_idx=0, text="", tables=[table])
    return parse_consolidated([page])


def extract_panos_from_table(
    table: List[List[str]],
    current_item_index: int = 1,
) -> List[Dict[str, Any]]:
    """
    Backward-compat: parse a single paños table.
    Wraps the table as if it were on page 1 so parse_detailed picks it up.
    """
    dummy_page0 = PageData(page_idx=0, text="", tables=[])
    dummy_page1 = PageData(page_idx=1, text="", tables=[table])
    panos = parse_detailed([dummy_page0, dummy_page1])
    # Override item_index if caller specified one
    if current_item_index != 1:
        for p in panos:
            p["item_index"] = current_item_index
    return panos


def extract_totals_from_text(text: str) -> Dict[str, str]:
    """Backward-compat: extract totals from raw text string."""
    page = PageData(page_idx=0, text=text)
    return parse_general_totals([page])


def extract_totals_from_tables(tables: List[List[List[str]]]) -> Dict[str, str]:
    """Backward-compat: scan a list of raw tables for totals."""
    page = PageData(page_idx=0, text="", tables=tables)
    return parse_general_totals([page])


# ─────────────────────────────────────────────────────────────────────────────
# Public entrypoint — unchanged signature
# ─────────────────────────────────────────────────────────────────────────────

def extract_standard_budget_pdf(pdf_path: str) -> Dict[str, Any]:
    """
    Main extraction function for standard budget PDFs.
    Returns a validated package ready for database insertion.
    Signature and output contract are unchanged.
    """
    with open(pdf_path, "rb") as f:
        file_hash = hashlib.sha256(f.read()).hexdigest()

    pdf_filename = Path(pdf_path).name

    try:
        extracted = extract_with_pdfplumber(pdf_path)
    except Exception as e:
        raise Exception(f"PDF extraction failed: {str(e)}")

    package: Dict[str, Any] = {
        "meta": {
            "extraction_date": datetime.utcnow().isoformat(),
            "pdf_filename": pdf_filename,
            "pdf_hash": file_hash,
            "extractor_version": "2.0.0",
        },
        "acopio": {
            "numero":      normalize_presupuesto_number(
                               extracted["header"].get("presupuesto_numero", "")),
            "fecha_alta":  normalize_date(extracted["header"].get("fecha", "")),
            "obra":        extracted["header"].get("obra", "") or "",
            "cliente":     extracted["header"].get("cliente", "") or "",
            **normalize_totals(extracted["totals"]),
        },
        "presupuestos": [
            {
                "numero":      normalize_presupuesto_number(
                                   extracted["header"].get("presupuesto_numero", "")),
                "fecha":       normalize_date(extracted["header"].get("fecha", "")),
                "condiciones": extracted["header"].get("condiciones", "") or "",
                "estado":      extracted["header"].get("estado", "") or "",
            }
        ],
        "items":               extracted["items"],
        "panos":               extracted["panos"],
        "pedidos":             [],
        "remitos":             [],
        "imputaciones":        [],
        "comprobantes":        [],
        "afectaciones_acopio": [],
        "documentos": [
            {
                "tipo_documento": "presupuesto_original",
                "nombre_archivo": pdf_filename,
                "hash":           file_hash,
            }
        ],
        "warnings": [],
    }

    # ── Sequential paño → item assignment ────────────────────────────────────
    # pdf_parser.parse_detailed already assigns item_index via the state
    # machine. The block below re-assigns sequentially based on item quantities
    # (to handle edge cases where state-machine item_index != consolidated order).
    current_pano_idx = 0
    total_panos = len(package["panos"])

    for idx, item in enumerate(package["items"]):
        target = idx + 1
        try:
            qty = int(item.get("cantidad", 0))
        except Exception:
            qty = 0

        assigned = 0
        while assigned < qty and current_pano_idx < total_panos:
            pano = package["panos"][current_pano_idx]
            pano["item_index"] = target
            assigned += int(pano.get("cantidad", 1))
            current_pano_idx += 1

    # ── Backfill totals from paños ────────────────────────────────────────────
    calc_m2 = Decimal("0")
    calc_ml = Decimal("0")
    calc_pesos = Decimal("0")

    for idx, item in enumerate(package["items"]):
        item_panos = [p for p in package["panos"] if p.get("item_index") == idx + 1]
        if item_panos:
            s_m2    = sum(Decimal(str(p["superficie_m2"])) for p in item_panos)
            s_ml    = sum(Decimal(str(p["perimetro_ml"]))  for p in item_panos)
            s_pesos = sum(Decimal(str(p["precio_total"]))  for p in item_panos)

            if Decimal(str(item.get("total_m2",    0))) == 0:
                item["total_m2"]    = float(s_m2)
            if Decimal(str(item.get("total_ml",    0))) == 0:
                item["total_ml"]    = float(s_ml)
            if Decimal(str(item.get("total_pesos", 0))) == 0:
                item["total_pesos"] = float(s_pesos)

            calc_m2    += s_m2
            calc_ml    += s_ml
            calc_pesos += s_pesos

    acopio = package["acopio"]
    if Decimal(str(acopio.get("total_m2",    0))) == 0:
        acopio["total_m2"]    = float(calc_m2)
    if Decimal(str(acopio.get("total_ml",    0))) == 0:
        acopio["total_ml"]    = float(calc_ml)
    if Decimal(str(acopio.get("total_pesos", 0))) == 0:
        acopio["total_pesos"] = float(calc_pesos)

    # ── Validation ────────────────────────────────────────────────────────────
    package["warnings"] = validate_package(package)

    return package
