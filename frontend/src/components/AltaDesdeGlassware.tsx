import {useEffect, useState} from 'react';
import {Link} from 'react-router-dom';
import apiClient from '../api/client';
import {glasswareId, glasswareRequest} from '../api/glassware';
import {formatCurrencyAR} from '../utils/formatters';

interface Preview {
    preview_id: string;
    data: {
        numero: string; cliente_nombre: string; obra_nombre: string;
        total_unidades: number; total_m2: string; total_ml: string; total_pesos: string; warnings: string[];
        metadata: {url: string; estado: string; importe_sin_ajuste: string; ajuste_importe: string; observaciones?: string};
        items: Array<{numero_item: number; descripcion: string; cantidad: number; total_m2: string;
            total_ml: string; total_pesos: string; panos: Array<{cantidad: number; ancho_mm: number;
                alto_mm: number; denominacion: string; superficie_m2: string; perimetro_ml: string}>}>;
    };
}
const fmt = (n: string) => Number(n).toLocaleString('es-AR', {minimumFractionDigits: 2, maximumFractionDigits: 2});

export default function AltaDesdeGlassware() {
    const [url, setUrl] = useState('');
    const [busy, setBusy] = useState(false);
    const [message, setMessage] = useState('');
    const [error, setError] = useState('');
    const [connection, setConnection] = useState('');
    const [preview, setPreview] = useState<Preview | null>(null);
    const [created, setCreated] = useState<number | null>(null);
    const [acknowledged, setAcknowledged] = useState(false);
    const [approved, setApproved] = useState(false);
    const run = async (task: () => Promise<void>) => {
        setBusy(true); setError('');
        try { await task(); } catch (err: any) {
            setError(typeof err.response?.data?.detail === 'string' ? err.response.data.detail : err.message || 'No se pudo completar la consulta.');
        } finally { setBusy(false); setMessage(''); }
    };
    useEffect(() => {
        const id = new URLSearchParams(window.location.search).get('glassware_preview');
        if (id && /^[0-9a-f-]{36}$/.test(id)) {
            void run(async () => {
                const response = await apiClient.get<Preview>(`/integrations/glassware/preview/${id}`);
                setPreview(response.data);
            });
        }
    }, []);
    const consult = () => run(async () => {
        const id = glasswareId(url);
        setPreview(null); setAcknowledged(false); setApproved(false);
        setMessage('Comprobando el conector de Chrome…');
        await glasswareRequest('ping');
        setMessage('Consultando el presupuesto y sus ítems en Glassware…');
        const raw = await glasswareRequest('collect', id);
        setMessage('Validando cantidades, medidas e importes…');
        const response = await apiClient.post<Preview>('/integrations/glassware/preview', raw);
        setPreview(response.data);
        const reviewUrl = new URL(window.location.href);
        reviewUrl.searchParams.set('glassware_preview', response.data.preview_id);
        window.history.replaceState(window.history.state, '', reviewUrl);
    });
    return <section className="form-section" style={{marginTop: '1rem'}}>
        <h3>Cargar desde Glassware</h3>
        <p>Mantené Glassware abierto y con la sesión iniciada en este mismo perfil de Chrome.</p>
        {!preview && !created && <>
            <form onSubmit={e => {e.preventDefault(); void consult();}} className="form-group">
                <label htmlFor="glassware-url">Enlace del presupuesto aprobado</label>
                <input id="glassware-url" type="url" value={url} disabled={busy}
                    onChange={e => setUrl(e.target.value)} placeholder="https://glassware.fontela.com.ar/budgets/16501"
                    style={{width: '100%', padding: 10, marginBottom: 12}} required />
                <button className="btn btn-primary" disabled={busy || !url.trim()}>Consultar Glassware</button>
            </form>
            <details style={{marginTop: 20}}><summary>Preparar el conector de Chrome</summary>
                <ol>
                    <li><a href="/glassware-connector.zip" download>Descargá el conector</a> y extraé la carpeta.</li>
                    <li>Abrí <code>chrome://extensions</code>, activá «Modo de desarrollador» y elegí «Cargar descomprimida». Seleccioná la carpeta extraída que contiene manifest.json.</li>
                    <li>Recargá Acopios y abrí Glassware en el mismo perfil de Chrome.</li>
                </ol>
                <p>Usá Acopios desde <a href="http://localhost:5173/acopios/alta">localhost:5173</a> en este equipo. La extensión solo consulta Glassware; no registra operaciones allí.</p>
                <button className="btn btn-secondary" disabled={busy} onClick={() => void run(async () => {
                    await glasswareRequest('ping'); setError(''); setMessage('');
                    setConnection('Conector disponible. Ya podés consultar un presupuesto.');
                })}>Comprobar conexión</button>
            </details>
        </>}
        {connection && <p role="status">{connection}</p>}
        {busy && <p role="status">{message || 'Guardando el acopio…'}</p>}
        {error && <p role="alert" style={{color: '#a11', whiteSpace: 'pre-wrap'}}>{error}</p>}
        {created && <div role="status"><h3>Acopio creado</h3>
            <Link className="btn btn-primary" to={`/acopios/${created}`}>Abrir acopio</Link>
            <button className="btn btn-secondary" onClick={() => {setCreated(null); setPreview(null); setUrl(''); setAcknowledged(false); setApproved(false); window.history.replaceState(window.history.state, '', window.location.pathname);}}>Cargar otro</button>
        </div>}
        {preview && !created && <>
            <h3>Revisar presupuesto {preview.data.numero}</h3>
            <p><strong>{preview.data.cliente_nombre}</strong> · {preview.data.obra_nombre} · {preview.data.metadata.estado}</p>
            <p>{preview.data.total_unidades} paños · {fmt(preview.data.total_m2)} m² · {fmt(preview.data.total_ml)} m</p>
            <p>Importe de los ítems: {formatCurrencyAR(Number(preview.data.metadata.importe_sin_ajuste))}<br/>
                Ajuste general: {formatCurrencyAR(Number(preview.data.metadata.ajuste_importe))}<br/>
                <strong>Total contratado: {formatCurrencyAR(Number(preview.data.total_pesos))}</strong></p>
            {preview.data.metadata.observaciones && <p><strong>Observaciones de Glassware:</strong> {preview.data.metadata.observaciones}</p>}
            {preview.data.warnings.map((w, i) => <p key={i} style={{background: '#fff3cd', padding: 12}}>{w}</p>)}
            <div style={{overflowX: 'auto'}}><table className="table"><thead><tr>
                <th>Ítem</th><th>Descripción</th><th>Paños</th><th>m²</th><th>m</th><th>Importe contratado</th>
            </tr></thead><tbody>{preview.data.items.map(it => <tr key={it.numero_item}>
                <td>{it.numero_item}</td><td>{it.descripcion}<details><summary>Ver medidas</summary>
                    {it.panos.map((p, n) => <p key={n}>{p.cantidad} × {p.ancho_mm} × {p.alto_mm} mm · {p.denominacion || 'Sin denominación'}</p>)}
                </details></td><td>{it.cantidad}</td><td>{fmt(it.total_m2)}</td><td>{fmt(it.total_ml)}</td>
                <td style={{whiteSpace: 'nowrap'}}>{formatCurrencyAR(Number(it.total_pesos))}</td>
            </tr>)}</tbody></table></div>
            {preview.data.metadata.estado !== 'Aceptado' && <label style={{display: 'block', margin: '18px 0'}}>
                <input type="checkbox" checked={approved} onChange={e => setApproved(e.target.checked)} disabled={busy}/>
                Confirmo que este presupuesto está aprobado por el total, aunque Glassware muestre «{preview.data.metadata.estado}».
            </label>}
            <label style={{display: 'block', margin: '18px 0'}}><input type="checkbox" checked={acknowledged}
                onChange={e => setAcknowledged(e.target.checked)} disabled={busy}/> Revisé el cliente, la obra y el total contratado.</label>
            <button className="btn btn-success" disabled={busy || !acknowledged || (preview.data.metadata.estado !== 'Aceptado' && !approved)} onClick={() => void run(async () => {
                const response = await apiClient.post('/integrations/glassware/confirm', {preview_id: preview.preview_id, aprobacion_verificada: approved});
                setCreated(response.data.acopio_id);
            })}>Confirmar y crear acopio</button>{' '}
            <button className="btn btn-secondary" disabled={busy} onClick={() => {setPreview(null); setError(''); setAcknowledged(false); setApproved(false); window.history.replaceState(window.history.state, '', window.location.pathname);}}>Descartar vista previa</button>
        </>}
    </section>;
}
