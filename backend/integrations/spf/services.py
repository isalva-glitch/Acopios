"""Service layer for querying the external spf_production database."""
from sqlalchemy.orm import Session
from .models import SpfPedido, SpfItem, SpfItemMedida, SpfItemComplemento


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
            
            item_total_m2 += sup * qty
            item_total_ml += per * qty
            item_total_pesos += tot
            
            panos_out.append({
                "cantidad": qty,
                "ancho": float(medida.ancho or 0),
                "alto": float(medida.alto or 0),
                "superficie_m2": sup,
                "perimetro_ml": per,
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
