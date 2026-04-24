"""PDF extractor for Fontela-format standard budget PDFs using structural table extraction.

Refactored to use pdfplumber's table detection for maximum robustness against 
multi-line descriptions and complex layouts.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from decimal import Decimal, ROUND_HALF_UP, InvalidOperation
from pathlib import Path
from typing import List, Optional, Dict, Any

import pdfplumber


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
        headers = [str(h).lower().strip() for h in table[0] if h]
        if "contacto" in headers or "estado" in headers:
            row = table[1]
            
            # Intentar leer empresa directamente de la tabla si existe la columna
            try:
                idx_emp = headers.index("empresa")
                raw_val = str(row[idx_emp]).strip() if row[idx_emp] else ""
                if raw_val:
                    raw_empresa_found = raw_val
                    if "/" in raw_val:
                        parts = raw_val.split("/", 1)
                        empresa = parts[0].strip()
                        potential_obra_from_empresa = parts[1].strip()
                    else:
                        empresa = raw_val
                        potential_obra_from_empresa = ""
            except (ValueError, IndexError): pass

            try:
                idx_cont = headers.index("contacto")
                contacto = str(row[idx_cont]).strip() if row[idx_cont] else ""
            except (ValueError, IndexError): pass
            
            try:
                idx_est = headers.index("estado")
                estado = str(row[idx_est]).strip() if row[idx_est] else ""
            except (ValueError, IndexError): pass
            
            try:
                idx_cot = headers.index("cotizado por")
                cotizado_por = str(row[idx_cot]).strip() if row[idx_cot] else ""
            except (ValueError, IndexError): pass
            
            try:
                idx_fecha = headers.index("fecha de aprobación")
                fecha_aprobacion = str(row[idx_fecha]).strip() if row[idx_fecha] else None
            except (ValueError, IndexError): pass
            
            break

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
    """Itera sobre todas las tablas de paños y las asocia a los ítems maestros."""
    item_map = {it.numero_item: it for it in items}
    
    current_item_no = None
    
    for page in pdf.pages:
        # Obtenemos tablas con coordenadas
        table_objs = page.find_tables()
        for t_obj in table_objs:
            data = t_obj.extract()
            if not data or not data[0]: continue
            
            headers = [str(h).lower() if h else "" for h in data[0]]
            
            # 1. CASO: Tabla de Paños (Detallada)
            if "ancho" in headers and "alto" in headers:
                # Buscar el número de ítem arriba de la tabla
                # Registramos el texto de un área mayor (hasta 100 pixels arriba)
                top = t_obj.bbox[1]
                # Buscamos en una ventana sobre la tabla
                above_area = (0, max(0, top - 100), page.width, top)
                above_text = page.within_bbox(above_area).extract_text() or ""
                
                # Buscamos el patrón "Nro_Item Descripcion" (ej: "2 Laminado...")
                # O simplemente el número más cercano al encabezado de la tabla
                lines = [ln.strip() for ln in above_text.splitlines() if ln.strip()]
                found_new_item = False
                for ln in reversed(lines):
                    m = re.match(r"^(\d+)\s+", ln)
                    if m:
                        possible_no = int(m.group(1))
                        if possible_no in item_map:
                            current_item_no = possible_no
                            found_new_item = True
                            break
                    # Caso donde el número está solo en la línea
                    if ln.isdigit():
                        possible_no = int(ln)
                        if possible_no in item_map:
                            current_item_no = possible_no
                            found_new_item = True
                            break
                
                if current_item_no is None:
                    continue
                
                target_item = item_map[current_item_no]
                
                # Extraer filas
                for row in data[1:]:
                    if not row or not any(row): continue
                    if "Totales" in str(row[0]):
                        # Capturar subtotales de la fila si están presentes
                        if len(row) >= 5:
                            if q2(parse_ar(row[3])) > 0: target_item.total_m2 = parse_ar(row[3])
                            if q2(parse_ar(row[4])) > 0: target_item.total_ml = parse_ar(row[4])
                        continue
                    
                    # Ignorar filas de encabezado repetidas (page breaks)
                    if "cantidad" in str(row[0]).lower(): continue
                    
                    try:
                        cant = int(parse_ar(row[0]))
                        if cant <= 0:
                            continue
                            
                        # Intentar parsear dimensiones
                        ancho = 0
                        alto = 0
                        try:
                            ancho = int(parse_ar(row[1]))
                            alto = int(parse_ar(row[2]))
                        except (ValueError, IndexError):
                            pass
                            
                        if ancho > 0 and alto > 0:
                            # Es un PAÑO productivo
                            target_item.panos.append(PdfPane(
                                row_no=len(target_item.panos) + 1,
                                cantidad=cant,
                                ancho_mm=ancho,
                                alto_mm=alto,
                                superficie_m2=parse_ar(row[3]) if len(row) > 3 else Decimal("0"),
                                perimetro_ml=parse_ar(row[4]) if len(row) > 4 else Decimal("0"),
                                denominacion=str(row[5]).strip() if len(row) > 5 and row[5] and str(row[5]) != "-" else None,
                                precio_unitario=parse_ar(row[6]) if len(row) > 6 else Decimal("0"),
                                precio_total=parse_ar(row[7]) if len(row) > 7 else Decimal("0")
                            ))
                        else:
                            # Es un ADICIONAL o SERVICIO
                            desc = str(row[1]).strip() if len(row) > 1 and row[1] else ""
                            # Algunos PDFs tienen el nombre de la pieza (Laminado...) sin medidas. Si es el nombre del ítem, lo ignoramos para evitar duplicar.
                            # Pero si tiene precios al final, probablemente es un adicional facturable.
                            if not desc or desc == "-":
                                continue
                                
                            p_tot = Decimal("0")
                            p_uni = Decimal("0")
                            
                            non_empty = [c for c in row if c and str(c).strip() and str(c).strip() != "-"]
                            if len(non_empty) >= 3:
                                try:
                                    p_tot = parse_ar(non_empty[-1])
                                    p_uni = parse_ar(non_empty[-2])
                                except ValueError:
                                    pass
                                    
                            # Solo lo agregamos si tiene impacto económico para evitar capturar títulos descriptivos como adicionales
                            if p_tot > 0 or p_uni > 0:
                                target_item.adicionales.append(PdfAdicional(
                                    row_no=len(target_item.adicionales) + 1,
                                    cantidad=cant,
                                    descripcion=desc,
                                    precio_unitario=p_uni,
                                    precio_total=p_tot
                                ))
                    except (ValueError, IndexError):
                        continue

            # 2. CASO: Tabla de Totales (a veces viene separada)
            elif any("totales" in str(c).lower() for c in data[0]):
                if current_item_no and current_item_no in item_map:
                    # Si la fila actual es "Totales" o la siguiente lo es
                    target_item = item_map[current_item_no]
                    for row in data:
                        if any("totales" in str(c).lower() for c in row) or (len(row) >= 4 and parse_ar(row[2]) > 0):
                            if len(row) >= 4:
                                val_m2 = parse_ar(row[2])
                                val_ml = parse_ar(row[3])
                                if val_m2 > 0: target_item.total_m2 = val_m2
                                if val_ml > 0: target_item.total_ml = val_ml
                            if len(row) >= 6: # A veces el total $ está más a la derecha
                                val_pesos = parse_ar(row[5])
                                if val_pesos > 0: target_item.total_pesos = val_pesos


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
            warnings.append(f"Ítem {item.numero_item}: Diferencia en cantidad ({sum_cant} vs {item.cantidad})")

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
