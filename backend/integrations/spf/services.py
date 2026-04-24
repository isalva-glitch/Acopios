from sqlalchemy.orm import Session
from sqlalchemy import func, or_, union_all, cast, String
from .models import (
    SpfPedido, SpfItem, SpfItemMedida, SpfItemComplemento,
    SpfCliente, SpfVComplemento, SpfComprobanteTemp,
    SpfTangoHeader, SpfTangoHeaderHistorico,
    SpfTangoBody, SpfTangoBodyHistorico,
    SpfLineaTangoFacturada, SpfLineaTangoRemitida
)

# Status mapping for SpfPedido.estado_id
ESTADOS_PEDIDO = {
    1: "Borrador",
    2: "Activo",
    3: "Finalizado",
    4: "Anulado",
    5: "Pausado",
    6: "Preactivo"
}


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
    # Local system uses "000209205" but SPF uses integer 209205. If numeric, strip zeros or parse int.
    search_id = int(v_presupuesto_id) if v_presupuesto_id.isdigit() else v_presupuesto_id

    items = db.query(SpfItem).filter(SpfItem.v_presupuesto_id == search_id).all()
    
    if not items:
        return None

    total_m2 = 0.0
    total_ml = 0.0
    total_pesos = 0.0
    
    pedidos_set = set()
    cliente_id = None
    
    items_out = []
    
    for item in items:
        if item.pedido:
            pedidos_set.add(item.pedido.nro_pedido or str(item.pedido.id))
            if cliente_id is None:
                cliente_id = item.pedido.cliente_id
                
        item_qty = 0
        panos_out = []
        item_total_m2 = 0.0
        item_total_ml = 0.0
        item_total_pesos = 0.0
                
        for medida in item.medidas:
            qty = medida.cantidad or 1
            item_qty += qty
            
            sup = float(medida.superficie or 0)
            per = float(medida.perimtero or 0)
            tot = float(medida.total_item or 0)
            
            item_total_m2 += sup
            item_total_ml += per
            item_total_pesos += tot
            
            panos_out.append({
                "cantidad": qty,
                "ancho": float(medida.ancho or 0),
                "alto": float(medida.alto or 0),
                "superficie_m2": sup / qty if qty > 0 else 0,
                "perimetro_ml": per / qty if qty > 0 else 0,
                "precio_total": tot,
                "precio_unitario": tot / qty if qty > 0 else 0.0
            })
            
        adicionales_out = []
        for comp in item.complementos:
            qty = comp.cantidad or 1
            unit_price = float(comp.total_complemento or 0)
            tot_comp = unit_price * qty
            item_total_pesos += tot_comp
            
            adicionales_out.append({
                "cantidad": qty,
                "descripcion": f"Complemento {comp.v_complemento_id}", # Or lookup name if needed
                "precio_total": tot_comp,
                "precio_unitario": unit_price
            })

        items_out.append({
            "descripcion": item.descripcion or f"Item {item.id}",
            "cantidad": item_qty or 1,
            "total_m2": item_total_m2,
            "total_ml": item_total_ml,
            "total_pesos": item_total_pesos,
            "panos": panos_out,
            "adicionales": adicionales_out
        })
        
        total_m2 += item_total_m2
        total_ml += item_total_ml
        total_pesos += item_total_pesos

    return {
        "v_presupuesto_id": v_presupuesto_id,
        "cliente_id": cliente_id,
        "cliente_nombre": f"Cliente ID: {cliente_id}" if cliente_id else "Desconocido",
        "obra_nombre": f"Presupuesto {v_presupuesto_id}",
        "pedidos_relacionados": list(pedidos_set),
        "total_m2": total_m2,
        "total_ml": total_ml,
        "total_pesos": total_pesos,
        "items_count": len(items_out),
        "items": items_out
    }


def get_avance_comercial_acopio(db: Session, v_presupuesto_id: str):
    """
    Obtiene el avance comercial y documental detallado de un acopio (presupuesto).
    Analiza todos los pedidos de producción vinculados a este presupuesto único y
    consolida su estado de facturación y remitos.
    """
    # 1. Get items and their orders
    items = db.query(SpfItem).filter(SpfItem.v_presupuesto_id == v_presupuesto_id).all()
    if not items:
        return None

    # Identify related orders and client
    pedido_ids = list(set(item.pedido_id for item in items if item.pedido_id))
    pedidos = db.query(SpfPedido).filter(SpfPedido.id.in_(pedido_ids)).all() if pedido_ids else []
    
    cliente_map = {}
    cliente_ids = list(set(p.cliente_id for p in pedidos if p.cliente_id))
    if cliente_ids:
        clientes = db.query(SpfCliente).filter(SpfCliente.id.in_(cliente_ids)).all()
        cliente_map = {c.id: c.nombre for c in clientes}

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
    def get_line_progress(item_id: int, item_type: str, total_qty_expected: float):
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
            return 0.0, 0.0, []

        # Sum facturado/remitido
        f_sum = db.query(func.sum(SpfLineaTangoFacturada.cantidad_ya_facturada)).filter(
            SpfLineaTangoFacturada.tango_body_id.in_(all_body_ids)
        ).scalar() or 0.0
        
        r_sum = db.query(func.sum(SpfLineaTangoRemitida.cantidad_ya_remitida)).filter(
            SpfLineaTangoRemitida.tango_body_id.in_(all_body_ids)
        ).scalar() or 0.0

        # Get comprobantes associated
        comp_fact = db.query(SpfComprobanteTemp).join(
            SpfLineaTangoFacturada, SpfComprobanteTemp.id == SpfLineaTangoFacturada.comprobante_temp_id
        ).filter(SpfLineaTangoFacturada.tango_body_id.in_(all_body_ids)).all()
        
        comp_remit = db.query(SpfComprobanteTemp).join(
            SpfLineaTangoRemitida, SpfComprobanteTemp.id == SpfLineaTangoRemitida.comprobante_temp_id
        ).filter(SpfLineaTangoRemitida.tango_body_id.in_(all_body_ids)).all()
        
        comprobantes = []
        for c in set(comp_fact + comp_remit):
            comprobantes.append({
                "nro_factura": c.nro_factura,
                "nro_remito": c.nro_remito,
                "empresa": "Fontela" if "Tango A" in (c.talonario or "") else "Viviana" if "Tango B" in (c.talonario or "") else c.talonario
            })

        perc_f = (float(f_sum) / total_qty_expected * 100) if total_qty_expected > 0 else 0.0
        perc_r = (float(r_sum) / total_qty_expected * 100) if total_qty_expected > 0 else 0.0
        
        return min(perc_f, 100.0), min(perc_r, 100.0), comprobantes

    # 4. Construct Output
    pedidos_out = []
    for p in pedidos:
        p_items = [it for it in items if it.pedido_id == p.id]
        items_detail = []
        
        for it in p_items:
            # Item Medidas
            for med in it.medidas:
                qty = med.cantidad or 1
                sup = float(med.superficie or 0)
                tot = float(med.total_item or 0)
                
                # Based on requirement: superficie is subtotal (total of the line)
                # precio por m2 = total_item / superficie
                # precio unitario = total_item / cantidad
                
                pf, pr, comps = get_line_progress(med.id, 'SpfPedido::ItemMedida', float(qty))
                
                items_detail.append({
                    "tipo": "Medida",
                    "descripcion": med.denominacion or it.descripcion,
                    "cantidad": qty,
                    "importe_total": tot,
                    "precio_unitario": tot / qty if qty > 0 else 0,
                    "precio_m2": tot / sup if sup > 0 else 0,
                    "avance_facturado": pf,
                    "avance_remitido": pr,
                    "comprobantes": comps
                })
            
            # Item Complementos
            for comp in it.complementos:
                qty = comp.cantidad or 1
                unit_price = float(comp.total_complemento or 0)
                tot = unit_price * qty
                desc = complement_names.get(comp.v_complemento_id, f"Complemento {comp.v_complemento_id}")
                
                pf, pr, comps = get_line_progress(comp.id, 'SpfPedido::ItemComplemento', float(qty))
                
                items_detail.append({
                    "tipo": "Complemento",
                    "descripcion": desc,
                    "cantidad": qty,
                    "importe_total": tot,
                    "precio_unitario": unit_price,
                    "avance_facturado": pf,
                    "avance_remitido": pr,
                    "comprobantes": comps
                })

        pedidos_out.append({
            "id": p.id,
            "nro_pedido": p.nro_pedido,
            "estado": ESTADOS_PEDIDO.get(p.estado_id, f"Estado {p.estado_id}"),
            "cliente": cliente_map.get(p.cliente_id, "Desconocido"),
            "items": items_detail
        })

    # 5. Global Summary
    global_tot = sum(p["importe_total"] for p_out in pedidos_out for p in p_out["items"])
    global_fact = sum(p["importe_total"] * (p["avance_facturado"] / 100.0) for p_out in pedidos_out for p in p_out["items"])
    global_remit = sum(p["importe_total"] * (p["avance_remitido"] / 100.0) for p_out in pedidos_out for p in p_out["items"])

    return {
        "v_presupuesto_id": v_presupuesto_id,
        "cliente": pedidos_out[0]["cliente"] if pedidos_out else "Desconocido",
        "obra": (pedidos[0].nrooc or "S/D") if pedidos else "S/D",
        "resumen": {
            "importe_total": global_tot,
            "facturado_total": global_fact,
            "remitido_total": global_remit,
            "porcentaje_facturado": (global_fact / global_tot * 100) if global_tot > 0 else 0,
            "porcentaje_remitido": (global_remit / global_tot * 100) if global_tot > 0 else 0,
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
    
    total_m2 = 0.0
    total_ml = 0.0
    total_pesos = 0.0
    total_qty = 0
    
    for it in items:
        if not v_presupuesto_id and it.v_presupuesto_id:
            v_presupuesto_id = str(it.v_presupuesto_id).zfill(9)
            
        for med in it.medidas:
            total_m2 += float(med.superficie or 0) # Already subtotal from requirement
            total_ml += float(med.perimtero or 0)
            total_pesos += float(med.total_item or 0)
            total_qty += (med.cantidad or 0)
            
        for comp in it.complementos:
            qty = comp.cantidad or 1
            unit_price = float(comp.total_complemento or 0)
            total_pesos += unit_price * qty
            # The units of adicionales should NOT count towards physical units consumed

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
        "empresa": empresa,
        "totals": {
            "m2": total_m2,
            "ml": total_ml,
            "pesos": total_pesos,
            "unidades": total_qty
        }
    }



