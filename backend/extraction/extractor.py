"""Main PDF extraction module."""
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
    normalize_totals
)
from extraction.validator import validate_package


def extract_raw_data_from_pdf(pdf_path: str) -> Dict[str, Any]:
    """
    Extracts raw text lines from page 1 and all tables from all pages.
    This creates an intermediate structured representation (CSV-like).
    """
    raw_data = {
        "text_lines": [],
        "tables": [] # List of (page_idx, table_idx, data)
    }
    
    with pdfplumber.open(pdf_path) as pdf:
        # Extract all text from page 1 for header/totals
        if len(pdf.pages) > 0:
            text = pdf.pages[0].extract_text()
            if text:
                raw_data["text_lines"] = text.split('\n')
        
        # Extract all tables from all pages
        for p_idx, page in enumerate(pdf.pages):
            tables = page.extract_tables()
            for t_idx, table in enumerate(tables):
                if table:
                    # Clean None values
                    clean_table = [[cell if cell is not None else "" for cell in row] for row in table]
                    raw_data["tables"].append({
                        "page_idx": p_idx,
                        "table_idx": t_idx,
                        "data": clean_table
                    })
                    
    return raw_data


def extract_with_pdfplumber(pdf_path: str) -> Dict[str, Any]:
    """
    Refactored extraction logic using intermediate raw data structures.
    """
    raw_data = extract_raw_data_from_pdf(pdf_path)
    
    result = {
        "header": extract_header_from_text("\n".join(raw_data["text_lines"])),
        "items": [],
        "panos": [],
        "totals": extract_totals_from_text("\n".join(raw_data["text_lines"]))
    }
    
    # Extract Items from Table 2 of Page 1 (standard layout)
    # If not found, try any table on page 1 that looks like items
    items_table = None
    for table_info in raw_data["tables"]:
        if table_info["page_idx"] == 0:
            data = table_info["data"]
            # Look for Item table keywords
            headers = [str(h).lower() for h in data[0] if h]
            header_text = " ".join(headers)
            if "descripci" in header_text or "total" in header_text:
                items_table = data
                # Don't break yet, Table 2 is usually the best one for Fontela
                if table_info["table_idx"] == 1: # Table 2 (0-indexed)
                    break
    
    if items_table:
        result["items"] = extract_items_from_table(items_table)
        
    # Extract Panos from all other tables
    all_panos = []
    for table_info in raw_data["tables"]:
        # Skip items table
        if table_info["page_idx"] == 0 and table_info["table_idx"] <= 1:
            continue
            
        panos = extract_panos_from_table(table_info["data"])
        all_panos.extend(panos)
        
    result["panos"] = all_panos
    
    # Totals fallback from tables
    table_totals = extract_totals_from_tables([t["data"] for t in raw_data["tables"]])
    for k, v in table_totals.items():
        if v and not result["totals"].get(k):
            result["totals"][k] = v
            
    return result


def extract_header_from_text(text: str) -> Dict[str, str]:
    """Extract header information from page text."""
    
    
    header = {
        "cliente": "",
        "obra": "",
        "presupuesto_numero": "",
        "fecha": "",
        "condiciones": "",
        "estado": ""
    }
    
    lines = text.split("\n")
    
    for line in lines:
        line = clean_text(line)
        
        # Client
        if "cliente" in line.lower() or "sr." in line.lower():
            # Extract text after "Cliente:" or "Sr."
            match = re.search(r"(?:cliente|sr\.?):?\s*(.+)", line, re.IGNORECASE)
            if match:
                header["cliente"] = clean_text(match.group(1))
        
        # Obra / Ref
        if "obra" in line.lower() or "ref" in line.lower():
            match = re.search(r"(?:obra|ref\.?|referencia):?\s*(.+)", line, re.IGNORECASE)
            if match:
                header["obra"] = clean_text(match.group(1))
        
        # Presupuesto number - look for #NNNNNN pattern anywhere
        match_presupuesto = re.search(r"#(\d{6,})", line)
        if match_presupuesto:
            header["presupuesto_numero"] = match_presupuesto.group(1)
        
        # Date
        if "fecha" in line.lower():
            match = re.search(r"(\d{1,2}[/-]\d{1,2}[/-]\d{2,4})", line)
            if match:
                header["fecha"] = match.group(1)
    
    # Special handling for client line ending with /
    # The line usually looks like: ABERTURAS Y CERRAMIENTOS ROSARIO SRL / CLUB JUAN Marcelo
    for line in lines:
        line_clean = clean_text(line)
        if "/" in line_clean and not re.search(r"\b\d{1,2}/\d{1,2}/\d{2,4}\b", line_clean) and "http" not in line_clean:
            # We assume the format is "CLIENTE / OBRA" or "CLIENTE/"
            # BUT wait, Fontela sometimes uses "CLIENTE / CLUB..." or just "CLIENTE /"
            parts = line_clean.split("/", 1)
            candidate = clean_text(parts[0])
            
            # If line starts with "Cotizado", it's a header for the state info, skip
            if candidate.lower().startswith("cotizado"):
                continue
                
            if len(candidate) > 3:
                header["cliente"] = candidate
                header["obra"] = "" # Obra is always manual
                break
                
    # Fallback to BUDGET # if found elsewhere
    if not header["presupuesto_numero"]:
        for line in lines:
            match = re.search(r"(?:presupuesto|pedido)\s*n[º°:]\s*#?(\d{5,})", line, re.IGNORECASE)
            if match:
                 header["presupuesto_numero"] = match.group(1)
                 break
    
    return header


def extract_items_from_table(table: List[List[str]]) -> List[Dict[str, Any]]:
    """Extract items from consolidated table."""
    if not table or len(table) < 2:
        return []
    
    items = []
    
    # Try to identify column indices
    headers = [clean_text(h or "").lower() for h in table[0]]
    
    # Look for common column names with expanded aliases
    col_map = {
        "descripcion": None,
        "material": None,
        "tipologia": None,
        "cantidad": None,
        "m2": None,
        "ml": None,
        "total": None
    }
    
    for idx, header in enumerate(headers):
        if any(x in header for x in ["descripcion", "descripción", "detalle", "designación"]):
            col_map["descripcion"] = idx
        elif "item" in header and len(header) <= 6:  # "Item" column (short)
            # If it's just "Item" by itself, might be item number, treat next column as descripcion
            if idx + 1 < len(headers):
                col_map["descripcion"] = idx + 1
        elif "material" in header:
            col_map["material"] = idx
        elif any(x in header for x in ["tipo", "tipología", "modelo"]):
            col_map["tipologia"] = idx
        elif any(x in header for x in ["cant", "cantidad", "unid", "uds"]):
            col_map["cantidad"] = idx
        elif any(x in header for x in ["m2", "m²", "superficie", "sup."]):
            col_map["m2"] = idx
        elif any(x in header for x in ["ml", "perímetro", "perimetro", "ml."]):
            col_map["ml"] = idx
        elif any(x in header for x in ["total", "precio", "importe"]):
            col_map["total"] = idx
    
    # Fallback heuristic: if we don't have a descripcion column, 
    # assume standard layout: Item# | Descripción | Cantidad | Total
    if col_map["descripcion"] is None and len(headers) >= 3:
        # For standardized budget PDFs with consistent 4-column layout
        if len(table[0]) >= 4:
            # Column 0: Item number
            # Column 1: Description  
            # Column 2: Cantidad
            # Column 3: Total
            col_map["descripcion"] = 1
            col_map["cantidad"] = 2
            col_map["total"] = 3
        elif len(table[0]) >= 3:
            # 3-column layout: Item | Description | Total
            col_map["descripcion"] = 1
            col_map["total"] = 2
        else:
            # Minimal layout
            col_map["descripcion"] = 1
            
    # Heuristic: If we have simple invalid columns (None) but detected Quantity,
    # assume the column after Quantity is Total pesos if available.
    if col_map["total"] is None and col_map["cantidad"] is not None:
         # Check if there is a column after quantity
         if col_map["cantidad"] + 1 < len(headers):
             col_map["total"] = col_map["cantidad"] + 1
             
    # NOTE: In most Fontela budgets, M2 and ML are NOT in the consolidated table.
    # They only appear in the footers and detailed paños tables.
    # If not found in the table, they will remain as Decimal(0) after normalization.
    # We will let the validator report them as discrepancies rather than backfilling.
    
    # Process data rows
    for row in table[1:]:
        if not row or len(row) == 0:
            continue
        
        # Skip total rows
        if any(clean_text(cell or "").lower().startswith("total") for cell in row):
            continue
        
        # Build item dict
        item = {}
        for key, idx in col_map.items():
            if idx is not None and idx < len(row):
                item[key] = row[idx]
            else:
                item[key] = ""
        
        # Only add if has descripcion
        if item.get("descripcion"):
            items.append(normalize_item_row(item))
    
    return items


def extract_panos_from_table(table: List[List[str]]) -> List[Dict[str, Any]]:
    """Extract paños from detailed table."""
    if not table or len(table) < 2:
        return []
    
    panos = []
    
    # Try to identify column indices
    # Scan first few rows to find the header row
    header_row_idx = 0
    headers = []
    
    for i in range(min(5, len(table))):
        row_text = "".join([str(c).lower() for c in table[i] if c])
        if "cantidad" in row_text or "ancho" in row_text:
            header_row_idx = i
            headers = [clean_text(h or "").lower() for h in table[i]]
            break
            
    if not headers:
         # Fallback to first row if no header found
         headers = [clean_text(h or "").lower() for h in table[0]]
    
    col_map = {
        "cantidad": None,
        "ancho": None,
        "alto": None,
        "superficie": None,
        "perimetro": None,
        "precio_unitario": None,
        "total": None
    }
    
    for idx, header in enumerate(headers):
        if "cant" in header:
            col_map["cantidad"] = idx
        elif "ancho" in header or "width" in header:
            col_map["ancho"] = idx
        elif "alto" in header or "height" in header:
            col_map["alto"] = idx
        elif "superficie" in header or "m2" in header or "m²" in header:
            col_map["superficie"] = idx
        elif "perímetro" in header or "perimetro" in header or "ml" in header:
            col_map["perimetro"] = idx
        elif "unitario" in header or "unit" in header:
            col_map["precio_unitario"] = idx
        elif "total" in header or "precio" in header:
            col_map["total"] = idx
    
    # Try to detect item separator (usually changes in description or material)
    current_item_index = 0
    
    # Process data rows
    for row in table[header_row_idx+1:]:
        if not row or len(row) == 0:
            continue
        
        # Skip total rows
        if any(clean_text(cell or "").lower().startswith("total") for cell in row):
            continue
        
        # Check if this is a new item header (legacy logic, kept but maybe less critical with sequential assignment)
        # Usually item headers have text in first column but no numeric data
        first_cell = clean_text(row[0] if row else "")
        has_numeric_data = False
        for cell in row:
            if cell and re.search(r"\d", str(cell)):
                has_numeric_data = True
                break
        
        # If row has descripcion-like text but no numbers, it's probably a new item
        if first_cell and len(first_cell) > 10 and not has_numeric_data:
            current_item_index += 1
            continue
        
        # Build paño dict
        pano = {}
        for key, idx in col_map.items():
            if idx is not None and idx < len(row):
                pano[key] = row[idx]
            else:
                pano[key] = ""
        
        # Only add if has ancho and alto
        if pano.get("ancho") and pano.get("alto"):
            panos.append(normalize_pano_row(pano, current_item_index))
    
    return panos


def extract_totals_from_text(text: str) -> Dict[str, str]:
    """Extract totals from text."""
    
    
    totals = {
        "m2": "",
        "ml": "",
        "pesos": ""
    }
    
    lines = text.split("\n")
    
    for line in lines:
        line_original = clean_text(line)
        line = line_original.lower()
        
        # Look for specific format: "Total superficie m2: 343.35"
        if "total superficie" in line and "m2" in line:
            match = re.search(r"total\s+superficie\s+m[2²]\s*:?\s*([\d.,]+)", line)
            if match:
                totals["m2"] = match.group(1)
        
        # Look for specific format: "Total perímetro ml: 275.98"
        if ("total" in line and "perímetro" in line) or ("total" in line and "perimetro" in line):
            match = re.search(r"total\s+(?:perímetro|perimetro)\s+(?:ml|m)\s*:?\s*([\d.,]+)", line)
            if match:
                totals["ml"] = match.group(1)
        
        # Generic total patterns (fallback)
        if "total" in line and not totals["m2"]:
            match = re.search(r"([\d.,]+)\s*m[2²]", line)
            if match:
                totals["m2"] = match.group(1)
        
        if "total" in line and not totals["ml"]:
            match = re.search(r"([\d.,]+)\s*ml", line)
            if match:
                totals["ml"] = match.group(1)
        
        # Look for pesos (usually the last number or with $ sign)
        if "total" in line and not totals["pesos"]:
            match = re.search(r"\$\s*([\d.,]+)", line)
            if match:
                totals["pesos"] = match.group(1)
        
        # Special case: Columnar layout (Headers on one line, Values on next)
        # "Total superficie m2: Total perimetro m: ..."
        # "134.66 376.78 ..."
        if "total superficie" in line and ("total perimetro" in line or "total perímetro" in line):
            # Check if values are on this line (handled by regex above) or next line
            # If not found by regex yet:
            if not totals["m2"] or not totals["ml"]:
                 try:
                     current_idx = lines.index(line_original) # Use original line for accurate index lookup
                     if current_idx + 1 < len(lines):
                         next_line = lines[current_idx+1]
                         # Find potential numbers in next line
                         # Filter out "Kg" or non-numeric if needed, or just take first few numbers
                         # Assuming M2 is first number, ML is second number
                         nums = re.findall(r"[\d.,]+", next_line)
                         # Filter to simple numbers (roughly)
                         nums = [n for n in nums if re.match(r"^\d+([.,]\d+)?$", n) and len(n) < 15]
                         
                         if len(nums) >= 1 and not totals["m2"]:
                             totals["m2"] = nums[0]
                         if len(nums) >= 2 and not totals["ml"]:
                             totals["ml"] = nums[1]
                 except ValueError:
                     pass # line not found in list? shouldn't happen
    
    return totals


def extract_totals_from_tables(tables: List[List[List[str]]]) -> Dict[str, str]:
    """Extract totals by scanning all table content."""
    totals = {
        "m2": "",
        "ml": "",
        "pesos": ""
    }
    
    # helper to check if value looks like a number
    def is_amount(s):
        return re.search(r"[\d.,]+", s) is not None
    
    # Iterate all tables, rows, cells
    for t_idx, table in enumerate(tables):
        if not table:
            continue
            
        for r_idx, row in enumerate(table):
            for c_idx, cell in enumerate(row):
                cell_text = clean_text(cell or "").lower()
                
                # Check M2
                if "total" in cell_text and ("superficie" in cell_text and "m2" in cell_text):
                    # Strategy 1: In same cell
                    match = re.search(r"[\d.,]+", cell_text.split(":")[-1])
                    if match and len(match.group(0)) > 1:
                         totals["m2"] = match.group(0)
                    # Strategy 2: Right cell
                    elif c_idx + 1 < len(row):
                        right = clean_text(row[c_idx+1] or "")
                        if is_amount(right):
                            totals["m2"] = right
                    # Strategy 3: Down cell
                    elif r_idx + 1 < len(table):
                        down = clean_text(table[r_idx+1][c_idx] or "")
                        if is_amount(down):
                            totals["m2"] = down
                            
                # Check ML (using 'm' or 'ml')
                if "total" in cell_text and ("perímetro" in cell_text or "perimetro" in cell_text):
                    # Strategy 1: In same cell
                    match = re.search(r"[\d.,]+", cell_text.split(":")[-1])
                    if match and len(match.group(0)) > 1:
                         totals["ml"] = match.group(0)
                    # Strategy 2: Right cell
                    elif c_idx + 1 < len(row):
                        right = clean_text(row[c_idx+1] or "")
                        if is_amount(right):
                            totals["ml"] = right
                    # Strategy 3: Down cell
                    elif r_idx + 1 < len(table):
                        down = clean_text(table[r_idx+1][c_idx] or "")
                        if is_amount(down):
                            totals["ml"] = down
                            
                # Check Pesos
                if "total" in cell_text and "$" in cell_text:
                     match = re.search(r"\$\s*([\d.,]+)", cell_text)
                     if match:
                         totals["pesos"] = match.group(1)
                elif "total" in cell_text and not totals["pesos"] and "m2" not in cell_text and "ml" not in cell_text:
                    # Generic total, maybe right or down
                     # Strategy 2: Right cell
                    if c_idx + 1 < len(row):
                        right = clean_text(row[c_idx+1] or "")
                        if "$" in right:
                             match = re.search(r"\$\s*([\d.,]+)", right)
                             if match: totals["pesos"] = match.group(1)
                    # Strategy 3: Down cell
                    if not totals["pesos"] and r_idx + 1 < len(table):
                        down = clean_text(table[r_idx+1][c_idx] or "")
                        if "$" in down:
                             match = re.search(r"\$\s*([\d.,]+)", down)
                             if match: totals["pesos"] = match.group(1)
    
    return totals


def extract_standard_budget_pdf(pdf_path: str) -> Dict[str, Any]:
    """
    Main extraction function for standard budget PDFs.
    
    Uses multi-strategy approach:
    1. pdfplumber (primary)
    2. camelot (fallback)
    3. tabula (fallback)
    
    Returns a validated package ready for database insertion.
    """
            
    # Calculate file hash
    with open(pdf_path, "rb") as f:
        file_content = f.read()
        file_hash = hashlib.sha256(file_content).hexdigest()
    
    pdf_filename = Path(pdf_path).name
    
    # Try pdfplumber first
    try:
        extracted = extract_with_pdfplumber(pdf_path)
    except Exception as e:
        # TODO: implement camelot/tabula fallback
        raise Exception(f"PDF extraction failed: {str(e)}")
    
    # Build the package
    package = {
        "meta": {
            "extraction_date": datetime.utcnow().isoformat(),
            "pdf_filename": pdf_filename,
            "pdf_hash": file_hash,
            "extractor_version": "1.0.0"
        },
        "acopio": {
            "numero": normalize_presupuesto_number(extracted["header"].get("presupuesto_numero", "")),
            "fecha_alta": normalize_date(extracted["header"].get("fecha", "")),
            "obra": extracted["header"].get("obra", ""),
            "cliente": extracted["header"].get("cliente", ""),
            **normalize_totals(extracted["totals"])
        },
        "presupuestos": [
            {
                "numero": normalize_presupuesto_number(extracted["header"].get("presupuesto_numero", "")),
                "fecha": normalize_date(extracted["header"].get("fecha", "")),
                "condiciones": extracted["header"].get("condiciones", ""),
                "estado": extracted["header"].get("estado", "")
            }
        ],
        "items": extracted["items"],
        "panos": extracted["panos"],
        "pedidos": [],
        "remitos": [],
        "imputaciones": [],
        "comprobantes": [],
        "afectaciones_acopio": [],
        "documentos": [
            {
                "tipo_documento": "presupuesto_original",
                "nombre_archivo": pdf_filename,
                "hash": file_hash
            }
        ],
        "warnings": []
    }
    
    
    # Sequential assignment of paños to items (as per plan)
    # We have a flat list of paños and a list of items with quantities.
    # We assign the first N paños to Item 1 where N is Item 1's quantity, and so on.
    
    current_pano_idx = 0
    total_panos = len(package["panos"])
    
    for idx, item in enumerate(package["items"]):
        try:
            qty = int(item.get("cantidad", 0))
        except:
            qty = 0
            
        # Assign next qty paños to this item
        # item_index is 1-based index corresponding to the item's position
        target_item_index = idx + 1
        
        # Assign paños to this item until we reach its quantity
        # item_index is 1-based index corresponding to the item's position
        target_item_index = idx + 1
        
        current_item_qty_assigned = 0
        
        while current_item_qty_assigned < qty and current_pano_idx < total_panos:
            pano = package["panos"][current_pano_idx]
            pano_qty = int(pano.get("cantidad", 1))
            
            # Assign this paño row to the current item
            pano["item_index"] = target_item_index
            current_pano_idx += 1
            current_item_qty_assigned += pano_qty
            
            # Note: If a single paño row causes overshoot (e.g. we needed 1 more but row has 2),
            # strictly speaking this shouldn't happen in a clean budget, but if it does, 
            # we assign the whole row to this item.
            
    # --- CONTROL CALCULATIONS (Re-enabled) ---
    # Calculate totals from sums for internal consistency
    calculated_acopio_m2 = Decimal("0")
    calculated_acopio_ml = Decimal("0")
    calculated_acopio_pesos = Decimal("0")
    
    for idx, item in enumerate(package["items"]):
        item_index = idx + 1
        item_panos = [p for p in package["panos"] if p.get("item_index") == item_index]
        if item_panos:
            sum_m2 = sum(Decimal(str(p["superficie_m2"])) for p in item_panos)
            sum_ml = sum(Decimal(str(p["perimetro_ml"])) for p in item_panos)
            sum_pesos = sum(Decimal(str(p["precio_total"])) for p in item_panos)
            
            # Backfill item totals if they are 0 or significantly different
            # (In this case, we prioritize the sum if extracted was 0)
            if Decimal(str(item.get("total_m2", 0))) == 0:
                item["total_m2"] = float(sum_m2)
            if Decimal(str(item.get("total_ml", 0))) == 0:
                item["total_ml"] = float(sum_ml)
            if Decimal(str(item.get("total_pesos", 0))) == 0:
                item["total_pesos"] = float(sum_pesos)
                
            calculated_acopio_m2 += sum_m2
            calculated_acopio_ml += sum_ml
            calculated_acopio_pesos += sum_pesos

    # Update acopio totals if they were missing or zero
    acopio = package["acopio"]
    if Decimal(str(acopio.get("total_m2", 0))) == 0:
        acopio["total_m2"] = float(calculated_acopio_m2)
    if Decimal(str(acopio.get("total_ml", 0))) == 0:
        acopio["total_ml"] = float(calculated_acopio_ml)
    if Decimal(str(acopio.get("total_pesos", 0))) == 0:
        acopio["total_pesos"] = float(calculated_acopio_pesos)
    # ------------------------------------------

    # Validation checks re-enabled
    warnings = validate_package(package)
    package["warnings"] = warnings
    
    return package
