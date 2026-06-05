from decimal import Decimal

from integrations.pdf.extractor import (
    PdfItem,
    PdfPane,
    ParsedBudget,
    PdfPresupuesto,
    _parse_detailed_all_pages,
    _parse_header_block_from_text,
    _validate,
)


class FakeTable:
    def __init__(self, rows, bbox=(0, 120, 500, 420)):
        self._rows = rows
        self.bbox = bbox

    def extract(self):
        return self._rows


class FakePage:
    def __init__(self, text, tables=None, above_text=""):
        self._text = text
        self._tables = tables or []
        self._above_text = above_text
        self.width = 500

    def find_tables(self):
        return self._tables

    def extract_text(self):
        return self._text

    def within_bbox(self, bbox):
        if bbox[3] <= bbox[1]:
            raise ValueError(f"{bbox} has a negative width or height")
        return FakePage(self._above_text, [])


class FakePdf:
    def __init__(self, pages):
        self.pages = pages


def _dummy_budget():
    return PdfPresupuesto(
        numero="1",
        empresa="x",
        contacto="x",
        estado="x",
        cotizado_por="x",
        fecha_aprobacion=None,
        total_unidades=0,
        total_importe=Decimal("0"),
        total_m2=Decimal("753.19"),
        total_ml=Decimal("0"),
        peso_estimado_kg=Decimal("0"),
    )


def test_parse_detailed_hybrid_recovers_rows_across_pages_without_duplicate_item_header():
    items = [
        PdfItem(numero_item=1, descripcion="ITEM 1", cantidad=422, total_pesos=Decimal("132081918.57")),
        PdfItem(numero_item=2, descripcion="ITEM 2", cantidad=85, total_pesos=Decimal("15443735.05")),
    ]

    table_page_1 = FakeTable(
        [
            ["Cantidad", "Ancho", "Alto", "Superficie", "Perimetro", "Denominacion", "Unitario", "Total"],
            ["100", "950", "1040", "118.60", "477.60", "PV1", "213.103,49", "21.310.349,00"],
        ]
    )
    table_page_2 = FakeTable(
        [
            ["Cantidad", "Ancho", "Alto", "Superficie", "Perimetro", "Denominacion", "Unitario", "Total"],
            ["77", "950", "1040", "91.18", "367.29", "PV2", "181.869,48", "14.003.950,04"],
        ]
    )

    page_1_text = "\n".join(
        [
            "1 Laminado",
            "100 950 1040 118,60 477,60 PV1 $213.103,49 $21.310.349,00",
            "2 BISAGRA PARED VIDRIO 90 DEG ZAMAK CROM FT $19.330,80 $38.661,60",
            "322 950 1040 381,68 1537,35 PV1 $216.368,85 $69.664.328,52",
            "422 pa\u00f1os 753,19 3014,95 $132.081.918,57",
        ]
    )
    page_2_text = "\n".join(
        [
            "2 Otro item",
            "8 950 1040 9,47 38,18 PV2 $179.973,13 $1.439.785,01",
            "85 pa\u00f1os 100,00 400,00 $15.443.735,05",
        ]
    )

    # Page 0 is the header/consolidated page (always skipped by the extractor).
    # Pages 1+ are the detail pages. Without a dummy page 0, pages[0] gets
    # page_idx=1 and is skipped, losing all item 1 panos.
    dummy_header_page = FakePage("Presupuesto consolidado:", [], above_text="")
    pdf = FakePdf(
        [
            dummy_header_page,
            FakePage(page_1_text, [table_page_1], above_text="1 Laminado"),
            FakePage(page_2_text, [table_page_2], above_text=""),
        ]
    )

    _parse_detailed_all_pages(pdf, items)

    item1 = items[0]
    item2 = items[1]
    assert sum(p.cantidad for p in item1.panos) == 422
    assert sum(p.cantidad for p in item2.panos) == 85
    assert item1.total_m2 == Decimal("753.19")
    assert item1.total_pesos == Decimal("132081918.57")
    assert item2.total_pesos == Decimal("15443735.05")
    assert len(item1.adicionales) == 1


def test_marks_incomplete_when_read_quantity_differs_from_expected():
    item = PdfItem(numero_item=1, descripcion="ITEM 1", cantidad=10, total_pesos=Decimal("1000"))
    item.panos.append(
        PdfPane(
            row_no=1,
            cantidad=8,
            ancho_mm=100,
            alto_mm=100,
            superficie_m2=Decimal("1"),
            perimetro_ml=Decimal("1"),
            denominacion="PV1",
            precio_unitario=Decimal("125"),
            precio_total=Decimal("1000"),
        )
    )
    parsed = ParsedBudget(presupuesto=_dummy_budget(), items=[item])
    _validate(parsed)

    assert item.incompleto is True
    assert any("esperada 10" in w and "8" in w for w in parsed.warnings)


def test_parse_detailed_skips_invalid_above_table_bbox():
    items = [
        PdfItem(numero_item=1, descripcion="ITEM 1", cantidad=1, total_pesos=Decimal("100")),
    ]
    table = FakeTable(
        [
            ["Cantidad", "Ancho", "Alto", "Superficie", "Perimetro", "Denominacion", "Unitario", "Total"],
            ["1", "1000", "1000", "1,00", "4,00", "-", "100,00", "100,00"],
        ],
        bbox=(0, -10, 500, 120),
    )
    pdf = FakePdf(
        [
            FakePage("Presupuesto consolidado:", []),
            FakePage("1 ITEM 1\n1 1000 1000 1,00 4,00 $100,00 $100,00", [table]),
        ]
    )

    _parse_detailed_all_pages(pdf, items)

    assert sum(p.cantidad for p in items[0].panos) == 1


def test_page_continuation_keeps_previous_item_until_subtotal_and_next_header():
    items = [
        PdfItem(numero_item=2, descripcion="ITEM 2", cantidad=5, total_pesos=Decimal("1050")),
        PdfItem(numero_item=3, descripcion="ITEM 3", cantidad=2, total_pesos=Decimal("500")),
    ]
    page_text = "\n".join(
        [
            "Cantidad Ancho Alto Superficie Perimetro Denominacion Unitario Total",
            "5 1000 1000 5,00 20,00 CW2 $210,00 $1.050,00",
            "Totales",
            "5 pa\u00f1os 5,00 20,00 $1.050,00",
            "DVH siguiente",
            "3 ITEM 3",
            "Cantidad Ancho Alto Superficie Perimetro Denominacion Unitario Total",
            "2 500 500 0,50 4,00 CW3 $250,00 $500,00",
            "Totales",
            "2 pa\u00f1os 0,50 4,00 $500,00",
        ]
    )
    pdf = FakePdf(
        [
            FakePage("Presupuesto consolidado:", []),
            FakePage("2 ITEM 2", []),
            FakePage(page_text, []),
        ]
    )

    _parse_detailed_all_pages(pdf, items)

    assert sum(p.cantidad for p in items[0].panos) == 5
    assert sum(p.cantidad for p in items[1].panos) == 2


def test_parse_header_block_recovers_split_empresa_obra():
    text = """
Presupuesto Nº:
#000209118
Cotizado Fecha de
Empresa Contacto Estado
por aprobación
CONSTRUCTORA MARIANO PANETTO / HOSPITAL MARIANO Abel
Parcial 07/10/25
SUNCHALES PARETTO Paladini
Presupuesto consolidado:
"""

    empresa, obra, contacto, cotizado, fecha = _parse_header_block_from_text(
        text,
        contacto="MARIANO PARETTO",
        cotizado_por="Abel Paladini",
        estado="Parcial",
    )

    assert empresa == "CONSTRUCTORA MARIANO PANETTO"
    assert obra == "HOSPITAL SUNCHALES"
    assert contacto == "MARIANO PARETTO"
    assert cotizado == "Abel Paladini"
    assert fecha == "07/10/25"


def test_parse_header_block_recovers_tail_after_contact():
    text = """
Cotizado Fecha de
Empresa Contacto Estado
por aprobación
Ing. Rinaldi Construcciones S.R.L. / OBRA ESPAÑA FRANCA
Anulado Abel Paladini 21/04/26
257 DAULON
Presupuesto consolidado:
"""

    empresa, obra, contacto, cotizado, fecha = _parse_header_block_from_text(
        text,
        contacto="FRANCA DAULON",
        cotizado_por="Abel Paladini",
        estado="Anulado",
    )

    assert empresa == "Ing. Rinaldi Construcciones S.R.L."
    assert obra == "OBRA ESPAÑA 257"
    assert contacto == "FRANCA DAULON"
    assert cotizado == "Abel Paladini"
    assert fecha == "21/04/26"


def test_parse_header_block_recovers_compact_empresa_obra_line():
    text = """
Presupuesto NÂº:
#000207644
Empresa Contacto Estado Cotizado por Fecha de aprobaciÃ³n
EDILIZIA / AQUILONIA DAVID BERON Ejecutado Admin User 05/08/25
Presupuesto consolidado:
"""

    empresa, obra, contacto, cotizado, fecha = _parse_header_block_from_text(
        text,
        contacto="DAVID BERON",
        cotizado_por="Admin User",
        estado="Ejecutado",
    )

    assert empresa == "EDILIZIA"
    assert obra == "AQUILONIA"
    assert contacto == "DAVID BERON"
    assert cotizado == "Admin User"
    assert fecha == "05/08/25"
