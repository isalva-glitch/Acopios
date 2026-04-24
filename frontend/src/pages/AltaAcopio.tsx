import { useState, useRef } from 'react';
import apiClient from '../api/client';

export interface SpfPresupuestoDetails {
    v_presupuesto_id: string;
    cliente_id: number | null;
    cliente_nombre: string;
    obra_nombre: string;
    pedidos_relacionados: string[];
    total_m2: number;
    total_ml: number;
    total_pesos: number;
    items_count: number;
}

export interface PdfExtractionPackage {
    presupuesto: {
        numero: string;
        empresa: string;
        contacto: string;
        estado: string;
        cotizado_por: string;
        fecha_aprobacion: string | null;
        total_unidades: number;
        total_importe: number;
        total_m2: number;
        total_ml: number;
        peso_estimado_kg: number;
        obra?: string;
        empresa_raw?: string;
    };
    items: Array<{
        numero_item: number;
        descripcion: string;
        cantidad: number;
        total_pesos: number;
        total_m2: number;
        total_ml: number;
        panos: Array<{
            cantidad: number;
            ancho_mm: number;
            alto_mm: number;
            superficie_m2: number;
            perimetro_ml: number;
            denominacion: string | null;
            precio_unitario: number;
            precio_total: number;
        }>;
        adicionales: Array<{
            cantidad: number;
            descripcion: string;
            precio_unitario: number;
            precio_total: number;
        }>;
    }>;
    warnings: string[];
}

export interface AcopioCreationResult {
    success: boolean;
    source: string;
    acopio_id: number;
    presupuesto_id: number | null;
    numero_presupuesto: string;
    cliente: string;
    totals: {
        cantidad: number;
        m2: number;
        ml: number;
        importe: number;
    };
    items_count: number;
    panos_count: number;
    warnings: string[];
}

function AltaAcopio() {
    const [activeTab, setActiveTab] = useState<'spf' | 'pdf'>('spf');
    const [searchQuery, setSearchQuery] = useState('');
    const [spfPreview, setSpfPreview] = useState<SpfPresupuestoDetails | null>(null);
    const [pdfPreview, setPdfPreview] = useState<PdfExtractionPackage | null>(null);
    const [loading, setLoading] = useState(false);
    const [error, setError] = useState<string | null>(null);
    const [successData, setSuccessData] = useState<AcopioCreationResult | null>(null);
    const fileInputRef = useRef<HTMLInputElement>(null);

    const handleSpfSearch = async (e: React.FormEvent) => {
        e.preventDefault();
        if (!searchQuery.trim()) {
            setError('Por favor ingrese un ID de presupuesto');
            return;
        }

        setLoading(true);
        setError(null);
        setSpfPreview(null);
        setSuccessData(null);

        try {
            const response = await apiClient.get<SpfPresupuestoDetails>(`/integrations/spf/presupuestos/${searchQuery.trim()}`);
            setSpfPreview(response.data);
        } catch (err: any) {
             setError(err.response?.data?.detail || 'Error al buscar el presupuesto en SPF');
        } finally {
            setLoading(false);
        }
    };

    const handlePdfUpload = async (e: React.ChangeEvent<HTMLInputElement>) => {
        const file = e.target.files?.[0];
        if (!file) return;

        setLoading(true);
        setError(null);
        setPdfPreview(null);
        setSuccessData(null);

        const formData = new FormData();
        formData.append('file', file);

        try {
            const response = await apiClient.post<{ extraction_package: PdfExtractionPackage, warnings: any[] }>('/acopios/upload-pdf', formData, {
                headers: { 'Content-Type': 'multipart/form-data' }
            });
            setPdfPreview(response.data.extraction_package);
        } catch (err: any) {
            setError(err.response?.data?.detail || 'Error al procesar el PDF');
        } finally {
            setLoading(false);
            if (fileInputRef.current) fileInputRef.current.value = '';
        }
    };

    const handleConfirmSpf = async () => {
        if (!spfPreview) return;
        setLoading(true);
        setError(null);
        try {
            const response = await apiClient.post<AcopioCreationResult>('/acopios/from-spf', {
                v_presupuesto_id: spfPreview.v_presupuesto_id,
            });
            setSuccessData(response.data);
            setSpfPreview(null);
            setSearchQuery('');
        } catch (err: any) {
            setError(err.response?.data?.detail || 'Error al crear el acopio');
        } finally {
            setLoading(false);
        }
    };

    const handleConfirmPdf = async () => {
        if (!pdfPreview) return;
        setLoading(true);
        setError(null);
        try {
            const response = await apiClient.post<AcopioCreationResult>('/acopios/confirm-pdf', {
                extraction_package: pdfPreview,
            });
            setSuccessData(response.data);
            setPdfPreview(null);
        } catch (err: any) {
            setError(err.response?.data?.detail || 'Error al crear el acopio');
        } finally {
            setLoading(false);
        }
    };

    const handleReset = () => {
        setSearchQuery('');
        setSpfPreview(null);
        setPdfPreview(null);
        setError(null);
        setSuccessData(null);
    };

    const tabStyle = (tab: 'spf' | 'pdf') => ({
        padding: '10px 20px',
        cursor: 'pointer',
        borderBottom: activeTab === tab ? '3px solid #007bff' : 'none',
        fontWeight: activeTab === tab ? 'bold' : 'normal',
        color: activeTab === tab ? '#007bff' : '#666',
        backgroundColor: 'transparent',
        border: 'none',
        outline: 'none'
    } as const);

    return (
        <div className="alta-acopio">
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                <h2>Alta de Acopio</h2>
                <div style={{ display: 'flex', gap: '10px' }}>
                    <button style={tabStyle('spf')} onClick={() => { setActiveTab('spf'); handleReset(); }}>Origen SPF</button>
                    <button style={tabStyle('pdf')} onClick={() => { setActiveTab('pdf'); handleReset(); }}>Origen PDF</button>
                </div>
            </div>

            {loading && (
                <div className="spinner-overlay">
                    <div className="loader"></div>
                    <div>Procesando... esto puede llevar unos momentos</div>
                </div>
            )}

            {successData && (
                <div className="form-section" style={{ backgroundColor: '#d4edda', borderColor: '#c3e6cb', color: '#155724', padding: '1.5rem', borderRadius: '4px', marginTop: '1rem' }}>
                    <h3 style={{ margin: 0 }}>✓ Acopio creado exitosamente</h3>
                    <div style={{ marginTop: '1rem', display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '1rem', fontSize: '0.95rem' }}>
                        <div>
                            <strong>ID Interno:</strong> {successData.acopio_id}<br />
                            <strong>Presupuesto:</strong> {successData.numero_presupuesto}<br />
                            <strong>Origen:</strong> {successData.source.toUpperCase()}<br />
                            <strong>Cliente:</strong> {successData.cliente}
                        </div>
                        <div>
                            <strong>Resumen:</strong><br />
                            {successData.items_count} ítems | {successData.panos_count} paños<br />
                            {Number(successData.totals.m2).toFixed(2)} m² | {Number(successData.totals.ml).toFixed(2)} ml<br />
                            $ {Number(successData.totals.importe).toLocaleString('es-AR', { minimumFractionDigits: 2 })}
                        </div>
                    </div>
                    <div style={{ marginTop: '1.5rem', display: 'flex', gap: '1rem' }}>
                        <button className="btn btn-primary" onClick={handleReset}>
                            Cargar otro acopio
                        </button>
                        <button className="btn btn-secondary" onClick={() => window.location.href = '/'}>
                            Volver al Inicio
                        </button>
                    </div>
                </div>
            )}

            {error && (
                <div className="error" style={{ color: 'red', margin: '1rem 0', padding: '1rem', border: '1px solid #ffcdd2', backgroundColor: '#ffebee', borderRadius: '4px' }}>
                    <strong>Error:</strong> {error}
                    <div style={{ marginTop: '10px' }}>
                         <button className="btn btn-secondary" onClick={() => setError(null)}>Cerrar</button>
                    </div>
                </div>
            )}

            {!successData && activeTab === 'spf' && !spfPreview && (
                <div className="form-section" style={{ marginTop: '1rem' }}>
                    <h3>1. Buscar Presupuesto en SPF</h3>
                    <form onSubmit={handleSpfSearch} className="form-group" style={{ display: 'flex', gap: '10px' }}>
                        <div style={{ flex: 1 }}>
                            <label>ID Presupuesto o Nro Referencia (Nro OC):</label>
                            <input
                                type="text"
                                value={searchQuery}
                                onChange={(e) => setSearchQuery(e.target.value)}
                                placeholder="Ej: 000203998"
                                style={{ width: '100%', padding: '8px' }}
                            />
                        </div>
                        <div style={{ alignSelf: 'flex-end' }}>
                            <button
                                type="submit"
                                className="btn btn-primary"
                                disabled={!searchQuery.trim() || loading}
                            >
                                {loading ? 'Buscando...' : 'Buscar en SPF'}
                            </button>
                        </div>
                    </form>
                </div>
            )}

            {!successData && activeTab === 'pdf' && !pdfPreview && (
                <div className="form-section" style={{ marginTop: '1rem', textAlign: 'center', padding: '2rem', border: '2px dashed #ccc' }}>
                    <h3>1. Subir PDF de Presupuesto</h3>
                    <p>Sube el archivo PDF del presupuesto original (formato Fontela)</p>
                    <input
                        type="file"
                        accept=".pdf"
                        onChange={handlePdfUpload}
                        ref={fileInputRef}
                        style={{ display: 'none' }}
                        id="pdf-upload"
                    />
                    <label htmlFor="pdf-upload" className="btn btn-primary" style={{ cursor: 'pointer', padding: '10px 20px' }}>
                        Seleccionar Archivo PDF
                    </label>
                </div>
            )}

            {spfPreview && (
                <>
                    <div className="form-section" style={{ marginTop: '1rem' }}>
                        <h3>2. Vista Previa (SPF)</h3>
                        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '1rem' }}>
                            <div>
                                <strong>Presupuesto ID:</strong> {spfPreview.v_presupuesto_id}<br />
                                <strong>Cliente:</strong> {spfPreview.cliente_nombre}<br />
                                <strong>Obra/Ref:</strong> {spfPreview.obra_nombre}
                            </div>
                            <div>
                                <strong>Totales:</strong><br />
                                m²: {Number(spfPreview.total_m2).toFixed(2)}<br />
                                ml: {Number(spfPreview.total_ml).toFixed(2)}<br />
                                $: {Number(spfPreview.total_pesos).toLocaleString('es-AR', { minimumFractionDigits: 2 })}
                            </div>
                        </div>
                    </div>

                    <div className="form-section">
                        <h3>3. Confirmar Creación</h3>
                        <div style={{ display: 'flex', gap: '1rem' }}>
                            <button className="btn btn-success" onClick={handleConfirmSpf} disabled={loading}>Confirmar y Crear</button>
                            <button className="btn btn-secondary" onClick={handleReset} disabled={loading}>Cancelar</button>
                        </div>
                    </div>
                </>
            )}

            {pdfPreview && (
                <>
                    <div className="form-section" style={{ marginTop: '1rem' }}>
                        <h3>2. Vista Previa (PDF)</h3>
                        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '1rem', borderBottom: '1px solid #eee', paddingBottom: '1rem' }}>
                            <div>
                                <strong>Presupuesto Nº:</strong> {pdfPreview.presupuesto.numero}<br />
                                <strong>Empresa:</strong> {pdfPreview.presupuesto.empresa_raw || pdfPreview.presupuesto.empresa}<br />
                                <strong>Obra:</strong> {pdfPreview.presupuesto.obra || "Sin especificar"}<br />
                                <strong>Contacto:</strong> {pdfPreview.presupuesto.contacto}<br />
                                <strong>Estado PDF:</strong> {pdfPreview.presupuesto.estado}
                            </div>
                            <div>
                                <strong>Totales PDF:</strong><br />
                                Unidades: {pdfPreview.presupuesto.total_unidades}<br />
                                m²: {pdfPreview.presupuesto.total_m2.toFixed(2)} | ml: {pdfPreview.presupuesto.total_ml.toFixed(2)}<br />
                                $: {pdfPreview.presupuesto.total_importe.toLocaleString('es-AR', { minimumFractionDigits: 2 })}<br />
                                Peso: {pdfPreview.presupuesto.peso_estimado_kg.toFixed(2)} Kg
                            </div>
                        </div>

                        {pdfPreview.warnings.length > 0 && (
                            <div style={{ backgroundColor: '#fff3cd', padding: '10px', borderRadius: '4px', marginTop: '10px', border: '1px solid #ffeeba' }}>
                                <strong>Avisos de validación:</strong>
                                <ul style={{ margin: '5px 0 0 20px', fontSize: '0.9rem' }}>
                                    {pdfPreview.warnings.map((w, i) => <li key={i}>{w}</li>)}
                                </ul>
                            </div>
                        )}

                        <div style={{ marginTop: '1rem' }}>
                            <h4>Detalle de Ítems</h4>
                            <div style={{ maxHeight: '300px', overflowY: 'auto', border: '1px solid #eee', padding: '10px' }}>
                                {pdfPreview.items.map((item) => (
                                    <div key={item.numero_item} style={{ marginBottom: '1rem', borderBottom: '1px solid #f9f9f9', paddingBottom: '0.5rem' }}>
                                        <strong>Ítem {item.numero_item}:</strong> {item.descripcion} ({item.cantidad} paños{item.adicionales?.length ? `, ${item.adicionales.length} adicionales` : ''})
                                        <div style={{ fontSize: '0.85rem', color: '#666', marginLeft: '1rem' }}>
                                            m²: {item.total_m2.toFixed(2)} | ml: {item.total_ml.toFixed(2)} | $: {item.total_pesos.toLocaleString('es-AR')}
                                        </div>
                                    </div>
                                ))}
                            </div>
                        </div>
                    </div>

                    <div className="form-section">
                        <h3>3. Confirmar Creación</h3>
                        <p style={{ fontSize: '0.9rem', color: '#666' }}>Se creará el acopio utilizando los datos extraídos del PDF.</p>
                        <div style={{ display: 'flex', gap: '1rem' }}>
                            <button className="btn btn-success" onClick={handleConfirmPdf} disabled={loading}>Confirmar y Crear</button>
                            <button className="btn btn-secondary" onClick={handleReset} disabled={loading}>Cancelar / Subir otro</button>
                        </div>
                    </div>
                </>
            )}
        </div>
    );
}

export default AltaAcopio;
