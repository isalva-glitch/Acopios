import { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import apiClient from '../api/client';
import { formatCurrencyAR } from '../utils/formatters';
import './DocumentacionAcopio.css';
import DocumentacionListado, { type FilaDocumento, type RegistroTango } from './DocumentacionListado';
import CoincidenciasNumero from './CoincidenciasNumero';
import AsociarDesdeTango, { type CandidatoTango } from './AsociarDesdeTango';

type Tipo = 'ORDEN_COMPRA' | 'FAC_ANTICIPO' | 'FAC_MERCADERIA' | 'RECIBO';
type Alcance = 'FACTURADO' | 'VIVIANA' | 'TOTAL';
export interface Comprobante {
    id: number; tipo: Tipo; numero: string; emisor: string; fecha: string;
    importe: number; iva: number | null; descripcion: string | null;
    aplicado: number; disponible: number; compartido: boolean;
    origen_tango?: { empresa: 'FONTELA' | 'VIVIANA'; bruto_original: string } | null;
    archivo: { nombre: string; url: string; disponible: boolean } | null;
}
export interface Aplicacion {
    id: number; comprobante: Comprobante; importe_aplicado: number;
    importe_facturado: number | null; importe_viviana: number | null;
    referencia_id: number | null; anulada: boolean; estado: string; diferencia: number | null;
}
interface Totales {
    oc_facturado: number; oc_viviana: number; anticipos_facturados: number;
    cobrado_facturado: number; cobrado_viviana: number; mercaderia_documentada: number;
}
interface Documentacion {
    acopio_id: number; numero: string; total_neto: number; porcentaje_facturado: number | null;
    porcentaje_viviana: number | null; acordado_facturado: number | null; acordado_viviana: number | null;
    totales: Totales; documentos: Aplicacion[]; alertas: string[];
    listado?: FilaDocumento[];
    conexion_tango?: { activo: boolean; access_abierto: boolean; mensaje: string };
    pendientes_tango?: number;
}
interface Formulario {
    tipo: Tipo; numero: string; emisor: string; fecha: string; importe: string; iva: string;
    descripcion: string; importe_aplicado: string; alcance: Alcance;
    importe_facturado: string; referencia_id: string;
}
const tipos: Record<Tipo, string> = { ORDEN_COMPRA: 'Orden de compra', FAC_ANTICIPO: 'Factura de anticipo', FAC_MERCADERIA: 'Factura de mercadería', RECIBO: 'Recibo' };
const nuevaFicha = (): Formulario => ({ tipo: 'ORDEN_COMPRA', numero: '', emisor: '', fecha: new Date().toLocaleDateString('en-CA'),
    importe: '', iva: '', descripcion: '', importe_aplicado: '', alcance: 'FACTURADO', importe_facturado: '', referencia_id: '' });
function errorText(error: any): string {
    const detail = error.response?.data?.detail;
    return typeof detail === 'string' ? detail : 'Revise los datos e intente nuevamente.';
}
function splitNeto(amount: string, pct: number) {
    // Enteros de centavos y centesimas de porcentaje: ROUND_HALF_UP sin aritmetica binaria.
    const normalized = Number(amount || 0).toFixed(2);
    if (!/^\d+\.\d{2}$/.test(normalized)) return '';
    const cents = BigInt(normalized.replace('.', ''));
    const percent = BigInt(Math.round(pct * 100));
    return (Number((cents * percent + 5000n) / 10000n) / 100).toFixed(2);
}
function esFactura(tipo: string) { return tipo === 'FAC_ANTICIPO' || tipo === 'FAC_MERCADERIA'; }
function alcanceInicial(tipo: Tipo, porcentaje: number | null): Alcance {
    if (esFactura(tipo) || porcentaje === 100) return 'FACTURADO';
    if (tipo === 'RECIBO' || porcentaje === 0) return 'VIVIANA';
    return porcentaje == null ? 'FACTURADO' : 'TOTAL';
}

export default function DocumentacionAcopio({ acopioId }: { acopioId: number }) {
    const [data, setData] = useState<Documentacion | null>(null);
    const [porcentaje, setPorcentaje] = useState('');
    const [loading, setLoading] = useState(true);
    const [busy, setBusy] = useState(false);
    const [error, setError] = useState('');
    const [message, setMessage] = useState('');
    const [mode, setMode] = useState<'new' | 'existing' | 'edit' | 'tango' | null>(null);
    const [editing, setEditing] = useState<Aplicacion | null>(null);
    const [form, setForm] = useState<Formulario>(nuevaFicha);
    const [file, setFile] = useState<File | null>(null);
    const [search, setSearch] = useState('');
    const [results, setResults] = useState<Comprobante[]>([]);
    const [hasSearched, setHasSearched] = useState(false);
    const [selected, setSelected] = useState<Comprobante | null>(null);
    const [selectedTango, setSelectedTango] = useState<CandidatoTango | null>(null);
    const [showHistory, setShowHistory] = useState(false);
    const [tangoBusy, setTangoBusy] = useState(false);
    const [ampliar, setAmpliar] = useState(false);
    const [avisosTango, setAvisosTango] = useState<string[]>([]);
    const base = `/acopios/${acopioId}/documentacion`;
    const acceptData = (next: Documentacion) => {
        setData(prev => ({ ...prev, ...next })); setPorcentaje(next.porcentaje_facturado == null ? '' : String(next.porcentaje_facturado));
    };
    const load = async () => {
        setLoading(true); setError('');
        try { acceptData((await apiClient.get<Documentacion>(base + '/panel')).data); }
        catch (err) { setError(errorText(err)); }
        finally { setLoading(false); }
    };
    useEffect(() => {
        let active = true;
        setLoading(true); setData(null); setMode(null); setError(''); setMessage('');
        apiClient.get<Documentacion>(base + '/panel').then(response => { if (active) acceptData(response.data); })
            .catch(err => { if (active) setError(errorText(err)); })
            .finally(() => { if (active) setLoading(false); });
        return () => { active = false; };
    }, [base]);
    const refreshUnified = async () => {
        try { setData((await apiClient.get<Documentacion>(base + '/panel')).data); }
        catch (err) { setError('No se pudo actualizar la lista. ' + errorText(err)); }
    };
    const consultarTango = async () => {
        setTangoBusy(true); setError(''); setMessage(''); setAvisosTango([]);
        try {
            const response = (await apiClient.post(base.replace('/documentacion', '/tango') + '/consultar', { ampliar })).data;
            setAvisosTango((response.consulta?.avisos || []).filter((a: string) => !a.startsWith('Conservar datos en este panel')));
            setMessage(response.consulta?.nuevos ? 'Se encontraron ' + response.consulta.nuevos + ' registros nuevos para revisar en la lista.'
                : 'Consulta terminada. Se mantienen las coincidencias y tus decisiones anteriores.');
            await refreshUnified();
        } catch (err) { setError(errorText(err)); }
        finally { setTangoBusy(false); }
    };
    const revisarTango = async (record: RegistroTango, estado: 'PENDIENTE' | 'CONSERVADO' | 'DESCARTADO') => {
        setTangoBusy(true); setError(''); setMessage('');
        try {
            await apiClient.patch(base.replace('/documentacion', '/tango') + '/registros/' + record.id, { estado });
            await refreshUnified();
            setMessage(estado === 'CONSERVADO' ? 'Datos conservados para control. Los importes asociados se mantienen.'
                : estado === 'DESCARTADO' ? 'Coincidencia descartada. Podés recuperarla desde el historial.'
                : 'Coincidencia disponible para revisar.');
        } catch (err) { setError(errorText(err)); }
        finally { setTangoBusy(false); }
    };
    const descartarPendientes = async () => {
        setTangoBusy(true); setError(''); setMessage('');
        try {
            await apiClient.post(base.replace('/documentacion', '/tango') + '/descartar-pendientes');
            await refreshUnified();
            setMessage('Coincidencias pendientes descartadas. Los comprobantes asociados se mantienen.');
        } catch (err) { setError(errorText(err)); }
        finally { setTangoBusy(false); }
    };
    const saveReparto = async () => {
        setBusy(true); setError(''); setMessage('');
        try {
            const next = (await apiClient.put<Documentacion>(base + '/reparto', { porcentaje_facturado: porcentaje === '' ? null : porcentaje })).data;
            acceptData(next);
            await refreshUnified();
            if (mode && next.porcentaje_facturado !== data?.porcentaje_facturado) {
                setForm(prev => {
                    const pct = next.porcentaje_facturado;
                    const alcance = selectedTango ? (selectedTango.empresa === 'VIVIANA' ? 'VIVIANA' : 'FACTURADO') : data?.porcentaje_facturado == null
                        || (pct === 0 && prev.alcance !== 'VIVIANA')
                        || (pct === 100 && prev.alcance !== 'FACTURADO')
                        ? alcanceInicial(prev.tipo, pct) : prev.alcance;
                    return { ...prev, alcance,
                        importe_facturado: alcance === 'TOTAL' ? splitNeto(prev.importe_aplicado, pct ?? 0) : prev.importe_facturado,
                        referencia_id: alcance === 'VIVIANA' ? '' : prev.referencia_id };
                });
            }
            setMessage(mode ? 'Reparto guardado. Podés continuar con el comprobante.' : 'Reparto guardado. Los consumos y saldos operativos se mantienen.');
        } catch (err) { setError(errorText(err)); }
        finally { setBusy(false); }
    };
    const start = (nextMode: 'new' | 'existing', row?: Aplicacion) => {
        setError(''); setMessage(''); setFile(null); setSelected(null); setSelectedTango(null); setResults([]); setSearch(''); setHasSearched(false);
        setEditing(row || null); setMode(row ? 'edit' : nextMode);
        if (row) {
            const c = row.comprobante;
            setForm({ tipo: c.tipo, numero: c.numero, emisor: c.emisor, fecha: c.fecha, importe: String(c.importe),
                iva: c.iva == null ? '' : String(c.iva), descripcion: c.descripcion || '',
                importe_aplicado: String(row.importe_aplicado), importe_facturado: String(row.importe_facturado ?? ''),
                alcance: row.importe_facturado === 0 ? 'VIVIANA' : row.importe_viviana === 0 ? 'FACTURADO' : 'TOTAL',
                referencia_id: row.referencia_id == null ? '' : String(row.referencia_id) });
        } else {
            const next = nuevaFicha();
            next.alcance = alcanceInicial(next.tipo, data?.porcentaje_facturado ?? null);

            setForm(next);
        }
    };
    const setValue = (field: keyof Formulario, value: string) => setForm(prev => {
        const next = { ...prev, [field]: value };
        if (field === 'importe' && mode === 'new') next.importe_aplicado = value;
        if (field === 'tipo') {
            next.referencia_id = '';
            next.alcance = alcanceInicial(value as Tipo, data?.porcentaje_facturado ?? null);
        }
        if (field === 'alcance' && value === 'VIVIANA') next.referencia_id = '';
        if (next.alcance === 'TOTAL' && ['importe', 'importe_aplicado', 'alcance', 'tipo'].includes(field)) {
            next.importe_facturado = splitNeto(next.importe_aplicado, data?.porcentaje_facturado || 0);
        }
        return next;
    });
    const find = async () => {
        setBusy(true); setError('');
        try { setResults((await apiClient.get<Comprobante[]>('/documentacion/comprobantes', { params: { buscar: search } })).data); setHasSearched(true); }
        catch (err) { setError(errorText(err)); }
        finally { setBusy(false); }
    };
    const choose = (comp: Comprobante) => {
        setSelected(comp); setSelectedTango(null);
        const alcance = comp.origen_tango ? (comp.origen_tango.empresa === 'VIVIANA' ? 'VIVIANA' : 'FACTURADO')
            : alcanceInicial(comp.tipo, data?.porcentaje_facturado ?? null);

        setForm({ tipo: comp.tipo, numero: comp.numero, emisor: comp.emisor, fecha: comp.fecha,
            importe: String(comp.importe), iva: comp.iva == null ? '' : String(comp.iva), descripcion: comp.descripcion || '',
            importe_aplicado: String(comp.disponible), alcance,
            importe_facturado: splitNeto(String(comp.disponible), data?.porcentaje_facturado || 0), referencia_id: '' });
    };
    const chooseTango = (candidate: CandidatoTango | null, preserveType = true) => {
        setSelectedTango(candidate); setSelected(null); setError('');
        if (!candidate) return;
        const tipo = preserveType && candidate.permite_clasificar && esFactura(form.tipo) ? form.tipo : candidate.tipo;
        setForm({ tipo, numero: candidate.numero, emisor: candidate.emisor, fecha: candidate.fecha,
            importe: candidate.importe || '', iva: candidate.iva ?? '', descripcion: candidate.observacion,
            importe_aplicado: candidate.sugerido, alcance: candidate.empresa === 'VIVIANA' ? 'VIVIANA' : 'FACTURADO',
            importe_facturado: candidate.empresa === 'VIVIANA' ? '0' : candidate.sugerido,
            referencia_id: candidate.referencia_id == null ? '' : String(candidate.referencia_id) });
    };
    const save = async (event: React.FormEvent) => {
        event.preventDefault();
        if (data?.porcentaje_facturado == null || repartoSinGuardar) {
            setError('Definí y guardá el reparto Facturado / Viviana antes de guardar el comprobante.');
            return;
        }
        setBusy(true); setError(''); setMessage('');
        const application = { importe_aplicado: form.importe_aplicado,
            importe_facturado: form.alcance === 'FACTURADO' ? form.importe_aplicado : form.alcance === 'VIVIANA' ? '0' : form.importe_facturado,
            referencia_id: form.referencia_id ? Number(form.referencia_id) : null };
        try {
            let next: Documentacion;
            if (selectedTango) {
                next = (await apiClient.post(base.replace('/documentacion', '/tango') + '/registros/' + selectedTango.id + '/asociar', { ...application, tipo_factura: esFactura(form.tipo) ? form.tipo : null })).data;
            } else if (selected) {
                next = (await apiClient.post(base + '/asociaciones', { ...application, comprobante_id: selected.id })).data;
            } else {
                const multipart = new FormData();
                multipart.append('payload', JSON.stringify({ ...application, tipo: form.tipo, numero: form.numero,
                    emisor: form.emisor, fecha: form.fecha, importe: form.importe,
                    iva: form.iva === '' ? null : form.iva, descripcion: form.descripcion || null }));
                if (file) multipart.append('file', file);
                const url = base + '/comprobantes' + (editing ? `/${editing.id}` : '');
                next = (await apiClient.request<Documentacion>({ method: editing ? 'PUT' : 'POST', url,
                    data: multipart, headers: { 'Content-Type': 'multipart/form-data' } })).data;
            }
            acceptData(next); await refreshUnified(); setMode(null); setEditing(null); setFile(null); setMessage('Documentación guardada.' + ((next as Documentacion & { tango_aviso?: string }).tango_aviso ? ' ' + (next as Documentacion & { tango_aviso?: string }).tango_aviso : ''));
        } catch (err) { setError(errorText(err)); }
        finally { setBusy(false); }
    };
    const changeState = async (row: Aplicacion) => {
        setBusy(true); setError(''); setMessage('');
        try {
            acceptData((await apiClient.patch(base + `/asociaciones/${row.id}`, { anulada: !row.anulada })).data);
            await refreshUnified();
            setMessage(row.anulada ? 'Asociación restaurada.' : 'Asociación anulada. Puede restaurarla desde el historial.');
        } catch (err) { setError(errorText(err)); }
        finally { setBusy(false); }
    };
    const repartoSinGuardar = porcentaje !== (data?.porcentaje_facturado == null ? '' : String(data.porcentaje_facturado));
    const faltaReparto = data?.porcentaje_facturado == null || repartoSinGuardar;
    const shared = !!selected || !!selectedTango || mode === 'existing' || !!editing?.comprobante.compartido || !!editing?.comprobante.origen_tango;
    const references = data?.documentos.filter(row => !row.anulada && row.id !== editing?.id &&
        (esFactura(form.tipo) ? row.comprobante.tipo === 'ORDEN_COMPRA' : esFactura(row.comprobante.tipo))) || [];
    const locked = busy || tangoBusy;

    return <section className="form-section documentacion-acopio" aria-labelledby="doc-title">
        <div className="doc-heading"><div><h3 id="doc-title">Documentación del acopio</h3>
            <p>Órdenes de compra, facturas y recibos, cargados manualmente o consultados en Tango. Importes en pesos, sin IVA.</p><p className="doc-note">La documentación y sus coincidencias se revisan en una sola lista. Los pedidos y sus comprobantes se consultan en <a href="#consumos-aplicados">Consumos aplicados</a>; sus consumos ya están incluidos en el saldo operativo.</p></div>
            <button type="button" className="btn btn-secondary btn-compact" onClick={load} disabled={locked || loading || !!mode}>Actualizar</button></div>
        {error && <div className="doc-error" role="alert">{error}</div>}
        {message && <div className="doc-message" role="status">{message}</div>}
        {loading ? <p>Cargando documentación...</p> : data && <>
            <form id={'doc-reparto-' + acopioId} className="doc-reparto" onSubmit={event => { event.preventDefault(); saveReparto(); }}>
                <label>Parte Facturado (%)<input type="number" aria-label="Parte Facturado (%)" min="0" max="100" step="0.01" value={porcentaje} onChange={e => setPorcentaje(e.target.value)} disabled={locked} placeholder="Por definir" /></label>
                <label>Parte Viviana (%)<input aria-label="Parte Viviana (%)" readOnly value={porcentaje === '' ? 'Por definir' : (100 - Number(porcentaje)).toFixed(2)} /></label>
                <div className="doc-presets">{[100, 50, 0].map(pct => <button key={pct} type="button" disabled={locked} onClick={() => setPorcentaje(String(pct))}>{pct === 100 ? '100% Facturado' : pct === 0 ? '100% Viviana' : '50 / 50'}</button>)}</div>
                <button className="btn btn-primary btn-compact" disabled={locked || !repartoSinGuardar}>Guardar reparto</button>
            </form>
            <div className="doc-metrics">
                <div><span>Acordado Facturado</span><strong>{data.acordado_facturado == null ? 'Por definir' : formatCurrencyAR(data.acordado_facturado)}</strong></div>
                <div><span>Acordado Viviana</span><strong>{data.acordado_viviana == null ? 'Por definir' : formatCurrencyAR(data.acordado_viviana)}</strong></div>
                <div><span>Anticipos facturados</span><strong>{formatCurrencyAR(data.totales.anticipos_facturados)}</strong></div><div><span>Mercadería documentada</span><strong>{formatCurrencyAR(data.totales.mercaderia_documentada || 0)}</strong></div>
                <div><span>Cobrado Facturado / Viviana</span><strong>{formatCurrencyAR(data.totales.cobrado_facturado)} / {formatCurrencyAR(data.totales.cobrado_viviana)}</strong></div>
            </div>
            <p className="doc-note">La factura de anticipo respalda la constitución del acopio; el recibo registra el cobro. La OC no se suma a ninguno de esos importes.</p>
            {data.alertas.length > 0 && <ul className="doc-alerts">{data.alertas.map((alert, i) => <li key={i}>{alert}</li>)}</ul>}
            {!mode && <div className="doc-actions">
                <button className="btn btn-primary btn-compact" type="button" disabled={locked} onClick={() => start('new')}>+ Agregar comprobante</button>
                <button className="btn btn-secondary btn-compact" type="button" disabled={locked} onClick={() => start('existing')}>Asociar existente</button>
                <button className="btn btn-secondary btn-compact" type="button" disabled={locked} onClick={consultarTango}>{tangoBusy ? 'Consultando Tango…' : 'Consultar Tango'}</button>
            </div>}
            {mode && <div className="doc-editor">
                <h4>{mode === 'edit' ? 'Editar comprobante' : mode === 'tango' ? 'Revisar comprobante encontrado' : mode === 'existing' ? 'Asociar comprobante existente' : 'Nuevo comprobante'}</h4>
                {faltaReparto && <p className="doc-setup-note" role="status">
                    Podés completar los datos o buscar un comprobante. Para guardarlo, primero <a href={'#doc-reparto-' + acopioId}>definí y guardá el reparto Facturado / Viviana</a> en el panel de arriba. Los datos ingresados se conservan.
                </p>}
                {mode === 'existing' && <AsociarDesdeTango acopioId={acopioId} selectedId={selectedTango?.id} onChoose={chooseTango} disabled={locked} onChange={refreshUnified} />}
                {mode === 'existing' && <h5>Comprobantes guardados en Acopios</h5>}
                {mode === 'existing' && <div className="doc-search"><label>Número o emisor<input value={search} onChange={e => setSearch(e.target.value)} onKeyDown={e => { if (e.key === 'Enter') { e.preventDefault(); find(); } }} /></label><button className="btn btn-secondary btn-compact" disabled={locked} onClick={find}>Buscar comprobantes</button>
                    <label className="doc-full">Resultado<select aria-label="Comprobante existente" value={selected?.id || ''} onChange={e => { const found = results.find(c => c.id === Number(e.target.value)); if (found) choose(found); }}><option value="">Seleccione un comprobante</option>{results.map(c => <option key={c.id} value={c.id}>{tipos[c.tipo]} {c.numero} · {c.emisor} · Disponible {formatCurrencyAR(c.disponible)}</option>)}</select></label></div>}
                {mode === 'existing' && hasSearched && results.length === 0 && <p className="doc-note" role="status">No se encontraron comprobantes guardados en Acopios. Revisá los resultados de Tango o probá otro número o emisor.</p>}
                {(mode !== 'existing' || selected || selectedTango) && <form onSubmit={save}>
                    {selectedTango && <p className="doc-setup-note" role="status">Datos traídos de Tango {selectedTango.emisor}. Original bruto: {formatCurrencyAR(Number(selectedTango.original_bruto))}. Se asociará únicamente el neto aplicado que confirmes abajo. El PDF se copiará si está disponible.</p>}
                    {shared && <p className="doc-note">Se conservan los datos originales del comprobante compartido. Aquí se modifica su aplicación a este acopio. Si reemplaza su PDF, el archivo se actualizará en todas sus asociaciones.</p>}
                    {mode === 'new' && (selected || selectedTango) && <button type="button" className="btn btn-secondary btn-compact" disabled={locked} onClick={() => {
                        const tipoActual = form.tipo;
                        setSelected(null); setSelectedTango(null); setFile(null);
                        setForm({ ...nuevaFicha(), tipo: tipoActual, alcance: alcanceInicial(tipoActual, data.porcentaje_facturado) });
                    }}>Ingresar otro número</button>}
                    {form.tipo === 'FAC_MERCADERIA' && <p className="doc-note">La factura de mercadería se registra como documentación, separada de los anticipos. Los desacopios se descuentan desde Consumos aplicados; asociar esta factura no vuelve a descontarlos.</p>}
                    <fieldset disabled={locked}><div className="doc-form-grid">
                        <label>Tipo<select aria-label="Tipo de comprobante" value={form.tipo} disabled={(shared && !selectedTango?.permite_clasificar) || mode === 'edit'} onChange={e => setValue('tipo', e.target.value)}>{Object.entries(tipos).map(([key, title]) => <option key={key} value={key} disabled={(esFactura(key) && data.porcentaje_facturado === 0) || (!!selectedTango && !esFactura(key))}>{title}</option>)}</select></label>
                        <label>Número<input required maxLength={100} value={form.numero} disabled={shared} onChange={e => setValue('numero', e.target.value)} /></label>
                        {mode === 'new' && (esFactura(form.tipo) || form.tipo === 'RECIBO') && <CoincidenciasNumero
                            numero={form.numero} acopioId={acopioId} enabled={!locked && !selected && !selectedTango}
                            onLocal={choose} onTango={chooseTango} onChange={refreshUnified} />}
                        <label>Emisor<input required maxLength={200} value={form.emisor} disabled={shared} onChange={e => setValue('emisor', e.target.value)} /></label>
                        <label>Fecha<input type="date" required value={form.fecha} disabled={shared} onChange={e => setValue('fecha', e.target.value)} /></label>
                        <label>{selectedTango || editing?.comprobante.origen_tango ? 'Neto de control del comprobante' : 'Neto original del comprobante'}<input type="number" min="0.01" step="0.01" required value={form.importe} disabled={shared} onChange={e => setValue('importe', e.target.value)} /></label>
                        <label>IVA del comprobante (opcional)<input type="number" min="0" step="0.01" value={form.iva} disabled={shared} onChange={e => setValue('iva', e.target.value)} /></label>
                        <label>Neto aplicado a este acopio<input type="number" min="0.01" step="0.01" max={selectedTango ? selectedTango.sugerido : form.importe || undefined} required value={form.importe_aplicado} onChange={e => setValue('importe_aplicado', e.target.value)} /></label>
                        <label>{form.tipo === 'ORDEN_COMPRA' ? 'La OC cubre' : 'Parte correspondiente'}<select value={form.alcance} disabled={!!selectedTango || !!selected?.origen_tango || !!editing?.comprobante.origen_tango} onChange={e => setValue('alcance', e.target.value)}>
                            <option value="FACTURADO" disabled={data.porcentaje_facturado === 0}>Facturado</option>
                            {!esFactura(form.tipo) && <option value="VIVIANA" disabled={data.porcentaje_facturado === 100}>Viviana</option>}
                            {form.tipo === 'ORDEN_COMPRA' && data.porcentaje_facturado !== 0 && data.porcentaje_facturado !== 100 && <option value="TOTAL">Ambas partes (OC total)</option>}
                        </select></label>
                        {form.alcance === 'TOTAL' && <><label>Neto de la OC asignado a Facturado<input type="number" min="0" max={form.importe_aplicado || undefined} step="0.01" required value={form.importe_facturado} onChange={e => setValue('importe_facturado', e.target.value)} /></label>
                            <label>Neto de la OC asignado a Viviana<input readOnly value={formatCurrencyAR(Number(form.importe_aplicado || 0) - Number(form.importe_facturado || 0))} /></label></>}
                        {(esFactura(form.tipo) || (form.tipo === 'RECIBO' && form.alcance === 'FACTURADO')) && <label className="doc-full">{esFactura(form.tipo) ? 'Orden de compra vinculada' : 'Factura vinculada (opcional)'}<select value={form.referencia_id} onChange={e => setValue('referencia_id', e.target.value)}><option value="">Sin vincular{esFactura(form.tipo) ? ' (pendiente de OC)' : ''}</option>{references.map(row => <option key={row.id} value={row.id}>{row.comprobante.numero} · Facturado {formatCurrencyAR(row.importe_facturado || 0)}</option>)}</select></label>}
                        {mode !== 'existing' && !selected && !selectedTango && <label className="doc-full">PDF {editing?.comprobante.archivo ? '(seleccione otro para reemplazarlo)' : '(puede adjuntarlo después)'}<input key={editing?.id || 'nuevo'} type="file" accept="application/pdf,.pdf" onChange={e => setFile(e.target.files?.[0] || null)} /><small>Hasta 20 MB. No se extraen datos del archivo.</small></label>}
                        <label className="doc-full">Observación<textarea maxLength={2000} value={form.descripcion} disabled={shared} onChange={e => setValue('descripcion', e.target.value)} /></label>
                    </div></fieldset>
                    <div className="doc-actions"><button className="btn btn-success btn-compact" disabled={locked || faltaReparto}>Guardar comprobante</button><button type="button" className="btn btn-secondary btn-compact" disabled={locked} onClick={() => { setMode(null); setEditing(null); setError(''); }}>Cancelar</button></div>
                </form>}
                {mode === 'existing' && !selected && !selectedTango && <button type="button" className="btn btn-secondary btn-compact" onClick={() => setMode(null)}>Cancelar</button>}
            </div>}
            <div className="doc-list-heading">
                <div><h4>Comprobantes y coincidencias</h4><p className="doc-note">Los totales incluyen únicamente comprobantes asociados. Conservar una coincidencia para control permite revisarla sin incorporarla a los importes.</p></div>
                {data.conexion_tango && <span className={'doc-connection ' + (data.conexion_tango.access_abierto ? 'is-connected' : '')}>{data.conexion_tango.mensaje}</span>}
            </div>
            <div className="doc-list-options">
                <label><input type="checkbox" checked={showHistory} onChange={e => setShowHistory(e.target.checked)} /> Mostrar historial: descartados, anulados y versiones anteriores</label>
                <details><summary>Opciones de consulta</summary>
                    <label><input type="checkbox" checked={ampliar} disabled={locked || !!mode} onChange={e => setAmpliar(e.target.checked)} /> Ampliar búsqueda de Tango por cliente</label>
                    {ampliar && <p className="doc-note">Puede incluir comprobantes de otras obras del mismo cliente. Revisá cada coincidencia.</p>}
                    {(data.pendientes_tango || 0) > 0 && <button type="button" className="btn btn-secondary btn-compact" disabled={locked || !!mode} onClick={descartarPendientes}>Descartar coincidencias pendientes ({data.pendientes_tango})</button>}
                </details>
                {(data.pendientes_tango || 0) > 0 && <span className="doc-status doc-tango-pendiente">{data.pendientes_tango} por revisar</span>}
            </div>
            {avisosTango.length > 0 && <ul className="doc-alerts">{avisosTango.map((aviso, i) => <li key={i}>{aviso}</li>)}</ul>}
            <DocumentacionListado acopioId={acopioId} rows={data.listado || []} aplicaciones={data.documentos} history={showHistory}
                busy={locked || !!mode} onEdit={row => start('new', row)} onState={changeState} onReview={revisarTango}
                onAssociate={candidate => { start('new'); setMode('tango'); chooseTango(candidate, false); }} />
        </>}
        {!loading && !data && <button className="btn btn-secondary" onClick={load}>Reintentar</button>}
    </section>;
}

export function DocumentacionPaquete({ paqueteId, revision }: { paqueteId: number; revision: string }) {
    const [data, setData] = useState<{ acopios: Documentacion[]; sin_clasificar: number; totales: Totales } | null>(null);
    const [error, setError] = useState('');
    useEffect(() => {
        let active = true;
        setData(null); setError('');
        apiClient.get(`/acopio-paquetes/${paqueteId}/documentacion`).then(response => { if (active) setData(response.data); })
            .catch(err => { if (active) setError(errorText(err)); });
        return () => { active = false; };
    }, [paqueteId, revision]);
    return <section className="form-section documentacion-acopio"><h3>Documentación de los acopios</h3>
        <p>Consolidado de las aplicaciones a los acopios hijos, sin repetir el importe original de los comprobantes compartidos.</p>
        {error && <p role="alert" className="doc-error">{error}</p>}
        {!data && !error && <p>Cargando documentación...</p>}
        {data && <><div className="doc-metrics"><div><span>Anticipos facturados</span><strong>{formatCurrencyAR(data.totales.anticipos_facturados)}</strong></div><div><span>Mercadería documentada</span><strong>{formatCurrencyAR(data.totales.mercaderia_documentada || 0)}</strong></div><div><span>Cobrado Facturado</span><strong>{formatCurrencyAR(data.totales.cobrado_facturado)}</strong></div><div><span>Cobrado Viviana</span><strong>{formatCurrencyAR(data.totales.cobrado_viviana)}</strong></div><div><span>Acopios por clasificar</span><strong>{data.sin_clasificar}</strong></div></div>
            <div className="doc-table-scroll"><table className="doc-table"><thead><tr><th>Acopio</th><th>Reparto Facturado / Viviana</th><th>Anticipos facturados</th><th>Mercadería documentada</th><th>Cobrado Facturado</th><th>Cobrado Viviana</th></tr></thead><tbody>{data.acopios.map(a => <tr key={a.acopio_id}><td><Link to={`/acopios/${a.acopio_id}`}>{a.numero}</Link></td><td>{a.porcentaje_facturado == null ? 'Por definir' : `${a.porcentaje_facturado}% / ${a.porcentaje_viviana}%`}</td><td>{formatCurrencyAR(a.totales.anticipos_facturados)}</td><td>{formatCurrencyAR(a.totales.mercaderia_documentada || 0)}</td><td>{formatCurrencyAR(a.totales.cobrado_facturado)}</td><td>{formatCurrencyAR(a.totales.cobrado_viviana)}</td></tr>)}</tbody></table></div></>}
    </section>;
}
