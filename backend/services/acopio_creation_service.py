"""Service for unified Acopio creation from any source."""
from typing import Dict, Any, List
from sqlalchemy.orm import Session
from datetime import date, datetime
from decimal import Decimal

from models import (
    Acopio, Presupuesto, AcopioItem, AcopioItemPano, EstadoAcopio
)
from services import acopio_service
from services.acopio_creation_models import (
    NormalizedAcopioData, NormalizedItem, NormalizedPano, NormalizedPresupuesto, NormalizedAdicional
)


class AcopioCreationService:
    """Service to orchestrate and persist Acopios from different sources."""

    @staticmethod
    def build_from_spf(spf_details: Dict[str, Any]) -> NormalizedAcopioData:
        """Map SPF specific data structure to NormalizedAcopioData."""
        
        # Map Presupuesto(s)
        # Note: SPF currently returns a single budget details object
        # but we can wrap it in a list.
        presupuestos = [
            NormalizedPresupuesto(
                numero=spf_details.get("v_presupuesto_id", ""),
                fecha=date.today(),  # SPF doesn't always provide approvals, so today is safe default
                estado="Aprobado",   # Implicit if we're creating acopio from it 
                empresa=spf_details.get("cliente_nombre"),
                condiciones=""
            )
        ]
        
        # Map Items and Panos
        items: List[NormalizedItem] = []
        for it_data in spf_details.get("items", []):
            panos: List[NormalizedPano] = []
            for p_data in it_data.get("panos", []):
                panos.append(NormalizedPano(
                    cantidad=p_data["cantidad"],
                    ancho_mm=int(p_data["ancho"]),
                    alto_mm=int(p_data["alto"]),
                    superficie_m2=Decimal(str(p_data["superficie_m2"])),
                    perimetro_ml=Decimal(str(p_data["perimetro_ml"])),
                    precio_unitario=Decimal(str(p_data.get("precio_unitario", 0))),
                    precio_total=Decimal(str(p_data.get("precio_total", 0))),
                    denominacion=None # SPF doesn't have PV1, etc labels
                ))
            adicionales: List[NormalizedAdicional] = []
            for a_data in it_data.get("adicionales", []):
                adicionales.append(NormalizedAdicional(
                    cantidad=a_data["cantidad"],
                    descripcion=a_data["descripcion"],
                    precio_unitario=Decimal(str(a_data.get("precio_unitario", 0))),
                    precio_total=Decimal(str(a_data.get("precio_total", 0)))
                ))
            
            items.append(NormalizedItem(
                descripcion=it_data["descripcion"],
                tipologia="SPF",
                cantidad=it_data.get("cantidad", 0),
                total_m2=Decimal(str(it_data.get("total_m2", 0))),
                total_ml=Decimal(str(it_data.get("total_ml", 0))),
                total_pesos=Decimal(str(it_data.get("total_pesos", 0))),
                panos=panos,
                adicionales=adicionales
            ))

        return NormalizedAcopioData(
            numero=spf_details.get("v_presupuesto_id", ""),
            cliente_nombre=spf_details.get("cliente_nombre", "Desconocido"),
            total_m2=Decimal(str(spf_details.get("total_m2", 0))),
            total_ml=Decimal(str(spf_details.get("total_ml", 0))),
            total_pesos=Decimal(str(spf_details.get("total_pesos", 0))),
            total_unidades=sum(item.cantidad for item in items),
            origen_datos="spf_production",
            v_presupuesto_id=spf_details.get("v_presupuesto_id"),
            cliente_id_spf=spf_details.get("cliente_id"),
            presupuestos=presupuestos,
            items=items,
            metadata={"raw_spf": spf_details}
        )

    @staticmethod
    def build_from_pdf(parsed_budget: Dict[str, Any]) -> NormalizedAcopioData:
        """Map PDF extraction data structure to NormalizedAcopioData."""
        hdr = parsed_budget["presupuesto"]
        
        # Map Presupuesto(s)
        fecha_aprob = None
        if hdr.get("fecha_aprobacion"):
            try:
                # The extractor manda DD/MM/YY
                dt = datetime.strptime(hdr["fecha_aprobacion"], "%d/%m/%y")
                fecha_aprob = dt.date()
            except:
                pass

        presupuestos = [
            NormalizedPresupuesto(
                numero=hdr["numero"],
                fecha=fecha_aprob,
                empresa=hdr["empresa"],
                contacto=hdr["contacto"],
                cotizado_por=hdr["cotizado_por"],
                peso_estimado_kg=Decimal(str(hdr["peso_estimado_kg"] or 0)),
                estado=hdr["estado"]
            )
        ]
        
        # Map Items and Panos
        items: List[NormalizedItem] = []
        for it_data in parsed_budget["items"]:
            panos: List[NormalizedPano] = []
            for p_data in it_data["panos"]:
                panos.append(NormalizedPano(
                    cantidad=p_data["cantidad"],
                    ancho_mm=p_data["ancho_mm"],
                    alto_mm=p_data["alto_mm"],
                    superficie_m2=Decimal(str(p_data["superficie_m2"])),
                    perimetro_ml=Decimal(str(p_data["perimetro_ml"])),
                    precio_unitario=Decimal(str(p_data["precio_unitario"])),
                    precio_total=Decimal(str(p_data["precio_total"])),
                    denominacion=p_data.get("denominacion")
                ))
            adicionales: List[NormalizedAdicional] = []
            for a_data in it_data.get("adicionales", []):
                adicionales.append(NormalizedAdicional(
                    cantidad=a_data["cantidad"],
                    descripcion=a_data["descripcion"],
                    precio_unitario=Decimal(str(a_data["precio_unitario"])),
                    precio_total=Decimal(str(a_data["precio_total"]))
                ))
            
            items.append(NormalizedItem(
                numero_item=it_data["numero_item"],
                descripcion=it_data["descripcion"],
                tipologia="PDF",
                cantidad=it_data["cantidad"],
                total_m2=Decimal(str(it_data["total_m2"])),
                total_ml=Decimal(str(it_data["total_ml"])),
                total_pesos=Decimal(str(it_data["total_pesos"])),
                panos=panos,
                adicionales=adicionales
            ))

        return NormalizedAcopioData(
            numero=hdr["numero"],
            v_presupuesto_id=hdr["numero"],
            cliente_nombre=hdr["empresa"] or hdr["contacto"] or "Desconocido",
            obra_nombre=hdr.get("obra") or "General",
            total_m2=Decimal(str(hdr["total_m2"])),
            total_ml=Decimal(str(hdr["total_ml"])),
            total_pesos=Decimal(str(hdr["total_importe"])),
            total_unidades=hdr["total_unidades"],
            origen_datos="pdf_upload",
            presupuestos=presupuestos,
            items=items,
            warnings=parsed_budget.get("warnings", []),
            metadata={"raw_pdf": parsed_budget}
        )

    @staticmethod
    def persist_from_normalized_data(db: Session, data: NormalizedAcopioData) -> Acopio:
        """Unified persistence logic using NormalizedAcopioData DTO."""
        
        # 1. Get or create Cliente
        cliente = acopio_service.get_or_create_cliente(db, data.cliente_nombre)
        
        # 2. Get or create Obra (if provided)
        obra_id = None
        if data.obra_nombre:
            obra = acopio_service.get_or_create_obra(db, data.obra_nombre, cliente.id)
            obra_id = obra.id
            
        # 3. Create Acopio
        acopio = Acopio(
            numero=data.numero,
            fecha_alta=date.today(),
            estado=EstadoAcopio.ACTIVO,
            total_m2=data.total_m2,
            total_ml=data.total_ml,
            total_pesos=data.total_pesos,
            total_unidades=data.total_unidades,
            saldo_m2=data.total_m2,
            saldo_ml=data.total_ml,
            saldo_pesos=data.total_pesos,
            saldo_unidades=data.total_unidades,
            origen_datos=data.origen_datos,
            v_presupuesto_id=data.v_presupuesto_id,
            cliente_id=data.cliente_id_spf,
            obra_id=obra_id
        )
        db.add(acopio)
        db.flush()
        
        # 4. Create Presupuestos
        for pres_data in data.presupuestos:
            pres = Presupuesto(
                acopio_id=acopio.id,
                numero=pres_data.numero,
                fecha=pres_data.fecha,
                empresa=pres_data.empresa,
                contacto=pres_data.contacto,
                cotizado_por=pres_data.cotizado_por,
                peso_estimado_kg=pres_data.peso_estimado_kg,
                estado=pres_data.estado,
                condiciones=pres_data.condiciones
            )
            db.add(pres)
            
        # 5. Create Items & Panos
        for it_data in data.items:
            item = AcopioItem(
                acopio_id=acopio.id,
                numero_item=it_data.numero_item,
                descripcion=it_data.descripcion,
                material=it_data.material,
                tipologia=it_data.tipologia,
                cantidad=it_data.cantidad,
                total_m2=it_data.total_m2,
                total_ml=it_data.total_ml,
                total_pesos=it_data.total_pesos,
                saldo_m2=it_data.total_m2,
                saldo_ml=it_data.total_ml,
                saldo_pesos=it_data.total_pesos,
                saldo_cantidad=it_data.cantidad
            )
            db.add(item)
            db.flush()
            
            for p_data in it_data.panos:
                pano = AcopioItemPano(
                    item_id=item.id,
                    cantidad=p_data.cantidad,
                    ancho=Decimal(str(p_data.ancho_mm)),
                    alto=Decimal(str(p_data.alto_mm)),
                    superficie_m2=p_data.superficie_m2,
                    perimetro_ml=p_data.perimetro_ml,
                    precio_unitario=p_data.precio_unitario,
                    precio_total=p_data.precio_total,
                    denominacion=p_data.denominacion
                )
                db.add(pano)
                
            from models.acopio_item_adicional import AcopioItemAdicional
            for a_data in it_data.adicionales:
                adicional = AcopioItemAdicional(
                    item_id=item.id,
                    cantidad=a_data.cantidad,
                    descripcion=a_data.descripcion,
                    precio_unitario=a_data.precio_unitario,
                    precio_total=a_data.precio_total,
                    tipo=a_data.tipo,
                    origen=data.origen_datos
                )
                db.add(adicional)
                
        db.commit()
        db.refresh(acopio)
        return acopio

    @classmethod
    def create_from_spf(cls, db: Session, spf_details: Dict[str, Any]) -> Acopio:
        """Orchestrate SPF creation."""
        data = cls.build_from_spf(spf_details)
        return cls.persist_from_normalized_data(db, data)

    @classmethod
    def create_from_pdf(cls, db: Session, parsed_budget: Dict[str, Any]) -> Acopio:
        """Orchestrate PDF creation."""
        data = cls.build_from_pdf(parsed_budget)
        return cls.persist_from_normalized_data(db, data)
