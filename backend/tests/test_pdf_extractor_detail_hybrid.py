from decimal import Decimal

from integrations.pdf.extractor import (
    PdfItem,
    PdfPane,
    ParsedBudget,
    PdfPresupuesto,
    _parse_detailed_all_pages,
    _validate,
)


class FakeTable:
    def __init__(self, rows):
        self._rows = rows
        self.bbox = (0, 120, 500, 420)

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

    def within_bbox(self, _bbox):
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
            ["Cantidad", "Ancho", "Alto", "Superficie", "Perímetro", "Denominación", "Unitario", "Total"],
            ["100", "950", "1040", "118.60", "477.60", "PV1", "213.103,49", "21.310.349,00"],
        ]
    )
    table_page_2 = FakeTable(
        [
            ["Cantidad", "Ancho", "Alto", "Superficie", "Perímetro", "Denominación", "Unitario", "Total"],
            ["77", "950", "1040", "91.18", "367.29", "PV2", "181.869,48", "14.003.950,04"],
        ]
    )

    page_1_text = "\n".join(
        [
            "1 Laminado",
            "100 950 1040 118,60 477,60 PV1 $213.103,49 $21.310.349,00",
            "2 BISAGRA PARED VIDRIO 90° ZAMAK CROM FT $19.330,80 $38.661,60",
            "322 950 1040 381,68 1537,35 PV1 $216.368,85 $69.664.328,52",
            "422 paños 753,19 3014,95 $132.081.918,57",
        ]
    )
    page_2_text = "\n".join(
        [
            "2 Otro item",
            "8 950 1040 9,47 38,18 PV2 $179.973,13 $1.439.785,01",
            "85 paños 100,00 400,00 $15.443.735,05",
        ]
    )

    pdf = FakePdf(
        [
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
    assert any("esperada 10" in w and "leída 8" in w for w in parsed.warnings)
