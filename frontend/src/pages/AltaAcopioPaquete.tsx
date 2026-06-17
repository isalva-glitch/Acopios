import { useMemo, useRef, useState, type ChangeEvent, type FormEvent } from 'react';
import { Link } from 'react-router-dom';
import apiClient from '../api/client';
import type { AcopioPaqueteDetalle, AcopioPaquetePreviewItem } from '../types';
import { formatCurrencyAR, formatNumberAR } from '../utils/formatters';

const today = new Date().toISOString().slice(0, 10);

interface PdfExtractionPackage {
    presupuesto: {
        numero: string;
        empresa: string;
        empresa_raw?: string;
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
    };
    items: Array<{
        numero_item: number;
        descripcion: string;
        cantidad: number;
        total_pesos: number;
        total_m2: number;
        total_ml: number;
        panos: unknown[];
        adicionales: unknown[];
    }>;
    warnings: string[];
}

interface AcopioPaquetePdfPreviewItem extends AcopioPaquetePreviewItem {
    extraction_package: PdfExtractionPackage;
    warnings: string[];
}

function parsePresupuestos(value: string) {
    return value
        .split(/[\n,;]+/)
        .map((item) => item.trim())
        .filter(Boolean);
}

function normalizePresupuesto(value: string) {
    const trimmedValue = value.trim().toLowerCase();
    return /^\d+$/.test(trimmedValue) ? String(Number(trimmedValue)) : trimmedValue;
}

function hasDuplicates(values: string[]) {
    const normalized = values.map(normalizePresupuesto);
    return new Set(normalized).size !== normalized.length;
}

function AltaAcopioPaquete() {
    const [nombre, setNombre] = useState('');
    const [cliente, setCliente] = useState('');
    const [fechaAlta, setFechaAlta] = useState(today);
    const [observaciones, setObservaciones] = useState('');
    const [presupuestosInput, setPresupuestosInput] = useState('');
    const [preview, setPreview] = useState<AcopioPaquetePreviewItem[]>([]);
    const [pdfPreviews, setPdfPreviews] = useState<AcopioPaquetePdfPreviewItem[]>([]);
    const [createdPackage, setCreatedPackage] = useState<AcopioPaqueteDetalle | null>(null);
    const [loading, setLoading] = useState(false);
    const [error, setError] = useState<string | null>(null);
    const fileInputRef = useRef<HTMLInputElement>(null);

    const presupuestos = useMemo(() => parsePresupuestos(presupuestosInput), [presupuestosInput]);
    const hasSpfSources = presupuestos.length > 0;
    const hasPdfSources = pdfPreviews.length > 0;
    const spfPreviewIsValid = !hasSpfSources || (preview.length > 0 && preview.every((item) => item.valido));
    const pdfPreviewIsValid = !hasPdfSources || pdfPreviews.every((item) => item.valido);
    const canCreate = (hasSpfSources || hasPdfSources) && spfPreviewIsValid && pdfPreviewIsValid;

    const validateSpfPresupuestos = () => {
        if (presupuestos.length === 0) {
            setError('Ingrese al menos un presupuesto SPF para previsualizar');
            return false;
        }

        if (hasDuplicates(presupuestos)) {
            setError('Hay presupuestos SPF repetidos');
            return false;
        }

        return true;
    };

    const validateSources = () => {
        const pdfPresupuestos = pdfPreviews.map((item) => item.presupuesto).filter(Boolean);

        if (presupuestos.length === 0 && pdfPresupuestos.length === 0) {
            setError('Ingrese al menos un presupuesto SPF o cargue un PDF');
            return false;
        }

        if (hasDuplicates([...presupuestos, ...pdfPresupuestos])) {
            setError('Hay presupuestos repetidos entre SPF y PDF');
            return false;
        }

        if (hasSpfSources && !spfPreviewIsValid) {
            setError('Previsualice y corrija los presupuestos SPF antes de crear el paquete');
            return false;
        }

        if (!pdfPreviewIsValid) {
            setError('Corrija o quite los PDFs con errores antes de crear el paquete');
            return false;
        }

        return true;
    };

    const handlePreview = async (event: FormEvent) => {
        event.preventDefault();
        setCreatedPackage(null);
        setPreview([]);
        setError(null);

        if (!validateSpfPresupuestos()) return;

        setLoading(true);
        try {
            const response = await apiClient.post<{ presupuestos: AcopioPaquetePreviewItem[] }>(
                '/acopio-paquetes/preview',
                { presupuestos },
            );
            setPreview(response.data.presupuestos);
        } catch (err: any) {
            setError(err.response?.data?.detail || 'Error al previsualizar presupuestos');
        } finally {
            setLoading(false);
        }
    };

    const handlePdfUpload = async (event: ChangeEvent<HTMLInputElement>) => {
        const file = event.target.files?.[0];
        if (!file) return;

        setLoading(true);
        setError(null);
        setCreatedPackage(null);

        const formData = new FormData();
        formData.append('file', file);

        try {
            const response = await apiClient.post<AcopioPaquetePdfPreviewItem>(
                '/acopio-paquetes/upload-pdf',
                formData,
                { headers: { 'Content-Type': 'multipart/form-data' } },
            );
            setPdfPreviews((current) => [...current, response.data]);
        } catch (err: any) {
            setError(err.response?.data?.detail || 'Error al procesar el PDF');
        } finally {
            setLoading(false);
            if (fileInputRef.current) fileInputRef.current.value = '';
        }
    };

    const handleRemovePdf = (index: number) => {
        setPdfPreviews((current) => current.filter((_, itemIndex) => itemIndex !== index));
    };

    const handleCreate = async () => {
        setError(null);

        if (!nombre.trim()) {
            setError('Ingrese el nombre del paquete');
            return;
        }

        if (!cliente.trim()) {
            setError('Ingrese el cliente del paquete');
            return;
        }

        if (!validateSources()) return;

        setLoading(true);
        try {
            const response = await apiClient.post<AcopioPaqueteDetalle>('/acopio-paquetes', {
                nombre: nombre.trim(),
                cliente: cliente.trim(),
                fecha_alta: fechaAlta,
                observaciones: observaciones.trim() || null,
                presupuestos,
                pdf_presupuestos: pdfPreviews.map((item) => item.extraction_package),
            });
            setCreatedPackage(response.data);
            setPreview([]);
            setPresupuestosInput('');
            setPdfPreviews([]);
        } catch (err: any) {
            setError(err.response?.data?.detail || 'Error al crear el paquete');
        } finally {
            setLoading(false);
        }
    };

    const handleReset = () => {
        setNombre('');
        setCliente('');
        setFechaAlta(today);
        setObservaciones('');
        setPresupuestosInput('');
        setPreview([]);
        setPdfPreviews([]);
        setCreatedPackage(null);
        setError(null);
        if (fileInputRef.current) fileInputRef.current.value = '';
    };

    return (
        <div className="alta-paquete">
            <div className="page-title-row">
                <h2>Nuevo Paquete de Obras</h2>
                <Link to="/paquetes" className="btn btn-secondary">
                    Ver paquetes
                </Link>
            </div>

            {error && <div className="error">{error}</div>}

            {createdPackage && (
                <div className="form-section success-panel">
                    <h3>Paquete creado</h3>
                    <div className="success-summary">
                        <div>
                            <strong>{createdPackage.numero || createdPackage.id}</strong>
                            <span>{createdPackage.nombre}</span>
                        </div>
                        <div>
                            <strong>{createdPackage.cantidad_acopios}</strong>
                            <span>acopios hijos</span>
                        </div>
                        <div>
                            <strong>{formatCurrencyAR(createdPackage.total_pesos)}</strong>
                            <span>total consolidado</span>
                        </div>
                    </div>
                    <div className="form-actions">
                        <Link to={`/paquetes/${createdPackage.id}`} className="btn btn-primary">
                            Ver detalle
                        </Link>
                        <button type="button" className="btn btn-secondary" onClick={handleReset}>
                            Nuevo paquete
                        </button>
                    </div>
                </div>
            )}

            {!createdPackage && (
                <>
                    <form className="form-section paquete-form" onSubmit={handlePreview}>
                        <div className="paquete-form-grid">
                            <div className="form-group">
                                <label htmlFor="paquete-nombre">Nombre</label>
                                <input
                                    id="paquete-nombre"
                                    value={nombre}
                                    onChange={(event) => setNombre(event.target.value)}
                                />
                            </div>

                            <div className="form-group">
                                <label htmlFor="paquete-cliente">Cliente</label>
                                <input
                                    id="paquete-cliente"
                                    value={cliente}
                                    onChange={(event) => setCliente(event.target.value)}
                                />
                            </div>

                            <div className="form-group">
                                <label htmlFor="paquete-fecha">Fecha Alta</label>
                                <input
                                    id="paquete-fecha"
                                    type="date"
                                    value={fechaAlta}
                                    onChange={(event) => setFechaAlta(event.target.value)}
                                />
                            </div>
                        </div>

                        <div className="form-group">
                            <label htmlFor="paquete-presupuestos">Presupuestos SPF</label>
                            <textarea
                                id="paquete-presupuestos"
                                rows={5}
                                value={presupuestosInput}
                                onChange={(event) => {
                                    setPresupuestosInput(event.target.value);
                                    setPreview([]);
                                }}
                                placeholder="Uno por linea, coma o punto y coma"
                            />
                        </div>

                        <div className="pdf-upload-panel">
                            <div>
                                <strong>Presupuesto madre por PDF</strong>
                                <span>Use esta opcion cuando el presupuesto no exista en SPF.</span>
                            </div>
                            <input
                                ref={fileInputRef}
                                id="paquete-pdf-upload"
                                type="file"
                                accept=".pdf"
                                onChange={handlePdfUpload}
                                style={{ display: 'none' }}
                            />
                            <label htmlFor="paquete-pdf-upload" className="btn btn-primary">
                                {loading ? 'Procesando...' : 'Agregar PDF'}
                            </label>
                        </div>

                        <div className="form-group">
                            <label htmlFor="paquete-observaciones">Observaciones</label>
                            <textarea
                                id="paquete-observaciones"
                                rows={3}
                                value={observaciones}
                                onChange={(event) => setObservaciones(event.target.value)}
                            />
                        </div>

                        <div className="form-actions">
                            <button type="submit" className="btn btn-primary" disabled={loading}>
                                {loading ? 'Validando...' : 'Previsualizar SPF'}
                            </button>
                            <button type="button" className="btn btn-secondary" onClick={handleReset} disabled={loading}>
                                Limpiar
                            </button>
                        </div>
                    </form>

                    {preview.length > 0 && (
                        <section className="form-section">
                            <div className="section-title-row">
                                <h3>Previsualizacion SPF</h3>
                                <span>{preview.length} presupuestos</span>
                            </div>

                            <div className="table paquetes-preview-table">
                                <table>
                                    <thead>
                                        <tr>
                                            <th>Presupuesto</th>
                                            <th>Cliente</th>
                                            <th>Obra</th>
                                            <th>Importe</th>
                                            <th>m2</th>
                                            <th>ml</th>
                                            <th>Unidades</th>
                                            <th>Estado</th>
                                            <th>Observaciones</th>
                                        </tr>
                                    </thead>
                                    <tbody>
                                        {preview.map((item) => (
                                            <tr key={item.presupuesto}>
                                                <td>{item.presupuesto || '-'}</td>
                                                <td>{item.cliente || '-'}</td>
                                                <td>{item.obra || '-'}</td>
                                                <td>{formatCurrencyAR(item.importe)}</td>
                                                <td>{formatNumberAR(item.m2)}</td>
                                                <td>{formatNumberAR(item.ml)}</td>
                                                <td>{item.unidades}</td>
                                                <td>
                                                    <span className={item.valido ? 'status-pill status-ok' : 'status-pill status-error'}>
                                                        {item.estado_validacion}
                                                    </span>
                                                </td>
                                                <td>{item.observaciones || '-'}</td>
                                            </tr>
                                        ))}
                                    </tbody>
                                </table>
                            </div>
                        </section>
                    )}

                    {pdfPreviews.length > 0 && (
                        <section className="form-section">
                            <div className="section-title-row">
                                <h3>Previsualizacion PDF</h3>
                                <span>{pdfPreviews.length} archivos</span>
                            </div>

                            <div className="table paquetes-preview-table">
                                <table>
                                    <thead>
                                        <tr>
                                            <th>Presupuesto</th>
                                            <th>Cliente</th>
                                            <th>Obra</th>
                                            <th>Importe</th>
                                            <th>m2</th>
                                            <th>ml</th>
                                            <th>Unidades</th>
                                            <th>Estado</th>
                                            <th>Observaciones</th>
                                            <th>Acciones</th>
                                        </tr>
                                    </thead>
                                    <tbody>
                                        {pdfPreviews.map((item, index) => (
                                            <tr key={`${item.presupuesto || 'pdf'}-${index}`}>
                                                <td>{item.presupuesto || '-'}</td>
                                                <td>{item.cliente || '-'}</td>
                                                <td>{item.obra || '-'}</td>
                                                <td>{formatCurrencyAR(item.importe)}</td>
                                                <td>{formatNumberAR(item.m2)}</td>
                                                <td>{formatNumberAR(item.ml)}</td>
                                                <td>{item.unidades}</td>
                                                <td>
                                                    <span className={item.valido ? 'status-pill status-ok' : 'status-pill status-error'}>
                                                        {item.estado_validacion}
                                                    </span>
                                                </td>
                                                <td>{item.observaciones || item.warnings.join(', ') || '-'}</td>
                                                <td>
                                                    <button
                                                        type="button"
                                                        className="btn btn-secondary btn-compact"
                                                        onClick={() => handleRemovePdf(index)}
                                                    >
                                                        Quitar
                                                    </button>
                                                </td>
                                            </tr>
                                        ))}
                                    </tbody>
                                </table>
                            </div>
                        </section>
                    )}

                    {(preview.length > 0 || pdfPreviews.length > 0) && (
                        <section className="form-section paquete-create-panel">
                            <div className="section-title-row">
                                <div>
                                    <h3>Crear paquete</h3>
                                    <p>
                                        Se creara un acopio normal por cada presupuesto SPF validado y por cada PDF cargado.
                                    </p>
                                </div>
                                <button
                                    type="button"
                                    className="btn btn-success"
                                    onClick={handleCreate}
                                    disabled={loading || !canCreate}
                                >
                                    {loading ? 'Creando...' : 'Crear paquete'}
                                </button>
                            </div>
                        </section>
                    )}
                </>
            )}
        </div>
    );
}

export default AltaAcopioPaquete;
