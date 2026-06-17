import { useEffect, useState } from 'react';
import { Link, useParams } from 'react-router-dom';
import apiClient from '../api/client';
import type { AcopioPaqueteDetalle } from '../types';
import { formatCurrencyAR, formatNumberAR } from '../utils/formatters';

function formatDate(value: string) {
    const date = new Date(`${value}T00:00:00`);
    return Number.isNaN(date.getTime()) ? '-' : date.toLocaleDateString('es-AR');
}

function DetalleAcopioPaquete() {
    const { id } = useParams<{ id: string }>();
    const [paquete, setPaquete] = useState<AcopioPaqueteDetalle | null>(null);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState<string | null>(null);

    useEffect(() => {
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

        loadPaquete();
    }, [id]);

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
                    <h3>Acopios hijos</h3>
                    <span>{paquete.acopios.length} registros</span>
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
                                        <Link
                                            to={`/acopios/${acopio.id}`}
                                            className="btn btn-primary btn-compact"
                                        >
                                            Ver acopio
                                        </Link>
                                    </td>
                                </tr>
                            ))}
                        </tbody>
                    </table>
                </div>
            </section>
        </div>
    );
}

export default DetalleAcopioPaquete;
