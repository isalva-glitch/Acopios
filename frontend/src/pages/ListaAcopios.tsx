import { useState, useEffect } from 'react';
import { Link } from 'react-router-dom';
import apiClient from '../api/client';
import type { Acopio } from '../types';

function ListaAcopios() {
    const [acopios, setAcopios] = useState<Acopio[]>([]);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState<string | null>(null);
    const [filtroEstado, setFiltroEstado] = useState('');

    useEffect(() => {
        loadAcopios();
    }, [filtroEstado]);

    const loadAcopios = async () => {
        setLoading(true);
        setError(null);

        try {
            const params = filtroEstado ? { estado: filtroEstado } : {};
            const response = await apiClient.get<Acopio[]>('/acopios', { params });
            setAcopios(response.data);
        } catch (err: any) {
            setError(err.response?.data?.detail || 'Error al cargar acopios');
        } finally {
            setLoading(false);
        }
    };

    const handleDelete = async (id: number, numero: string) => {
        if (window.confirm(`¿Está seguro que desea eliminar de forma permanente el acopio #${numero}?`)) {
            try {
                await apiClient.delete(`/acopios/${id}`);
                setAcopios(acopios.filter(a => a.id !== id));
            } catch (err: any) {
                alert(err.response?.data?.detail || 'Error al eliminar el acopio');
            }
        }
    };

    const getEstadoBadge = (estado: string) => {
        const colors: Record<string, string> = {
            ACTIVO: '#27ae60',
            PENDIENTE: '#f39c12',
            PARCIALMENTE_CONSUMIDO: '#3498db',
            CONSUMIDO: '#95a5a6',
            CANCELADO: '#e74c3c',
        };
        return {
            backgroundColor: colors[estado] || '#95a5a6',
            color: 'white',
            padding: '0.25rem 0.5rem',
            borderRadius: '4px',
            fontSize: '0.85rem',
            display: 'inline-block',
        };
    };

    if (loading) {
        return <div className="loading">Cargando acopios...</div>;
    }

    if (error) {
        return <div className="error">{error}</div>;
    }

    return (
        <div className="lista-acopios">
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '1.5rem' }}>
                <h2>Acopios</h2>
                <Link to="/acopios/alta" className="btn btn-primary">
                    + Nuevo Acopio
                </Link>
            </div>

            <div className="form-section" style={{ marginBottom: '1.5rem' }}>
                <label style={{ marginRight: '1rem' }}>Filtrar por estado:</label>
                <select
                    value={filtroEstado}
                    onChange={(e) => setFiltroEstado(e.target.value)}
                    style={{ padding: '0.5rem', borderRadius: '4px', border: '1px solid #ddd' }}
                >
                    <option value="">Todos</option>
                    <option value="ACTIVO">Activo</option>
                    <option value="PENDIENTE">Pendiente</option>
                    <option value="PARCIALMENTE_CONSUMIDO">Parcialmente Consumido</option>
                    <option value="CONSUMIDO">Consumido</option>
                    <option value="CANCELADO">Cancelado</option>
                </select>
            </div>

            {acopios.length === 0 ? (
                <div className="form-section">
                    <p>No hay acopios para mostrar.</p>
                </div>
            ) : (
                <div className="table">
                    <table>
                        <thead>
                            <tr>
                                <th>Número</th>
                                <th>Estado</th>
                                <th>Cliente</th>
                                <th>Fecha Alta</th>
                                <th>Paños</th>
                                <th>Saldo m²</th>
                                <th>Saldo ml</th>
                                <th>Saldo $</th>
                                <th>Acciones</th>
                            </tr>
                        </thead>
                        <tbody>
                            {acopios.map((acopio) => (
                                <tr key={acopio.id}>
                                    <td>{acopio.numero}</td>
                                    <td>
                                        <span style={getEstadoBadge(acopio.estado)}>
                                            {acopio.estado}
                                        </span>
                                    </td>
                                    <td>{acopio.cliente || '-'}</td>
                                    <td>{new Date(acopio.fecha_alta).toLocaleDateString()}</td>
                                    <td>{acopio.saldo_unidades ?? 0}</td>
                                    <td>{Number(acopio.saldo_m2).toFixed(2)}</td>
                                    <td>{Number(acopio.saldo_ml).toFixed(2)}</td>
                                    <td>${Number(acopio.saldo_pesos).toFixed(2)}</td>
                                    <td>
                                        <div style={{ display: 'flex', gap: '0.5rem' }}>
                                            <Link to={`/acopios/${acopio.id}`} className="btn btn-primary" style={{ padding: '0.4rem 0.8rem', fontSize: '0.85rem' }}>
                                                Detalle
                                            </Link>
                                            <button 
                                                onClick={() => handleDelete(acopio.id, acopio.numero)} 
                                                className="btn" 
                                                style={{ backgroundColor: '#e74c3c', color: 'white', padding: '0.4rem 0.8rem', fontSize: '0.85rem', border: 'none', borderRadius: '4px', cursor: 'pointer' }}
                                            >
                                                Borrar
                                            </button>
                                        </div>
                                    </td>
                                </tr>
                            ))}
                        </tbody>
                    </table>
                </div>
            )}
        </div>
    );
}

export default ListaAcopios;
