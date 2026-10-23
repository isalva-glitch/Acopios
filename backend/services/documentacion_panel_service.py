"""Read-only projection of documents and Tango observations into one list."""
import re
import unicodedata
from fastapi import HTTPException
from services import documentacion_service as docs
from services import tango_service as tango
from services import tango_asociacion_service as association
from services.comprobante_numero import number_query

COMPANY_NAMES = {
    "FONTELA": "FONTELA", "FONTELACRISTALES": "FONTELA",
    "JOSEMFONTELAEHIJOSSACIF": "FONTELA",
    "VIVIANA": "VIVIANA", "VIVIANAFONTELA": "VIVIANA",
}


def source_key(data):
    return data["empresa"], data["tipo"], data["origen_id"]


def commercial_key(company, source_type, number):
    if source_type not in ("FAC", "REC"):
        return None
    try:
        query = number_query(number)
    except HTTPException:
        return None
    # Short sequences alone cannot identify a fiscal document across branches.
    if query["numero_modo"] != "COMPLETO":
        return None
    return company, source_type, query["numero_normalizado"]


def panel(db, acopio_id):
    documentacion = docs.snapshot(db, acopio_id)
    observations = tango.snapshot(db, acopio_id)
    candidates = {r["id"]: r for r in association.choices(db, acopio_id)["resultados"]}
    groups = {}
    for record in observations["registros"]:
        groups.setdefault(source_key(record["datos"]), []).append(record)

    rows = []
    linked = {}
    manual = {}
    for application in documentacion["documentos"]:
        comp = application["comprobante"]
        row = {"id": "asociacion-" + str(application["id"]), "aplicacion": application,
               "tango": None, "versiones_tango": [], "candidato": None,
               "archivado": application["anulada"], "actualizacion_tango": False}
        rows.append(row)
        origin = comp.get("origen_tango")
        if origin:
            linked.setdefault((origin["empresa"], origin["origen_tipo"], origin["origen_id"]), []).append(row)
        else:
            issuer = re.sub(r"[^A-Z0-9]", "", unicodedata.normalize("NFKD", comp["emisor"]).encode("ascii", "ignore").decode().upper())
            company = COMPANY_NAMES.get(issuer)
            source_type = "FAC" if comp["tipo"] in docs.INVOICE_TYPES else "REC" if comp["tipo"] == "RECIBO" else None
            key = commercial_key(company, source_type, comp["numero"]) if company else None
            if key:
                manual.setdefault(key, []).append(row)

    for key, versions in groups.items():
        versions.sort(key=lambda r: r["id"], reverse=True)
        latest = versions[0]
        retained = next((r for r in versions if r["estado"] == "CONSERVADO"), None)
        primary = retained if latest["estado"] == "DESCARTADO" and retained else latest
        data = primary["datos"]
        matches = linked.get(key)
        if not matches:
            matches = manual.get(commercial_key(data["empresa"], data["tipo"], data["numero"]), [])
        if matches:
            # A Tango identity (or an exact full number + known issuer) enriches
            # the existing application instead of producing another visible row.
            for row in matches:
                row["tango"] = primary
                row["versiones_tango"] = versions
                row["actualizacion_tango"] = latest["estado"] == "PENDIENTE"
                if row["actualizacion_tango"]:
                    row["archivado"] = False
            continue
        candidate = candidates.get(primary["id"]) if primary["id"] == latest["id"] else None
        rows.append({"id": "tango-" + "-".join(map(str, key)), "aplicacion": None,
                     "tango": primary, "versiones_tango": versions, "candidato": candidate,
                     "archivado": primary["estado"] in ("DESCARTADO", "SUPERADO"),
                     "actualizacion_tango": bool(primary["version_conservada_id"])})
    documentacion["listado"] = rows
    documentacion["conexion_tango"] = observations["conexion"]
    documentacion["pendientes_tango"] = sum(r["estado"] == "PENDIENTE" and r["es_actual"]
                                           for r in observations["registros"])
    return documentacion
