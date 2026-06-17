import { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import apiClient from '../api/client';
import type { AcopioPaquete } from '../types';
import { formatCurrencyAR, formatNumberAR } from '../utils/formatters';

function formatDate(value: string) {
    const date = new Date(`${value}T00:00:00`);
    return Number.isNaN(date.getTime()) ? '-' : date.toLocaleDateString('es-AR');
}

function ListaAcopioPaquetes() {
    const [paquetes, setPaquetes] = useState<AcopioPaquete[]>([]);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState<string | null>(null);

    const loadPaquetes = async () => {
        setLoading(true);
        setError(null);

        try {
            const response = await apiClient.get<AcopioPaquete[]>('/acopio-paquetes');
            setPaquetes(response.data);
        } catch (err: any) {
            setError(err.response?.data?.detail || 'Error al cargar paquetes');
        } finally {
            setLoading(false);
        }
    };

    useEffect(() => {
        loadPaquetes();
    }, []);

    if (loading) {
        return <div className="loading">Cargando paquetes...</div>;
    }

    if (error) {
        return <div className="error">{error}</div>;
    }

    return (
        <div className="lista-paquetes">
            <div className="page-title-row">
                <h2>Paquetes de Obras</h2>
                <Link to="/paquetes/nuevo" className="btn btn-primary">
                    + Nuevo Paquete
                </Link>
            </div>

            {paquetes.length === 0 ? (
                <div className="form-section">
                    <p>No hay paquetes para mostrar.</p>
                </div>
            ) : (
                <div className="table paquetes-table">
                    <table>
                        <thead>
                            <tr>
                                <th>Numero</th>
                                <th>Nombre</th>
                                <th>Cliente</th>
                                <th>Fecha Alta</th>
                                <th>Estado</th>
                                <th>Obras</th>
                                <th>Total</th>
                                <th>m2</th>
                                <th>ml</th>
                                <th>Unidades</th>
                                <th>Acciones</th>
                            </tr>
                        </thead>
                        <tbody>
                            {paquetes.map((paquete) => (
                                <tr key={paquete.id}>
                                    <td>{paquete.numero || paquete.id}</td>
                                    <td>{paquete.nombre}</td>
                                    <td>{paquete.cliente}</td>
                                    <td>{formatDate(paquete.fecha_alta)}</td>
                                    <td>
                                        <span className="estado-badge paquete-estado">{paquete.estado}</span>
                                    </td>
                                    <td>{paquete.cantidad_acopios}</td>
                                    <td>{formatCurrencyAR(paquete.total_pesos)}</td>
                                    <td>{formatNumberAR(paquete.total_m2)}</td>
                                    <td>{formatNumberAR(paquete.total_ml)}</td>
                                    <td>{paquete.total_unidades}</td>
                                    <td>
                                        <Link
                                            to={`/paquetes/${paquete.id}`}
                                            className="btn btn-primary btn-compact"
                                        >
                                            Ver detalle
                                        </Link>
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

export default ListaAcopioPaquetes;
