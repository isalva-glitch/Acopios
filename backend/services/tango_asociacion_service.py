"""Explicitly associate a reviewed Tango candidate with commercial documentation."""
from datetime import date
from io import BytesIO
from fastapi import HTTPException, UploadFile
from models import Comprobante, TipoComprobante, AfectacionAcopio
from models.tango_comprobante import TangoComprobante
from models.tango_registro import TangoRegistro
from services import documentacion_service as docs
from services import tango_service as tango
from services.tango_access_bridge import request_access
from services.tango_discovery import active_invoices, matches_invoice


def original_net(data):
    value = data.get("neto_documental")
    if value is None and data["tipo"] == "FAC" and data["empresa"] == "FONTELA":
        value = data["importe_control"]
    if value is None and data["tipo"] == "REC" and data["empresa"] == "VIVIANA":
        value = data["total"]
    return docs.money(value) if value is not None else None


def source_link(db, data, lock=False):
    q = db.query(TangoComprobante).filter_by(empresa=data["empresa"], origen_tipo=data["tipo"], origen_id=data["origen_id"])
    return (q.with_for_update() if lock else q).first()


def invoice_kind(data):
    return "FAC_MERCADERIA" if data.get("es_anticipo") is False else "FAC_ANTICIPO"


def metadata(data, kind=None):
    return {
        "tipo": (kind or invoice_kind(data)) if data["tipo"] == "FAC" else "RECIBO",
        "numero": data["numero"], "emisor": "Fontela" if data["empresa"] == "FONTELA" else "Viviana",
        "fecha": date.fromisoformat(data["fecha"]), "importe": original_net(data),
        "iva": docs.money(data["iva"]) if data["tipo"] == "FAC" else None,
    }


def blocked(data):
    if data["tipo"] != "REC" and not (data["tipo"] == "FAC" and data["empresa"] == "FONTELA"):
        return "Es un ajuste o registro interno. Puede conservarse para control; no se incorpora como factura fiscal o cobro."
    if str(data.get("fecha_anulacion") or "") > "1900-01-01":
        return "Comprobante anulado en Tango."
    if not data.get("moneda_corriente", True):
        return "Requiere revisar la conversión de moneda antes de asociarlo."
    if original_net(data) is None or original_net(data) <= 0:
        return "No se pudo determinar el neto completo del recibo. Revisá sus aplicaciones en Tango."
    if any(a.get("neto_equivalente") is None for a in data.get("aplicaciones", [])):
        return "Hay aplicaciones pendientes de revisión; no se puede proponer un neto seguro."
    return None


def suggested(data):
    if data["tipo"] == "REC" and data.get("aplicaciones"):
        return sum((docs.money(a.get("neto_equivalente")) for a in data["aplicaciones"]), docs.ZERO)
    return original_net(data) or docs.ZERO


def matching_reference(db, acopio_id, data):
    if data["tipo"] != "REC" or data["empresa"] != "FONTELA":
        return None
    ids = {a["factura_id"] for a in data.get("aplicaciones", [])}
    references = db.query(AfectacionAcopio).join(Comprobante).join(
        TangoComprobante, TangoComprobante.comprobante_id == Comprobante.id).filter(
        AfectacionAcopio.acopio_id == acopio_id, AfectacionAcopio.anulada.is_(False),
        TangoComprobante.empresa == "FONTELA", TangoComprobante.origen_tipo == "FAC",
        TangoComprobante.origen_id.in_(ids)).all() if ids else []
    # A manually entered invoice is also explicit evidence; do not manufacture a
    # TangoComprobante link or duplicate its economic application.
    for reference in active_invoices(db, acopio_id):
        if any(matches_invoice(reference, data["empresa"], app.get("factura_numero", ""))
               for app in data.get("aplicaciones", [])) and reference not in references:
            references.append(reference)
    return references[0].id if len(references) == 1 else None


def choices(db, acopio_id):
    panel = tango.snapshot(db, acopio_id)
    result = []
    for row in panel["registros"]:
        if not row["es_actual"] or row["estado"] in ("DESCARTADO", "SUPERADO"):
            continue
        data = row["datos"]
        link = source_link(db, data)
        comp = db.query(Comprobante).filter_by(id=link.comprobante_id).first() if link else None
        original = original_net(data)
        available = docs.money(docs.serialize_comprobante(db, comp)["disponible"]) if comp else original
        already = db.query(AfectacionAcopio).filter_by(acopio_id=acopio_id, comprobante_id=comp.id).first() if comp else None
        reason = blocked(data)
        if not already and data["tipo"] == "FAC":
            already = next((r for r in active_invoices(db, acopio_id)
                            if matches_invoice(r, data["empresa"], data["numero"])), None)
        if already:
            reason = "Ya está asociado a este acopio. Editá o restaurá el vínculo existente."
        amount = min(suggested(data), available or docs.ZERO)
        if amount <= 0 and not reason:
            reason = "No queda importe disponible para asociar."
        result.append({
            "id": row["id"], "empresa": data["empresa"], "tipo": docs.kind(comp) if comp else metadata(data)["tipo"],
            "permite_clasificar": not link and data["tipo"] == "FAC" and data["empresa"] == "FONTELA",
            "cliente": data.get("cliente", ""),
            "numero": data["numero"], "emisor": "Fontela" if data["empresa"] == "FONTELA" else "Viviana",
            "fecha": data["fecha"], "importe": str(original) if original is not None else None,
            "iva": data["iva"] if data["tipo"] == "FAC" else None,
            "original_bruto": data["total"], "disponible": str(available) if available is not None else None,
            "sugerido": str(amount), "referencia_id": matching_reference(db, acopio_id, data),
            "motivos": data.get("motivos", []), "observacion": data.get("observacion", ""),
            "bloqueo": reason, "pdf_url": f"/acopios/{acopio_id}/tango/registros/{row['id']}/pdf" if data.get("pdf_disponible") else None,
            "etiqueta": ("Factura de mercadería" if (docs.kind(comp) if comp else invoice_kind(data)) == "FAC_MERCADERIA" else "Factura de anticipo") if data["tipo"] == "FAC" and data["empresa"] == "FONTELA" else
                        "Recibo" if data["tipo"] == "REC" else "Ajuste / registro interno",
        })
    return {"conexion": panel["conexion"], "resultados": result}


async def associate(db, acopio_id, record_id, payload):
    record = db.query(TangoRegistro).filter_by(id=record_id, acopio_id=acopio_id).first()
    if not record:
        raise HTTPException(404, "Registro de Tango no encontrado en este acopio.")
    data = record.datos
    reason = blocked(data)
    if reason:
        raise HTTPException(422, reason)
    # Fetch a PDF before acquiring locks. Lack of a copy must not lose the association.
    pdf = None
    warning = None
    if data.get("pdf_disponible"):
        try:
            pdf = await request_access("pdf", {"empresa": record.empresa, "origen_id": record.origen_id})
        except HTTPException:
            warning = "Se guardó la asociación, pero no se pudo copiar el PDF de Tango. Podés adjuntarlo después."
    acopio = docs.get_acopio(db, acopio_id, lock=True)
    db.refresh(record)
    latest = db.query(TangoRegistro).filter_by(acopio_id=acopio_id, empresa=record.empresa,
        origen_tipo=record.origen_tipo, origen_id=record.origen_id).order_by(TangoRegistro.id.desc()).first()
    if record.id != latest.id or record.estado in ("DESCARTADO", "SUPERADO"):
        raise HTTPException(409, "La coincidencia cambió o fue descartada. Actualizá la búsqueda.")
    if docs.money(payload.importe_aplicado) > suggested(data):
        raise HTTPException(422, "El importe supera las aplicaciones de Tango relacionadas con este acopio.")
    fact = docs.money(payload.importe_facturado)
    if (data["empresa"] == "VIVIANA" and fact != 0) or (data["empresa"] == "FONTELA" and fact != docs.money(payload.importe_aplicado)):
        raise HTTPException(422, "La parte Facturado / Viviana debe coincidir con la empresa de Tango.")
    link = source_link(db, data, lock=True)
    requested_kind = getattr(payload, "tipo_factura", None)
    if requested_kind and (data["tipo"] != "FAC" or data["empresa"] != "FONTELA"):
        raise HTTPException(422, "La clasificación de factura solo corresponde a una factura de Fontela.")
    stored = db.query(Comprobante).filter_by(id=link.comprobante_id).with_for_update().one() if link else None
    meta = metadata(data, requested_kind or (docs.kind(stored) if stored else None))
    if link:
        comp = db.query(Comprobante).filter_by(id=link.comprobante_id).with_for_update().one()
        if any(getattr(comp, k) != (TipoComprobante(v) if k == "tipo" else v) for k, v in meta.items()) or docs.money(link.datos["total"]) != docs.money(data["total"]):
            raise HTTPException(409, "Los importes o datos originales cambiaron en Tango. Revisá el comprobante ya incorporado.")
        if db.query(AfectacionAcopio).filter_by(acopio_id=acopio_id, comprobante_id=comp.id).first():
            raise HTTPException(409, "El comprobante ya está asociado. Editá o restaurá el vínculo existente.")
    else:
        # Do not silently merge a manual document with an external source.
        existing = db.query(Comprobante).filter_by(numero=meta["numero"], emisor=meta["emisor"])
        kinds = docs.INVOICE_TYPES if meta["tipo"] in docs.INVOICE_TYPES else {meta["tipo"]}
        if existing.filter(Comprobante.tipo.in_([TipoComprobante(t) for t in kinds])).first():
            raise HTTPException(409, "Ya existe un comprobante con ese número y emisor. Seleccionalo entre los guardados en Acopios.")
        comp = Comprobante(**{**meta, "tipo": TipoComprobante(meta["tipo"])},
            descripcion=("Consultado desde Tango " + data["empresa"] + ". " + data.get("observacion", ""))[:2000])
        db.add(comp)
        db.flush()
        link = TangoComprobante(empresa=data["empresa"], origen_tipo=data["tipo"], origen_id=data["origen_id"],
                                comprobante_id=comp.id, datos=data)
        db.add(link)
    docs.validate_application(db, acopio, comp, payload)
    if payload.referencia_id and data["tipo"] == "REC":
        reference = docs.get_aplicacion(db, acopio_id, payload.referencia_id)
        ref_link = db.query(TangoComprobante).filter_by(comprobante_id=reference.comprobante_id).first()
        related = [a for a in data.get("aplicaciones", [])
                   if (ref_link and ref_link.empresa == data["empresa"]
                       and a["factura_id"] == ref_link.origen_id)
                   or (not ref_link and matches_invoice(reference, data["empresa"], a.get("factura_numero", "")))]
        if not related:
            raise HTTPException(422, "La factura elegida no figura entre las aplicaciones de ese recibo en Tango.")
        if docs.money(payload.importe_aplicado) > sum((docs.money(a["neto_equivalente"]) for a in related), docs.ZERO):
            raise HTTPException(422, "El importe supera lo aplicado en Tango a la factura elegida.")

    row = AfectacionAcopio(acopio_id=acopio_id, comprobante_id=comp.id)
    docs.set_application(row, payload)
    db.add(row)
    if pdf and not comp.documento_id:
        await docs.attach_pdf(db, comp, UploadFile(filename="Tango-" + data["numero"] + ".pdf", file=BytesIO(pdf)))
    # Explicit association also retains this source observation, without touching consumption.
    for previous in db.query(TangoRegistro).filter_by(acopio_id=acopio_id, empresa=record.empresa,
            origen_tipo=record.origen_tipo, origen_id=record.origen_id).filter(TangoRegistro.id != record.id,
            TangoRegistro.estado.in_(["CONSERVADO", "PENDIENTE"])):
        previous.estado = "SUPERADO"
    from datetime import datetime
    record.estado = "CONSERVADO"
    record.revisado_at = datetime.utcnow()
    db.commit()
    result = docs.snapshot(db, acopio_id)
    result["tango_aviso"] = warning
    return result
