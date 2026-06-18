"""Business service for acopio packages."""
from decimal import Decimal
from typing import Any, Dict, Iterable, List, Optional

from sqlalchemy import or_
from sqlalchemy.orm import Session, joinedload

from integrations.spf import services as spf_services
from models import Acopio, AcopioPaquete, Obra
from services.acopio_creation_service import AcopioCreationService
from schemas.acopio_paquete import (
    AcopioPaqueteAcopio,
    AcopioPaqueteCreate,
    AcopioPaqueteDetalle,
    AcopioPaqueteListItem,
    AcopioPaquetePdfPreviewResponse,
    AcopioPaquetePreviewItem,
    AcopioPaqueteUpdate,
)


def _to_decimal(value) -> Decimal:
    if value is None:
        return Decimal("0")
    if isinstance(value, Decimal):
        return value
    return Decimal(str(value))


def _to_float(value) -> float:
    return float(_to_decimal(value))


def _clean_presupuesto(value: str) -> str:
    return str(value or "").strip()


def _presupuesto_variants(value: str) -> list[str]:
    raw_value = _clean_presupuesto(value)
    if not raw_value:
        return []

    variants = {raw_value}
    if raw_value.isdigit():
        numeric_text = str(int(raw_value))
        variants.add(numeric_text)
        variants.add(numeric_text.zfill(9))
    return list(variants)


def _display_presupuesto(value: str | None) -> Optional[str]:
    raw_value = _clean_presupuesto(value)
    if raw_value.isdigit():
        return str(int(raw_value)).zfill(9)
    return raw_value or None


def _total_unidades_from_details(details: dict) -> int:
    return sum(int(item.get("cantidad") or 0) for item in details.get("items", []))


def _pdf_header(extraction_package: Dict[str, Any]) -> Dict[str, Any]:
    return extraction_package.get("presupuesto") or {}


def _pdf_presupuesto_number(extraction_package: Dict[str, Any]) -> str:
    return _clean_presupuesto(_pdf_header(extraction_package).get("numero"))


def _pdf_cliente(extraction_package: Dict[str, Any]) -> Optional[str]:
    header = _pdf_header(extraction_package)
    return header.get("empresa") or header.get("empresa_raw") or header.get("contacto")


def _pdf_obra(extraction_package: Dict[str, Any]) -> Optional[str]:
    return _pdf_header(extraction_package).get("obra")


def _acopio_presupuesto(acopio: Acopio) -> Optional[str]:
    if acopio.presupuestos:
        return _display_presupuesto(acopio.presupuestos[0].numero)
    return _display_presupuesto(acopio.v_presupuesto_id or acopio.numero)


def _acopio_cliente(acopio: Acopio) -> Optional[str]:
    if acopio.obra and acopio.obra.cliente:
        return acopio.obra.cliente.nombre
    return None


def _acopio_estado(acopio: Acopio) -> str:
    return acopio.estado.value if hasattr(acopio.estado, "value") else str(acopio.estado)


class AcopioPaqueteService:
    """Create and read packages without duplicating acopio logic."""

    @staticmethod
    def _query_paquetes(db: Session):
        return db.query(AcopioPaquete).options(
            joinedload(AcopioPaquete.acopios)
            .joinedload(Acopio.obra)
            .joinedload(Obra.cliente),
            joinedload(AcopioPaquete.acopios)
            .joinedload(Acopio.presupuestos),
        )

    @staticmethod
    def _existing_acopio_for_presupuesto(db: Session, presupuesto: str) -> Optional[Acopio]:
        variants = _presupuesto_variants(presupuesto)
        if not variants:
            return None

        return db.query(Acopio).filter(
            or_(
                Acopio.v_presupuesto_id.in_(variants),
                Acopio.numero.in_(variants),
            )
        ).first()

    @classmethod
    def _validate_no_repeated_sources(
        cls,
        presupuestos: Iterable[str],
        pdf_presupuestos: Iterable[Dict[str, Any]],
    ) -> None:
        seen: set[str] = set()

        for raw_value in [
            *presupuestos,
            *(_pdf_presupuesto_number(item) for item in pdf_presupuestos),
        ]:
            value = _clean_presupuesto(raw_value)
            if not value:
                raise ValueError("Todos los presupuestos deben tener numero")

            variants = {variant.lower() for variant in _presupuesto_variants(value)}
            if seen.intersection(variants):
                raise ValueError(f"Presupuesto repetido en el paquete: {value}")
            seen.update(variants)

    @classmethod
    def preview_pdf_extraction(
        cls,
        db: Session,
        extraction_package: Dict[str, Any],
    ) -> AcopioPaquetePdfPreviewResponse:
        presupuesto = _pdf_presupuesto_number(extraction_package)
        header = _pdf_header(extraction_package)
        warnings = extraction_package.get("warnings", [])

        if not presupuesto:
            return AcopioPaquetePdfPreviewResponse(
                presupuesto="",
                cliente=_pdf_cliente(extraction_package),
                obra=_pdf_obra(extraction_package),
                importe=_to_float(header.get("total_importe")),
                m2=_to_float(header.get("total_m2")),
                ml=_to_float(header.get("total_ml")),
                unidades=int(header.get("total_unidades") or 0),
                estado_validacion="ERROR",
                observaciones="El PDF no tiene numero de presupuesto",
                valido=False,
                extraction_package=extraction_package,
                warnings=warnings,
            )

        existing = cls._existing_acopio_for_presupuesto(db, presupuesto)
        if existing:
            return AcopioPaquetePdfPreviewResponse(
                presupuesto=presupuesto,
                cliente=_acopio_cliente(existing) or _pdf_cliente(extraction_package),
                obra=(existing.obra.nombre if existing.obra else None) or _pdf_obra(extraction_package),
                importe=_to_float(existing.total_pesos),
                m2=_to_float(existing.total_m2),
                ml=_to_float(existing.total_ml),
                unidades=existing.total_unidades or 0,
                estado_validacion="ERROR",
                observaciones=f"Ya existe un acopio para el presupuesto {presupuesto}",
                valido=False,
                extraction_package=extraction_package,
                warnings=warnings,
            )

        return AcopioPaquetePdfPreviewResponse(
            presupuesto=presupuesto,
            cliente=_pdf_cliente(extraction_package),
            obra=_pdf_obra(extraction_package),
            importe=_to_float(header.get("total_importe")),
            m2=_to_float(header.get("total_m2")),
            ml=_to_float(header.get("total_ml")),
            unidades=int(header.get("total_unidades") or 0),
            estado_validacion="OK",
            observaciones=None,
            valido=True,
            extraction_package=extraction_package,
            warnings=warnings,
        )

    @classmethod
    def preview_presupuestos(
        cls,
        db: Session,
        spf_db: Session,
        presupuestos: Iterable[str],
    ) -> List[AcopioPaquetePreviewItem]:
        seen: set[str] = set()
        preview: List[AcopioPaquetePreviewItem] = []

        for presupuesto_raw in presupuestos:
            presupuesto = _clean_presupuesto(presupuesto_raw)
            if not presupuesto:
                preview.append(AcopioPaquetePreviewItem(
                    presupuesto=presupuesto,
                    estado_validacion="ERROR",
                    observaciones="Presupuesto vacio",
                    valido=False,
                ))
                continue

            variants = {variant.lower() for variant in _presupuesto_variants(presupuesto)}
            if seen.intersection(variants):
                preview.append(AcopioPaquetePreviewItem(
                    presupuesto=presupuesto,
                    estado_validacion="ERROR",
                    observaciones="Presupuesto repetido en la solicitud",
                    valido=False,
                ))
                continue
            seen.update(variants)

            existing = cls._existing_acopio_for_presupuesto(db, presupuesto)
            if existing:
                preview.append(AcopioPaquetePreviewItem(
                    presupuesto=presupuesto,
                    cliente=_acopio_cliente(existing),
                    obra=existing.obra.nombre if existing.obra else None,
                    importe=_to_float(existing.total_pesos),
                    m2=_to_float(existing.total_m2),
                    ml=_to_float(existing.total_ml),
                    unidades=existing.total_unidades or 0,
                    estado_validacion="ERROR",
                    observaciones=f"Ya existe un acopio para el presupuesto {presupuesto}",
                    valido=False,
                ))
                continue

            details = spf_services.get_presupuesto_details(spf_db, presupuesto)
            if not details:
                preview.append(AcopioPaquetePreviewItem(
                    presupuesto=presupuesto,
                    estado_validacion="ERROR",
                    observaciones="Presupuesto no encontrado en SPF",
                    valido=False,
                ))
                continue

            preview.append(AcopioPaquetePreviewItem(
                presupuesto=details.get("v_presupuesto_id") or presupuesto,
                cliente=details.get("cliente_nombre"),
                obra=details.get("obra_nombre"),
                importe=_to_float(details.get("total_pesos")),
                m2=_to_float(details.get("total_m2")),
                ml=_to_float(details.get("total_ml")),
                unidades=_total_unidades_from_details(details),
                estado_validacion="OK",
                observaciones=None,
                valido=True,
            ))

        return preview

    @classmethod
    def create_paquete(
        cls,
        db: Session,
        spf_db: Session,
        payload: AcopioPaqueteCreate,
    ) -> AcopioPaqueteDetalle:
        nombre = payload.nombre.strip()
        cliente = payload.cliente.strip()
        if not nombre:
            raise ValueError("El nombre del paquete es obligatorio")
        if not cliente:
            raise ValueError("El cliente del paquete es obligatorio")

        presupuestos = [_clean_presupuesto(item) for item in payload.presupuestos]
        pdf_presupuestos = payload.pdf_presupuestos
        if not presupuestos and not pdf_presupuestos:
            raise ValueError("Debe cargar al menos un presupuesto SPF o PDF")

        cls._validate_no_repeated_sources(presupuestos, pdf_presupuestos)

        preview = cls.preview_presupuestos(db, spf_db, presupuestos)
        invalid_items = [item for item in preview if not item.valido]
        pdf_preview = [cls.preview_pdf_extraction(db, item) for item in pdf_presupuestos]
        invalid_items.extend(item for item in pdf_preview if not item.valido)
        if invalid_items:
            messages = [
                f"{item.presupuesto or '-'}: {item.observaciones or item.estado_validacion}"
                for item in invalid_items
            ]
            raise ValueError("; ".join(messages))

        paquete = AcopioPaquete(
            nombre=nombre,
            cliente=cliente,
            fecha_alta=payload.fecha_alta,
            estado="ACTIVO",
            observaciones=payload.observaciones.strip() if payload.observaciones else None,
            total_pesos=Decimal("0"),
            total_m2=Decimal("0"),
            total_ml=Decimal("0"),
            total_unidades=0,
        )

        try:
            db.add(paquete)
            db.flush()
            paquete.numero = f"PAQ-{paquete.id:06d}"

            for presupuesto in presupuestos:
                existing = cls._existing_acopio_for_presupuesto(db, presupuesto)
                if existing:
                    raise ValueError(f"{presupuesto}: Ya existe un acopio para este presupuesto")

                details = spf_services.get_presupuesto_details(spf_db, presupuesto)
                if not details:
                    raise ValueError(f"{presupuesto}: Presupuesto no encontrado en SPF")

                normalized_data = AcopioCreationService.build_from_spf(details)
                AcopioCreationService.persist_from_normalized_data(
                    db,
                    normalized_data,
                    commit=False,
                    fecha_alta=payload.fecha_alta,
                    paquete_id=paquete.id,
                )

            for extraction_package in pdf_presupuestos:
                presupuesto = _pdf_presupuesto_number(extraction_package)
                existing = cls._existing_acopio_for_presupuesto(db, presupuesto)
                if existing:
                    raise ValueError(f"{presupuesto}: Ya existe un acopio para este presupuesto")

                normalized_data = AcopioCreationService.build_from_pdf(extraction_package)
                AcopioCreationService.persist_from_normalized_data(
                    db,
                    normalized_data,
                    commit=False,
                    fecha_alta=payload.fecha_alta,
                    paquete_id=paquete.id,
                )

            db.flush()
            cls.recalculate_totals(paquete)
            db.commit()
            db.refresh(paquete)
            return cls.build_detalle(paquete)
        except Exception:
            db.rollback()
            raise

    @staticmethod
    def recalculate_totals(paquete: AcopioPaquete) -> None:
        paquete.total_pesos = sum((_to_decimal(a.total_pesos) for a in paquete.acopios), Decimal("0"))
        paquete.total_m2 = sum((_to_decimal(a.total_m2) for a in paquete.acopios), Decimal("0"))
        paquete.total_ml = sum((_to_decimal(a.total_ml) for a in paquete.acopios), Decimal("0"))
        paquete.total_unidades = sum((a.total_unidades or 0) for a in paquete.acopios)

    @classmethod
    def list_paquetes(cls, db: Session) -> List[AcopioPaqueteListItem]:
        paquetes = cls._query_paquetes(db).order_by(AcopioPaquete.fecha_alta.desc(), AcopioPaquete.id.desc()).all()
        return [cls.build_list_item(paquete) for paquete in paquetes]

    @classmethod
    def get_paquete(cls, db: Session, paquete_id: int) -> Optional[AcopioPaqueteDetalle]:
        paquete = cls._query_paquetes(db).filter(AcopioPaquete.id == paquete_id).first()
        if not paquete:
            return None
        return cls.build_detalle(paquete)

    @classmethod
    def update_paquete(
        cls,
        db: Session,
        paquete_id: int,
        payload: AcopioPaqueteUpdate,
    ) -> Optional[AcopioPaqueteDetalle]:
        paquete = cls._query_paquetes(db).filter(AcopioPaquete.id == paquete_id).first()
        if not paquete:
            return None

        data = payload.model_dump(exclude_unset=True)
        for field in ("nombre", "cliente", "observaciones", "estado"):
            if field in data:
                value = data[field]
                if value is None:
                    if field in ("nombre", "cliente", "estado"):
                        raise ValueError(f"{field} no puede estar vacio")
                    setattr(paquete, field, None)
                    continue

                if isinstance(value, str):
                    value = value.strip()
                    if field in ("nombre", "cliente", "estado") and not value:
                        raise ValueError(f"{field} no puede estar vacio")

                setattr(paquete, field, value)
        if "fecha_alta" in data:
            paquete.fecha_alta = data["fecha_alta"]

        try:
            cls.recalculate_totals(paquete)
            db.commit()
            db.refresh(paquete)
            return cls.build_detalle(paquete)
        except Exception:
            db.rollback()
            raise

    @classmethod
    def add_presupuesto(
        cls,
        db: Session,
        spf_db: Session,
        paquete_id: int,
        presupuesto: str,
    ) -> AcopioPaqueteDetalle:
        paquete = cls._query_paquetes(db).filter(AcopioPaquete.id == paquete_id).first()
        if not paquete:
            raise ValueError("Paquete no encontrado")

        presupuesto = _clean_presupuesto(presupuesto)
        if not presupuesto:
            raise ValueError("Presupuesto invalido")

        existing = cls._existing_acopio_for_presupuesto(db, presupuesto)
        if existing:
            raise ValueError(f"{presupuesto}: Ya existe un acopio para este presupuesto")

        details = spf_services.get_presupuesto_details(spf_db, presupuesto)
        if not details:
            raise ValueError(f"{presupuesto}: Presupuesto no encontrado en SPF")

        try:
            normalized_data = AcopioCreationService.build_from_spf(details)
            AcopioCreationService.persist_from_normalized_data(
                db,
                normalized_data,
                commit=False,
                fecha_alta=paquete.fecha_alta,
                paquete_id=paquete.id,
            )
            db.flush()
            db.refresh(paquete)
            cls.recalculate_totals(paquete)
            db.commit()
            db.refresh(paquete)
            return cls.build_detalle(paquete)
        except Exception:
            db.rollback()
            raise

    @classmethod
    def remove_acopio(
        cls,
        db: Session,
        paquete_id: int,
        acopio_id: int,
    ) -> AcopioPaqueteDetalle:
        paquete = cls._query_paquetes(db).filter(AcopioPaquete.id == paquete_id).first()
        if not paquete:
            raise ValueError("Paquete no encontrado")

        acopio = next((a for a in paquete.acopios if a.id == acopio_id), None)
        if not acopio:
            raise ValueError("El acopio no pertenece a este paquete")

        try:
            db.delete(acopio)
            db.flush()
            db.refresh(paquete)
            cls.recalculate_totals(paquete)
            db.commit()
            db.refresh(paquete)
            return cls.build_detalle(paquete)
        except Exception:
            db.rollback()
            raise

    @staticmethod
    def build_list_item(paquete: AcopioPaquete) -> AcopioPaqueteListItem:
        total_pesos = sum((_to_decimal(a.total_pesos) for a in paquete.acopios), Decimal("0"))
        total_m2 = sum((_to_decimal(a.total_m2) for a in paquete.acopios), Decimal("0"))
        total_ml = sum((_to_decimal(a.total_ml) for a in paquete.acopios), Decimal("0"))
        total_unidades = sum((a.total_unidades or 0) for a in paquete.acopios)

        return AcopioPaqueteListItem(
            id=paquete.id,
            numero=paquete.numero,
            nombre=paquete.nombre,
            cliente=paquete.cliente,
            fecha_alta=paquete.fecha_alta.isoformat() if paquete.fecha_alta else "",
            estado=paquete.estado,
            cantidad_acopios=len(paquete.acopios),
            total_pesos=float(total_pesos),
            total_m2=float(total_m2),
            total_ml=float(total_ml),
            total_unidades=total_unidades,
        )

    @classmethod
    def build_detalle(cls, paquete: AcopioPaquete) -> AcopioPaqueteDetalle:
        base = cls.build_list_item(paquete)
        acopios = sorted(paquete.acopios, key=lambda item: item.id or 0)

        return AcopioPaqueteDetalle(
            **base.model_dump(),
            observaciones=paquete.observaciones,
            acopios=[
                AcopioPaqueteAcopio(
                    id=acopio.id,
                    numero_acopio=acopio.numero,
                    presupuesto=_acopio_presupuesto(acopio),
                    obra=acopio.obra.nombre if acopio.obra else None,
                    cliente=_acopio_cliente(acopio),
                    estado=_acopio_estado(acopio),
                    total_pesos=_to_float(acopio.total_pesos),
                    saldo_pesos=_to_float(acopio.saldo_pesos),
                    total_m2=_to_float(acopio.total_m2),
                    total_ml=_to_float(acopio.total_ml),
                    total_unidades=acopio.total_unidades or 0,
                )
                for acopio in acopios
            ],
        )
