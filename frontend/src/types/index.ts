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
