"""Reuse explicit invoice associations as scoped search evidence, never as payments."""
from fastapi import HTTPException
from models import Comprobante, AfectacionAcopio
from services.comprobante_numero import number_query


def invoice_identity(number, issuer):
    company = {"FONTELA": "FONTELA", "VIVIANA": "VIVIANA",
               "JOSE M. FONTELA E HIJOS SACIF": "FONTELA"}.get((issuer or "").strip().upper())
    if not company:
        return None
    try:
        query = number_query(number)
    except HTTPException:
        return None
    if query["numero_modo"] != "COMPLETO":
        return None
    return company, query["numero_normalizado"]


def active_invoices(db, acopio_id):
    return db.query(AfectacionAcopio).join(Comprobante).filter(
        AfectacionAcopio.acopio_id == acopio_id, AfectacionAcopio.anulada.is_(False),
        Comprobante.tipo.in_(["FAC_ANTICIPO", "FAC_MERCADERIA"])).all()


def confirmed_invoices(db, acopio_id):
    identities = set()
    for row in active_invoices(db, acopio_id):
        identity = invoice_identity(row.comprobante.numero, row.comprobante.emisor)
        if identity:
            identities.add(identity)
    if len(identities) > 20:
        raise HTTPException(422, "Hay mas de veinte facturas asociadas: consulta por numero para acotar la busqueda.")
    return [{"empresa": company, "numero": number} for company, number in sorted(identities)]


def matches_invoice(reference, company, number):
    identity = invoice_identity(reference.comprobante.numero, reference.comprobante.emisor)
    return identity is not None and identity == invoice_identity(number, company)
