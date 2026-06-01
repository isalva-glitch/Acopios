import { useEffect, useMemo, useState } from 'react';
import apiClient from '../api/client';
import { formatCurrencyAR, formatNumberAR } from '../utils/formatters';

type ReportType = 'acopios-activos' | 'excedentes' | 'vencimientos-precio';

type DashboardRow = {
    id?: number;
    numero?: string;
    acopio_numero?: string;
    pedido_numero?: string;
    obra?: string;
    cliente?: string;
    estado?: string;
    saldo_m2?: number;
    saldo_ml?: number;
    saldo_pesos?: number;
    cantidad_m2?: number;
    cantidad_ml?: number;
    cantidad_pesos?: number;
    fecha?: string;
    fecha_alta?: string;
    fecha_vencimiento?: string | null;
    dias_restantes?: number | null;
};

const reportes = [
    {
        key: 'acopios-activos',
        label: 'Acopios activos',
        description: 'Saldos disponibles por obra y cliente',
        responseKey: 'acopios',
    },
    {
        key: 'excedentes',
        label: 'Excedentes',
        description: 'Consumos por encima de lo contratado',
        responseKey: 'excedentes',
    },
    {
        key: 'vencimientos-precio',
        label: 'Vencimientos',
        description: 'Acopios proximos a vencer por precio',
        responseKey: 'vencimientos',
    },
] as const;

function toNumber(value: number | string | null | undefined) {
    const parsed = Number(value);
    return Number.isFinite(parsed) ? parsed : 0;
}

function formatDate(value: string | null | undefined) {
    if (!value) return '-';

    const normalizedValue = /^\d{4}-\d{2}-\d{2}$/.test(value) ? `${value}T00:00:00` : value;
    const date = new Date(normalizedValue);
    if (Number.isNaN(date.getTime())) return '-';

    return date.toLocaleDateString('es-AR');
}

function Reportes() {
    const [selectedReport, setSelectedReport] = useState<ReportType>('acopios-activos');
    const [data, setData] = useState<DashboardRow[]>([]);
    const [loading, setLoading] = useState(false);
    const [error, setError] = useState<string | null>(null);
    const [filtroTexto, setFiltroTexto] = useState('');
    const [estadoFiltro, setEstadoFiltro] = useState('todos');

    const selectedInfo = reportes.find((item) => item.key === selectedReport) || reportes[0];

    const loadReport = async (format: 'json' | 'csv' = 'json') => {
        setLoading(true);
        setError(null);

        try {
            const endpoint = `/reportes/${selectedReport}`;

            if (format === 'csv') {
                const response = await apiClient.get(endpoint, {
                    params: { format: 'csv' },
                    responseType: 'blob',
                });

                const url = window.URL.createObjectURL(new Blob([response.data]));
                const link = document.createElement('a');
                link.href = url;
                link.setAttribute('download', `${selectedReport}.csv`);
                document.body.appendChild(link);
                link.click();
                link.remove();
                window.URL.revokeObjectURL(url);
                return;
            }

            const response = await apiClient.get(endpoint);
            setData(response.data[selectedInfo.responseKey] || []);
        } catch (err: any) {
            setError(err.response?.data?.detail || 'Error al cargar el informe');
        } finally {
            setLoading(false);
        }
    };

    useEffect(() => {
        loadReport('json');
    }, [selectedReport]);

    const estadosDisponibles = useMemo(() => {
        const estados = new Set<string>();

        data.forEach((item) => {
            if (item.estado) estados.add(String(item.estado));
        });

        return Array.from(estados).sort();
    }, [data]);

    const filteredData = useMemo(() => {
        const normalizedSearch = filtroTexto.trim().toLowerCase();

        return data.filter((item) => {
            const searchableText = [
                item.numero,
                item.acopio_numero,
                item.pedido_numero,
                item.obra,
                item.cliente,
            ].filter(Boolean).join(' ').toLowerCase();

            const coincideTexto = !normalizedSearch || searchableText.includes(normalizedSearch);
            const coincideEstado =
                estadoFiltro === 'todos' ||
                String(item.estado || '').toLowerCase() === estadoFiltro.toLowerCase();

            return coincideTexto && coincideEstado;
        });
    }, [data, filtroTexto, estadoFiltro]);

    const metricas = useMemo(() => {
        const totalPesos = filteredData.reduce((sum, item) => {
            return sum + toNumber(item.saldo_pesos ?? item.cantidad_pesos);
        }, 0);

        const totalM2 = filteredData.reduce((sum, item) => {
            return sum + toNumber(item.saldo_m2 ?? item.cantidad_m2);
        }, 0);

        const totalMl = filteredData.reduce((sum, item) => {
            return sum + toNumber(item.saldo_ml ?? item.cantidad_ml);
        }, 0);

        const alertas = filteredData.filter((item) => {
            if (selectedReport === 'vencimientos-precio') {
                return toNumber(item.dias_restantes) <= 15;
            }

            if (selectedReport === 'excedentes') {
                return toNumber(item.cantidad_pesos) > 0;
            }

            return toNumber(item.saldo_pesos) > 0;
        }).length;

        return {
            registros: filteredData.length,
            totalPesos,
            totalM2,
            totalMl,
            alertas,
        };
    }, [filteredData, selectedReport]);

    const topObras = useMemo(() => {
        const grouped = new Map<string, number>();

        filteredData.forEach((item) => {
            const obra = item.obra || 'Sin obra';
            const importe = toNumber(item.saldo_pesos ?? item.cantidad_pesos);
            grouped.set(obra, (grouped.get(obra) || 0) + importe);
        });

        return Array.from(grouped.entries())
            .map(([obra, importe]) => ({ obra, importe }))
            .sort((a, b) => b.importe - a.importe)
            .slice(0, 6);
    }, [filteredData]);

    const maxObra = Math.max(...topObras.map((item) => item.importe), 1);
    const promedioPorRegistro = metricas.registros > 0 ? metricas.totalPesos / metricas.registros : 0;

    return (
        <div className="informes-page">
            <section className="informes-header">
                <div>
                    <span className="informes-eyebrow">Panel ejecutivo</span>
                    <h2>Informes</h2>
                    <p>Control comercial, operativo y financiero.</p>
                </div>

                <div className="informes-actions">
                    <button className="btn btn-secondary" onClick={() => loadReport('json')} disabled={loading}>
                        {loading ? 'Actualizando...' : 'Actualizar'}
                    </button>
                    <button className="btn btn-primary" onClick={() => loadReport('csv')} disabled={loading}>
                        Exportar CSV
                    </button>
                </div>
            </section>

            <section className="informes-tabs" aria-label="Tipos de informe">
                {reportes.map((reporte) => (
                    <button
                        key={reporte.key}
                        className={selectedReport === reporte.key ? 'informe-tab active' : 'informe-tab'}
                        onClick={() => {
                            setSelectedReport(reporte.key);
                            setFiltroTexto('');
                            setEstadoFiltro('todos');
                        }}
                    >
                        <strong>{reporte.label}</strong>
                        <span>{reporte.description}</span>
                    </button>
                ))}
            </section>

            <section className="informes-filtros">
                <div>
                    <label htmlFor="informes-busqueda">Buscar</label>
                    <input
                        id="informes-busqueda"
                        value={filtroTexto}
                        onChange={(e) => setFiltroTexto(e.target.value)}
                        placeholder="Obra, cliente, acopio o pedido"
                    />
                </div>

                <div>
                    <label htmlFor="informes-estado">Estado</label>
                    <select
                        id="informes-estado"
                        value={estadoFiltro}
                        onChange={(e) => setEstadoFiltro(e.target.value)}
                    >
                        <option value="todos">Todos</option>
                        {estadosDisponibles.map((estado) => (
                            <option key={estado} value={estado}>
                                {estado}
                            </option>
                        ))}
                    </select>
                </div>

                <div className="informe-contexto">
                    <span>Informe seleccionado</span>
                    <strong>{selectedInfo.label}</strong>
                </div>
            </section>

            {error && <div className="error">{error}</div>}

            <section className="kpi-grid">
                <article className="kpi-card primary">
                    <span>Importe analizado</span>
                    <strong>{formatCurrencyAR(metricas.totalPesos)}</strong>
                    <small>Total del informe filtrado</small>
                </article>

                <article className="kpi-card">
                    <span>Registros</span>
                    <strong>{metricas.registros}</strong>
                    <small>Resultados visibles</small>
                </article>

                <article className="kpi-card">
                    <span>Saldo / consumo m²</span>
                    <strong>{formatNumberAR(metricas.totalM2)}</strong>
                    <small>Metros cuadrados acumulados</small>
                </article>

                <article className="kpi-card">
                    <span>Saldo / consumo ml</span>
                    <strong>{formatNumberAR(metricas.totalMl)}</strong>
                    <small>Metros lineales acumulados</small>
                </article>

                <article className="kpi-card danger">
                    <span>Alertas</span>
                    <strong>{metricas.alertas}</strong>
                    <small>Casos para seguimiento</small>
                </article>
            </section>

            <section className="informes-layout">
                <article className="dashboard-card chart-card">
                    <div className="dashboard-card-header">
                        <div>
                            <h3>Ranking por obra</h3>
                            <p>Distribucion economica del informe actual</p>
                        </div>
                    </div>

                    <div className="bar-chart">
                        {topObras.length === 0 && (
                            <div className="empty-state">
                                {loading ? 'Cargando datos...' : 'Sin datos para mostrar'}
                            </div>
                        )}

                        {topObras.map((item) => (
                            <div className="bar-row" key={item.obra}>
                                <div className="bar-label">
                                    <span>{item.obra}</span>
                                    <strong>{formatCurrencyAR(item.importe)}</strong>
                                </div>
                                <div className="bar-track">
                                    <div
                                        className="bar-fill"
                                        style={{ width: `${Math.max((item.importe / maxObra) * 100, 4)}%` }}
                                    />
                                </div>
                            </div>
                        ))}
                    </div>
                </article>

                <article className="dashboard-card insight-card">
                    <div className="dashboard-card-header">
                        <div>
                            <h3>Lectura rapida</h3>
                            <p>Indicadores para decision</p>
                        </div>
                    </div>

                    <div className="insight-list">
                        <div>
                            <span>Mayor concentracion</span>
                            <strong>{topObras[0]?.obra || 'Sin datos'}</strong>
                        </div>
                        <div>
                            <span>Promedio por registro</span>
                            <strong>{formatCurrencyAR(promedioPorRegistro)}</strong>
                        </div>
                        <div>
                            <span>Estado del tablero</span>
                            <strong>{loading ? 'Actualizando' : 'Actualizado'}</strong>
                        </div>
                    </div>
                </article>
            </section>

            <section className="dashboard-card">
                <div className="dashboard-card-header">
                    <div>
                        <h3>Detalle operativo</h3>
                        <p>{filteredData.length} registros encontrados</p>
                    </div>
                </div>

                <div className="table informes-table">
                    <table>
                        <thead>
                            <tr>
                                <th>Referencia</th>
                                <th>Obra</th>
                                <th>Cliente</th>
                                <th>Estado</th>
                                <th>m²</th>
                                <th>ml</th>
                                <th>Importe</th>
                                <th>Fecha / vencimiento</th>
                            </tr>
                        </thead>
                        <tbody>
                            {filteredData.map((item, idx) => (
                                <tr key={`${item.id || idx}-${item.numero || item.pedido_numero || selectedReport}`}>
                                    <td>
                                        <strong>{item.numero || item.acopio_numero || item.pedido_numero || '-'}</strong>
                                        {item.pedido_numero && <small>Pedido {item.pedido_numero}</small>}
                                    </td>
                                    <td>{item.obra || '-'}</td>
                                    <td>{item.cliente || '-'}</td>
                                    <td>
                                        <span className="status-pill">{item.estado || selectedInfo.label}</span>
                                    </td>
                                    <td>{formatNumberAR(item.saldo_m2 ?? item.cantidad_m2 ?? 0)}</td>
                                    <td>{formatNumberAR(item.saldo_ml ?? item.cantidad_ml ?? 0)}</td>
                                    <td>{formatCurrencyAR(item.saldo_pesos ?? item.cantidad_pesos ?? 0)}</td>
                                    <td>
                                        {formatDate(item.fecha_vencimiento || item.fecha || item.fecha_alta)}
                                        {item.dias_restantes !== undefined && item.dias_restantes !== null && (
                                            <small>{item.dias_restantes} dias restantes</small>
                                        )}
                                    </td>
                                </tr>
                            ))}

                            {!loading && filteredData.length === 0 && (
                                <tr>
                                    <td colSpan={8}>
                                        <div className="empty-state">Sin registros para los filtros actuales</div>
                                    </td>
                                </tr>
                            )}
                        </tbody>
                    </table>
                </div>
            </section>
        </div>
    );
}

export default Reportes;
