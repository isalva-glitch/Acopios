import pytest
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
    def __init__(self, rows, bbox=(0, 100, 500, 400)):
        self._rows = rows
        self.bbox = bbox

    def extract(self):
        return self._rows

class FakePage:
    def __init__(self, text, tables=None, width=500):
        self._text = text
        self._tables = tables or []
        self.width = width

    def find_tables(self):
        return self._tables

    def extract_text(self):
        return self._text

    def within_bbox(self, bbox):
        return FakePage("Encabezado de Item")

class FakePdf:
    def __init__(self, pages):
        self.pages = pages

def test_large_budget_extraction_reproduces_missing_rows():
    """
    Simula un presupuesto grande donde la detección de tablas falla en algunas filas
    pero el texto las contiene.
    """
    items = [
        PdfItem(numero_item=1, descripcion="Laminado 4+4", cantidad=422, total_pesos=Decimal("132081918.57")),
        PdfItem(numero_item=2, descripcion="Templado 10mm", cantidad=85, total_pesos=Decimal("15443735.05")),
    ]

    # Página 2: Item 1.
    table_p1 = FakeTable([
        ["Cant", "Ancho", "Alto", "Sup", "Per", "Denom", "Unit", "Total"],
        ["303", "950", "1040", "300.00", "1200.00", "PV1", "100.00", "30300.00"],
    ])
    
    page1_text = """
1 Laminado 4+4
12 950 1040 11,86 47,76 PV1 $213.103,49 $2.557.241,88
107 950 1040 105,50 425,00 PV1 $213.103,49 $22.802.073,43
303 950 1040 300,00 1200,00 PV1 $100,00 $30.300,00
422 paños 753,19 xxx $132.081.918,57
"""

    # Página 3: Item 2.
    table_p2 = FakeTable([
        ["Cant", "Ancho", "Alto", "Sup", "Per", "Denom", "Unit", "Total"],
        ["77", "800", "2000", "123.20", "431.20", "PV2", "150.00", "11550.00"],
    ])
    page2_text = """
2 Templado 10mm
8 800 2000 12,80 44,80 PV2 $150,00 $1.200,00
77 800 2000 123,20 431,20 PV2 $150,00 $11.550,00
85 paños 136,00 xxx $15.443.735,05
"""

    pdf = FakePdf([
        FakePage("Consolidado"),
        FakePage(page1_text, [table_p1]),
        FakePage(page2_text, [table_p2]),
    ])

    _parse_detailed_all_pages(pdf, items)

    assert sum(p.cantidad for p in items[0].panos) == 422
    assert sum(p.cantidad for p in items[1].panos) == 85
    assert items[0].total_pesos == Decimal("132081918.57")
    assert items[1].total_pesos == Decimal("15443735.05")

def test_legitimate_duplicates_are_preserved():
    """
    Si el presupuesto tiene dos filas idénticas físicamente en el texto, ambas deben conservarse.
    """
    items = [
        PdfItem(numero_item=1, descripcion="Laminado", cantidad=20, total_pesos=Decimal("2000")),
    ]
    page_text = """
1 Laminado
10 950 1040 10,00 40,00 PV1 $100,00 $1.000,00
10 950 1040 10,00 40,00 PV1 $100,00 $1.000,00
20 paños 20,00 xxx $2.000,00
"""
    pdf = FakePdf([
        FakePage("Consolidado"),
        FakePage(page_text, []),
    ])
    
    _parse_detailed_all_pages(pdf, items)
    
    assert len(items[0].panos) == 2
    assert items[0].panos[0].cantidad == 10
    assert items[0].panos[1].cantidad == 10
    assert sum(p.cantidad for p in items[0].panos) == 20
