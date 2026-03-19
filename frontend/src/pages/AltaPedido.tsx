import { useState } from 'react';
import apiClient from '../api/client';
import type { AcopioPreview } from '../types';

function AltaPedido() {
    const [file, setFile] = useState<File | null>(null);
    const [preview, setPreview] = useState<AcopioPreview | null>(null);
    const [obraId, setObraId] = useState('');
    const [loading, setLoading] = useState(false);
    const [error, setError] = useState<string | null>(null);
    const [success, setSuccess] = useState(false);

    const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
        if (e.target.files && e.target.files[0]) {
            setFile(e.target.files[0]);
            setPreview(null);
            setError(null);
            setSuccess(false);
        }
    };

    const handleUpload = async () => {
        if (!file) {
            setError('Por favor seleccione un archivo PDF');
            return;
        }

        setLoading(true);
        setError(null);

        const formData = new FormData();
        formData.append('file', file);

        try {
            const response = await apiClient.post<AcopioPreview>('/pedidos/upload-pdf', formData, {
                headers: {
                    'Content-Type': 'multipart/form-data',
                },
            });
            setPreview(response.data);
        } catch (err: any) {
            setError(err.response?.data?.detail || 'Error al procesar el PDF');
        } finally {
            setLoading(false);
        }
    };

    const handleConfirm = async () => {
        if (!preview || !obraId) {
            setError('Por favor ingrese el ID de la obra');
            return;
        }

        setLoading(true);
        setError(null);

        try {
            await apiClient.post('/pedidos/confirm', {
                extraction_package: preview.extraction_package,
                obra_id: parseInt(obraId),
            });
            setSuccess(true);
            setPreview(null);
            setFile(null);
            setObraId('');
        } catch (err: any) {
            setError(err.response?.data?.detail || 'Error al confirmar el pedido');
        } finally {
            setLoading(false);
        }
    };

    const handleReset = () => {
        setFile(null);
        setPreview(null);
        setError(null);
        setSuccess(false);
        setObraId('');
    };

    return (
        <div className="alta-pedido">
            <h2>Alta de Pedido</h2>

            {success && (
                <div className="form-section" style={{ backgroundColor: '#d4edda', borderColor: '#c3e6cb', color: '#155724' }}>
                    <h3>✓ Pedido creado exitosamente</h3>
                    <button className="btn btn-primary" onClick={handleReset}>
                        Cargar otro pedido
                    </button>
                </div>
            )}

            {!success && !preview && (
                <div className="form-section">
                    <h3>1. Subir Pedido PDF</h3>
                    <div className="form-group">
                        <label>Seleccione el archivo PDF:</label>
                        <input type="file" accept=".pdf" onChange={handleFileChange} />
                    </div>
                    {file && <p>Archivo seleccionado: {file.name}</p>}
                    <button
                        className="btn btn-primary"
                        onClick={handleUpload}
                        disabled={!file || loading}
                    >
                        {loading ? 'Procesando...' : 'Procesar PDF'}
                    </button>
                </div>
            )}

            {error && (
                <div className="error">
                    <strong>Error:</strong> {error}
                </div>
            )}

            {preview && (
                <>
                    <div className="form-section">
                        <h3>2. Vista Previa de Datos Extraídos</h3>

                        <div style={{ marginBottom: '1rem' }}>
                            <strong>Cliente:</strong> {preview.extraction_package.acopio.cliente}<br />
                            <strong>Obra:</strong> {preview.extraction_package.acopio.obra}<br />
                        </div>

                        {preview.extraction_package.pedidos && preview.extraction_package.pedidos.length > 0 && (
                            <div>
                                <strong>Pedido:</strong> {preview.extraction_package.pedidos[0].numero}<br />
                                <strong>Fecha:</strong> {preview.extraction_package.pedidos[0].fecha}<br />
                            </div>
                        )}
                    </div>

                    {preview.warnings && preview.warnings.length > 0 && (
                        <div className="warning-box">
                            <h4>Advertencias</h4>
                            {preview.warnings.map((warning, idx) => (
                                <div key={idx} className={`warning-item ${warning.level.toLowerCase()}`}>
                                    <strong>[{warning.level}]</strong> {warning.message}
                                </div>
                            ))}
                        </div>
                    )}

                    <div className="form-section">
                        <h3>3. Asociar con Obra</h3>
                        <div className="form-group">
                            <label>ID de Obra:</label>
                            <input
                                type="number"
                                value={obraId}
                                onChange={(e) => setObraId(e.target.value)}
                                placeholder="Ingrese el ID de la obra"
                            />
                        </div>
                    </div>

                    <div className="form-section">
                        <h3>4. Confirmar Creación</h3>
                        <div style={{ display: 'flex', gap: '1rem' }}>
                            <button
                                className="btn btn-success"
                                onClick={handleConfirm}
                                disabled={loading || !obraId}
                            >
                                {loading ? 'Creando...' : 'Confirmar y Crear Pedido'}
                            </button>
                            <button
                                className="btn btn-secondary"
                                onClick={handleReset}
                                disabled={loading}
                            >
                                Cancelar
                            </button>
                        </div>
                    </div>
                </>
            )}
        </div>
    );
}

export default AltaPedido;
