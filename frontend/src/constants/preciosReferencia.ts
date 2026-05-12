export type PrecioReferenciaProcesoKey =
    | 'vidrio_exterior'
    | 'vidrio_interior'
    | 'camara_estructural'
    | 'pulido'
    | 'fason_templado_exterior'
    | 'pegado_bastidor'
    | 'camara_normal'
    | 'opacificado_perimetral'
    | 'opacificado_total'
    | 'camara_offset';

export type PrecioReferenciaProcesoUnidad = 'm2' | 'ml';

export const PRECIO_REFERENCIA_PROCESOS: Array<{
    key: PrecioReferenciaProcesoKey;
    label: string;
    shortLabel: string;
    unidad: PrecioReferenciaProcesoUnidad;
}> = [
    { key: 'vidrio_exterior', label: 'Vidrio Exterior', shortLabel: 'Vidrio ext.', unidad: 'm2' },
    { key: 'vidrio_interior', label: 'Vidrio Interior', shortLabel: 'Vidrio int.', unidad: 'm2' },
    { key: 'camara_estructural', label: 'Cámara Estructural', shortLabel: 'Cám. estruct.', unidad: 'ml' },
    { key: 'pulido', label: 'Pulido', shortLabel: 'Pulido', unidad: 'ml' },
    { key: 'fason_templado_exterior', label: 'Fasón Templado Exterior', shortLabel: 'Fasón temp.', unidad: 'm2' },
    { key: 'pegado_bastidor', label: 'Pegado a Bastidor', shortLabel: 'Peg. bastidor', unidad: 'ml' },
    { key: 'camara_normal', label: 'Cámara Normal', shortLabel: 'Cám. normal', unidad: 'ml' },
    { key: 'opacificado_perimetral', label: 'Opacificado Perimetral', shortLabel: 'Opac. perim.', unidad: 'ml' },
    { key: 'opacificado_total', label: 'Opacificado Total', shortLabel: 'Opac. total', unidad: 'm2' },
    { key: 'camara_offset', label: 'Cámara Offset', shortLabel: 'Cám. offset', unidad: 'ml' },
];
