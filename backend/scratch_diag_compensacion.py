"""Diagnostico: muestra qué computa el resumen de compensacion para cada imputacion."""
from decimal import Decimal
from database import SessionLocal
from models import Acopio, AcopioItem, Imputacion

PROCESS_UNITS = {
    "vidrio_exterior": "m2",
    "vidrio_interior": "m2",
    "camara_estructural": "ml",
    "pulido": "ml",
    "fason_templado_exterior": "m2",
    "pegado_bastidor": "ml",
    "camara_normal": "ml",
    "opacificado_perimetral": "ml",
    "opacificado_total": "m2",
    "camara_offset": "ml",
}

def to_dec(v):
    return Decimal("0") if v is None else (v if isinstance(v, Decimal) else Decimal(str(v)))

def main():
    db = SessionLocal()
    try:
        acopio = db.query(Acopio).filter(Acopio.numero == '000209118').first()
        item_map = {item.id: item for item in acopio.items}

        print("=== ACOPIO ITEMS Y PROCESOS ===")
        for item in sorted(acopio.items, key=lambda x: x.numero_item or 0):
            print(f"\nItem {item.numero_item} (ID={item.id}): {item.descripcion[:60]}...")
            for field, unit in PROCESS_UNITS.items():
                active = bool(getattr(item, f"proceso_{field}", False))
                if active:
                    qty = to_dec(item.total_m2 if unit == "m2" else item.total_ml)
                    print(f"  [ACTIVO] {field}: {qty} {unit}")

        print("\n\n=== IMPUTACIONES Y PRORRATEADO CAMARA ESTRUCTURAL ===")
        for imp in sorted(acopio.imputaciones, key=lambda x: x.pedido.numero if x.pedido else ""):
            pedido_num = imp.pedido.numero if imp.pedido else str(imp.pedido_id)
            item_num = None
            item = None
            if imp.acopio_item_id and imp.acopio_item_id in item_map:
                item = item_map[imp.acopio_item_id]
                item_num = item.numero_item

            print(f"\nImputacion {imp.id} | Pedido {pedido_num} | Item Acopio #{item_num}")
            print(f"  Consumo: {imp.cantidad_m2} m2, {imp.cantidad_ml} ml")

            if imp.procesos:
                print(f"  Tiene {len(imp.procesos)} proceso(s) directos -> NO prorratea")
                for p in imp.procesos:
                    print(f"    {p.proceso}: {p.cantidad} {PROCESS_UNITS.get(p.proceso, '?')}")
                continue

            if item:
                # Mostramos solo camara_estructural
                field = "camara_estructural"
                if bool(getattr(item, f"proceso_{field}", False)):
                    unit = PROCESS_UNITS[field]
                    item_total = to_dec(item.total_ml)
                    imp_ml = to_dec(imp.cantidad_ml)
                    if item_total != 0:
                        ratio = imp_ml / item_total
                        cantidad = ratio * item_total  # = imp_ml
                        print(f"  -> camara_estructural prorrateado: ratio={float(ratio):.4f}, ml={float(cantidad):.4f}")
                    else:
                        print(f"  -> camara_estructural: item total_ml=0, skip")
                else:
                    print(f"  -> camara_estructural: NO activo en este item")
            else:
                print(f"  -> Sin item asignado, distribucion global")

    finally:
        db.close()

if __name__ == "__main__":
    main()
