import { useEffect, useMemo, useState } from 'react';
import {
    Bar,
    BarChart,
    CartesianGrid,
    Cell,
    Legend,
    Line,
    LineChart,
    Pie,
    PieChart,
    ResponsiveContainer,
    Tooltip,
    XAxis,
    YAxis,
} from 'recharts';
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

const chartColors = ['#2563eb', '#16a34a', '#f59e0b', '#dc2626', '#7c3aed', '#0891b2', '#64748b'];

function toNumber(value: number | string | null | undefined) {
    const parsed = Number(value);
    return Number.isFinite(parsed) ? parsed : 0;
}

function parseDateValue(value: string | null | undefined) {
    if (!value) return null;

    const normalizedValue = /^\d{4}-\d{2}-\d{2}$/.test(value) ? `${value}T00:00:00` : value;
    const date = new Date(normalizedValue);
    return Number.isNaN(date.getTime()) ? null : date;
}

function getRowDate(item: DashboardRow) {
    return parseDateValue(item.fecha_vencimiento || item.fecha || item.fecha_alta);
}

function formatDate(value: string | null | undefined) {
    const date = parseDateValue(value);
    return date ? date.toLocaleDateString('es-AR') : '-';
}

function getImporte(item: DashboardRow) {
    return toNumber(item.saldo_pesos ?? item.cantidad_pesos);
}

function getEstadoVisual(item: DashboardRow, selectedReport: ReportType, fallback: string) {
    if (item.estado) return item.estado;

    if (selectedReport === 'excedentes') {
        return 'Excedido';
    }

    if (selectedReport === 'vencimientos-precio') {
        const diasRestantes = toNumber(item.dias_restantes);
        if (diasRestantes < 0) return 'Vencido';
        if (diasRestantes <= 15) return 'Vence <= 15 dias';
        return 'Vence 16-30 dias';
    }

    return fallback;
}

function truncateLabel(value: string, maxLength = 18) {
    return value.length > maxLength ? `${value.slice(0, maxLength - 1)}...` : value;
}

function Reportes() {
    const [selectedReport, setSelectedReport] = useState<ReportType>('acopios-activos');
    const [data, setData] = useState<DashboardRow[]>([]);
    const [loading, setLoading] = useState(false);
    const [error, setError] = useState<string | null>(null);
    const [filtroTexto, setFiltroTexto] = useState('');
    const [estadoFiltro, setEstadoFiltro] = useState('todos');
    const [obraFiltro, setObraFiltro] = useState('todos');
    const [clienteFiltro, setClienteFiltro] = useState('todos');
    const [fechaDesde, setFechaDesde] = useState('');
    const [fechaHasta, setFechaHasta] = useState('');

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
            estados.add(getEstadoVisual(item, selectedReport, selectedInfo.label));
        });

        return Array.from(estados).sort();
    }, [data, selectedInfo.label, selectedReport]);

    const obrasDisponibles = useMemo(() => {
        const obras = new Set<string>();

        data.forEach((item) => {
            if (item.obra) obras.add(item.obra);
        });

        return Array.from(obras).sort();
    }, [data]);

    const clientesDisponibles = useMemo(() => {
        const clientes = new Set<string>();

        data.forEach((item) => {
            if (item.cliente) clientes.add(item.cliente);
        });

        return Array.from(clientes).sort();
    }, [data]);

    const filteredData = useMemo(() => {
        const normalizedSearch = filtroTexto.trim().toLowerCase();
        const desde = parseDateValue(fechaDesde);
        const hasta = parseDateValue(fechaHasta);
        if (hasta) hasta.setHours(23, 59, 59, 999);

        return data.filter((item) => {
            const searchableText = [
                item.numero,
                item.acopio_numero,
                item.pedido_numero,
                item.obra,
                item.cliente,
            ].filter(Boolean).join(' ').toLowerCase();

            const estadoVisual = getEstadoVisual(item, selectedReport, selectedInfo.label);
            const itemDate = getRowDate(item);

            const coincideTexto = !normalizedSearch || searchableText.includes(normalizedSearch);
            const coincideEstado = estadoFiltro === 'todos' || estadoVisual === estadoFiltro;
            const coincideObra = obraFiltro === 'todos' || item.obra === obraFiltro;
            const coincideCliente = clienteFiltro === 'todos' || item.cliente === clienteFiltro;
            const coincideDesde = !desde || (itemDate !== null && itemDate >= desde);
            const coincideHasta = !hasta || (itemDate !== null && itemDate <= hasta);

            return (
                coincideTexto &&
                coincideEstado &&
                coincideObra &&
                coincideCliente &&
                coincideDesde &&
                coincideHasta
            );
        });
    }, [
        clienteFiltro,
        data,
        estadoFiltro,
        fechaDesde,
        fechaHasta,
        filtroTexto,
        obraFiltro,
        selectedInfo.label,
        selectedReport,
    ]);

    const metricas = useMemo(() => {
        const totalPesos = filteredData.reduce((sum, item) => sum + getImporte(item), 0);
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
                return getImporte(item) > 0;
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
        const grouped = new Map<string, { obra: string; importe: number; registros: number }>();

        filteredData.forEach((item) => {
            const obra = item.obra || 'Sin obra';
            const current = grouped.get(obra) || { obra, importe: 0, registros: 0 };
            current.importe += getImporte(item);
            current.registros += 1;
            grouped.set(obra, current);
        });

        return Array.from(grouped.values())
            .sort((a, b) => b.importe - a.importe)
            .slice(0, 8);
    }, [filteredData]);

    const estadosChartData = useMemo(() => {
        const grouped = new Map<string, { estado: string; cantidad: number; importe: number }>();

        filteredData.forEach((item) => {
            const estado = getEstadoVisual(item, selectedReport, selectedInfo.label);
            const current = grouped.get(estado) || { estado, cantidad: 0, importe: 0 };
            current.cantidad += 1;
            current.importe += getImporte(item);
            grouped.set(estado, current);
        });

        return Array.from(grouped.values()).sort((a, b) => b.cantidad - a.cantidad);
    }, [filteredData, selectedInfo.label, selectedReport]);

    const timelineData = useMemo(() => {
        const grouped = new Map<string, { periodo: string; label: string; importe: number; registros: number }>();

        filteredData.forEach((item) => {
            const date = getRowDate(item);
            if (!date) return;

            const periodo = `${date.getFullYear()}-${String(date.getMonth() + 1).padStart(2, '0')}`;
            const label = date.toLocaleDateString('es-AR', { month: 'short', year: '2-digit' });
            const current = grouped.get(periodo) || { periodo, label, importe: 0, registros: 0 };
            current.importe += getImporte(item);
            current.registros += 1;
            grouped.set(periodo, current);
        });

        return Array.from(grouped.values())
            .sort((a, b) => a.periodo.localeCompare(b.periodo))
            .slice(-12);
    }, [filteredData]);

    const promedioPorRegistro = metricas.registros > 0 ? metricas.totalPesos / metricas.registros : 0;
    const hasActiveFilters =
        filtroTexto || estadoFiltro !== 'todos' || obraFiltro !== 'todos' || clienteFiltro !== 'todos' || fechaDesde || fechaHasta;

    const clearFilters = () => {
        setFiltroTexto('');
        setEstadoFiltro('todos');
        setObraFiltro('todos');
        setClienteFiltro('todos');
        setFechaDesde('');
        setFechaHasta('');
    };

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
                            clearFilters();
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
                    <label htmlFor="informes-obra">Obra</label>
                    <select id="informes-obra" value={obraFiltro} onChange={(e) => setObraFiltro(e.target.value)}>
                        <option value="todos">Todas</option>
                        {obrasDisponibles.map((obra) => (
                            <option key={obra} value={obra}>
                                {obra}
                            </option>
                        ))}
                    </select>
                </div>

                <div>
                    <label htmlFor="informes-cliente">Cliente</label>
                    <select
                        id="informes-cliente"
                        value={clienteFiltro}
                        onChange={(e) => setClienteFiltro(e.target.value)}
                    >
                        <option value="todos">Todos</option>
                        {clientesDisponibles.map((cliente) => (
                            <option key={cliente} value={cliente}>
                                {cliente}
                            </option>
                        ))}
                    </select>
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

                <div>
                    <label htmlFor="informes-desde">Desde</label>
                    <input
                        id="informes-desde"
                        type="date"
                        value={fechaDesde}
                        onChange={(e) => setFechaDesde(e.target.value)}
                    />
                </div>

                <div>
                    <label htmlFor="informes-hasta">Hasta</label>
                    <input
                        id="informes-hasta"
                        type="date"
                        value={fechaHasta}
                        onChange={(e) => setFechaHasta(e.target.value)}
                    />
                </div>

                <div className="informe-contexto">
                    <span>Informe seleccionado</span>
                    <strong>{selectedInfo.label}</strong>
                </div>

                <button
                    className="btn btn-secondary informes-clear-filters"
                    onClick={clearFilters}
                    disabled={!hasActiveFilters}
                    type="button"
                >
                    Limpiar filtros
                </button>
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
                    <span>Saldo / consumo m2</span>
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

            <section className="charts-grid">
                <article className="dashboard-card chart-card chart-card-wide">
                    <div className="dashboard-card-header">
                        <div>
                            <h3>Barras por obra</h3>
                            <p>Saldo o consumo en pesos por obra</p>
                        </div>
                    </div>

                    <div className="chart-container">
                        {topObras.length === 0 ? (
                            <div className="empty-state">
                                {loading ? 'Cargando datos...' : 'Sin datos para mostrar'}
                            </div>
                        ) : (
                            <ResponsiveContainer width="100%" height="100%">
                                <BarChart data={topObras} margin={{ top: 8, right: 16, left: 16, bottom: 40 }}>
                                    <CartesianGrid strokeDasharray="3 3" vertical={false} />
                                    <XAxis
                                        dataKey="obra"
                                        tickFormatter={(value) => truncateLabel(String(value), 14)}
                                        interval={0}
                                        angle={-25}
                                        textAnchor="end"
                                        height={58}
                                    />
                                    <YAxis tickFormatter={(value) => `$${formatNumberAR(Number(value), 0)}`} width={88} />
                                    <Tooltip
                                        formatter={(value) => [formatCurrencyAR(toNumber(value as number)), 'Importe']}
                                        labelFormatter={(label) => String(label)}
                                    />
                                    <Bar dataKey="importe" name="Importe" fill="#2563eb" radius={[4, 4, 0, 0]} />
                                </BarChart>
                            </ResponsiveContainer>
                        )}
                    </div>
                </article>

                <article className="dashboard-card chart-card">
                    <div className="dashboard-card-header">
                        <div>
                            <h3>Dona por estado</h3>
                            <p>Distribucion de registros</p>
                        </div>
                    </div>

                    <div className="chart-container">
                        {estadosChartData.length === 0 ? (
                            <div className="empty-state">Sin datos para mostrar</div>
                        ) : (
                            <ResponsiveContainer width="100%" height="100%">
                                <PieChart>
                                    <Pie
                                        data={estadosChartData}
                                        dataKey="cantidad"
                                        nameKey="estado"
                                        innerRadius="58%"
                                        outerRadius="82%"
                                        paddingAngle={3}
                                    >
                                        {estadosChartData.map((entry, index) => (
                                            <Cell
                                                key={entry.estado}
                                                fill={chartColors[index % chartColors.length]}
                                            />
                                        ))}
                                    </Pie>
                                    <Tooltip
                                        formatter={(value, _name, props) => [
                                            `${value} registros (${formatCurrencyAR(toNumber(props.payload?.importe))})`,
                                            props.payload?.estado,
                                        ]}
                                    />
                                    <Legend verticalAlign="bottom" height={44} />
                                </PieChart>
                            </ResponsiveContainer>
                        )}
                    </div>
                </article>
            </section>

            <section className="informes-layout">
                <article className="dashboard-card chart-card">
                    <div className="dashboard-card-header">
                        <div>
                            <h3>Linea temporal</h3>
                            <p>Evolucion mensual del importe filtrado</p>
                        </div>
                    </div>

                    <div className="chart-container chart-container-compact">
                        {timelineData.length === 0 ? (
                            <div className="empty-state">Sin fechas para graficar</div>
                        ) : (
                            <ResponsiveContainer width="100%" height="100%">
                                <LineChart data={timelineData} margin={{ top: 8, right: 16, left: 16, bottom: 8 }}>
                                    <CartesianGrid strokeDasharray="3 3" vertical={false} />
                                    <XAxis dataKey="label" />
                                    <YAxis tickFormatter={(value) => `$${formatNumberAR(Number(value), 0)}`} width={88} />
                                    <Tooltip
                                        formatter={(value) => [formatCurrencyAR(toNumber(value as number)), 'Importe']}
                                        labelFormatter={(label) => String(label)}
                                    />
                                    <Line
                                        type="monotone"
                                        dataKey="importe"
                                        name="Importe"
                                        stroke="#16a34a"
                                        strokeWidth={2}
                                        dot={{ r: 3 }}
                                        activeDot={{ r: 5 }}
                                    />
                                </LineChart>
                            </ResponsiveContainer>
                        )}
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
                            <span>Filtros aplicados</span>
                            <strong>{hasActiveFilters ? 'Si' : 'No'}</strong>
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
                        <h3>Tabla ejecutiva</h3>
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
                                <th>m2</th>
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
                                        <span className="status-pill">
                                            {getEstadoVisual(item, selectedReport, selectedInfo.label)}
                                        </span>
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
