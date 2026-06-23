import sys
import os
sys.path.append(os.path.dirname(__file__))

from database import SessionLocal
from integrations.spf.database import get_spf_db
from integrations.spf import services as spf_services
from models import Acopio

def fix_data():
    db = SessionLocal()
    spf_db_gen = get_spf_db()
    spf_db = next(spf_db_gen)

    acopios = db.query(Acopio).filter(Acopio.origen_datos == 'spf_production').all()
    count = 0

    for acopio in acopios:
        if not acopio.v_presupuesto_id:
            continue
        
        details = spf_services.get_presupuesto_details(spf_db, acopio.v_presupuesto_id)
        if not details:
            continue
            
        real_cliente_nombre = details.get("cliente_nombre")
        real_obra_nombre = details.get("obra_nombre")
        
        if acopio.obra:
            if real_obra_nombre and acopio.obra.nombre.startswith("Presupuesto "):
                print(f"Fixing Obra: {acopio.obra.nombre} -> {real_obra_nombre}")
                acopio.obra.nombre = real_obra_nombre
                count += 1
                
            if acopio.obra.cliente and real_cliente_nombre and acopio.obra.cliente.nombre.startswith("Cliente ID: "):
                print(f"Fixing Cliente: {acopio.obra.cliente.nombre} -> {real_cliente_nombre}")
                acopio.obra.cliente.nombre = real_cliente_nombre
                count += 1

    db.commit()
    print(f"Fixed {count} records!")

if __name__ == '__main__':
    fix_data()
