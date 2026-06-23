import { useEffect, useRef, useState } from 'react';
import { Link, useParams } from 'react-router-dom';
import apiClient from '../api/client';
import type { AcopioPaqueteDetalle } from '../types';
import { formatCurrencyAR, formatNumberAR } from '../utils/formatters';

function formatDate(value: string) {
    const date = new Date(`${value}T00:00:00`);
    return Number.isNaN(date.getTime()) ? '-' : date.toLocaleDateString('es-AR');
}

interface PdfPreview {
    presupuesto: string;
    cliente: string | null;
    obra: string | null;
    importe: number;
    m2: number;
    ml: number;
    unidades: number;
    estado_validacion: string;
    observaciones: string | null;
    valido: boolean;
    extraction_package: Record<string, unknown>;
    warnings: string[];
}

type AddTab = 'spf' | 'pdf';

function DetalleAcopioPaquete() {
    const { id } = useParams<{ id: string }>();
    const [paquete, setPaquete] = useState<AcopioPaqueteDetalle | null>(null);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState<string | null>(null);

    // Modal state
    const [showAddModal, setShowAddModal] = useState(false);
    const [addTab, setAddTab] = useState<AddTab>('spf');

    // SPF tab state
    const [newPresupuesto, setNewPresupuesto] = useState('');
    const [isAddingSpf, setIsAddingSpf] = useState(false);

    // PDF tab state
    const [pdfPreview, setPdfPreview] = useState<PdfPreview | null>(null);
    const [isUploadingPdf, setIsUploadingPdf] = useState(false);
    const [isAddingPdf, setIsAddingPdf] = useState(false);
    const [pdfError, setPdfError] = useState<string | null>(null);
    const fileInputRef = useRef<HTMLInputElement>(null);

    const loadPaquete = async () => {
        if (!id) return;
        setLoading(true);
        setError(null);
        try {
            const response = await apiClient.get<AcopioPaqueteDetalle>(`/acopio-paquetes/${id}`);
            setPaquete(response.data);
        } catch (err: any) {
            setError(err.response?.data?.detail || 'Error al cargar el paquete');
        } finally {
            setLoading(false);
        }
    };

    useEffect(() => {
        loadPaquete();
    }, [id]);

    const handleCloseModal = () => {
        setShowAddModal(false);
        setNewPresupuesto('');
        setIsAddingSpf(false);
        setPdfPreview(null);
        setPdfError(null);
        setIsUploadingPdf(false);
        setIsAddingPdf(false);
        if (fileInputRef.current) fileInputRef.current.value = '';
    };

    const handleOpenModal = () => {
        setAddTab('spf');
        setShowAddModal(true);
    };

    // ── SPF handlers ──────────────────────────────────────────────────────────
    const handleAddPresupuesto = async () => {
        if (!newPresupuesto.trim() || !id) return;
        setIsAddingSpf(true);
        try {
            const response = await apiClient.post<AcopioPaqueteDetalle>(`/acopio-paquetes/${id}/presupuestos`, {
                presupuesto: newPresupuesto.trim()
            });
            setPaquete(response.data);
            handleCloseModal();
        } catch (err: any) {
            alert(err.response?.data?.detail || 'Error al agregar presupuesto');
        } finally {
            setIsAddingSpf(false);
        }
    };

    // ── PDF handlers ──────────────────────────────────────────────────────────
    const handlePdfUpload = async (e: React.ChangeEvent<HTMLInputElement>) => {
        const file = e.target.files?.[0];
        if (!file) return;

        setPdfPreview(null);
        setPdfError(null);
        setIsUploadingPdf(true);

        const formData = new FormData();
        formData.append('file', file);

        try {
            const response = await apiClient.post<PdfPreview>(
                '/acopio-paquetes/upload-pdf',
                formData,
                { headers: { 'Content-Type': 'multipart/form-data' } }
            );
            setPdfPreview(response.data);
        } catch (err: any) {
            setPdfError(err.response?.data?.detail || 'Error al procesar el PDF');
        } finally {
            setIsUploadingPdf(false);
            if (fileInputRef.current) fileInputRef.current.value = '';
        }
    };

    const handleAddFromPdf = async () => {
        if (!pdfPreview || !id) return;
        setIsAddingPdf(true);
        setPdfError(null);
        try {
            const response = await apiClient.post<AcopioPaqueteDetalle>(
                `/acopio-paquetes/${id}/presupuestos-pdf`,
                { extraction_package: pdfPreview.extraction_package }
            );
            setPaquete(response.data);
            handleCloseModal();
        } catch (err: any) {
            setPdfError(err.response?.data?.detail || 'Error al agregar desde PDF');
        } finally {
            setIsAddingPdf(false);
        }
    };

    // ── Delete handler ────────────────────────────────────────────────────────
    const handleDeleteAcopio = async (acopioId: number) => {
        if (!id || !window.confirm('¿Estás seguro de que deseas eliminar este acopio del paquete? Esta acción no se puede deshacer.')) {
            return;
        }
        try {
            const response = await apiClient.delete<AcopioPaqueteDetalle>(`/acopio-paquetes/${id}/acopios/${acopioId}`);
            setPaquete(response.data);
        } catch (err: any) {
            alert(err.response?.data?.detail || 'Error al eliminar acopio');
        }
    };

    if (loading) {
        return <div className="loading">Cargando paquete...</div>;
    }

    if (error) {
        return <div className="error">{error}</div>;
    }

    if (!paquete) {
        return <div className="error">Paquete no encontrado</div>;
    }

    return (
        <div className="detalle-paquete">
            <div className="page-title-row">
                <div>
                    <h2>{paquete.nombre}</h2>
                    <p className="page-subtitle">{paquete.numero || `Paquete ${paquete.id}`}</p>
                </div>
                <div className="form-actions">
                    <Link to="/paquetes" className="btn btn-secondary">
                        Ver paquetes
                    </Link>
                    <Link to="/paquetes/nuevo" className="btn btn-primary">
                        Nuevo Paquete
                    </Link>
                </div>
            </div>

            <section className="form-section paquete-resumen">
                <div className="paquete-resumen-header">
                    <div>
                        <span>Cliente</span>
                        <strong>{paquete.cliente}</strong>
                    </div>
                    <div>
                        <span>Fecha</span>
                        <strong>{formatDate(paquete.fecha_alta)}</strong>
                    </div>
                    <div>
                        <span>Estado</span>
                        <strong>{paquete.estado}</strong>
                    </div>
                    <div>
                        <span>Obras</span>
                        <strong>{paquete.cantidad_acopios}</strong>
                    </div>
                </div>

                <div className="kpi-grid paquete-kpis">
                    <article className="kpi-card primary">
                        <span>Total paquete</span>
                        <strong>{formatCurrencyAR(paquete.total_pesos)}</strong>
                        <small>Acopios hijos consolidados</small>
                    </article>
                    <article className="kpi-card">
                        <span>m2</span>
                        <strong>{formatNumberAR(paquete.total_m2)}</strong>
                        <small>Total contratado</small>
                    </article>
                    <article className="kpi-card">
                        <span>ml</span>
                        <strong>{formatNumberAR(paquete.total_ml)}</strong>
                        <small>Total contratado</small>
                    </article>
                    <article className="kpi-card">
                        <span>Unidades</span>
                        <strong>{paquete.total_unidades}</strong>
                        <small>Total contratado</small>
                    </article>
                </div>

                {paquete.observaciones && (
                    <div className="paquete-observaciones">
                        <span>Observaciones</span>
                        <p>{paquete.observaciones}</p>
                    </div>
                )}
            </section>

            <section className="form-section">
                <div className="section-title-row">
                    <div>
                        <h3 style={{ display: 'inline-block', marginRight: '1rem' }}>Acopios hijos</h3>
                        <span>{paquete.acopios.length} registros</span>
                    </div>
                    <button className="btn btn-secondary btn-compact" onClick={handleOpenModal}>
                        + Agregar
                    </button>
                </div>

                <div className="table paquetes-hijos-table">
                    <table>
                        <thead>
                            <tr>
                                <th>Presupuesto</th>
                                <th>Acopio</th>
                                <th>Obra</th>
                                <th>Cliente</th>
                                <th>Estado</th>
                                <th>Total</th>
                                <th>Saldo operativo</th>
                                <th>m2</th>
                                <th>ml</th>
                                <th>Unidades</th>
                                <th>Acciones</th>
                            </tr>
                        </thead>
                        <tbody>
                            {paquete.acopios.map((acopio) => (
                                <tr key={acopio.id}>
                                    <td>{acopio.presupuesto || '-'}</td>
                                    <td>{acopio.numero_acopio || acopio.id}</td>
                                    <td>{acopio.obra || '-'}</td>
                                    <td>{acopio.cliente || '-'}</td>
                                    <td>
                                        <span className="estado-badge paquete-estado">{acopio.estado}</span>
                                    </td>
                                    <td>{formatCurrencyAR(acopio.total_pesos)}</td>
                                    <td>{formatCurrencyAR(acopio.saldo_pesos)}</td>
                                    <td>{formatNumberAR(acopio.total_m2)}</td>
                                    <td>{formatNumberAR(acopio.total_ml)}</td>
                                    <td>{acopio.total_unidades}</td>
                                    <td>
                                        <div style={{ display: 'flex', gap: '0.5rem' }}>
                                            <Link
                                                to={`/acopios/${acopio.id}`}
                                                className="btn btn-primary btn-compact"
                                            >
                                                Ver
                                            </Link>
                                            <button
                                                className="btn btn-compact"
                                                style={{ backgroundColor: '#dc3545', color: 'white', border: 'none' }}
                                                onClick={() => handleDeleteAcopio(acopio.id)}
                                                title="Eliminar acopio"
                                            >
                                                🗑️
                                            </button>
                                        </div>
                                    </td>
                                </tr>
                            ))}
                        </tbody>
                    </table>
                </div>
            </section>

            {/* ── ADD MODAL ──────────────────────────────────────────────────── */}
            {showAddModal && (
                <div className="modal-overlay">
                    <div className="modal-content" style={{ maxWidth: '480px' }}>
                        <h3>Agregar Acopio</h3>

                        {/* Tabs */}
                        <div
                            className="modal-tabs"
                            style={{
                                display: 'flex',
                                gap: 0,
                                marginBottom: '1.25rem',
                                borderBottom: '2px solid var(--border-color, #e2e8f0)',
                            }}
                        >
                            <button
                                type="button"
                                onClick={() => { setAddTab('spf'); setPdfPreview(null); setPdfError(null); }}
                                style={{
                                    flex: 1,
                                    padding: '0.6rem 1rem',
                                    border: 'none',
                                    background: 'none',
                                    cursor: 'pointer',
                                    fontWeight: addTab === 'spf' ? 700 : 400,
                                    borderBottom: addTab === 'spf'
                                        ? '2px solid var(--color-primary, #2563eb)'
                                        : '2px solid transparent',
                                    color: addTab === 'spf' ? 'var(--color-primary, #2563eb)' : 'inherit',
                                    marginBottom: '-2px',
                                    transition: 'all 0.15s',
                                }}
                            >
                                📋 N° Presupuesto SPF
                            </button>
                            <button
                                type="button"
                                onClick={() => { setAddTab('pdf'); setNewPresupuesto(''); }}
                                style={{
                                    flex: 1,
                                    padding: '0.6rem 1rem',
                                    border: 'none',
                                    background: 'none',
                                    cursor: 'pointer',
                                    fontWeight: addTab === 'pdf' ? 700 : 400,
                                    borderBottom: addTab === 'pdf'
                                        ? '2px solid var(--color-primary, #2563eb)'
                                        : '2px solid transparent',
                                    color: addTab === 'pdf' ? 'var(--color-primary, #2563eb)' : 'inherit',
                                    marginBottom: '-2px',
                                    transition: 'all 0.15s',
                                }}
                            >
                                📄 Desde PDF
                            </button>
                        </div>

                        {/* ── SPF TAB ── */}
                        {addTab === 'spf' && (
                            <>
                                <p style={{ color: 'var(--text-muted, #64748b)', marginBottom: '1rem' }}>
                                    Ingresá el número de presupuesto de SPF para agregarlo a este paquete.
                                </p>
                                <div className="form-group">
                                    <label>N° Presupuesto SPF</label>
                                    <input
                                        type="text"
                                        value={newPresupuesto}
                                        onChange={e => setNewPresupuesto(e.target.value)}
                                        placeholder="Ej: 000213054"
                                        onKeyDown={e => e.key === 'Enter' && handleAddPresupuesto()}
                                        autoFocus
                                    />
                                </div>
                                <div className="modal-actions">
                                    <button className="btn btn-secondary" onClick={handleCloseModal} disabled={isAddingSpf}>
                                        Cancelar
                                    </button>
                                    <button
                                        className="btn btn-primary"
                                        onClick={handleAddPresupuesto}
                                        disabled={!newPresupuesto.trim() || isAddingSpf}
                                    >
                                        {isAddingSpf ? 'Agregando...' : 'Agregar'}
                                    </button>
                                </div>
                            </>
                        )}

                        {/* ── PDF TAB ── */}
                        {addTab === 'pdf' && (
                            <>
                                <p style={{ color: 'var(--text-muted, #64748b)', marginBottom: '1rem' }}>
                                    Usá esta opción cuando el presupuesto no exista en SPF.
                                    Se creará un acopio a partir del PDF.
                                </p>

                                {/* File picker (shown when no preview yet) */}
                                {!pdfPreview && (
                                    <div style={{ textAlign: 'center', padding: '1rem 0' }}>
                                        <input
                                            ref={fileInputRef}
                                            id="modal-pdf-upload"
                                            type="file"
                                            accept=".pdf"
                                            onChange={handlePdfUpload}
                                            style={{ display: 'none' }}
                                        />
                                        <label
                                            htmlFor="modal-pdf-upload"
                                            className="btn btn-primary"
                                            style={{
                                                cursor: isUploadingPdf ? 'not-allowed' : 'pointer',
                                                opacity: isUploadingPdf ? 0.7 : 1,
                                            }}
                                        >
                                            {isUploadingPdf ? '⏳ Procesando PDF...' : '📂 Seleccionar PDF'}
                                        </label>
                                    </div>
                                )}

                                {/* Upload error (before preview) */}
                                {!pdfPreview && pdfError && (
                                    <div className="error" style={{ marginTop: '0.75rem' }}>
                                        {pdfError}
                                    </div>
                                )}

                                {/* PDF preview card */}
                                {pdfPreview && (
                                    <div style={{ marginTop: '0.5rem' }}>
                                        <div
                                            style={{
                                                background: pdfPreview.valido
                                                    ? 'var(--color-success-bg, #f0fdf4)'
                                                    : 'var(--color-error-bg, #fef2f2)',
                                                border: `1px solid ${pdfPreview.valido ? '#86efac' : '#fca5a5'}`,
                                                borderRadius: '8px',
                                                padding: '0.85rem 1rem',
                                                marginBottom: '1rem',
                                            }}
                                        >
                                            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '0.4rem' }}>
                                                <strong style={{ fontSize: '1rem' }}>
                                                    {pdfPreview.presupuesto || '(Sin número)'}
                                                </strong>
                                                <span className={pdfPreview.valido ? 'status-pill status-ok' : 'status-pill status-error'}>
                                                    {pdfPreview.estado_validacion}
                                                </span>
                                            </div>
                                            <div style={{
                                                display: 'grid',
                                                gridTemplateColumns: '1fr 1fr',
                                                gap: '0.25rem 1rem',
                                                fontSize: '0.875rem',
                                                color: 'var(--text-muted, #64748b)',
                                            }}>
                                                {pdfPreview.cliente && <span>👤 {pdfPreview.cliente}</span>}
                                                {pdfPreview.obra && <span>🏗️ {pdfPreview.obra}</span>}
                                                <span>💰 {formatCurrencyAR(pdfPreview.importe)}</span>
                                                <span>📐 {formatNumberAR(pdfPreview.m2)} m²&nbsp;·&nbsp;{formatNumberAR(pdfPreview.ml)} ml</span>
                                                <span>📦 {pdfPreview.unidades} unidades</span>
                                            </div>
                                            {pdfPreview.observaciones && (
                                                <p style={{ marginTop: '0.5rem', fontSize: '0.85rem', color: '#b91c1c' }}>
                                                    ⚠️ {pdfPreview.observaciones}
                                                </p>
                                            )}
                                            {pdfPreview.warnings?.length > 0 && (
                                                <p style={{ marginTop: '0.4rem', fontSize: '0.8rem', color: '#92400e' }}>
                                                    ⚠️ {pdfPreview.warnings.join(' · ')}
                                                </p>
                                            )}
                                        </div>

                                        {/* Add error (shown after preview, on confirm) */}
                                        {pdfError && (
                                            <div className="error" style={{ marginBottom: '0.75rem' }}>
                                                {pdfError}
                                            </div>
                                        )}

                                        <div className="modal-actions">
                                            <button
                                                type="button"
                                                className="btn btn-secondary"
                                                onClick={() => { setPdfPreview(null); setPdfError(null); }}
                                                disabled={isAddingPdf}
                                            >
                                                Cambiar PDF
                                            </button>
                                            <button
                                                className="btn btn-secondary"
                                                onClick={handleCloseModal}
                                                disabled={isAddingPdf}
                                            >
                                                Cancelar
                                            </button>
                                            <button
                                                className="btn btn-primary"
                                                onClick={handleAddFromPdf}
                                                disabled={!pdfPreview.valido || isAddingPdf}
                                            >
                                                {isAddingPdf ? 'Agregando...' : 'Agregar'}
                                            </button>
                                        </div>
                                    </div>
                                )}

                                {/* Cancel-only row (before preview) */}
                                {!pdfPreview && (
                                    <div className="modal-actions" style={{ marginTop: '1rem' }}>
                                        <button
                                            className="btn btn-secondary"
                                            onClick={handleCloseModal}
                                            disabled={isUploadingPdf}
                                        >
                                            Cancelar
                                        </button>
                                    </div>
                                )}
                            </>
                        )}
                    </div>
                </div>
            )}
        </div>
    );
}

export default DetalleAcopioPaquete;
