
from integrations.spf.database import SpfSessionLocal
from integrations.spf.models import SpfPedido, SpfItem
from sqlalchemy import or_

def diagnose(query_str):
    db = SpfSessionLocal()
    try:
        print(f"--- Diagnóstico 2 para: '{query_str}' ---")
        
        if query_str.isdigit():
            val = int(query_str)
            pedido = db.query(SpfPedido).filter(SpfPedido.id == val).first()
            if pedido:
                print(f"PEDIDO ENCONTRADO: ID={pedido.id}, Presupuesto={pedido.id_presupuesto}")
                
                # Check items
                items = db.query(SpfItem).filter(SpfItem.pedido_id == pedido.id).all()
                print(f"ITEMS ASOCIADOS: {len(items)}")
                for it in items:
                    print(f" - Item ID: {it.id}, Presupuesto ID en Item: {it.v_presupuesto_id}")
            else:
                print("Pedido NO encontrado.")

    finally:
        db.close()

if __name__ == "__main__":
    import sys
    q = sys.argv[1] if len(sys.argv) > 1 else ""
    diagnose(q)
