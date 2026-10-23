import { useEffect, useState } from 'react';
import apiClient from '../api/client';
import { formatCurrencyAR } from '../utils/formatters';
import { type CandidatoTango } from './AsociarDesdeTango';

export interface ComprobanteNumero {
    id: number; tipo: 'ORDEN_COMPRA' | 'FAC_ANTICIPO' | 'FAC_MERCADERIA' | 'RECIBO'; numero: string; emisor: string; fecha: string;
    importe: number; iva: number | null; descripcion: string | null;
    aplicado: number; disponible: number; compartido: boolean; bloqueo?: string | null;
    origen_tango?: { empresa: 'FONTELA' | 'VIVIANA'; bruto_original: string } | null;
    archivo: { nombre: string; url: string; disponible: boolean } | null;
}
function message(error: any) {
    return typeof error.response?.data?.detail === 'string' ? error.response.data.detail : 'No se pudo completar la búsqueda.';
}
export default function CoincidenciasNumero({ numero, acopioId, enabled, onLocal, onTango, onChange }:
    { numero: string; acopioId: number; enabled: boolean; onLocal: (c: ComprobanteNumero) => void;
      onTango: (c: CandidatoTango) => void; onChange?: () => void }) {
    const [local, setLocal] = useState<ComprobanteNumero[]>([]);
    const [tango, setTango] = useState<CandidatoTango[]>([]);
    const [loading, setLoading] = useState(false);
    const [checked, setChecked] = useState(false);
    const [errors, setErrors] = useState<string[]>([]);
    const [notices, setNotices] = useState<string[]>([]);
    const [retry, setRetry] = useState(0);
    useEffect(() => {
        let active = true;
        const controller = new AbortController();
        setLocal([]); setTango([]); setErrors([]); setNotices([]); setChecked(false); setLoading(false);
        if (!enabled || numero.replace(/[^0-9]/g, '').length < 3) return;
        const timer = window.setTimeout(async () => {
            setLoading(true);
            await Promise.allSettled([
                apiClient.get('/documentacion/coincidencias-numero', { params: { numero }, signal: controller.signal })
                    .then(response => { if (active) { setLocal(response.data.resultados); if (response.data.limitado) setNotices(prev => [...prev, 'Hay más resultados locales: completá el número.']); } })
                    .catch(error => { if (active) setErrors(prev => [...prev, 'Acopios: ' + message(error)]); }),
                apiClient.post('/acopios/' + acopioId + '/tango/buscar-numero', { numero }, { signal: controller.signal })
                    .then(response => { if (active) { setTango(response.data.resultados); setNotices(prev => [...prev, ...(response.data.avisos || [])]); onChange?.(); } })
                    .catch(error => { if (active) setErrors(prev => [...prev, 'Tango: ' + message(error)]); }),
            ]);
            if (active) { setLoading(false); setChecked(true); }
        }, 650);
        return () => { active = false; window.clearTimeout(timer); controller.abort(); };
    }, [numero, acopioId, enabled, retry]);
    if (!enabled || (!loading && !checked)) return null;
    return <div className="doc-full doc-number-matches" aria-label="Coincidencias del número">
        <strong>Coincidencias para {numero}</strong>
        {loading && <p role="status">Buscando el número en facturas y recibos de Acopios y Tango…</p>}
        {errors.map((error, i) => <p className="doc-note" role="status" key={i}>{error}</p>)}
        {notices.map((notice, i) => <small key={i}>{notice}</small>)}
        {local.map(c => <div className="doc-number-result" key={'local-' + c.id}>
            <div><strong>Acopios · {c.tipo === 'RECIBO' ? 'Recibo' : c.tipo === 'FAC_MERCADERIA' ? 'Factura de mercadería' : 'Factura de anticipo'} {c.numero}</strong>
                <small>{c.emisor} · {new Date(c.fecha + 'T00:00:00').toLocaleDateString('es-AR')} · Neto disponible {formatCurrencyAR(c.disponible)}</small>
                <small>{c.bloqueo || 'Ya está guardado: usá el comprobante existente para evitar duplicarlo.'}</small></div>
            <button type="button" className="btn btn-primary btn-compact" disabled={loading || !!c.bloqueo || c.disponible <= 0} onClick={() => onLocal(c)}>Usar existente</button>
        </div>)}
        {tango.map(c => <div className="doc-number-result" key={'tango-' + c.id}>
            <div><strong>Tango {c.emisor} · {c.etiqueta} {c.numero}</strong>
                <small>{c.cliente} · {new Date(c.fecha + 'T00:00:00').toLocaleDateString('es-AR')}</small>
                <small>Neto de control: {c.importe == null ? 'Por revisar' : formatCurrencyAR(Number(c.importe))} · Disponible {c.disponible == null ? 'Por revisar' : formatCurrencyAR(Number(c.disponible))}</small>
                {c.motivos.map((m, i) => <small key={i}>{m}</small>)}
                {c.bloqueo && <small className="doc-missing">{c.bloqueo}</small>}
                {c.etiqueta === 'Recibo' && <small>Puede cubrir otras facturas. Revisá el importe que corresponde a este acopio.</small>}</div>
            <button type="button" className="btn btn-primary btn-compact" disabled={loading || !!c.bloqueo} onClick={() => onTango(c)}>Usar datos de Tango</button>
        </div>)}
        {checked && local.length === 0 && tango.length === 0 && <p role="status">{errors.length ? 'No se encontraron coincidencias en las fuentes que respondieron.' : 'No se encontraron facturas ni recibos con ese número. Podés continuar la carga manual.'}</p>}
        {!loading && <button type="button" className="btn btn-secondary btn-compact" onClick={() => setRetry(value => value + 1)}>Volver a buscar este número</button>}
    </div>;
}
