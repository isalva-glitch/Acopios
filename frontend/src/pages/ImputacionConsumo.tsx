import { useState, useEffect } from 'react';
import apiClient from '../api/client';
import type { Acopio, Pedido } from '../types';

function ImputacionConsumo() {
    const [pedidos, setPedidos] = useState<Pedido[]>([]);
    const [acopios, setAcopios] = useState<Acopio[]>([]);
    const [selectedPedido, setSelectedPedido] = useState('');
    const [selectedAcopio, setSelectedAcopio] = useState('');
    const [cantidadM2, setCantidadM2] = useState('');
    const [cantidadMl, setCantidadMl] = useState('');
    const [cantidadPesos, setCantidadPesos] = useState('');
    const [cantidadUnidades, setCantidadUnidades] = useState('');
    const [loading, setLoading] = useState(false);
    const [error, setError] = useState<string | null>(null);
    const [success, setSuccess] = useState(false);
    const [warning, setWarning] = useState<string | null>(null);

    useEffect(() => {
        loadData();
    }, []);

    const loadData = async () => {
        try {
            const [pedidosRes, acopiosRes] = await Promise.all([
                apiClient.get<Pedido[]>('/pedidos'),
                apiClient.get<Acopio[]>('/acopios'),
            ]);
            setPedidos(pedidosRes.data);
            setAcopios(acopiosRes.data.filter(a => a.saldo_m2 > 0 || a.saldo_ml > 0 || a.saldo_pesos > 0));
        } catch (err) {
            console.error('Error loading data:', err);
        }
    };

    const handleSubmit = async (e: React.FormEvent) => {
        e.preventDefault();
        setLoading(true);
        setError(null);
        setWarning(null);
        setSuccess(false);

        try {
            const response = await apiClient.post('/imputaciones', {
                pedido_id: parseInt(selectedPedido),
                acopio_id: parseInt(selectedAcopio),
                cantidad_m2: parseFloat(cantidadM2),
                cantidad_ml: parseFloat(cantidadMl),
                cantidad_pesos: parseFloat(cantidadPesos),
                cantidad_unidades: parseInt(cantidadUnidades) || 0,
            });

            setSuccess(true);

            if (response.data.warning) {
                setWarning(response.data.warning);
            }

            // Reset form
            setSelectedPedido('');
            setSelectedAcopio('');
            setCantidadM2('');
            setCantidadMl('');
            setCantidadPesos('');
            setCantidadUnidades('');

            // Reload data
            loadData();
        } catch (err: any) {
            setError(err.response?.data?.detail || 'Error al crear imputación');
        } finally {
            setLoading(false);
        }
    };

    return (
        <div className="imputacion-consumo">
            <h2>Imputación de Consumo</h2>

            {success && (
                <div className="form-section" style={{ backgroundColor: '#d4edda', borderColor: '#c3e6cb', color: '#155724' }}>
                    <p>✓ Imputación creada exitosamente</p>
                </div>
            )}

            {warning && (
                <div className="warning-box">
                    <p>⚠️ {warning}</p>
                </div>
            )}

            {error && (
                <div className="error">
                    <strong>Error:</strong> {error}
                </div>
            )}

            <div className="form-section">
                <form onSubmit={handleSubmit}>
                    <div className="form-group">
                        <label>Pedido *</label>
                        <select
                            value={selectedPedido}
                            onChange={(e) => setSelectedPedido(e.target.value)}
                            required
                        >
                            <option value="">Seleccione un pedido</option>
                            {pedidos.map((p) => (
                                <option key={p.id} value={p.id}>
                                    {p.numero} - {p.estado}
                                </option>
                            ))}
                        </select>
                    </div>

                    <div className="form-group">
                        <label>Acopio *</label>
                        <select
                            value={selectedAcopio}
                            onChange={(e) => setSelectedAcopio(e.target.value)}
                            required
                        >
                            <option value="">Seleccione un acopio</option>
                            {acopios.map((a) => (
                                <option key={a.id} value={a.id}>
                                    {a.numero} - Saldo: {Number(a.saldo_m2).toFixed(2)}m² / {Number(a.saldo_ml).toFixed(2)}ml / ${Number(a.saldo_pesos).toFixed(2)}
                                </option>
                            ))}
                        </select>
                    </div>

                    <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: '1rem' }}>
                        <div className="form-group">
                            <label>Cantidad (Paños) *</label>
                            <input
                                type="number"
                                step="1"
                                value={cantidadUnidades}
                                onChange={(e) => setCantidadUnidades(e.target.value)}
                                required
                            />
                        </div>

                        <div className="form-group">
                            <label>Cantidad m² *</label>
                            <input
                                type="number"
                                step="0.01"
                                value={cantidadM2}
                                onChange={(e) => setCantidadM2(e.target.value)}
                                required
                            />
                        </div>

                        <div className="form-group">
                            <label>Cantidad ml *</label>
                            <input
                                type="number"
                                step="0.01"
                                value={cantidadMl}
                                onChange={(e) => setCantidadMl(e.target.value)}
                                required
                            />
                        </div>

                        <div className="form-group">
                            <label>Cantidad $ *</label>
                            <input
                                type="number"
                                step="0.01"
                                value={cantidadPesos}
                                onChange={(e) => setCantidadPesos(e.target.value)}
                                required
                            />
                        </div>
                    </div>

                    <button
                        type="submit"
                        className="btn btn-success"
                        disabled={loading}
                    >
                        {loading ? 'Procesando...' : 'Imputar Consumo'}
                    </button>
                </form>
            </div>
        </div>
    );
}

export default ImputacionConsumo;
