
from database import SessionLocal
from models.acopio import Acopio
from sqlalchemy import func

def diagnose():
    db = SessionLocal()
    try:
        print("--- Diagnóstico Local Acopios ---")
        acopios = db.query(Acopio).all()
        print(f"Total acopios locales: {len(acopios)}")
        for a in acopios:
            print(f" - ID: {a.id}, Numero: {a.numero}, V_Presupuesto_ID: '{a.v_presupuesto_id}'")
            
        # Specific search for 000209205
        target = "000209205"
        res = db.query(Acopio).filter(Acopio.v_presupuesto_id == target).first()
        if res:
            print(f"ENCONTRADO ACPIADO PARA {target}: ID={res.id}")
        else:
            print(f"NO ENCONTRADO ACOPIO PARA {target}")

    finally:
        db.close()

if __name__ == "__main__":
    diagnose()
