from sqlalchemy.orm import Session
from sqlalchemy import func, or_, union_all
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
    Search for presupuestos by v_presupuesto_id or related nro_pedido.
    Returns a distinct list of v_presupuesto_id.
    """
    if not query:
        return []

    # Search by v_presupuesto_id directly in the items
    items_query = db.query(SpfItem.v_presupuesto_id).filter(
        SpfItem.v_presupuesto_id.ilike(f"%{query}%")
    ).distinct()
    
    # Or by matching nro_pedido in the pedidos
    pedidos_query = db.query(SpfItem.v_presupuesto_id).join(SpfPedido, SpfItem.pedido_id == SpfPedido.id).filter(
        SpfPedido.nro_pedido.ilike(f"%{query}%")
    ).distinct()

    results = items_query.union(pedidos_query).limit(20).all()
    return [r[0] for r in results if r[0]]


def get_presupuesto_details(db: Session, v_presupuesto_id: str):
    """
    Get full details and aggregates for a given v_presupuesto_id.
    Calculates m2, ml, and pesos based on items, medidas, and complementos.
    """
    items = db.query(SpfItem).filter(SpfItem.v_presupuesto_id == v_presupuesto_id).all()
    
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
            
        for comp in item.complementos:
            qty = comp.cantidad or 1
            # Complementos don't add to paños directly, but they sum to the item's total
            tot_comp = float(comp.total_complemento or 0)
            item_total_pesos += tot_comp

        items_out.append({
            "descripcion": item.descripcion or f"Item {item.id}",
            "cantidad": item_qty or 1,
            "total_m2": item_total_m2,
            "total_ml": item_total_ml,
            "total_pesos": item_total_pesos,
            "panos": panos_out
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
    Detailed commercial and documentary advancement for an acopio.
    Fetches orders, items, pricing, billing/dispatch progress and receipts.
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
                tot = float(comp.total_complemento or 0)
                desc = complement_names.get(comp.v_complemento_id, f"Complemento {comp.v_complemento_id}")
                
                pf, pr, comps = get_line_progress(comp.id, 'SpfPedido::ItemComplemento', float(qty))
                
                items_detail.append({
                    "tipo": "Complemento",
                    "descripcion": desc,
                    "cantidad": qty,
                    "importe_total": tot,
                    "precio_unitario": tot / qty if qty > 0 else 0,
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

    return {
        "v_presupuesto_id": v_presupuesto_id,
        "pedidos": pedidos_out
    }

