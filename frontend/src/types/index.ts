// TypeScript types for the application

export interface Acopio {
    id: number;
    numero: string;
    obra_id: number;
    fecha_alta: string;
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
    acopio_item_id?: number;
    cantidad_m2: number;
    cantidad_ml: number;
    cantidad_pesos: number;
    cantidad_unidades?: number;
    es_excedente: boolean;
}
