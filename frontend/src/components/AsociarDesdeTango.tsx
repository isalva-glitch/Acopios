import { useEffect, useRef, useState } from 'react';
import apiClient from '../api/client';
import { formatCurrencyAR } from '../utils/formatters';

export interface CandidatoTango {
    permite_clasificar?: boolean;
    id: number; empresa: 'FONTELA' | 'VIVIANA'; tipo: 'FAC_ANTICIPO' | 'FAC_MERCADERIA' | 'RECIBO';
    numero: string; emisor: string; cliente?: string; fecha: string; importe: string | null; iva: string | null;
    original_bruto: string; disponible: string | null; sugerido: string; referencia_id: number | null;
    motivos: string[]; observacion: string; bloqueo: string | null; pdf_url: string | null; etiqueta: string;
}
interface Lista { resultados: CandidatoTango[]; conexion: { mensaje: string } }
function errorText(error: any) {
    return typeof error.response?.data?.detail === 'string' ? error.response.data.detail : 'No se pudo consultar Tango.';
}
export default function AsociarDesdeTango({ acopioId, selectedId, onChoose, disabled, onChange }:
    { acopioId: number; selectedId?: number; onChoose: (value: CandidatoTango | null) => void; disabled: boolean; onChange?: () => void }) {
    const [data, setData] = useState<Lista | null>(null);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState('');
    const [ampliar, setAmpliar] = useState(false);
    const [showBlocked, setShowBlocked] = useState(false);
    const base = '/acopios/' + acopioId + '/tango';
    const initialQuery = useRef<Promise<{ data: Lista | null; error: string }> | null>(null);
    useEffect(() => {
        let active = true;
        // StrictMode mounts effects twice; share the lookup instead of querying Access twice.
        if (!initialQuery.current) initialQuery.current = (async () => {
            let cached: Lista | null = null;
            try {
                cached = (await apiClient.get<Lista>(base + '/asociables')).data;
                await apiClient.post(base + '/consultar', { ampliar: false });
                return { data: (await apiClient.get<Lista>(base + '/asociables')).data, error: '' };
            } catch (err) { return { data: cached, error: errorText(err) }; }
        })();
        initialQuery.current.then(result => {
            if (active) { setData(result.data); setError(result.error); setLoading(false); onChange?.(); }
        });
        return () => { active = false; };
    }, [base]);
    const consultar = async () => {
        setLoading(true); setError('');
        try {
            await apiClient.post(base + '/consultar', { ampliar });
            setData((await apiClient.get<Lista>(base + '/asociables')).data);
            onChange?.();
        } catch (err) { setError(errorText(err)); }
        finally { setLoading(false); }
    };
    const descartar = async (row: CandidatoTango) => {
        setLoading(true); setError('');
        try {
            await apiClient.patch(base + '/registros/' + row.id, { estado: 'DESCARTADO' });
            setData((await apiClient.get<Lista>(base + '/asociables')).data);
            onChange?.();
            if (row.id === selectedId) onChoose(null);
        } catch (err) { setError(errorText(err)); }
        finally { setLoading(false); }
    };
    const rows = data?.resultados.filter(r => showBlocked || !r.bloqueo) || [];
    return <div className="doc-tango-search">
        <h5>Comprobantes encontrados en Tango</h5>
        <p className="doc-note">Se consulta Fontela y Viviana al abrir este formulario. Las facturas ya asociadas permiten recuperar sus recibos aunque el titular facturado sea diferente. Elegí un comprobante para completar los datos y revisá el importe antes de confirmar la asociación.</p>
        {loading && <p role="status">Consultando datos de Tango…</p>}
        {error && <p className="doc-setup-note" role="status">{error} Podés usar los resultados anteriores o los comprobantes guardados en Acopios.</p>}
        <div className="doc-actions">
            <label><input type="checkbox" checked={ampliar} disabled={disabled || loading} onChange={e => setAmpliar(e.target.checked)} /> Ampliar búsqueda por cliente</label>
            <label><input type="checkbox" checked={showBlocked} onChange={e => setShowBlocked(e.target.checked)} /> Mostrar ajustes y no disponibles</label>
            <button type="button" className="btn btn-secondary btn-compact" disabled={disabled || loading} onClick={consultar}>Volver a consultar Tango</button>
        </div>
        {ampliar && <p className="doc-note">Puede incluir documentos de otras obras del mismo cliente. Revisá las coincidencias.</p>}
        {!loading && rows.length === 0 && <p role="status">No se encontraron comprobantes disponibles en Tango con estos criterios.</p>}
        {rows.length > 0 && <div className="doc-table-scroll"><table className="doc-table">
            <thead><tr><th>Empresa y comprobante</th><th>Coincidencia</th><th>Importes sin IVA</th><th>Acciones</th></tr></thead>
            <tbody>{rows.map(row => <tr key={row.id} className={row.id === selectedId ? 'doc-tango-selected' : ''}>
                <td><strong>{row.emisor} · {row.etiqueta}</strong><small>{row.numero} · {new Date(row.fecha + 'T00:00:00').toLocaleDateString('es-AR')}</small>
                    {row.cliente && <small>Titular en Tango: {row.cliente}</small>}
                    {row.pdf_url && <a href={apiClient.defaults.baseURL + row.pdf_url} target="_blank" rel="noreferrer">Ver PDF de Tango ↗</a>}</td>
                <td>{row.motivos.map((m, i) => <small key={i}>{m}</small>)}{row.bloqueo && <small className="doc-missing">{row.bloqueo}</small>}</td>
                <td><strong>Aplicación sugerida: {formatCurrencyAR(Number(row.sugerido))}</strong>
                    <small>Neto de control completo: {row.importe == null ? 'Por revisar' : formatCurrencyAR(Number(row.importe))}</small>
                    <small>Disponible entre acopios: {row.disponible == null ? 'Por revisar' : formatCurrencyAR(Number(row.disponible))}</small>
                    <small>Original bruto en Tango: {formatCurrencyAR(Number(row.original_bruto))}</small></td>
                <td><div className="doc-row-actions"><button type="button" className="btn btn-primary btn-compact" disabled={disabled || loading || !!row.bloqueo} onClick={() => onChoose(row)}>
                    {row.id === selectedId ? 'Seleccionado' : 'Usar estos datos'}</button>
                    {!row.bloqueo && <button type="button" className="btn btn-secondary btn-compact" disabled={disabled || loading} onClick={() => descartar(row)}>Descartar coincidencia</button>}</div></td>
            </tr>)}</tbody>
        </table></div>}
    </div>;
}
