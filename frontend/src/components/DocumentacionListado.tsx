import apiClient from '../api/client';
import { formatCurrencyAR } from '../utils/formatters';
import type { Aplicacion } from './DocumentacionAcopio';
import type { CandidatoTango } from './AsociarDesdeTango';

export type EstadoTango = 'PENDIENTE' | 'CONSERVADO' | 'DESCARTADO' | 'SUPERADO';
interface DatoTango {
    empresa: 'FONTELA' | 'VIVIANA'; tipo: string; numero: string; fecha: string; cliente: string;
    cliente_codigo: string; total: string; importe_control: string; iva: string;
    moneda_corriente: boolean; fecha_anulacion?: string; es_anticipo?: boolean;
    base_importe: string; neto_documental?: string | null; pdf_disponible: boolean; observacion: string; motivos: string[];
    aplicaciones: { factura_id: number; factura_numero: string; importe_bruto: string;
        neto_equivalente?: string | null; criterio_neto?: string }[];
    referencias_pedido: { id: number; pedido: string; oc: string; obra: string; importe: string }[];
}
export interface RegistroTango {
    id: number; estado: EstadoTango; datos: DatoTango; consultado_at: string;
    revisado_at: string | null; es_actual: boolean; version_conservada_id: number | null;
}
export interface FilaDocumento {
    id: string; aplicacion: Aplicacion | null; tango: RegistroTango | null; versiones_tango: RegistroTango[];
    candidato: CandidatoTango | null; archivado: boolean; actualizacion_tango: boolean;
}
export const tiposDocumento: Record<string, string> = {
    ORDEN_COMPRA: 'Orden de compra', FAC_ANTICIPO: 'Factura de anticipo',
    FAC_MERCADERIA: 'Factura de mercadería', RECIBO: 'Recibo',
};
const estadosDocumento: Record<string, string> = {
    REGISTRADO: 'Asociado', ANULADA: 'Vínculo anulado', SIN_CLASIFICAR: 'Sin clasificar',
    PENDIENTE_FACTURA: 'Pendiente de factura', PENDIENTE_OC: 'Pendiente de OC', COINCIDENTE: 'Coincidente',
    CON_DIFERENCIA: 'Con diferencia', COBRO_EXCEDIDO: 'Cobro superior a la factura',
    REVISAR_ANTICIPOS: 'Revisar aplicación de anticipos',
};
const estadosTango: Record<EstadoTango, string> = {
    PENDIENTE: 'Por revisar', CONSERVADO: 'Conservado para control',
    DESCARTADO: 'Descartado', SUPERADO: 'Versión anterior',
};
function fecha(value: string) { return new Date(value + 'T00:00:00').toLocaleDateString('es-AR'); }
function fechaConsulta(value: string) {
    return new Date(/[zZ]|[+-]\d\d:\d\d$/.test(value) ? value : value + 'Z').toLocaleString('es-AR');
}
function tipoTango(dato: DatoTango) {
    if (dato.tipo === 'FAC') return dato.empresa === 'VIVIANA' ? 'Registro interno Viviana'
        : dato.es_anticipo === false ? 'Factura de mercadería' : 'Factura de anticipo';
    return dato.tipo === 'REC' ? 'Recibo' : dato.tipo.startsWith('NC') ? 'Nota de crédito' : dato.tipo;
}
function netoTango(dato: DatoTango) {
    if (dato.tipo === 'REC' && dato.aplicaciones.length) {
        if (dato.aplicaciones.some(a => a.neto_equivalente == null)) return 'Por revisar';
        return formatCurrencyAR(dato.aplicaciones.reduce((sum, a) => sum + Number(a.neto_equivalente), 0));
    }
    if (dato.tipo === 'REC') {
        if (dato.empresa === 'VIVIANA') return formatCurrencyAR(Number(dato.total));
        return dato.neto_documental == null ? 'Por revisar' : formatCurrencyAR(Number(dato.neto_documental));
    }
    return formatCurrencyAR(Number(dato.importe_control));
}

export default function DocumentacionListado({ acopioId, rows, aplicaciones, history, busy, onEdit, onState, onAssociate, onReview }:
    { acopioId: number; rows: FilaDocumento[]; aplicaciones: Aplicacion[]; history: boolean; busy: boolean;
      onEdit: (row: Aplicacion) => void; onState: (row: Aplicacion) => void;
      onAssociate: (candidate: CandidatoTango) => void;
      onReview: (record: RegistroTango, estado: 'PENDIENTE' | 'CONSERVADO' | 'DESCARTADO') => void }) {
    const visible = rows.filter(row => history || !row.archivado);
    if (!visible.length) return <p className="doc-empty">Sin comprobantes asociados ni coincidencias pendientes. Agregá un comprobante, asociá uno existente o consultá Tango.</p>;
    return <div className="doc-table-scroll"><table className="doc-table doc-unified-table">
        <thead><tr><th>Comprobante / PDF</th><th>Origen y estado</th><th>Importe sin IVA</th><th>Aplicado al acopio</th><th>Detalle y control</th><th>Acciones</th></tr></thead>
        <tbody>{visible.map(row => {
            const app = row.aplicacion;
            const comp = app?.comprobante;
            const observation = row.tango;
            const dato = observation?.datos;
            const latest = row.versiones_tango[0];
            const number = comp?.numero || dato?.numero || '';
            const docDate = comp?.fecha || dato?.fecha || '';
            const pdfUrl = comp?.archivo?.disponible ? comp.archivo.url
                : dato?.pdf_disponible ? '/acopios/' + acopioId + '/tango/registros/' + observation!.id + '/pdf' : null;
            const reference = aplicaciones.find(a => a.id === app?.referencia_id);
            return <tr key={row.id} className={row.archivado ? 'doc-annulled' : !app ? 'doc-discovered' : ''}>
                <td><small>{comp ? tiposDocumento[comp.tipo] : dato ? tipoTango(dato) : ''}</small>
                    {pdfUrl ? <a href={apiClient.defaults.baseURL + pdfUrl} target="_blank" rel="noreferrer">{number} ↗</a> : <strong>{number}</strong>}
                    <small>{comp?.emisor || (dato?.empresa === 'FONTELA' ? 'Fontela' : 'Viviana')} · {fecha(docDate)}</small>
                    {!pdfUrl && <small className="doc-missing">PDF pendiente</small>}
                    {dato && <small>{dato.cliente}</small>}
                </td>
                <td><span className="doc-origin">{comp?.origen_tango ? 'Tango ' + (comp.origen_tango.empresa === 'FONTELA' ? 'Fontela' : 'Viviana') : app ? dato ? 'Carga manual · datos en Tango' : 'Carga manual' : dato?.empresa === 'FONTELA' ? 'Tango Fontela' : 'Tango Viviana'}</span>
                    <small><span className={'doc-status ' + (app ? 'doc-status-' + app.estado.toLowerCase() : 'doc-tango-' + observation?.estado.toLowerCase())}>
                        {app ? app.anulada ? 'Vínculo anulado' : 'Asociado' : observation?.estado === 'CONSERVADO' ? 'Conservado · sin asociar' : estadosTango[observation!.estado]}</span></small>
                    {row.actualizacion_tango && <small className="doc-missing">Datos de Tango por revisar</small>}
                </td>
                <td><strong>{comp ? formatCurrencyAR(comp.importe) : dato ? netoTango(dato) : 'Por revisar'}</strong>
                    <small>{comp ? 'Neto de control original' : dato?.tipo === 'REC' && dato.aplicaciones.length ? 'Equivalente de las aplicaciones relacionadas' : dato?.base_importe}</small>
                    {dato?.tipo.startsWith('NC') && <small>Es un ajuste, no un cobro.</small>}
                </td>
                <td>{app ? <><strong>{formatCurrencyAR(app.importe_aplicado)}</strong>
                    <small>Facturado: {app.importe_facturado == null ? 'Sin clasificar' : formatCurrencyAR(app.importe_facturado)}</small>
                    <small>Viviana: {app.importe_viviana == null ? 'Sin clasificar' : formatCurrencyAR(app.importe_viviana)}</small></>
                    : <><strong>Sin asociar</strong><small>No incluido en los totales.</small></>}
                </td>
                <td>{app && <><span className={'doc-status doc-status-' + app.estado.toLowerCase()}>{estadosDocumento[app.estado] || app.estado}</span>
                    {app.diferencia != null && app.diferencia !== 0 && <small>Diferencia: {formatCurrencyAR(app.diferencia)}</small>}
                    {reference && <small>{tiposDocumento[reference.comprobante.tipo]} {reference.comprobante.numero}</small>}</>}
                    {!app && row.candidato?.bloqueo && <small className="doc-missing">{row.candidato.bloqueo}</small>}
                    {dato?.fecha_anulacion && dato.fecha_anulacion > '1900-01-01' && <small className="doc-missing">Anulado en Tango el {fecha(dato.fecha_anulacion)}.</small>}
                    {dato && !dato.moneda_corriente && <small className="doc-missing">Moneda extranjera: revisar conversión.</small>}
                    {app && row.actualizacion_tango && <small>Revisá la consulta debajo. Los importes asociados se conservan.</small>}
                    <details className="doc-unified-detail"><summary>Ver detalle{history && row.versiones_tango.length > 1 ? ' e historial' : ''}</summary>
                        {comp?.descripcion && <p>{comp.descripcion}</p>}
                        {comp?.iva != null && <small>IVA del comprobante: {formatCurrencyAR(comp.iva)}</small>}
                        {comp?.origen_tango && <small>Original bruto en Tango: {formatCurrencyAR(Number(comp.origen_tango.bruto_original))}</small>}
                        {dato && <div className="doc-source-detail">
                            <strong>Datos consultados en Tango</strong><small>Consultado: {fechaConsulta(observation!.consultado_at)}</small>
                            <small>Original bruto: {formatCurrencyAR(Number(dato.total))} · IVA informado: {formatCurrencyAR(Number(dato.iva))}</small>
                            {dato.motivos.map((m, i) => <small key={i}>{m}</small>)}
                            {dato.aplicaciones.map((a, i) => <div key={i}><strong>Factura {a.factura_numero}</strong>
                                <small>Aplicado original: {formatCurrencyAR(Number(a.importe_bruto))}</small>
                                <small>Neto equivalente: {a.neto_equivalente == null ? 'Por revisar' : formatCurrencyAR(Number(a.neto_equivalente))}</small>
                                <small>{a.criterio_neto}</small></div>)}
                            {dato.referencias_pedido.map(p => <div key={p.id}><strong>Pedido {p.pedido}</strong>
                                <small>OC: {p.oc || 'Sin número informado'} · {p.obra}</small><small>{formatCurrencyAR(Number(p.importe))}</small></div>)}
                            {dato.observacion && <p>{dato.observacion}</p>}
                        </div>}
                        {history && row.versiones_tango.length > 0 && <div className="doc-source-history"><strong>Historial de consultas</strong>
                            {row.versiones_tango.map(version => <div key={version.id}><small>{fechaConsulta(version.consultado_at)} · {estadosTango[version.estado]}</small>
                                <small>{netoTango(version.datos)} · Bruto {formatCurrencyAR(Number(version.datos.total))}</small>
                                {version.datos.observacion && <small>{version.datos.observacion}</small>}
                                {version.id === latest?.id && version.estado === 'DESCARTADO' && <button type="button" className="btn btn-secondary btn-compact" disabled={busy} onClick={() => onReview(version, 'PENDIENTE')}>Volver a revisar</button>}
                            </div>)}
                        </div>}
                    </details>
                </td>
                <td><div className="doc-row-actions">
                    {app ? <>
                        {!app.anulada && <button type="button" className="btn btn-secondary btn-compact" disabled={busy} onClick={() => onEdit(app)}>Editar</button>}
                        <button type="button" className="btn btn-secondary btn-compact" disabled={busy} onClick={() => onState(app)}>{app.anulada ? 'Restaurar vínculo' : 'Anular vínculo'}</button>
                    </> : <>
                        {row.candidato && !row.candidato.bloqueo && <button type="button" className="btn btn-primary btn-compact" disabled={busy} onClick={() => onAssociate(row.candidato!)}>Revisar y asociar</button>}
                        {latest?.estado === 'PENDIENTE' && <button type="button" className="btn btn-secondary btn-compact" disabled={busy} onClick={() => onReview(latest, 'CONSERVADO')}>Conservar para control</button>}
                        {latest && (latest.estado === 'PENDIENTE' || latest.estado === 'CONSERVADO') && <button type="button" className="btn btn-secondary btn-compact" disabled={busy} onClick={() => onReview(latest, 'DESCARTADO')}>Descartar coincidencia</button>}
                        {latest?.estado === 'DESCARTADO' && <button type="button" className="btn btn-secondary btn-compact" disabled={busy} onClick={() => onReview(latest, 'PENDIENTE')}>Volver a revisar</button>}
                    </>}
                    {app && latest?.estado === 'PENDIENTE' && <>
                        <button type="button" className="btn btn-secondary btn-compact" disabled={busy} onClick={() => onReview(latest, 'CONSERVADO')}>Conservar actualización para control</button>
                        <button type="button" className="btn btn-secondary btn-compact" disabled={busy} onClick={() => onReview(latest, 'DESCARTADO')}>Descartar actualización</button>
                    </>}
                </div></td>
            </tr>;
        })}</tbody>
    </table></div>;
}
