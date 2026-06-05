"""PDF extractor for Fontela-format standard budget PDFs using structural table extraction.

Refactored to use pdfplumber's table detection for maximum robustness against
multi-line descriptions and complex layouts.
"""
from __future__ import annotations

import logging
import os
import re
import unicodedata
from dataclasses import dataclass, field
from decimal import Decimal, ROUND_HALF_UP, InvalidOperation
from pathlib import Path
from typing import List, Optional, Dict, Any

import pdfplumber
from collections import Counter

logger = logging.getLogger(__name__)
DEBUG_DETAIL_PARSE = os.getenv("PDF_EXTRACTOR_DEBUG", "").lower() in {"1", "true", "yes", "on"}


# ─── helpers numéricos ──────────────────────────────────────────────────────

TWO = Decimal("0.01")

def q2(v: Any) -> Decimal:
    """Asegura que el valor sea Decimal y aplica quantize(0.01)."""
    if not isinstance(v, Decimal):
        try:
            v = Decimal(str(v))
        except (InvalidOperation, TypeError):
            return Decimal("0.00")
    return v.quantize(TWO, rounding=ROUND_HALF_UP)


def parse_ar(raw: Any) -> Decimal:
    """Convierte número argentino ($3.154.152,35 → 3154152.35)."""
    if raw is None:
        return Decimal("0")
    s = str(raw).strip().replace("$", "").replace("Kg", "").strip()
    if not s or s == "-":
        return Decimal("0")
    try:
        # Handle cases like "3.154.152,35" or "152,35"
        if "," in s and "." in s:
            s = s.replace(".", "").replace(",", ".")
        elif "," in s:
            s = s.replace(",", ".")
        return Decimal(s)
    except InvalidOperation:
        return Decimal("0")


def _clean_text(raw: Any) -> str:
    if raw is None:
        return ""
    return " ".join(str(raw).split())


def _norm_header(raw: Any) -> str:
    text = unicodedata.normalize("NFKD", _clean_text(raw).lower())
    return "".join(ch for ch in text if not unicodedata.combining(ch))


ESTADOS_PRESUPUESTO = [
    "Parcial",
    "Produccion",
    "Producción",
    "Enviado",
    "Anulado",
    "Aprobado",
    "Pendiente",
    "Ejecutado",
]


def _split_empresa_obra(raw_empresa: str) -> tuple[str, str]:
    raw_empresa = _clean_text(raw_empresa)
    if "/" not in raw_empresa:
        return raw_empresa, ""
    empresa, obra = raw_empresa.split("/", 1)
    return _clean_text(empresa), _clean_text(obra)


def _strip_trailing_token(text: str, token: str) -> str:
    text = _clean_text(text)
    token = _clean_text(token)
    if not text or not token:
        return text
    pattern = rf"\s+{re.escape(token)}$"
    return re.sub(pattern, "", text, flags=re.IGNORECASE).strip()


def _remove_header_value(text: str, value: str) -> str:
    text = _clean_text(text)
    value = _clean_text(value)
    if not text or not value:
        return text
    return _clean_text(
        re.sub(rf"\b{re.escape(value)}\b", " ", text, count=1, flags=re.IGNORECASE)
    )


def _parse_single_line_header_values(
    line: str,
    contacto: str,
    cotizado_por: str,
    estado: str,
    fecha_aprobacion: Optional[str],
) -> tuple[str, str, str, str, Optional[str]]:
    """Parse compact header rows like: Empresa / Obra Contacto Estado Cotizador Fecha."""
    line = _clean_text(line)
    if not line:
        return "", "", _clean_text(contacto), _clean_text(cotizado_por), fecha_aprobacion

    date_m = re.search(r"\b\d{2}/\d{2}/\d{2,4}\b", line)
    if date_m and not fecha_aprobacion:
        fecha_aprobacion = date_m.group(0)
    if date_m:
        line = _remove_header_value(line, date_m.group(0))

    estado_found = estado or next(
        (
            possible
            for possible in ESTADOS_PRESUPUESTO
            if re.search(rf"\b{re.escape(possible)}\b", line, re.IGNORECASE)
        ),
        "",
    )

    line = _remove_header_value(line, cotizado_por)
    line = _remove_header_value(line, estado_found)
    line = _remove_header_value(line, contacto)

    empresa, obra = _split_empresa_obra(line)
    return empresa, obra, _clean_text(contacto), _clean_text(cotizado_por), fecha_aprobacion


def _parse_header_block_from_text(
    text: str,
    contacto: str = "",
    cotizado_por: str = "",
    estado: str = "",
    fecha_aprobacion: Optional[str] = None,
) -> tuple[str, str, str, str, Optional[str]]:
    """Recover Empresa/Obra when pdfplumber drops the Empresa column."""
    block_m = None
    for pattern in (
        r"Empresa\s+Contacto\s+Estado\s+Cotizado\s+por\s+Fecha\s+de\s+aprobaci\S*\s*(.*?)\s*Presupuesto consolidado:",
        r"Cotizado\s+Fecha\s+de\s+Empresa\s+Contacto\s+Estado\s+por\s+aprobaci\S*\s*(.*?)\s*Presupuesto consolidado:",
        r"por\s+aprobaci\S*\s*(.*?)\s*Presupuesto consolidado:",
    ):
        block_m = re.search(pattern, text, re.IGNORECASE | re.DOTALL)
        if block_m:
            break
    if not block_m:
        return "", "", contacto, cotizado_por, fecha_aprobacion

    lines = [_clean_text(line) for line in block_m.group(1).splitlines() if _clean_text(line)]
    if not lines:
        return "", "", contacto, cotizado_por, fecha_aprobacion

    if len(lines) == 1:
        return _parse_single_line_header_values(
            lines[0],
            contacto,
            cotizado_por,
            estado,
            fecha_aprobacion,
        )

    state_idx = None
    estado_found = estado
    for idx, line in enumerate(lines):
        for possible in ESTADOS_PRESUPUESTO:
            if re.search(rf"\b{re.escape(possible)}\b", line, re.IGNORECASE):
                state_idx = idx
                estado_found = estado_found or possible
                break
        if state_idx is not None:
            break

    before_lines = lines if state_idx is None else lines[:state_idx]
    state_line = "" if state_idx is None else lines[state_idx]
    after_lines = [] if state_idx is None else lines[state_idx + 1:]

    date_m = re.search(r"\b\d{2}/\d{2}/\d{2,4}\b", state_line)
    if date_m and not fecha_aprobacion:
        fecha_aprobacion = date_m.group(0)

    if state_line and not cotizado_por:
        state_without_date = re.sub(r"\b\d{2}/\d{2}/\d{2,4}\b", "", state_line)
        if estado_found:
            state_without_date = re.sub(rf"\b{re.escape(estado_found)}\b", "", state_without_date, flags=re.IGNORECASE)
        cotizado_por = _clean_text(state_without_date)

    contact_parts = contacto.split()
    cotizado_parts = cotizado_por.split()
    contact_first = contact_parts[0] if contact_parts else ""
    contact_last = contact_parts[-1] if len(contact_parts) > 1 else contact_first
    cotizado_first = cotizado_parts[0] if cotizado_parts else ""
    cotizado_last = cotizado_parts[-1] if len(cotizado_parts) > 1 else cotizado_first

    cleaned_before = []
    for line in before_lines:
        line = _strip_trailing_token(line, cotizado_first)
        line = _strip_trailing_token(line, contact_first)
        if line:
            cleaned_before.append(line)

    cleaned_after = []
    for line in after_lines:
        line = _strip_trailing_token(line, cotizado_last)
        line = _strip_trailing_token(line, contact_last)
        if line:
            cleaned_after.append(line)

    raw_empresa = _clean_text(" ".join(cleaned_before + cleaned_after))
    empresa, obra = _split_empresa_obra(raw_empresa)
    return empresa, obra, _clean_text(contacto), _clean_text(cotizado_por), fecha_aprobacion


# ─── dataclasses ────────────────────────────────────────────────────────────

@dataclass
class PdfPane:
    row_no: int
    cantidad: int
    ancho_mm: int
    alto_mm: int
    superficie_m2: Decimal
    perimetro_ml: Decimal
    denominacion: Optional[str]
    precio_unitario: Decimal
    precio_total: Decimal


@dataclass
class PdfAdicional:
    row_no: int
    cantidad: int
    descripcion: str
    precio_unitario: Decimal
    precio_total: Decimal


@dataclass
class PdfItem:
    numero_item: int
    descripcion: str
    cantidad: int
    total_pesos: Decimal
    total_m2: Decimal = Decimal("0")
    total_ml: Decimal = Decimal("0")
    panos: List[PdfPane] = field(default_factory=list)
    adicionales: List[PdfAdicional] = field(default_factory=list)
    incompleto: bool = False


@dataclass
class PdfPresupuesto:
    numero: str
    empresa: str
    contacto: str
    estado: str
    cotizado_por: str
    fecha_aprobacion: Optional[str]     # DD/MM/YY o None
    total_unidades: int
    total_importe: Decimal
    total_m2: Decimal
    total_ml: Decimal
    peso_estimado_kg: Decimal
    obra: str = ""
    empresa_raw: str = ""


@dataclass
class ParsedBudget:
    presupuesto: PdfPresupuesto
    items: List[PdfItem]
    warnings: List[str] = field(default_factory=list)


# ─── Extracción Principal ───────────────────────────────────────────────────

def extract_budget_pdf(pdf_path: str | Path) -> ParsedBudget:
    """
    Extrae un presupuesto Fontela de un PDF usando detección de tablas.
    """
    with pdfplumber.open(str(pdf_path)) as pdf:
        # 1. Parsear Encabezado y Totales Generales
        budget_hdr = _parse_header_and_totals(pdf)

        # 2. Parsear Items Consolidados (Lista maestra)
        items = _parse_consolidated(pdf.pages[0])

        # 3. Parsear Detalle de Paños (Páginas 2 en adelante)
        _parse_detailed_all_pages(pdf, items)

        # 4. Backfill y Validación
        _backfill_item_totals(items)
        result = ParsedBudget(presupuesto=budget_hdr, items=items)
        _validate(result)

        return result


def _parse_header_and_totals(pdf) -> PdfPresupuesto:
    page1 = pdf.pages[0]
    text = page1.extract_text() or ""

    # Búsqueda de campo número (está fuera de tabla usualmente)
    # Patrón flexible para: Presupuesto Nº: 000209365, Presupuesto N° 123, etc.
    num_m = re.search(r"Presupuesto\s*N[º°]?\s*[:\s]*\s*#?(\d+)", text, re.IGNORECASE)
    numero = num_m.group(1) if num_m else ""

    # Detección de tabla de cabecera (Contacto, Estado, etc.)
    empresa = contacto = estado = cotizado_por = ""
    raw_empresa_found = ""
    potential_obra_from_empresa = ""
    fecha_aprobacion = None

    tables = page1.extract_tables()
    for table in tables:
        # Buscamos la tabla que contiene Contacto/Estado
        headers = [_norm_header(h) for h in table[0]]
        if "contacto" in headers or "estado" in headers:
            row = table[1]

            # Intentar leer empresa directamente de la tabla si existe la columna
            try:
                idx_emp = headers.index("empresa")
                raw_val = _clean_text(row[idx_emp]) if row[idx_emp] else ""
                if raw_val:
                    raw_empresa_found = raw_val
                    empresa, potential_obra_from_empresa = _split_empresa_obra(raw_val)
            except (ValueError, IndexError): pass

            try:
                idx_cont = headers.index("contacto")
                contacto = _clean_text(row[idx_cont]) if row[idx_cont] else ""
            except (ValueError, IndexError): pass

            try:
                idx_est = headers.index("estado")
                estado = _clean_text(row[idx_est]) if row[idx_est] else ""
            except (ValueError, IndexError): pass

            try:
                idx_cot = headers.index("cotizado por")
                cotizado_por = _clean_text(row[idx_cot]) if row[idx_cot] else ""
            except (ValueError, IndexError): pass

            try:
                idx_fecha = headers.index("fecha de aprobación")
                fecha_aprobacion = _clean_text(row[idx_fecha]) if row[idx_fecha] else None
            except (ValueError, IndexError): pass

            if fecha_aprobacion is None:
                try:
                    idx_fecha = headers.index("fecha de aprobacion")
                    fecha_aprobacion = _clean_text(row[idx_fecha]) if row[idx_fecha] else None
                except (ValueError, IndexError): pass

            break

    if not empresa:
        (
            fallback_empresa,
            fallback_obra,
            contacto,
            cotizado_por,
            fecha_aprobacion,
        ) = _parse_header_block_from_text(text, contacto, cotizado_por, estado, fecha_aprobacion)
        if fallback_empresa:
            empresa = fallback_empresa
            potential_obra_from_empresa = fallback_obra
            raw_empresa_found = _clean_text(f"{empresa} / {fallback_obra}" if fallback_obra else empresa)

    # Fallback robusto si no se encontró en tabla (para PDFs con texto plano o tablas no detectadas)
    if not empresa:
        header_block_match = re.search(
            r"Empresa\s+Contacto\s+Estado\s+Cotizado por\s+Fecha de aprobación\s*(.*?)\s*Presupuesto consolidado:",
            text,
            re.IGNORECASE | re.DOTALL,
        )
        if header_block_match:
            header_line = " ".join(header_block_match.group(1).split())

            # Estados esperados para delimitar
            estados_list = ["Parcial", "Enviado", "Anulado", "Aprobado", "Pendiente"]
            estado_found = next((e for e in estados_list if f" {e} " in f" {header_line} "), None)

            if estado_found:
                before_estado, after_estado = header_line.split(estado_found, 1)

                # El contacto suele ser las últimas 2 palabras antes del estado
                tokens = before_estado.split()
                if len(tokens) >= 3:
                    contacto = contacto or " ".join(tokens[-2:])
                    raw_empresa_found = " ".join(tokens[:-2])

                    if "/" in raw_empresa_found:
                        parts = raw_empresa_found.split("/", 1)
                        empresa = parts[0].strip()
                        potential_obra_from_empresa = parts[1].strip()
                    else:
                        empresa = raw_empresa_found.strip()
                        potential_obra_from_empresa = ""

                estado = estado or estado_found

    # Si aún no tenemos raw_empresa_found pero sí empresa
    if empresa and not raw_empresa_found:
        raw_empresa_found = empresa

    # Búsqueda de campo Referencia/Obra (NADA -> captura Ref: si existe)
    obra_ref = ""
    ref_m = re.search(r"Ref\s*[:\-–]?\s*(.*?)(?:\n|$)", text, re.IGNORECASE)
    if ref_m:
        obra_ref = ref_m.group(1).strip()

    # Consolidar nombre de Obra
    obra = obra_ref or potential_obra_from_empresa or ""

    # Totales Generales
    total_u = 0
    total_imp = Decimal("0")
    total_m2 = Decimal("0")
    total_ml = Decimal("0")
    peso = Decimal("0")

    # Los totales suelen estar en una tabla al final de la hoja 1
    # O identificables por texto clave
    tot_m = re.search(r"Total\s+(\d+)\s+\$([\d\.,]+)", text, re.IGNORECASE)
    if tot_m:
        total_u = int(tot_m.group(1))
        total_imp = parse_ar(tot_m.group(2))

    met_m = re.search(
        r"Total superficie m2:\s*Total perimetro m:.*?([\d\.,]+)\s+([\d\.,]+)\s+([\d\.,]+)\s+([\d\.,]+)\s*Kg",
        text, re.IGNORECASE | re.DOTALL,
    )
    if met_m:
        total_m2 = parse_ar(met_m.group(1))
        total_ml = parse_ar(met_m.group(2))
        peso = parse_ar(met_m.group(4))

    return PdfPresupuesto(
        numero=numero, empresa=empresa, contacto=contacto,
        estado=estado, cotizado_por=cotizado_por,
        fecha_aprobacion=fecha_aprobacion,
        total_unidades=total_u, total_importe=total_imp,
        total_m2=total_m2, total_ml=total_ml, peso_estimado_kg=peso,
        obra=obra,
        empresa_raw=raw_empresa_found
    )


def _parse_consolidated(page1) -> List[PdfItem]:
    """Extrae la lista maestra de ítems de la primera tabla de consolidado."""
    items: List[PdfItem] = []
    tables = page1.extract_tables()

    for table in tables:
        # Identificamos tabla por el header "Descripción"
        headers = [str(h).lower() if h else "" for h in table[0]]
        if "descripción" in headers and "cantidad" in headers:
            for row in table[1:]:
                # Filtrar filas vacías o de total
                if not row or len(row) < 3: continue
                item_no_raw = str(row[0]).strip()
                if not item_no_raw.isdigit(): continue

                desc = str(row[1]).strip().replace("\n", " ")
                cant = int(parse_ar(row[2]))
                total = parse_ar(row[3])

                items.append(PdfItem(
                    numero_item=int(item_no_raw),
                    descripcion=desc,
                    cantidad=cant,
                    total_pesos=total
                ))
            break
    return items


def _parse_detailed_all_pages(pdf, items: List[PdfItem]):
    """Itera sobre todas las páginas y combina parsing por tablas + texto."""
    item_map = {it.numero_item: it for it in items}
    current_item_no = None

    # Cache para deduplicar filas físicas leídas por dos métodos (tabla/texto)
    # pero PERMITIR duplicados legítimos si aparecen múltiples veces en la página.

    for page_idx, page in enumerate(pdf.pages, start=1):
        if page_idx == 1: continue # El detalle empieza en pág 2+ usualmente

        page_text = page.extract_text() or ""
        page_lines = [ln.strip() for ln in page_text.splitlines() if ln.strip()]

        # 1. Detectar si el item cambia al inicio de página
        for probe in page_lines[:10]:
            if _is_detail_continuation_line(probe):
                break
            maybe = _detect_item_start(probe, item_map, None)
            if maybe:
                current_item_no = maybe
                break

        # Listas para fusionar al final de la página
        table_candidates = [] # list of (item_no, obj)
        text_candidates = []  # list of (item_no, obj)

        # A) Parsing por TABLAS
        table_objs = page.find_tables()
        # Ordenar por posición vertical
        table_objs.sort(key=lambda t: t.bbox[1])

        temp_item_table = current_item_no
        for t_obj in table_objs:
            # Re-detectar item antes de cada tabla
            top = t_obj.bbox[1]
            above_text = ""
            if top > 0:
                above_area = (0, max(0, top - 80), page.width, top)
                if above_area[1] < above_area[3]:
                    above_text = page.within_bbox(above_area).extract_text() or ""
            temp_item_table = _detect_item_start(above_text, item_map, temp_item_table)

            data = t_obj.extract()
            if not data: continue

            headers = [str(h).lower() if h else "" for h in data[0]]
            is_detail = "ancho" in headers and "alto" in headers

            for row in data[1:]:
                if not any(row): continue
                row_text = " ".join(str(c).strip() for c in row if c).strip()

                # Cambio de item dentro de la tabla? (Raro pero posible)
                maybe = _detect_item_start(row_text, item_map, None)
                if maybe:
                    temp_item_table = maybe
                    continue

                if temp_item_table is None: continue

                # Paño
                if is_detail:
                    pane = _parse_pane_from_cells(row)
                    if pane:
                        table_candidates.append((temp_item_table, pane))
                        continue

                # Adicional
                adic = _parse_adicional_from_cells(row)
                if adic:
                    table_candidates.append((temp_item_table, adic))

        # B) Parsing por TEXTO
        temp_item_text = current_item_no
        for line in page_lines:
            maybe = _detect_item_start(line, item_map, None)
            if maybe:
                temp_item_text = maybe
                # No 'continue' porque la misma línea puede ser un paño (raro pero por las dudas)

            # Subtotal/Cierre (para registrar totales esperados)
            subt = _parse_subtotal_line(line)
            if subt and temp_item_text in item_map:
                qty, m2, pesos = subt
                it = item_map[temp_item_text]
                it.cantidad = it.cantidad or qty
                if m2 > 0: it.total_m2 = m2
                if pesos > 0: it.total_pesos = pesos
                continue

            if temp_item_text is None: continue

            # Paño
            pane = _parse_pane_from_text(line)
            if pane:
                text_candidates.append((temp_item_text, pane))
                continue

            # Adicional
            adic = _parse_adicional_from_text(line)
            if adic:
                text_candidates.append((temp_item_text, adic))

        # C) FUSIONAR RESULTADOS DE LA PÁGINA
        # Para cada (item_no, tipo, contenido), tomar el MAX de ocurrencias entre tabla y texto.
        # Esto asegura que si la tabla perdió filas pero el texto no (o viceversa), capturamos todo.
        # Y si ambos detectaron lo mismo, no lo duplicamos.

        all_item_nos = set(c[0] for c in table_candidates) | set(c[0] for c in text_candidates)
        if temp_item_text: all_item_nos.add(temp_item_text)

        for it_no in sorted(all_item_nos):
            if it_no not in item_map: continue
            target_item = item_map[it_no]

            # Agrupar candidatos por "contenido"
            def _norm_denom(d):
                """Normalize denominacion: None, '-', '' all become ''."""
                s = (d or "").strip()
                return "" if s == "-" else s

            def get_key(obj):
                if isinstance(obj, PdfPane):
                    return ("PANE", obj.cantidad, obj.ancho_mm, obj.alto_mm, q2(obj.superficie_m2), q2(obj.perimetro_ml), _norm_denom(obj.denominacion), q2(obj.precio_total))
                else:
                    return ("ADIC", obj.cantidad, obj.descripcion.strip(), q2(obj.precio_total))

            it_table_objs = [c[1] for c in table_candidates if c[0] == it_no]
            it_text_objs = [c[1] for c in text_candidates if c[0] == it_no]

            table_counts = Counter(get_key(o) for o in it_table_objs)
            text_counts = Counter(get_key(o) for o in it_text_objs)

            all_keys = set(table_counts.keys()) | set(text_counts.keys())

            rows_added_this_page = 0
            for k in all_keys:
                count = max(table_counts[k], text_counts[k])
                # Buscar el objeto original para copiar (preferir el de tabla si existe)
                sample_obj = next((o for o in it_table_objs if get_key(o) == k), None)
                if not sample_obj:
                    sample_obj = next((o for o in it_text_objs if get_key(o) == k), None)

                for _ in range(count):
                    if isinstance(sample_obj, PdfPane):
                        new_pane = PdfPane(**sample_obj.__dict__)
                        new_pane.row_no = len(target_item.panos) + 1
                        target_item.panos.append(new_pane)
                    else:
                        new_adic = PdfAdicional(**sample_obj.__dict__)
                        new_adic.row_no = len(target_item.adicionales) + 1
                        target_item.adicionales.append(new_adic)
                    rows_added_this_page += 1

            if DEBUG_DETAIL_PARSE:
                logger.debug("[pdf-detail] pág=%s item=%s filas_agregadas=%s", page_idx, it_no, rows_added_this_page)

        # Actualizar estado para la siguiente página
        current_item_no = temp_item_text or current_item_no


# 8-field variant: cantidad ancho alto sup per denom unitario total
PANE_TEXT_RE_8 = re.compile(
    r"^\s*(\d+)\s+(\d{2,5})\s+(\d{2,5})\s+([\d\.,]+)\s+([\d\.,]+)\s+(.+?)\s+\$?\s*([\d\.,]+)\s+\$?\s*([\d\.,]+)\s*$"
)
# 7-field variant: cantidad ancho alto sup per unitario total (no denom column)
PANE_TEXT_RE_7 = re.compile(
    r"^\s*(\d+)\s+(\d{2,5})\s+(\d{2,5})\s+([\d\.,]+)\s+([\d\.,]+)\s+\$?\s*([\d\.,]+)\s+\$?\s*([\d\.,]+)\s*$"
)
ADICIONAL_TEXT_RE = re.compile(r"^\s*(\d+)\s+(.+?)\s+\$?\s*([\d\.,]+)\s+\$?\s*([\d\.,]+)\s*$")
SUBTOTAL_RE = re.compile(r"^\s*(\d+)\s+paños?\s+([\d\.,]+)\s+[\d\.,]+\s+\$?\s*([\d\.,]+)\s*$", re.IGNORECASE)
TOT_RE = re.compile(r"^\s*Totales?\s*$", re.IGNORECASE)


def _is_detail_continuation_line(line: str) -> bool:
    stripped = (line or "").strip()
    if not stripped:
        return False
    lower = stripped.lower()
    if "cantidad" in lower and "ancho" in lower and "alto" in lower:
        return True
    if TOT_RE.match(stripped):
        return True
    if _parse_subtotal_line(stripped):
        return True
    return _parse_pane_from_text(stripped) is not None


def _detect_item_start(text: str, item_map: Dict[int, PdfItem], default: Optional[int]) -> Optional[int]:
    """Detect if text contains an item header line.

    When text is multi-line (e.g. above_text from a bounding box), check each
    line individually and return the LAST detected item number (the one closest
    to the table below).
    """
    raw = (text or "").strip()
    if not raw:
        return default

    # Split into individual lines and check each one
    lines = raw.splitlines()
    last_found = default

    for line in lines:
        line = line.strip()
        if not line:
            continue
        if "$" in line:
            continue
        if _parse_subtotal_line(line):
            continue

        m = re.match(r"^(\d+)\s+[A-Za-zÁÉÍÓÚÜÑáéíóúüñ]", line)
        if m:
            item_no = int(m.group(1))
            if item_no in item_map:
                last_found = item_no
                continue
        if line.isdigit():
            item_no = int(line)
            if item_no in item_map:
                last_found = item_no

    return last_found


def _parse_subtotal_line(line: str) -> Optional[tuple[int, Decimal, Decimal]]:
    m = SUBTOTAL_RE.match((line or "").strip())
    if not m:
        return None
    return int(m.group(1)), parse_ar(m.group(2)), parse_ar(m.group(3))


def _parse_pane_from_cells(row: list[Any]) -> Optional[PdfPane]:
    try:
        cant = int(parse_ar(row[0]))
        ancho = int(parse_ar(row[1]))
        alto = int(parse_ar(row[2]))
    except (IndexError, ValueError):
        return None
    if cant <= 0 or ancho <= 0 or alto <= 0:
        return None
    denominacion = str(row[5]).strip() if len(row) > 5 and row[5] else None
    if denominacion == "-":
        denominacion = None
    return PdfPane(
        row_no=0,
        cantidad=cant,
        ancho_mm=ancho,
        alto_mm=alto,
        superficie_m2=parse_ar(row[3]) if len(row) > 3 else Decimal("0"),
        perimetro_ml=parse_ar(row[4]) if len(row) > 4 else Decimal("0"),
        denominacion=denominacion,
        precio_unitario=parse_ar(row[6]) if len(row) > 6 else Decimal("0"),
        precio_total=parse_ar(row[7]) if len(row) > 7 else Decimal("0"),
    )


def _parse_pane_from_text(line: str) -> Optional[PdfPane]:
    stripped = (line or "").strip()
    # Try 8-field variant first (with denomination column)
    m = PANE_TEXT_RE_8.match(stripped)
    if m:
        return PdfPane(
            row_no=0,
            cantidad=int(m.group(1)),
            ancho_mm=int(m.group(2)),
            alto_mm=int(m.group(3)),
            superficie_m2=parse_ar(m.group(4)),
            perimetro_ml=parse_ar(m.group(5)),
            denominacion=m.group(6),
            precio_unitario=parse_ar(m.group(7)),
            precio_total=parse_ar(m.group(8)),
        )
    # Try 7-field variant (no denomination column)
    m = PANE_TEXT_RE_7.match(stripped)
    if m:
        return PdfPane(
            row_no=0,
            cantidad=int(m.group(1)),
            ancho_mm=int(m.group(2)),
            alto_mm=int(m.group(3)),
            superficie_m2=parse_ar(m.group(4)),
            perimetro_ml=parse_ar(m.group(5)),
            denominacion=None,
            precio_unitario=parse_ar(m.group(6)),
            precio_total=parse_ar(m.group(7)),
        )
    return None


def _parse_adicional_from_cells(row: list[Any]) -> Optional[PdfAdicional]:
    if not row:
        return None
    try:
        cant = int(parse_ar(row[0]))
    except (ValueError, IndexError):
        return None
    if cant <= 0:
        return None
    desc = str(row[1]).strip() if len(row) > 1 and row[1] else ""
    if not desc or desc == "-":
        return None
    if not any(ch.isalpha() for ch in desc):
        return None
    non_empty = [str(c).strip() for c in row if c and str(c).strip() and str(c).strip() != "-"]
    if len(non_empty) < 3:
        return None
    p_uni = parse_ar(non_empty[-2])
    p_tot = parse_ar(non_empty[-1])
    if p_uni <= 0 and p_tot <= 0:
        return None
    return PdfAdicional(row_no=0, cantidad=cant, descripcion=desc, precio_unitario=p_uni, precio_total=p_tot)


def _parse_adicional_from_text(line: str) -> Optional[PdfAdicional]:
    line = (line or "").strip()
    if "paños" in line.lower():
        return None
    if _parse_pane_from_text(line):
        return None
    m = ADICIONAL_TEXT_RE.match(line)
    if not m:
        return None
    qty = int(m.group(1))
    desc = m.group(2).strip()
    if not desc:
        return None
    if not any(ch.isalpha() for ch in desc):
        return None
    p_uni = parse_ar(m.group(3))
    p_tot = parse_ar(m.group(4))
    if p_uni <= 0 and p_tot <= 0:
        return None
    return PdfAdicional(row_no=0, cantidad=qty, descripcion=desc, precio_unitario=p_uni, precio_total=p_tot)


def _pane_key(item_no: int, pane: PdfPane) -> tuple:
    return (
        item_no,
        pane.cantidad,
        pane.ancho_mm,
        pane.alto_mm,
        q2(pane.superficie_m2),
        q2(pane.perimetro_ml),
        (pane.denominacion or "").strip(),
        q2(pane.precio_total),
    )


def _append_pane_if_new(item: PdfItem, pane: PdfPane, item_no: int, seen: set[tuple]) -> bool:
    key = _pane_key(item_no, pane)
    if key in seen:
        return False
    seen.add(key)
    pane.row_no = len(item.panos) + 1
    item.panos.append(pane)
    return True


def _append_adicional(item: PdfItem, adicional: PdfAdicional) -> None:
    adicional.row_no = len(item.adicionales) + 1
    item.adicionales.append(adicional)


def _backfill_item_totals(items: List[PdfItem]) -> None:
    """Si item.total_m2 == 0, calcular desde suma de paños."""
    for item in items:
        sum_m2 = sum((p.superficie_m2 for p in item.panos), Decimal("0"))
        sum_ml = sum((p.perimetro_ml for p in item.panos), Decimal("0"))
        sum_pesos = sum((p.precio_total for p in item.panos), Decimal("0")) + sum((a.precio_total for a in item.adicionales), Decimal("0"))
        if item.total_m2 == Decimal("0") and sum_m2 > 0:
            item.total_m2 = q2(sum_m2)
        if item.total_ml == Decimal("0") and sum_ml > 0:
            item.total_ml = q2(sum_ml)
        if item.total_pesos == Decimal("0") and sum_pesos > 0:
            item.total_pesos = q2(sum_pesos)


def _validate(budget: ParsedBudget) -> None:
    warnings: List[str] = []
    TOL = Decimal("0.10")

    for item in budget.items:
        if not item.panos and not item.adicionales:
            warnings.append(f"Ítem {item.numero_item}: sin paños ni adicionales detectados")
            continue

        sum_pesos = q2(sum((p.precio_total for p in item.panos), Decimal("0")) + sum((a.precio_total for a in item.adicionales), Decimal("0")))
        sum_m2 = q2(sum((p.superficie_m2 for p in item.panos), Decimal("0")))
        sum_ml = q2(sum((p.perimetro_ml for p in item.panos), Decimal("0")))
        sum_cant = sum((p.cantidad for p in item.panos), 0) # Solo paños! No sumar adicionales

        if abs(sum_pesos - q2(item.total_pesos)) > TOL:
            warnings.append(f"Ítem {item.numero_item}: Diferencia en total pesos (${sum_pesos} vs ${q2(item.total_pesos)})")
        if abs(sum_m2 - q2(item.total_m2)) > TOL:
            warnings.append(f"Ítem {item.numero_item}: Diferencia en m² ({sum_m2} vs {q2(item.total_m2)})")
        if sum_cant != item.cantidad:
            item.incompleto = True
            warnings.append(
                f"Ítem {item.numero_item}: Diferencia en cantidad (leída {sum_cant} vs esperada {item.cantidad}) [incompleto]"
            )

    # Totales generales
    hdr = budget.presupuesto
    if hdr.total_m2 > 0:
        sum_m2_global = q2(sum((it.total_m2 for it in budget.items), Decimal("0")))
        if abs(sum_m2_global - q2(hdr.total_m2)) > Decimal("0.50"):
            warnings.append(f"Total m² general desigual: ítems {sum_m2_global} vs encabezado {q2(hdr.total_m2)}")

    budget.warnings.extend(warnings)


def parsed_budget_to_dict(budget: ParsedBudget) -> Dict[str, Any]:
    """Convierte ParsedBudget a dict serializable."""
    def _dec(v) -> float | None:
        if isinstance(v, Decimal): return float(v)
        return v

    items_out = []
    for item in budget.items:
        panos_out = []
        for p in item.panos:
            panos_out.append({
                "row_no": p.row_no, "cantidad": p.cantidad,
                "ancho_mm": p.ancho_mm, "alto_mm": p.alto_mm,
                "superficie_m2": _dec(p.superficie_m2),
                "perimetro_ml": _dec(p.perimetro_ml),
                "denominacion": p.denominacion,
                "precio_unitario": _dec(p.precio_unitario),
                "precio_total": _dec(p.precio_total),
            })
        adicionales_out = []
        for a in item.adicionales:
            adicionales_out.append({
                "row_no": a.row_no, "cantidad": a.cantidad,
                "descripcion": a.descripcion,
                "precio_unitario": _dec(a.precio_unitario),
                "precio_total": _dec(a.precio_total),
            })
        items_out.append({
            "numero_item": item.numero_item,
            "descripcion": item.descripcion,
            "cantidad": item.cantidad,
            "incompleto": item.incompleto,
            "total_pesos": _dec(item.total_pesos),
            "total_m2": _dec(item.total_m2),
            "total_ml": _dec(item.total_ml),
            "panos": panos_out,
            "adicionales": adicionales_out,
        })

    hdr = budget.presupuesto
    return {
        "presupuesto": {
            "numero": hdr.numero, "empresa": hdr.empresa,
            "cliente": hdr.empresa, # Alias for frontend compatibility
            "contacto": hdr.contacto, "estado": hdr.estado,
            "cotizado_por": hdr.cotizado_por, "fecha_aprobacion": hdr.fecha_aprobacion,
            "total_unidades": hdr.total_unidades, "total_importe": _dec(hdr.total_importe),
            "total_m2": _dec(hdr.total_m2), "total_ml": _dec(hdr.total_ml),
            "peso_estimado_kg": _dec(hdr.peso_estimado_kg),
            "obra": hdr.obra,
            "empresa_raw": hdr.empresa_raw,
        },
        "items": items_out,
        "warnings": budget.warnings,
    }


if __name__ == "__main__":
    import json
    import sys
    path = sys.argv[1] if len(sys.argv) > 1 else "sample.pdf"
    res = extract_budget_pdf(path)
    print(json.dumps(parsed_budget_to_dict(res), indent=2, ensure_ascii=False))
