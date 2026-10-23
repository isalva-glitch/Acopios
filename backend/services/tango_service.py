"""Reviewable external records. This service never writes operational/manual balances."""
from datetime import datetime, timedelta
from decimal import Decimal, ROUND_HALF_UP
import hashlib
import json
from fastapi import HTTPException
from models import Acopio
from models.tango_registro import TangoRegistro
from services.tango_access_bridge import request_access, bridge_status

CENT = Decimal("0.01")
ALLOWED_TYPES = {"FAC", "REC", "NCD", "NCE", "NCB", "NCI", "NCC", "PED"}


def money(value):
    return Decimal(str(value or 0)).quantize(CENT, rounding=ROUND_HALF_UP)


def acopio_or_404(db, acopio_id, lock=False):
    query = db.query(Acopio).filter_by(id=acopio_id)
    acopio = (query.with_for_update() if lock else query).first()
    if not acopio:
        raise HTTPException(404, "Acopio no encontrado")
    return acopio


def add_net_applications(records):
    """Keep receipt gross values; derive only the amount related to each advance.

    A fully settled invoice distributes its residual net after actual credit notes,
    so receipt rounding cannot create a cent of extra/missing net. Partial payments
    use a clearly labelled proportional equivalent. Viviana uses the internal amount.
    """
    invoices = {r["origen_id"]: r for r in records if r["tipo"] == "FAC"}
    for invoice_id, invoice in invoices.items():
        applications = []
        for record in records:
            for application in record.get("aplicaciones", []):
                if application.get("factura_id") == invoice_id:
                    applications.append((record, application))
        if any(str(r.get("fecha_anulacion") or "") > "1900-01-01" for r in [invoice] + [r for r, _ in applications]):
            for _, application in applications:
                application["neto_equivalente"] = None
                application["criterio_neto"] = "Hay un comprobante anulado en Tango: revisar sus aplicaciones."
            continue
        if not invoice.get("moneda_corriente", True) or any(
            not record.get("moneda_corriente", True) for record, _ in applications
        ):
            for _, application in applications:
                application["neto_equivalente"] = None
                application["criterio_neto"] = "Moneda extranjera: requiere revisar cotizaciones antes de calcular un neto equivalente."
            continue
        gross = money(invoice["total"])
        net = money(invoice["importe_control"])
        if not gross or not applications:
            continue
        receipts = [(r, a) for r, a in applications if r["tipo"] == "REC"]
        other = [(r, a) for r, a in applications if r["tipo"] != "REC"]
        credits_net = Decimal("0")
        for record, application in other:
            original = money(record["total"])
            amount = money(application["importe_bruto"])
            equivalent = money(amount * money(record["importe_control"]) / original) if original else Decimal("0")
            application["neto_equivalente"] = str(equivalent)
            application["criterio_neto"] = "Proporción del neto de la nota de crédito."
            credits_net += equivalent
        total_applied = sum((money(a["importe_bruto"]) for _, a in applications), Decimal("0"))
        settled = abs(total_applied - gross) <= CENT
        remaining = net - credits_net
        receipt_total = sum((money(a["importe_bruto"]) for _, a in receipts), Decimal("0"))
        assigned = Decimal("0")
        for index, (record, application) in enumerate(receipts):
            amount = money(application["importe_bruto"])
            if invoice["empresa"] == "VIVIANA":
                equivalent = amount
                criterion = "Viviana: importe interno aplicado."
            elif settled and receipt_total:
                equivalent = remaining - assigned if index == len(receipts) - 1 else money(remaining * amount / receipt_total)
                criterion = "Neto restante de la factura, descontando notas de crédito y distribuyendo los cobros."
            else:
                equivalent = money(amount * net / gross)
                criterion = "Equivalente neto proporcional de un cobro parcial; revisar."
            assigned += equivalent
            application["neto_equivalente"] = str(equivalent)
            application["criterio_neto"] = criterion
    return records



def add_document_nets(records):
    """Receipt source gross remains unchanged; a complete net is required to share it."""
    for record in records:
        record["neto_documental"] = None
        if record["tipo"] == "FAC" and record["empresa"] == "FONTELA":
            record["neto_documental"] = record["importe_control"]
        elif record["tipo"] == "REC" and record["empresa"] == "VIVIANA":
            record["neto_documental"] = record["total"]
        elif record["tipo"] == "REC":
            context = record.get("contexto_neto", [])
            documents = {}
            for row in context:
                invoice_id = int(row["factura_id"])
                documents.setdefault(("FAC", invoice_id), {
                    "empresa": "FONTELA", "origen_id": invoice_id, "tipo": "FAC",
                    "total": str(money(row["factura_total"])), "importe_control": str(money(row["factura_neto"])),
                    "moneda_corriente": row["factura_moneda"], "fecha_anulacion": row.get("factura_anulacion"),
                    "aplicaciones": [],
                })
                source = documents.setdefault((row["tipo"], int(row["origen_id"])), {
                    "empresa": "FONTELA", "origen_id": int(row["origen_id"]), "tipo": row["tipo"],
                    "total": str(money(row["total"])), "importe_control": str(money(row["neto"])),
                    "moneda_corriente": row["moneda_corriente"], "fecha_anulacion": row.get("fecha_anulacion"),
                    "aplicaciones": [],
                })
                source["aplicaciones"].append({"factura_id": invoice_id, "importe_bruto": str(money(row["aplicado"]))})
            add_net_applications(list(documents.values()))
            receipt = documents.get(("REC", record["origen_id"]))
            if receipt:
                apps = receipt["aplicaciones"]
                complete = abs(sum((money(a["importe_bruto"]) for a in apps), Decimal(0)) - money(record["total"])) <= CENT
                if complete and all(a.get("neto_equivalente") is not None for a in apps):
                    record["neto_documental"] = str(sum((money(a["neto_equivalente"]) for a in apps), Decimal(0)))
                by_invoice = {a["factura_id"]: a for a in apps}
                for related in record.get("aplicaciones", []):
                    if related["factura_id"] in by_invoice:
                        related.update({k: v for k, v in by_invoice[related["factura_id"]].items()
                                        if k in ("neto_equivalente", "criterio_neto")})
    return records

def _identity(row):
    return row.empresa, row.origen_tipo, row.origen_id


def snapshot(db, acopio_id, *, consultation=None):
    acopio_or_404(db, acopio_id)
    rows = db.query(TangoRegistro).filter_by(acopio_id=acopio_id).order_by(TangoRegistro.id).all()
    groups = {}
    for row in rows:
        groups.setdefault(_identity(row), []).append(row)
    current = set()
    previous = {}
    for versions in groups.values():
        latest = versions[-1]
        retained = next((r for r in reversed(versions) if r.estado == "CONSERVADO"), None)
        current.add(latest.id)
        if latest.estado == "DESCARTADO" and retained:
            current.add(retained.id)
        if latest.estado == "PENDIENTE" and retained and retained.id != latest.id:
            previous[latest.id] = retained.id
    return {"acopio_id": acopio_id, "conexion": bridge_status(), "consulta": consultation,
            "registros": [{"id": r.id, "estado": r.estado, "datos": r.datos,
                           "consultado_at": r.created_at.isoformat(),
                           "revisado_at": r.revisado_at.isoformat() if r.revisado_at else None,
                           "es_actual": r.id in current, "version_conservada_id": previous.get(r.id)}
                          for r in reversed(rows)]}


async def consult(db, acopio_id, ampliar=False, number=None):
    acopio = acopio_or_404(db, acopio_id)
    customer = acopio.obra.cliente if acopio.obra else None
    if not customer or not customer.nombre.strip():
        raise HTTPException(422, "El acopio necesita un cliente para buscar sus datos en Tango.")
    total = money(acopio.total_pesos)
    pct = acopio.porcentaje_facturado
    targets = {"FONTELA": [str(total)], "VIVIANA": [str(total)]}
    if pct is not None:
        fact = money(total * Decimal(str(pct)) / 100)
        targets = {"FONTELA": [str(fact)] if fact else [],
                   "VIVIANA": [str(total - fact)] if total - fact else []}
    arguments = {"acopio_id": acopio_id, "cliente": customer.nombre, "cuit": customer.cuit,
                 "obra": acopio.obra.nombre, "presupuesto": acopio.v_presupuesto_id or acopio.numero or "",
                 "objetivos": targets, "desde": (acopio.fecha_alta - timedelta(days=730)).isoformat(),
                 "ampliar": ampliar}
    from services.tango_discovery import confirmed_invoices
    arguments["facturas_confirmadas"] = confirmed_invoices(db, acopio_id)
    if number:
        from services.comprobante_numero import number_query
        arguments.update(number_query(number))
    response = await request_access("lookup", arguments)
    return persist_consultation(db, acopio_id, response)


def persist_consultation(db, acopio_id, response):
    records = response.get("registros", [])
    if not isinstance(records, list) or len(records) > 120:
        raise HTTPException(502, "La consulta de Tango devolvió demasiados registros.")
    for record in records:
        if (not isinstance(record, dict) or record.get("empresa") not in ("FONTELA", "VIVIANA")
                or record.get("tipo") not in ALLOWED_TYPES
                or not isinstance(record.get("origen_id"), int) or record["origen_id"] <= 0):
            raise HTTPException(502, "Tango devolvió un registro sin identificación válida.")
        for field in ("total", "importe_control", "iva"):
            try:
                amount = money(record.get(field))
                if not amount.is_finite():
                    raise ValueError()
                record[field] = str(amount)
            except Exception as exc:
                raise HTTPException(502, "Tango devolvió un importe inválido.") from exc
    # Apply equivalent nets within each company: numeric source IDs can coincide.
    for company in ("FONTELA", "VIVIANA"):
        add_net_applications([r for r in records if r["empresa"] == company])
    add_document_nets(records)
    acopio_or_404(db, acopio_id, lock=True)
    inserted = 0
    seen = set()
    for record in records:
        key = record["empresa"], record["tipo"], record["origen_id"]
        if key in seen:
            raise HTTPException(502, "Tango devolvió un comprobante duplicado.")
        seen.add(key)
        latest = db.query(TangoRegistro).filter_by(acopio_id=acopio_id, empresa=key[0],
            origen_tipo=key[1], origen_id=key[2]).order_by(TangoRegistro.id.desc()).first()
        if not latest or latest.datos != record:
            # A source can return to an older value. It is a new observation,
            # rather than silently making a different historical revision current.
            canonical = json.dumps(record, sort_keys=True, ensure_ascii=False, separators=(",", ":"))
            fingerprint = hashlib.sha256((str(latest.id if latest else 0) + ":" + canonical).encode()).hexdigest()
            for previous in db.query(TangoRegistro).filter_by(acopio_id=acopio_id, empresa=key[0],
                    origen_tipo=key[1], origen_id=key[2], estado="PENDIENTE"):
                previous.estado = "SUPERADO"
            db.add(TangoRegistro(acopio_id=acopio_id, empresa=key[0], origen_tipo=key[1],
                                 origen_id=key[2], huella=fingerprint, datos=record, estado="PENDIENTE"))
            inserted += 1
    db.commit()
    return snapshot(db, acopio_id, consultation={"nuevos": inserted, "encontrados": len(records),
                                                "avisos": response.get("avisos", [])})


def review(db, acopio_id, record_id, state):
    acopio_or_404(db, acopio_id, lock=True)
    record = db.query(TangoRegistro).filter_by(id=record_id, acopio_id=acopio_id).first()
    if not record:
        raise HTTPException(404, "Registro no encontrado en este acopio")
    latest = db.query(TangoRegistro).filter_by(acopio_id=acopio_id, empresa=record.empresa,
        origen_tipo=record.origen_tipo, origen_id=record.origen_id).order_by(TangoRegistro.id.desc()).first()
    if record.id != latest.id and not (state == "DESCARTADO" and record.estado == "CONSERVADO"):
        raise HTTPException(409, "Hay una versión más reciente. Revisá los datos actualizados.")
    if state == "CONSERVADO":
        others = db.query(TangoRegistro).filter(TangoRegistro.acopio_id == acopio_id,
            TangoRegistro.empresa == record.empresa, TangoRegistro.origen_tipo == record.origen_tipo,
            TangoRegistro.origen_id == record.origen_id, TangoRegistro.id != record.id,
            TangoRegistro.estado.in_(["CONSERVADO", "PENDIENTE"])).all()
        for previous in others:
            previous.estado = "SUPERADO"
    record.estado = state
    record.revisado_at = datetime.utcnow() if state != "PENDIENTE" else None
    db.commit()
    return snapshot(db, acopio_id)


def discard_pending(db, acopio_id):
    acopio_or_404(db, acopio_id, lock=True)
    for row in db.query(TangoRegistro).filter_by(acopio_id=acopio_id, estado="PENDIENTE"):
        row.estado = "DESCARTADO"
        row.revisado_at = datetime.utcnow()
    db.commit()
    return snapshot(db, acopio_id)