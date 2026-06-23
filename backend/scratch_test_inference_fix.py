"""Verifica que el fix de proceso_inference funciona correctamente."""
from services.proceso_inference import infer_item_processes_from_texts

cases = [
    # (descripcion, espera camara_estructural, espera camara_offset)
    ("DVH Ekoglass + Cámara 12 mm. Estructural + Laminado 3+3", True, False),
    ("DVH Ekoglass + Cámara 12 mm. Estructural Offset + Laminado 3+3 + Opacificado perimetral", False, True),
    ("DVH Ekoglass + Cámara 12 mm. Normal + Laminado 3+3", False, False),
    ("DVH Ekoglass + Cámara Estructural + Pegado estructural a bastidores", True, False),
    ("DVH Ekoglass + Cámara Offset + Pegado estructural", False, True),
    ("Silicona estructural + cámara 16 mm", True, False),
    ("Pegado estructural a bastidores de aluminio", False, False),  # "pegado estructural" no es camara_estructural
]

all_ok = True
for desc, expect_ce, expect_co in cases:
    result = infer_item_processes_from_texts([desc])
    ce = result["camara_estructural"]
    co = result["camara_offset"]
    ok = (ce == expect_ce) and (co == expect_co)
    status = "✓ OK" if ok else "✗ FAIL"
    if not ok:
        all_ok = False
    print(f"{status} | camara_estructural={ce} (esperado {expect_ce}), camara_offset={co} (esperado {expect_co})")
    print(f"       Texto: {desc[:80]}")

print()
print("=== RESULTADO FINAL:", "TODOS OK ✓" if all_ok else "HAY FALLOS ✗")
