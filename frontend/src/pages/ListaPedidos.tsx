import { useState, useEffect } from 'react';
import { Link } from 'react-router-dom';
import apiClient from '../api/client';
import type { Pedido } from '../types';

function ListaPedidos() {
    const [pedidos, setPedidos] = useState<Pedido[]>([]);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState<string | null>(null);

    useEffect(() => {
        loadPedidos();
    }, []);

    const loadPedidos = async () => {
        setLoading(true);
        setError(null);

        try {
            const response = await apiClient.get<Pedido[]>('/pedidos');
            setPedidos(response.data);
        } catch (err: any) {
            setError(err.response?.data?.detail || 'Error al cargar pedidos');
        } finally {
            setLoading(false);
        }
    };

    if (loading) {
        return <div className="loading">Cargando pedidos...</div>;
    }

    if (error) {
        return <div className="error">{error}</div>;
    }

    return (
        <div className="lista-pedidos">
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '1.5rem' }}>
                <h2>Pedidos</h2>
                <Link to="/pedidos/alta" className="btn btn-primary">
                    + Nuevo Pedido
                </Link>
            </div>

            {pedidos.length === 0 ? (
                <div className="form-section">
                    <p>No hay pedidos para mostrar.</p>
                </div>
            ) : (
                <div className="table">
                    <table>
                        <thead>
                            <tr>
                                <th>Número</th>
                                <th>Estado</th>
                                <th>Fecha</th>
                                <th>Total m²</th>
                                <th>Total ml</th>
                                <th>Total $</th>
                            </tr>
                        </thead>
                        <tbody>
                            {pedidos.map((pedido) => (
                                <tr key={pedido.id}>
                                    <td>{pedido.numero}</td>
                                    <td>{pedido.estado}</td>
                                    <td>{new Date(pedido.fecha).toLocaleDateString()}</td>
                                    <td>{Number(pedido.total_m2).toFixed(2)}</td>
                                    <td>{Number(pedido.total_ml).toFixed(2)}</td>
                                    <td>${Number(pedido.total_pesos).toFixed(2)}</td>
                                </tr>
                            ))}
                        </tbody>
                    </table>
                </div>
            )}
        </div>
    );
}

export default ListaPedidos;
