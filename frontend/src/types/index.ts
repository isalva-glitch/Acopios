// TypeScript types for the application

export interface Acopio {
    id: number;
    numero: string;
    obra_id: number;
    fecha_alta: string;
    fecha_vencimiento?: string | null;
    estado: string;
    total_m2: number;
    total_ml: number;
    total_pesos: number;
    total_unidades?: number;
    saldo_m2: number;
    saldo_ml: number;
    saldo_pesos: number;
    saldo_unidades?: number;
    panos?: number; // Compatibilidad legacy: usar saldo_unidades cuando exista
    cliente?: string | null;
    obra?: string | null;
}

export interface AcopioPaquete {
    id: number;
    numero?: string | null;
    nombre: string;
    cliente: string;
    fecha_alta: string;
    estado: string;
    observaciones?: string | null;
    cantidad_acopios: number;
    total_pesos: number;
    total_m2: number;
    total_ml: number;
    total_unidades: number;
}

export interface AcopioPaqueteAcopio {
    id: number;
    numero_acopio?: string | null;
    presupuesto?: string | null;
    obra?: string | null;
    cliente?: string | null;
    estado: string;
    total_pesos: number;
    saldo_pesos: number;
    total_m2: number;
    total_ml: number;
    total_unidades: number;
}

export interface AcopioPaqueteDetalle extends AcopioPaquete {
    acopios: AcopioPaqueteAcopio[];
}

export interface AcopioPaquetePreviewItem {
    presupuesto: string;
    cliente?: string | null;
    obra?: string | null;
    importe: number;
    m2: number;
    ml: number;
    unidades: number;
    estado_validacion: string;
    observaciones?: string | null;
    valido: boolean;
}

export interface PrecioReferencia {
    id?: number;
    acopio_id: number;
    vidrio_exterior: number;
    vidrio_interior: number;
    camara_estructural: number;
    pulido: number;
    fason_templado_exterior: number;
    pegado_bastidor: number;
    camara_normal: number;
    opacificado_perimetral: number;
    opacificado_total: number;
    camara_offset: number;
    created_at?: string;
    updated_at?: string;
}

export type UnidadPrecioReferencia = 'm2' | 'ml' | 'unidad';
export type OrigenPrecioReferencia = 'autodetectado' | 'manual' | 'migrado';
export type EstadoPreciosReferencia = 'completo' | 'incompleto' | 'sin_conceptos' | 'revisar';

export interface ConceptoPrecioReferencia {
    concepto: string;
    unidad: UnidadPrecioReferencia;
    habilitado: boolean;
    precio_base: number | null;
    precio_actual: number | null;
    origen: OrigenPrecioReferencia;
}

export interface ItemPreciosReferencia {
    item_id: number;
    numero_item: string;
    descripcion: string;
    cantidad: number;
    total_m2: number;
    total_ml: number;
    total_pesos: number;
    conceptos: ConceptoPrecioReferencia[];
    estado_precios_referencia: EstadoPreciosReferencia;
}

export interface AcopioItemsPreciosReferencia {
    acopio_id: number;
    items: ItemPreciosReferencia[];
}

export interface Pedido {
    id: number;
    numero: string;
    obra_id: number;
    fecha: string;
    estado: string;
    total_m2: number;
    total_ml: number;
    total_pesos: number;
}

export interface Warning {
    level: 'INFO' | 'WARNING' | 'ERROR';
    message: string;
    field?: string;
    expected?: any;
    actual?: any;
    tolerance?: number;
}

export interface ExtractionPackage {
    meta: {
        extraction_date: string;
        pdf_filename: string;
        pdf_hash: string;
        extractor_version?: string;
    };
    acopio: {
        numero: string;
        fecha_alta: string;
        obra: string;
        cliente: string;
        total_m2?: number;
        total_ml?: number;
        total_pesos?: number;
    };
    presupuestos: any[];
    items: any[];
    panos: any[];
    pedidos?: any[];
    warnings: Warning[];
}

export interface AcopioPreview {
    extraction_package: ExtractionPackage;
    warnings: Warning[];
}

export interface Imputacion {
    id: number;
    pedido_id: number;
    acopio_id: number;
    acopio_item_id?: number | null;
    cantidad_m2: number;
    cantidad_ml: number;
    cantidad_pesos: number;
    cantidad_unidades?: number;
    es_excedente: boolean;
    pedido_item_descripcion?: string | null;
    composicion_match_estado?: string | null;
    composicion_match_score?: number | null;
    composicion_advertencia?: string | null;
}

export interface ResumenCompensacionDetalle {
    cantidad: number;
}

export interface ResumenCompensacionItemDetalle extends ResumenCompensacionDetalle {
    item_id: number;
    descripcion: string;
}

export interface ResumenCompensacionPedidoDetalle extends ResumenCompensacionDetalle {
    imputacion_id: number;
    pedido_id: number;
    pedido_numero?: string | null;
    origen: string;
}

export interface ResumenCompensacionItemValorizacion {
    item_id: number;
    descripcion: string;
    cantidad_acopio: number;
    cantidad_pedidos: number;
    diferencia: number;
    precio_referencia: number;
    importe: number;
    precio_faltante: boolean;
}

export interface ResumenCompensacionRow {
    proceso: string;
    label: string;
    unidad: 'm2' | 'ml';
    cantidad_acopio: number;
    cantidad_pedidos: number;
    diferencia: number;
    precio_referencia: number;
    importe: number;
    estado: 'sobrante_acopio' | 'excedente_pedido' | 'compensado';
    precio_faltante: boolean;
    items_acopio: ResumenCompensacionItemDetalle[];
    pedidos: ResumenCompensacionPedidoDetalle[];
    items_valorizacion?: ResumenCompensacionItemValorizacion[];
}

export interface ResumenCompensacion {
    acopio_id: number;
    numero?: string | null;
    v_presupuesto_id?: string | null;
    totals: {
        positivo: number;
        negativo: number;
        saldo: number;
    };
    rows: ResumenCompensacionRow[];
    warnings: string[];
}
