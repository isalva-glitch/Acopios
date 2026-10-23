"""File queue shared by Docker and the Windows/Access worker; no network listener."""
import asyncio
import json
import os
import time
from pathlib import Path
from uuid import uuid4
from fastapi import HTTPException

SPOOL = Path(__file__).resolve().parents[1] / ".tango_access_bridge"
VERSION = 1
MAX_PDF = 20 * 1024 * 1024


def bridge_status(root=None):
    root = Path(root or SPOOL)
    try:
        data = json.loads((root / "heartbeat.json").read_text(encoding="utf-8-sig"))
        live = data.get("version") == VERSION and 0 <= time.time() - float(data["utc"]) < 20
        return {"activo": live, "access_abierto": bool(live and data.get("access")),
                "mensaje": "Conector disponible." if live and data.get("access") else
                "Abrí la interfaz Access de Tango." if live else
                "El conector de Access no está iniciado en este equipo. Ejecutá iniciar_sistema.bat o reiniciar_sistema.bat; abrir Access por sí solo no inicia la conexión con Acopios."}
    except (OSError, ValueError, TypeError, KeyError):
        return {"activo": False, "access_abierto": False,
                "mensaje": "El conector de Access no está iniciado en este equipo. Ejecutá iniciar_sistema.bat o reiniciar_sistema.bat; abrir Access por sí solo no inicia la conexión con Acopios."}


async def request_access(operation, arguments, *, root=None, timeout=90):
    if operation not in ("lookup", "pdf"):
        raise ValueError("Unsupported Access operation")
    root = Path(root or SPOOL)
    status = bridge_status(root)
    if not status["activo"] or not status["access_abierto"]:
        raise HTTPException(503, status["mensaje"])
    requests, responses = root / "requests", root / "responses"
    requests.mkdir(parents=True, exist_ok=True)
    responses.mkdir(parents=True, exist_ok=True)
    if len(list(requests.glob("*.json"))) >= 10:
        raise HTTPException(503, "Hay otras consultas en curso. Volvé a intentar en unos segundos.")
    job = uuid4().hex
    queued, result = requests / (job + ".json"), responses / (job + ".json")
    temporary = requests / (job + ".tmp")
    temporary.write_text(json.dumps({"version": VERSION, "id": job, "operation": operation,
                                    "expires": time.time() + timeout, "arguments": arguments}),
                         encoding="utf-8")
    os.replace(temporary, queued)
    try:
        deadline = time.monotonic() + timeout
        while not result.exists():
            if time.monotonic() >= deadline:
                raise HTTPException(504, "Access no respondió a tiempo. Revisá que esté abierto e intentá nuevamente.")
            await asyncio.sleep(0.25)
        if result.stat().st_size > 2 * 1024 * 1024:
            raise HTTPException(502, "La respuesta de Access supera el tamaño permitido.")
        packet = json.loads(result.read_text(encoding="utf-8-sig"))
        if packet.get("id") != job or packet.get("version") != VERSION:
            raise HTTPException(502, "Respuesta inválida del conector de Access.")
        if not packet.get("ok"):
            raise HTTPException(503, packet.get("error") or "No se pudo consultar Tango mediante Access.")
        if operation == "pdf":
            # A response cannot choose a local path: only this job's fixed file is read.
            path = responses / (job + ".pdf")
            if not path.is_file():
                raise HTTPException(404, "Tango no tiene un PDF accesible para este comprobante.")
            try:
                if path.stat().st_size > MAX_PDF:
                    raise HTTPException(422, "El PDF supera 20 MB.")
                content = path.read_bytes()
                if not content.startswith(b"%PDF-"):
                    raise HTTPException(422, "El archivo encontrado no es un PDF válido.")
                return content
            finally:
                path.unlink(missing_ok=True)
        return packet.get("data", {})
    except (ValueError, OSError) as exc:
        raise HTTPException(502, "No se pudo leer la respuesta del conector de Access.") from exc
    finally:
        result.unlink(missing_ok=True)
        queued.unlink(missing_ok=True)