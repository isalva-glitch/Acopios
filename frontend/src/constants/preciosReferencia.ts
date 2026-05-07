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

export const PRECIO_REFERENCIA_PROCESOS: Array<{
    key: PrecioReferenciaProcesoKey;
    label: string;
    shortLabel: string;
}> = [
    { key: 'vidrio_exterior', label: 'Vidrio Exterior', shortLabel: 'Vidrio ext.' },
    { key: 'vidrio_interior', label: 'Vidrio Interior', shortLabel: 'Vidrio int.' },
    { key: 'camara_estructural', label: 'Cámara Estructural', shortLabel: 'Cám. estruct.' },
    { key: 'pulido', label: 'Pulido', shortLabel: 'Pulido' },
    { key: 'fason_templado_exterior', label: 'Fasón Templado Exterior', shortLabel: 'Fasón temp.' },
    { key: 'pegado_bastidor', label: 'Pegado a Bastidor', shortLabel: 'Peg. bastidor' },
    { key: 'camara_normal', label: 'Cámara Normal', shortLabel: 'Cám. normal' },
    { key: 'opacificado_perimetral', label: 'Opacificado Perimetral', shortLabel: 'Opac. perim.' },
    { key: 'opacificado_total', label: 'Opacificado Total', shortLabel: 'Opac. total' },
    { key: 'camara_offset', label: 'Cámara Offset', shortLabel: 'Cám. offset' },
];
