import { useState } from 'react';
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

function AltaAcopio() {
    const [searchQuery, setSearchQuery] = useState('');
    const [preview, setPreview] = useState<SpfPresupuestoDetails | null>(null);
    const [loading, setLoading] = useState(false);
    const [error, setError] = useState<string | null>(null);
    const [success, setSuccess] = useState(false);

    const handleSearch = async (e: React.FormEvent) => {
        e.preventDefault();
        if (!searchQuery.trim()) {
            setError('Por favor ingrese un ID de presupuesto');
            return;
        }

        setLoading(true);
        setError(null);
        setPreview(null);
        setSuccess(false);

        try {
            const response = await apiClient.get<SpfPresupuestoDetails>(`/integrations/spf/presupuestos/${searchQuery.trim()}`);
            setPreview(response.data);
        } catch (err: any) {
             setError(err.response?.data?.detail || 'Error al buscar el presupuesto en SPF');
        } finally {
            setLoading(false);
        }
    };

    const handleConfirm = async () => {
        if (!preview) return;

        setLoading(true);
        setError(null);

        try {
            await apiClient.post('/acopios/from-spf', {
                v_presupuesto_id: preview.v_presupuesto_id,
            });
            setSuccess(true);
            setPreview(null);
            setSearchQuery('');
        } catch (err: any) {
            setError(err.response?.data?.detail || 'Error al crear el acopio');
        } finally {
            setLoading(false);
        }
    };

    const handleReset = () => {
        setSearchQuery('');
        setPreview(null);
        setError(null);
        setSuccess(false);
    };

    return (
        <div className="alta-acopio">
            <h2>Alta de Acopio desde SPF</h2>

            {loading && (
                <div className="spinner-overlay">
                    <div className="loader"></div>
                    <div>Procesando... esto puede llevar unos momentos</div>
                </div>
            )}

            {success && (
                <div className="form-section" style={{ backgroundColor: '#d4edda', borderColor: '#c3e6cb', color: '#155724', padding: '1rem', borderRadius: '4px' }}>
                    <h3>✓ Acopio creado exitosamente</h3>
                    <button className="btn btn-primary" onClick={handleReset} style={{ marginTop: '1rem' }}>
                        Cargar otro acopio
                    </button>
                </div>
            )}

            {!success && !preview && (
                <div className="form-section">
                    <h3>1. Buscar Presupuesto SPF</h3>
                    <form onSubmit={handleSearch} className="form-group" style={{ display: 'flex', gap: '10px' }}>
                        <div style={{ flex: 1 }}>
                            <label>ID Presupuesto o Nro Pedido SPF:</label>
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
                                {loading ? 'Buscando...' : 'Buscar'}
                            </button>
                        </div>
                    </form>
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

            {preview && (
                <>
                    <div className="form-section">
                        <h3>2. Vista Previa de Datos (SPF)</h3>

                        <div style={{ marginBottom: '1rem' }}>
                            <strong>Presupuesto ID (SPF):</strong> {preview.v_presupuesto_id}<br />
                            <strong>Cliente detectado:</strong> {preview.cliente_nombre}<br />
                            <strong>Nombre/Referencia Obra:</strong> {preview.obra_nombre}<br />
                            <strong>Cantidad de Pedidos Relacionados:</strong> {preview.pedidos_relacionados.length} <br />
                        </div>

                        <div style={{ marginBottom: '1rem' }}>
                            <strong>Totales Calculados desde SPF:</strong><br />
                            m²: {Number(preview.total_m2).toFixed(2)}<br />
                            ml: {Number(preview.total_ml).toFixed(2)}<br />
                            $: {Number(preview.total_pesos).toLocaleString('es-AR', { minimumFractionDigits: 2 })}
                        </div>

                        <div>
                            <strong>Items Encontrados:</strong> {preview.items_count}<br />
                        </div>
                    </div>

                    <div className="form-section">
                        <h3>3. Confirmar Creación</h3>
                        <div style={{ display: 'flex', gap: '1rem' }}>
                            <button
                                className="btn btn-success"
                                onClick={handleConfirm}
                                disabled={loading}
                            >
                                {loading ? 'Creando...' : 'Confirmar y Crear Acopio'}
                            </button>
                            <button
                                className="btn btn-secondary"
                                onClick={handleReset}
                                disabled={loading}
                            >
                                Cancelar / Buscar Otro
                            </button>
                        </div>
                    </div>
                </>
            )}
        </div>
    );
}

export default AltaAcopio;
