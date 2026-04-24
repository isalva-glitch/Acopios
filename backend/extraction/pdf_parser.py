"""
Modular PDF parsing for Fontela Cristales budget PDFs.

Public API:
    extract_pages(pdf_path)      -> List[PageData]
    parse_header(pages)          -> Dict
    parse_general_totals(pages)  -> Dict
    parse_consolidated(pages)    -> List[Dict]
    parse_detailed(pages)        -> List[Dict]
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

import pdfplumber

from extraction.helpers import clean_text, parse_spanish_number
from extraction.normalizer import normalize_item_row, normalize_pano_row


# ─────────────────────────────────────────────────────────────────────────────
# Data structure
# ─────────────────────────────────────────────────────────────────────────────

@dataclass
class PageData:
    """All extracted content for a single PDF page."""
    page_idx: int
    text: str
    words: List[Dict[str, Any]] = field(default_factory=list)
    tables: List[List[List[str]]] = field(default_factory=list)


# ─────────────────────────────────────────────────────────────────────────────
# Stage 1 — Raw extraction
# ─────────────────────────────────────────────────────────────────────────────

def extract_pages(pdf_path: str) -> List[PageData]:
    """
    Open the PDF and extract text, words and tables for every page.
    Never raises; returns [] on any failure.
    """
    pages: List[PageData] = []
    try:
        with pdfplumber.open(pdf_path) as pdf:
            for i, page in enumerate(pdf.pages):
                text = page.extract_text() or ""
                words = page.extract_words() or []
                raw_tables = page.extract_tables() or []
                clean_tables = [
                    [
                        [cell if cell is not None else "" for cell in row]
                        for row in t
                    ]
                    for t in raw_tables
                    if t
                ]
                pages.append(PageData(
                    page_idx=i,
                    text=text,
                    words=words,
                    tables=clean_tables,
                ))
    except Exception:
        pass
    return pages


# ─────────────────────────────────────────────────────────────────────────────
# Stage 2 — Header (page 0)
# ─────────────────────────────────────────────────────────────────────────────

def parse_header(pages: List[PageData]) -> Dict[str, str]:
    """
    Extract header fields from page 0.

    Strategy 1 (table-assisted):
        Locate the Contacto/Estado/Cotizado table on page 0.
        Use those values to strip noise from the Empresa text block, then
        split on '/' to obtain Cliente and Obra.

    Strategy 2 (regex fallback):
        Look for #NNNNNN, lines containing '/', or explicit Cliente: labels.

    All fields default to '' — never raises.
    """
    header: Dict[str, str] = {
        "cliente": "",
        "obra": "",
        "presupuesto_numero": "",
        "fecha": "",
        "condiciones": "",
        "estado": "",
    }
    if not pages:
        return header

    p0 = pages[0]
    lines = p0.text.split("\n") if p0.text else []

    # ── Presupuesto number & date ────────────────────────────────────────────
    for raw in lines:
        line = clean_text(raw)
        m = re.search(r"#(\d{6,})", line)
        if m:
            header["presupuesto_numero"] = m.group(1)
        if "fecha" in line.lower():
            m2 = re.search(r"(\d{1,2}[/-]\d{1,2}[/-]\d{2,4})", line)
            if m2:
                header["fecha"] = m2.group(1)

    if not header["presupuesto_numero"]:
        for raw in lines:
            m = re.search(
                r"(?:presupuesto|pedido)\s*n[º°:]\s*#?(\d{5,})",
                raw, re.IGNORECASE,
            )
            if m:
                header["presupuesto_numero"] = m.group(1)
                break

    # ── Table-assisted Cliente / Obra ────────────────────────────────────────
    contacto = estado = cotizado = ""
    for table in p0.tables:
        if not table or not table[0]:
            continue
        col_names = [str(h).lower().replace("\n", " ").strip() for h in table[0] if h]
        if "contacto" in col_names and "estado" in col_names and len(table) > 1:
            row = table[1]
            try:
                contacto = str(row[col_names.index("contacto")]).replace("\n", " ")
            except Exception:
                pass
            try:
                estado = str(row[col_names.index("estado")]).replace("\n", " ")
            except Exception:
                pass
            try:
                idx_cot = next(i for i, h in enumerate(col_names) if "cotizado" in h)
                cotizado = str(row[idx_cot]).replace("\n", " ")
            except Exception:
                pass
            break

    # Locate the text block: "Empresa … Contacto" header → "Presupuesto consolidado"
    start = end = -1
    for i, raw in enumerate(lines):
        lo = raw.lower()
        if "empresa" in lo and "contacto" in lo:
            start = i + 1
        if "presupuesto consolidado" in lo or "presupuesto detallado" in lo:
            end = i
            break

    if start != -1 and end != -1 and end > start:
        block = " ".join(lines[start:end])

        # Strip known noise phrases
        for phrase in [
            "por aprobación", "fecha de aprobación", "fecha de",
            "aprobación", "aprobacion",
        ]:
            block = re.sub(rf"(?i)\b{re.escape(phrase)}\b", "", block)

        # Strip dates
        block = re.sub(r"\b\d{1,2}[/-]\d{1,2}[/-]\d{2,4}\b", "", block)

        # Strip known column-value tokens
        for token in [estado, cotizado]:
            if token:
                block = re.sub(re.escape(token), "", block, flags=re.IGNORECASE)

        if contacto:
            for word in contacto.split():
                if len(word) > 2:
                    block = re.sub(
                        rf"\b{re.escape(word)}\b", "", block, flags=re.IGNORECASE
                    )

        block = re.sub(r"^\s*por\s+", "", block, flags=re.IGNORECASE)
        block = re.sub(r"\s+", " ", block).strip()

        if "/" in block:
            left, right = block.split("/", 1)
            header["cliente"] = left.strip()
            header["obra"] = right.strip()
        elif len(block) > 3:
            header["cliente"] = block

    # ── Regex fallback ───────────────────────────────────────────────────────
    if not header["cliente"]:
        for raw in lines:
            line_c = clean_text(raw)
            if (
                "/" in line_c
                and not re.search(r"\b\d{1,2}[/-]\d{1,2}[/-]\d{2,4}\b", line_c)
                and "http" not in line_c
            ):
                parts = line_c.split("/", 1)
                candidate = clean_text(parts[0])
                if not candidate.lower().startswith("cotizado") and len(candidate) > 3:
                    header["cliente"] = candidate
                    header["obra"] = clean_text(parts[1]) if len(parts) > 1 else ""
                    break

            if not header["cliente"]:
                m = re.search(r"(?:cliente|sr\.?):?\s*(.+)", line_c, re.IGNORECASE)
                if m:
                    header["cliente"] = clean_text(m.group(1))

            if not header["obra"]:
                m = re.search(r"(?:obra|ref\.?|referencia):?\s*(.+)", line_c, re.IGNORECASE)
                if m:
                    header["obra"] = clean_text(m.group(1))

    return header


# ─────────────────────────────────────────────────────────────────────────────
# Stage 3 — General totals (page 0)
# ─────────────────────────────────────────────────────────────────────────────

def parse_general_totals(pages: List[PageData]) -> Dict[str, str]:
    """
    Extract global totals (m2, ml, pesos) from page 0.

    Strategies (in order of preference):
    1. Specific text patterns ("Total superficie m2:", "Total perímetro m:").
    2. Columnar layout — labels on one line, values on the next.
    3. Table scan — look for matching labels in table cells.

    Returns dict {m2, ml, pesos} with str values (may be '').
    """
    totals: Dict[str, str] = {"m2": "", "ml": "", "pesos": ""}
    if not pages:
        return totals

    p0 = pages[0]
    lines = p0.text.split("\n") if p0.text else []

    # ── Text strategies ──────────────────────────────────────────────────────
    for idx, raw in enumerate(lines):
        lo = raw.lower()

        if "total superficie" in lo and "m2" in lo:
            m = re.search(r"total\s+superficie\s+m[2²]\s*:?\s*([\d.,]+)", lo)
            if m:
                totals["m2"] = m.group(1)

        if "total" in lo and ("perímetro" in lo or "perimetro" in lo):
            m = re.search(
                r"total\s+(?:perímetro|perimetro)\s+(?:ml|m)\s*:?\s*([\d.,]+)", lo
            )
            if m:
                totals["ml"] = m.group(1)

        if "total" in lo and not totals["m2"]:
            m = re.search(r"([\d.,]+)\s*m[2²]", lo)
            if m:
                totals["m2"] = m.group(1)

        if "total" in lo and not totals["ml"]:
            m = re.search(r"([\d.,]+)\s*ml", lo)
            if m:
                totals["ml"] = m.group(1)

        if "total" in lo and "$" in lo and not totals["pesos"]:
            m = re.search(r"\$\s*([\d.,]+)", lo)
            if m:
                totals["pesos"] = m.group(1)

        # Columnar layout: headers on this line, values on the next
        if "total superficie" in lo and ("total perimetro" in lo or "total perímetro" in lo):
            if not totals["m2"] or not totals["ml"]:
                if idx + 1 < len(lines):
                    nums = re.findall(r"[\d.,]+", lines[idx + 1])
                    nums = [n for n in nums if re.match(r"^\d+([.,]\d+)?$", n) and len(n) < 15]
                    if len(nums) >= 1 and not totals["m2"]:
                        totals["m2"] = nums[0]
                    if len(nums) >= 2 and not totals["ml"]:
                        totals["ml"] = nums[1]

    # ── Table scan fallback ───────────────────────────────────────────────────
    def _is_amount(s: str) -> bool:
        return bool(re.search(r"[\d.,]+", s))

    for table in p0.tables:
        for r_idx, row in enumerate(table):
            for c_idx, cell in enumerate(row):
                ct = clean_text(cell).lower()

                if "total" in ct and "superficie" in ct and "m2" in ct and not totals["m2"]:
                    m = re.search(r"[\d.,]+", ct.split(":")[-1])
                    if m and len(m.group(0)) > 1:
                        totals["m2"] = m.group(0)
                    elif c_idx + 1 < len(row) and _is_amount(clean_text(row[c_idx + 1])):
                        totals["m2"] = clean_text(row[c_idx + 1])
                    elif r_idx + 1 < len(table) and _is_amount(clean_text(table[r_idx + 1][c_idx])):
                        totals["m2"] = clean_text(table[r_idx + 1][c_idx])

                if "total" in ct and ("perímetro" in ct or "perimetro" in ct) and not totals["ml"]:
                    m = re.search(r"[\d.,]+", ct.split(":")[-1])
                    if m and len(m.group(0)) > 1:
                        totals["ml"] = m.group(0)
                    elif c_idx + 1 < len(row) and _is_amount(clean_text(row[c_idx + 1])):
                        totals["ml"] = clean_text(row[c_idx + 1])
                    elif r_idx + 1 < len(table) and _is_amount(clean_text(table[r_idx + 1][c_idx])):
                        totals["ml"] = clean_text(table[r_idx + 1][c_idx])

                if "total" in ct and "$" in ct and not totals["pesos"]:
                    m = re.search(r"\$\s*([\d.,]+)", ct)
                    if m:
                        totals["pesos"] = m.group(1)

    return totals


# ─────────────────────────────────────────────────────────────────────────────
# Stage 4 — Consolidated items (page 0)
# ─────────────────────────────────────────────────────────────────────────────

def _detect_col_map(headers: List[str]) -> Dict[str, Optional[int]]:
    """Map semantic column names to column indices from a header row."""
    col_map: Dict[str, Optional[int]] = {
        "descripcion": None,
        "material": None,
        "tipologia": None,
        "cantidad": None,
        "m2": None,
        "ml": None,
        "total": None,
    }
    for idx, h in enumerate(headers):
        h = h.lower()
        if any(x in h for x in ["descripcion", "descripción", "detalle", "designación"]):
            col_map["descripcion"] = idx
        elif "item" in h and len(h) <= 6 and idx + 1 < len(headers):
            col_map["descripcion"] = idx + 1
        elif "material" in h:
            col_map["material"] = idx
        elif any(x in h for x in ["tipo", "tipología", "modelo"]):
            col_map["tipologia"] = idx
        elif any(x in h for x in ["cant", "cantidad", "unid", "uds"]):
            col_map["cantidad"] = idx
        elif any(x in h for x in ["m2", "m²", "superficie", "sup."]):
            col_map["m2"] = idx
        elif any(x in h for x in ["ml", "perímetro", "perimetro", "ml."]):
            col_map["ml"] = idx
        elif any(x in h for x in ["total", "precio", "importe"]):
            col_map["total"] = idx

    # Fallback: assume standard layout if no descripcion found
    if col_map["descripcion"] is None and len(headers) >= 3:
        ncols = len(headers)
        if ncols >= 4:
            col_map["descripcion"] = 1
            col_map["cantidad"] = 2
            col_map["total"] = 3
        elif ncols >= 3:
            col_map["descripcion"] = 1
            col_map["total"] = 2
        else:
            col_map["descripcion"] = 1

    if col_map["total"] is None and col_map["cantidad"] is not None:
        nxt = col_map["cantidad"] + 1
        if nxt < len(headers):
            col_map["total"] = nxt

    return col_map


def parse_consolidated(pages: List[PageData]) -> List[Dict[str, Any]]:
    """
    Extract the consolidated item list from page 0.

    Strategy 1 (table): Find the table on page 0 that has a 'Descripción'
        or 'Cantidad' / 'Total' header (table index 1 in standard Fontela layout).
    Strategy 2 (text fallback): Line-by-line regex (minimal).

    Returns a list of normalized item dicts.
    """
    if not pages:
        return []

    p0 = pages[0]
    items_table: Optional[List[List[str]]] = None

    for t_idx, table in enumerate(p0.tables):
        if not table or not table[0]:
            continue
        hdrs = [clean_text(h or "").lower() for h in table[0]]
        hdr_text = " ".join(hdrs)
        if "descripci" in hdr_text or ("cantidad" in hdr_text and "total" in hdr_text):
            items_table = table
            if t_idx == 1:  # preferred: table index 1
                break

    if not items_table or len(items_table) < 2:
        return []

    col_map = _detect_col_map([clean_text(h or "").lower() for h in items_table[0]])
    items = []

    for row in items_table[1:]:
        if not row:
            continue
        # Skip total/summary rows
        if any(clean_text(c or "").lower().startswith("total") for c in row):
            continue

        raw: Dict[str, Any] = {}
        for key, idx in col_map.items():
            raw[key] = row[idx] if (idx is not None and idx < len(row)) else ""

        if raw.get("descripcion"):
            items.append(normalize_item_row(raw))

    return items


# ─────────────────────────────────────────────────────────────────────────────
# Stage 5 — Detailed paños (pages 1+) — state machine over tables
# ─────────────────────────────────────────────────────────────────────────────

_PANO_HEADER_KEYS = {"cantidad", "ancho", "alto"}


def _is_pano_table(table: List[List[str]]) -> bool:
    """Return True if this table's first row looks like a paños header."""
    if not table or not table[0]:
        return False
    hdrs = {clean_text(h or "").lower() for h in table[0] if h}
    return bool(hdrs & _PANO_HEADER_KEYS)


def _detect_pano_col_map(headers: List[str]) -> Dict[str, Optional[int]]:
    col_map: Dict[str, Optional[int]] = {
        "cantidad": None, "ancho": None, "alto": None,
        "superficie": None, "perimetro": None,
        "precio_unitario": None, "total": None,
    }
    for idx, h in enumerate(headers):
        h = h.lower()
        if "cant" in h:
            col_map["cantidad"] = idx
        elif "ancho" in h or "width" in h:
            col_map["ancho"] = idx
        elif "alto" in h or "height" in h:
            col_map["alto"] = idx
        elif "superficie" in h or "m2" in h or "m²" in h:
            col_map["superficie"] = idx
        elif "perímetro" in h or "perimetro" in h or "ml" in h:
            col_map["perimetro"] = idx
        elif "unitario" in h or "unit" in h:
            col_map["precio_unitario"] = idx
        elif "total" in h or "precio" in h:
            col_map["total"] = idx
    return col_map


def parse_detailed(pages: List[PageData]) -> List[Dict[str, Any]]:
    """
    Extract all paños from the detailed section (pages 1+).

    State machine (over tables across pages):
        IDLE          – waiting for first paños table
        IN_ITEM(N)    – collecting paños for item N

    Transition rules:
        • Any table passing _is_pano_table():
            - If state is IDLE → enter IN_ITEM(1)
            - If state is IN_ITEM(N) AND the previous paños table ended with
              a 'Totales' row → enter IN_ITEM(N+1)   (new item)
            - Otherwise: stay IN_ITEM(N)  (page-break continuation)
        • Non-paños tables are ignored for state transitions.

    Returns flat list of normalized paño dicts with item_index set.
    """
    panos: List[Dict[str, Any]] = []

    if len(pages) < 2:
        return panos

    # ── State ────────────────────────────────────────────────────────────────
    item_index = 0           # 0 = not started
    last_had_totales = False  # did last paños-table end with a "Totales" row?

    for page in pages[1:]:
        for table in page.tables:
            if not _is_pano_table(table):
                # Continuation tables (empty header, page-split) may still
                # carry the final "Totales" row for the current item.
                # Detect it so the state machine advances correctly.
                if item_index > 0:
                    for row in table:
                        if row and clean_text(row[0] or "").lower().startswith("total"):
                            last_had_totales = True
                            break
                continue

            # ── State transition ─────────────────────────────────────────────
            if item_index == 0:
                item_index = 1
                last_had_totales = False
            elif last_had_totales:
                item_index += 1
                last_had_totales = False
            # else: continuation across page break — keep item_index

            # ── Find header row (may not be row 0 for continuation tables) ──
            header_row_idx = 0
            for i in range(min(5, len(table))):
                row_joined = "".join(str(c).lower() for c in table[i] if c)
                if "cantidad" in row_joined or "ancho" in row_joined:
                    header_row_idx = i
                    break

            col_map = _detect_pano_col_map(
                [clean_text(h or "").lower() for h in table[header_row_idx]]
            )

            # ── Process data rows ─────────────────────────────────────────────
            for row in table[header_row_idx + 1:]:
                if not row:
                    continue
                first = clean_text(row[0] or "").lower()

                if first.startswith("total"):
                    last_had_totales = True
                    continue

                raw: Dict[str, Any] = {}
                for key, idx in col_map.items():
                    raw[key] = row[idx] if (idx is not None and idx < len(row)) else ""

                if raw.get("ancho") and raw.get("alto"):
                    panos.append(normalize_pano_row(raw, item_index))

    return panos
