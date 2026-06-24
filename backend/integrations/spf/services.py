from decimal import Decimal
import re
from sqlalchemy.orm import Session
from sqlalchemy import func, or_, union_all, cast, String
from .models import (
    SpfPedido, SpfItem, SpfItemMedida, SpfItemComplemento,
    SpfCliente, SpfVComplemento, SpfComprobanteTemp,
    SpfTangoHeader, SpfTangoHeaderHistorico,
    SpfTangoBody, SpfTangoBodyHistorico,
    SpfLineaTangoFacturada, SpfLineaTangoRemitida
)
from services.proceso_inference import (
    PROCESS_FIELDS,
    PROCESS_UNITS,
    infer_item_processes_from_texts,
)
from services.composicion_normalization import normalizar_composicion

# Status mapping for SpfPedido.estado_id
ESTADOS_PEDIDO = {
    1: "Borrador",
    2: "Activo",
    3: "Finalizado",
    4: "Anulado",
    5: "Pausado",
    6: "Preactivo"
}



def _to_decimal(value) -> Decimal:
    if value is None:
        return Decimal("0")
    if isinstance(value, Decimal):
        return value
    return Decimal(str(value))


def _to_float(value) -> float:
    return float(_to_decimal(value))


def _presupuesto_lookup_values(v_presupuesto_id: str):
    raw_value = str(v_presupuesto_id or "").strip()
    text_values = {raw_value}
    numeric_value = None

    if raw_value.isdigit():
        numeric_value = int(raw_value)
        text_values.add(str(numeric_value))
        text_values.add(str(numeric_value).zfill(9))

    return numeric_value, list(text_values)


def _normalize_presupuesto_id(value: str | int | None) -> str:
    raw_value = str(value or "").strip()
    if raw_value.isdigit():
        return str(int(raw_value)).zfill(9)
    return raw_value


def _clean_spf_text(value) -> str | None:
    if value is None:
        return None
    cleaned = re.sub(r"\s+", " ", str(value).strip())
    return cleaned or None


def _spf_cliente_display_name(cliente) -> str:
    if not cliente:
        return "Desconocido"

    for attr in ("razon_social", "nombre_corto", "apellido", "nombre", "descripcion"):
        value = _clean_spf_text(getattr(cliente, attr, None))
        if value:
            return value

    return "Desconocido"


def _empresa_from_talonario(talonario: str | None) -> str | None:
    if not talonario:
        return None
    if "Tango A" in talonario:
        return "Fontela"
    if "Tango B" in talonario:
        return "Viviana"
    return talonario


def _dedupe_comprobantes(comprobantes):
    out = []
    seen = set()

    for comprobante in comprobantes:
        key = (
            comprobante.nro_factura or "",
            comprobante.nro_remito or "",
            comprobante.talonario or "",
        )
        if key == ("", "", "") or key in seen:
            continue

        seen.add(key)
        out.append({
            "nro_factura": comprobante.nro_factura,
            "nro_remito": comprobante.nro_remito,
            "empresa": _empresa_from_talonario(comprobante.talonario),
        })

    return out


def _get_complement_names(db: Session, items):
    complement_ids = {
        comp.v_complemento_id
        for item in items
        for comp in item.complementos
        if comp.v_complemento_id
    }
    if not complement_ids:
        return {}

    complements = db.query(SpfVComplemento).filter(
        SpfVComplemento.id.in_(list(complement_ids))
    ).all()
    return {comp.id: comp.nombre for comp in complements}


def summarize_spf_items_processes(db: Session, items):
    """
    Summarize SPF items by reference-price process.

    A process consumes the item's full m2 or ml according to PROCESS_UNITS,
    matching the summary spreadsheet model.
    """
    totals = {field: Decimal("0") for field in PROCESS_FIELDS}
    complement_names = _get_complement_names(db, items)

    for item in items:
        item_m2 = sum(_to_decimal(med.superficie) for med in item.medidas)
        item_ml = sum(_to_decimal(med.perimtero) for med in item.medidas)
        texts = [
            item.descripcion,
            *(med.denominacion for med in item.medidas),
            *(
                complement_names.get(comp.v_complemento_id, f"Complemento {comp.v_complemento_id}")
                for comp in item.complementos
            ),
        ]
        inferred = infer_item_processes_from_texts(texts)

        for field in PROCESS_FIELDS:
            if not inferred[field]:
                continue
            totals[field] += item_m2 if PROCESS_UNITS[field] == "m2" else item_ml

    return [
        {
            "proceso": field,
            "unidad": PROCESS_UNITS[field],
            "cantidad": _to_float(totals[field]),
        }
        for field in PROCESS_FIELDS
        if totals[field] != 0
    ]


def summarize_spf_item_processes(db: Session, item, complement_names=None):
    """Summarize one SPF item by process and return its normalized composition."""
    complement_names = complement_names or _get_complement_names(db, [item])
    item_m2 = sum(_to_decimal(med.superficie) for med in item.medidas)
    item_ml = sum(_to_decimal(med.perimtero) for med in item.medidas)
    texts = [
        item.descripcion,
        *(med.denominacion for med in item.medidas),
        *(
            complement_names.get(comp.v_complemento_id, f"Complemento {comp.v_complemento_id}")
            for comp in item.complementos
        ),
    ]
    composicion = normalizar_composicion(texts)
    procesos = []
    for field in PROCESS_FIELDS:
        if not composicion.procesos[field]:
            continue

        cantidad = item_m2 if PROCESS_UNITS[field] == "m2" else item_ml
        if cantidad == 0:
            continue

        procesos.append({
            "proceso": field,
            "unidad": PROCESS_UNITS[field],
            "cantidad": _to_float(cantidad),
        })

    return procesos, composicion


def search_presupuestos(db: Session, query: str):
    """
    Busca presupuestos únicos en SPF.
    Un presupuesto es el origen comercial de un acopio.
    Se puede buscar por el ID del presupuesto o por un número de pedido asociado a él.
    """
    if not query:
        return []

    # Search by v_presupuesto_id directly in the items
    items_query = db.query(SpfItem.v_presupuesto_id).filter(
        cast(SpfItem.v_presupuesto_id, String).ilike(f"%{query}%")
    ).distinct()
    
    # Or by matching nro_pedido in the pedidos
    pedidos_query = db.query(SpfItem.v_presupuesto_id).join(SpfPedido, SpfItem.pedido_id == SpfPedido.id).filter(
        cast(SpfPedido.nro_pedido, String).ilike(f"%{query}%")
    ).distinct()

    results = items_query.union(pedidos_query).limit(20).all()
    # Apply zfill to 9 for the returned results to match local system expectations
    return [str(r[0]).zfill(9) for r in results if r[0]]


def get_presupuesto_details(db: Session, v_presupuesto_id: str):
    """
    Get full details and aggregates for a given v_presupuesto_id.
    Calculates m2, ml, and pesos based on items, medidas, and complementos.
    """
    presupuesto_int, presupuesto_texts = _presupuesto_lookup_values(v_presupuesto_id)
    normalized_presupuesto_id = _normalize_presupuesto_id(v_presupuesto_id)
    item_filters = [cast(SpfItem.v_presupuesto_id, String).in_(presupuesto_texts)]
    if presupuesto_int is not None:
        item_filters.append(SpfItem.v_presupuesto_id == presupuesto_int)

    items = db.query(SpfItem).filter(or_(*item_filters)).all()
    
    if not items:
        return None

    total_m2 = Decimal("0")
    total_ml = Decimal("0")
    total_pesos = Decimal("0")
    
    pedidos_set = set()
    cliente_id = None
    obra_nombre = None
    
    items_out = []
    
    for item in items:
        if item.pedido:
            pedidos_set.add(item.pedido.nro_pedido or str(item.pedido.id))
            if cliente_id is None:
                cliente_id = item.pedido.cliente_id
            if not obra_nombre and item.pedido.nrooc:
                obra_nombre = item.pedido.nrooc
                
        item_qty = 0
        panos_out = []
        item_total_m2 = Decimal("0")
        item_total_ml = Decimal("0")
        item_total_pesos = Decimal("0")
                
        for medida in item.medidas:
            qty = medida.cantidad or 1
            item_qty += qty
            
            sup = _to_decimal(medida.superficie)
            per = _to_decimal(medida.perimtero)
            tot = _to_decimal(medida.total_item)
            
            item_total_m2 += sup
            item_total_ml += per
            item_total_pesos += tot
            
            panos_out.append({
                "cantidad": qty,
                "ancho": _to_float(medida.ancho),
                "alto": _to_float(medida.alto),
                "superficie_m2": _to_float(sup / _to_decimal(qty)) if qty > 0 else 0.0,
                "perimetro_ml": _to_float(per / _to_decimal(qty)) if qty > 0 else 0.0,
                "precio_total": _to_float(tot),
                "precio_unitario": _to_float(tot / _to_decimal(qty)) if qty > 0 else 0.0
            })
            
        adicionales_out = []
        for comp in item.complementos:
            qty = comp.cantidad or 1
            unit_price = _to_decimal(comp.total_complemento)
            tot_comp = unit_price * _to_decimal(qty)
            item_total_pesos += tot_comp
            
            adicionales_out.append({
                "cantidad": qty,
                "descripcion": f"Complemento {comp.v_complemento_id}", # Or lookup name if needed
                "precio_total": _to_float(tot_comp),
                "precio_unitario": _to_float(unit_price)
            })

        items_out.append({
            "descripcion": item.descripcion or f"Item {item.id}",
            "cantidad": item_qty or 1,
            "total_m2": _to_float(item_total_m2),
            "total_ml": _to_float(item_total_ml),
            "total_pesos": _to_float(item_total_pesos),
            "panos": panos_out,
            "adicionales": adicionales_out
        })
        
        total_m2 += item_total_m2
        total_ml += item_total_ml
        total_pesos += item_total_pesos

    cliente_nombre = "Desconocido"
    if cliente_id:
        cliente_db = db.query(SpfCliente).filter(SpfCliente.id == cliente_id).first()
        if cliente_db:
            cliente_nombre = _spf_cliente_display_name(cliente_db)

    return {
        "v_presupuesto_id": normalized_presupuesto_id,
        "cliente_id": cliente_id,
        "cliente_nombre": cliente_nombre,
        "obra_nombre": obra_nombre or f"Presupuesto {normalized_presupuesto_id}",
        "pedidos_relacionados": list(pedidos_set),
        "total_m2": _to_float(total_m2),
        "total_ml": _to_float(total_ml),
        "total_pesos": _to_float(total_pesos),
        "items_count": len(items_out),
        "items": items_out
    }


def get_avance_comercial_acopio(db: Session, v_presupuesto_id: str, nro_pedidos: list[str] | None = None):
    """
    Obtiene el avance comercial y documental detallado de un acopio (presupuesto).
    Analiza todos los pedidos de producción vinculados a este presupuesto único y
    consolida su estado de facturación y remitos.
    """
    # 1. Get items and their orders. SPF installations differ on whether the
    # budget id is stored as text with leading zeros or as a plain integer.
    presupuesto_int, presupuesto_texts = _presupuesto_lookup_values(v_presupuesto_id)
    pedido_ids_por_presupuesto = []
    if presupuesto_int is not None:
        pedido_ids_por_presupuesto = [
            row[0]
            for row in db.query(SpfPedido.id)
            .filter(SpfPedido.id_presupuesto == presupuesto_int)
            .all()
        ]

    pedido_ids_por_numero = []
    pedido_texts = [
        str(nro_pedido).strip()
        for nro_pedido in (nro_pedidos or [])
        if str(nro_pedido or "").strip()
    ]
    pedido_ints = [int(nro_pedido) for nro_pedido in pedido_texts if nro_pedido.isdigit()]
    pedido_filters = []
    if pedido_ints:
        pedido_filters.append(SpfPedido.id.in_(pedido_ints))
        pedido_filters.append(SpfPedido.nro_pedido.in_(pedido_ints))
    if pedido_texts:
        pedido_filters.append(cast(SpfPedido.nro_pedido, String).in_(pedido_texts))
        pedido_filters.append(SpfPedido.nrooc.in_(pedido_texts))
    if pedido_filters:
        pedido_ids_por_numero = [
            row[0]
            for row in db.query(SpfPedido.id)
            .filter(or_(*pedido_filters))
            .all()
        ]

    pedido_ids_relacionados = list(set(pedido_ids_por_presupuesto + pedido_ids_por_numero))

    item_filters = [cast(SpfItem.v_presupuesto_id, String).in_(presupuesto_texts)]
    if pedido_ids_relacionados:
        item_filters.append(SpfItem.pedido_id.in_(pedido_ids_relacionados))

    items = db.query(SpfItem).filter(or_(*item_filters)).all()
    if not items:
        return None

    # Identify related orders and client
    pedido_ids = list(set(item.pedido_id for item in items if item.pedido_id))
    pedidos = db.query(SpfPedido).filter(SpfPedido.id.in_(pedido_ids)).all() if pedido_ids else []
    
    cliente_map = {}
    cliente_ids = list(set(p.cliente_id for p in pedidos if p.cliente_id))
    if cliente_ids:
        clientes = db.query(SpfCliente).filter(SpfCliente.id.in_(cliente_ids)).all()
        cliente_map = {c.id: _spf_cliente_display_name(c) for c in clientes}

    # 2. Map Complement names
    complement_ids = []
    for item in items:
        for c in item.complementos:
            complement_ids.append(c.v_complemento_id)
    
    complement_names = {}
    if complement_ids:
        v_comps = db.query(SpfVComplemento).filter(SpfVComplemento.id.in_(list(set(complement_ids)))).all()
        complement_names = {vc.id: vc.nombre for vc in v_comps}

    # 3. Handle Billing & Remitos (Tango Unions)
    # We query the bodies related to these items or pedidos
    # This part can be complex due to polymorphic links.
    
    # helper to process billing/dispatch per line
    def get_line_progress(item_id: int, item_type: str, total_qty_expected):
        # Find bodies in union
        bodies = db.query(SpfTangoBody).filter(
            SpfTangoBody.linea_item_id == item_id,
            SpfTangoBody.linea_item_type == item_type
        ).all()
        hist_bodies = db.query(SpfTangoBodyHistorico).filter(
            SpfTangoBodyHistorico.linea_item_id == item_id,
            SpfTangoBodyHistorico.linea_item_type == item_type
        ).all()
        
        all_body_ids = [b.id for b in bodies] + [b.id for b in hist_bodies]
        if not all_body_ids:
            return Decimal("0"), Decimal("0"), []

        # Sum facturado/remitido
        f_sum = db.query(func.sum(SpfLineaTangoFacturada.cantidad_ya_facturada)).filter(
            SpfLineaTangoFacturada.tango_body_id.in_(all_body_ids)
        ).scalar() or Decimal("0")
        
        r_sum = db.query(func.sum(SpfLineaTangoRemitida.cantidad_ya_remitida)).filter(
            SpfLineaTangoRemitida.tango_body_id.in_(all_body_ids)
        ).scalar() or Decimal("0")

        # Get comprobantes associated
        comp_fact = db.query(SpfComprobanteTemp).join(
            SpfLineaTangoFacturada, SpfComprobanteTemp.id == SpfLineaTangoFacturada.comprobante_temp_id
        ).filter(SpfLineaTangoFacturada.tango_body_id.in_(all_body_ids)).all()
        
        comp_remit = db.query(SpfComprobanteTemp).join(
            SpfLineaTangoRemitida, SpfComprobanteTemp.id == SpfLineaTangoRemitida.comprobante_temp_id
        ).filter(SpfLineaTangoRemitida.tango_body_id.in_(all_body_ids)).all()
        
        comprobantes = _dedupe_comprobantes(comp_fact + comp_remit)

        expected = _to_decimal(total_qty_expected)
        perc_f = (_to_decimal(f_sum) / expected * Decimal("100")) if expected > 0 else Decimal("0")
        perc_r = (_to_decimal(r_sum) / expected * Decimal("100")) if expected > 0 else Decimal("0")
        
        return min(perc_f, Decimal("100")), min(perc_r, Decimal("100")), comprobantes

    # 4. Construct Output
    pedidos_out = []
    global_tot = Decimal("0")
    global_fact = Decimal("0")
    global_remit = Decimal("0")
    for p in pedidos:
        p_items = [it for it in items if it.pedido_id == p.id]
        items_detail = []
        pedido_comprobantes = _dedupe_comprobantes(
            db.query(SpfComprobanteTemp)
            .filter(SpfComprobanteTemp.pedido_id == p.id)
            .all()
        )
        
        for it in p_items:
            # Item Medidas
            for med in it.medidas:
                qty = med.cantidad or 1
                qty_decimal = _to_decimal(qty)
                sup = _to_decimal(med.superficie)
                tot = _to_decimal(med.total_item)
                
                # Based on requirement: superficie is subtotal (total of the line)
                # precio por m2 = total_item / superficie
                # precio unitario = total_item / cantidad
                
                pf, pr, comps = get_line_progress(med.id, 'SpfPedido::ItemMedida', qty)
                global_tot += tot
                global_fact += tot * pf / Decimal("100")
                global_remit += tot * pr / Decimal("100")
                
                items_detail.append({
                    "tipo": "Medida",
                    "descripcion": med.denominacion or it.descripcion,
                    "cantidad": qty,
                    "importe_total": _to_float(tot),
                    "precio_unitario": _to_float(tot / qty_decimal) if qty > 0 else 0.0,
                    "precio_m2": _to_float(tot / sup) if sup > 0 else 0.0,
                    "avance_facturado": _to_float(pf),
                    "avance_remitido": _to_float(pr),
                    "comprobantes": comps
                })
            
            # Item Complementos
            for comp in it.complementos:
                qty = comp.cantidad or 1
                unit_price = _to_decimal(comp.total_complemento)
                tot = unit_price * _to_decimal(qty)
                desc = complement_names.get(comp.v_complemento_id, f"Complemento {comp.v_complemento_id}")
                
                pf, pr, comps = get_line_progress(comp.id, 'SpfPedido::ItemComplemento', qty)
                global_tot += tot
                global_fact += tot * pf / Decimal("100")
                global_remit += tot * pr / Decimal("100")
                
                items_detail.append({
                    "tipo": "Complemento",
                    "descripcion": desc,
                    "cantidad": qty,
                    "importe_total": _to_float(tot),
                    "precio_unitario": _to_float(unit_price),
                    "avance_facturado": _to_float(pf),
                    "avance_remitido": _to_float(pr),
                    "comprobantes": comps
                })

        pedidos_out.append({
            "id": p.id,
            "nro_pedido": p.nro_pedido or str(p.id),
            "estado": ESTADOS_PEDIDO.get(p.estado_id, f"Estado {p.estado_id}"),
            "cliente": cliente_map.get(p.cliente_id, "Desconocido"),
            "comprobantes": pedido_comprobantes,
            "items": items_detail
        })

    return {
        "v_presupuesto_id": _normalize_presupuesto_id(v_presupuesto_id),
        "cliente": pedidos_out[0]["cliente"] if pedidos_out else "Desconocido",
        "obra": (pedidos[0].nrooc or "S/D") if pedidos else "S/D",
        "resumen": {
            "importe_total": _to_float(global_tot),
            "facturado_total": _to_float(global_fact),
            "remitido_total": _to_float(global_remit),
            "porcentaje_facturado": _to_float(global_fact / global_tot * Decimal("100")) if global_tot > 0 else 0.0,
            "porcentaje_remitido": _to_float(global_remit / global_tot * Decimal("100")) if global_tot > 0 else 0.0,
        },
        "pedidos": pedidos_out
    }


def get_pedido_for_imputation(db: Session, nro_pedido: str):
    """
    Busca un pedido de producción específico en SPF para registrar una entrega/consumo.
    Un pedido representa una ejecución (parcial o total) del presupuesto de acopio.
    """
    query = db.query(SpfPedido)
    
    # Try exact matches in various fields
    pedido = None
    
    # If numeric, try ID first (per user specialized info) then other foreign IDs
    if nro_pedido.isdigit():
        val = int(nro_pedido)
        # Prioritize ID match
        pedido = query.filter(SpfPedido.id == val).first()
        if not pedido:
            pedido = query.filter(or_(
                SpfPedido.nro_pedido == val,
                SpfPedido.id_presupuesto == val
            )).order_by(SpfPedido.id.desc()).first()
        
    # If still not found or not numeric, try nrooc
    if not pedido:
        pedido = query.filter(SpfPedido.nrooc == nro_pedido).first()
        
    # Final fallback: partial match on nrooc or id_presupuesto (as string)
    if not pedido:
        pedido = query.filter(or_(
            SpfPedido.nrooc.like(f"%{nro_pedido}%"),
            cast(SpfPedido.id_presupuesto, String).like(f"%{nro_pedido}%")
        )).order_by(SpfPedido.id.desc()).first()
        
    if not pedido:
        return None

    # Get budget ID (Commercial origin)
    # We prioritize the id_presupuesto from the pedido table, then fall back to items
    v_presupuesto_id = str(pedido.id_presupuesto).zfill(9) if pedido.id_presupuesto else None

    # Get items for totals
    items = db.query(SpfItem).filter(SpfItem.pedido_id == pedido.id).all()
    
    total_m2 = Decimal("0")
    total_ml = Decimal("0")
    total_pesos = Decimal("0")
    total_qty = 0
    items_out = []
    complement_names = _get_complement_names(db, items)
    
    for it in items:
        if not v_presupuesto_id and it.v_presupuesto_id:
            v_presupuesto_id = str(it.v_presupuesto_id).zfill(9)

        item_m2 = Decimal("0")
        item_ml = Decimal("0")
        item_pesos = Decimal("0")
        item_qty = 0

        for med in it.medidas:
            item_m2 += _to_decimal(med.superficie) # Already subtotal from requirement
            item_ml += _to_decimal(med.perimtero)
            item_pesos += _to_decimal(med.total_item)
            item_qty += (med.cantidad or 0)
            
        for comp in it.complementos:
            qty = comp.cantidad or 1
            unit_price = _to_decimal(comp.total_complemento)
            item_pesos += unit_price * _to_decimal(qty)
            # The units of adicionales should NOT count towards physical units consumed

        item_procesos, composicion = summarize_spf_item_processes(db, it, complement_names)
        items_out.append({
            "id": it.id,
            "v_item_id": it.v_item_id,
            "descripcion": it.descripcion or f"Item {it.id}",
            "total_m2": _to_float(item_m2),
            "total_ml": _to_float(item_ml),
            "total_pesos": _to_float(item_pesos),
            "total_unidades": item_qty,
            "procesos": item_procesos,
            "composicion": {
                "normalizada": composicion.texto_normalizado,
                "firma": composicion.firma,
                "componentes": list(composicion.componentes),
                "procesos": composicion.procesos,
            },
        })

        total_m2 += item_m2
        total_ml += item_ml
        total_pesos += item_pesos
        total_qty += item_qty

    # Resolve issuing company
    talonarios = db.query(SpfComprobanteTemp.talonario).filter(
        SpfComprobanteTemp.pedido_id == pedido.id
    ).all()
    
    empresa = "Desconocida"
    if talonarios:
        talonarios_str = " ".join([t[0] or "" for t in talonarios])
        if "Tango A" in talonarios_str:
            empresa = "Fontela"
        elif "Tango B" in talonarios_str:
            empresa = "Viviana"

    return {
        "id": pedido.id,
        "nro_pedido": pedido.nro_pedido or str(pedido.id),
        "nrooc": pedido.nrooc,
        "v_presupuesto_id": v_presupuesto_id,
        "estado_id": pedido.estado_id,
        "estado": ESTADOS_PEDIDO.get(pedido.estado_id, f"Estado {pedido.estado_id}"),

        "empresa": empresa,
        "procesos": summarize_spf_items_processes(db, items),
        "items": items_out,
        "totals": {
            "m2": _to_float(total_m2),
            "ml": _to_float(total_ml),
            "pesos": _to_float(total_pesos),
            "unidades": total_qty
        }
    }
