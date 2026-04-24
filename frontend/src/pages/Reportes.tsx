import { useState } from 'react';
import apiClient from '../api/client';

type ReportType = 'acopios-activos' | 'excedentes' | 'vencimientos-precio';

function Reportes() {
    const [selectedReport, setSelectedReport] = useState<ReportType>('acopios-activos');
    const [data, setData] = useState<any[]>([]);
    const [loading, setLoading] = useState(false);
    const [error, setError] = useState<string | null>(null);

    const loadReport = async (format: 'json' | 'csv' = 'json') => {
        setLoading(true);
        setError(null);

        try {
            const endpoint = `/reportes/${selectedReport}`;
            const params = format === 'csv' ? { format: 'csv' } : {};

            if (format === 'csv') {
                // Download CSV
                const response = await apiClient.get(endpoint, {
                    params,
                    responseType: 'blob',
                });

                const url = window.URL.createObjectURL(new Blob([response.data]));
                const link = document.createElement('a');
                link.href = url;
                link.setAttribute('download', `${selectedReport}.csv`);
                document.body.appendChild(link);
                link.click();
                link.remove();
            } else {
                // Load JSON
                const response = await apiClient.get(endpoint, { params });

                // Extract data from response
                if (selectedReport === 'acopios-activos') {
                    setData(response.data.acopios || []);
                } else if (selectedReport === 'excedentes') {
                    setData(response.data.excedentes || []);
                } else if (selectedReport === 'vencimientos-precio') {
                    setData(response.data.vencimientos || []);
                }
            }
        } catch (err: any) {
            setError(err.response?.data?.detail || 'Error al cargar reporte');
        } finally {
            setLoading(false);
        }
    };

    return (
        <div className="reportes">
            <h2>Reportes</h2>

            <div className="form-section">
                <div className="form-group">
                    <label>Seleccione el tipo de reporte:</label>
                    <select
                        value={selectedReport}
                        onChange={(e) => {
                            setSelectedReport(e.target.value as ReportType);
                            setData([]);
                        }}
                    >
                        <option value="acopios-activos">Acopios Activos</option>
                        <option value="excedentes">Excedentes</option>
                        <option value="vencimientos-precio">Vencimientos de Precio</option>
                    </select>
                </div>

                <div style={{ display: 'flex', gap: '1rem' }}>
                    <button
                        className="btn btn-primary"
                        onClick={() => loadReport('json')}
                        disabled={loading}
                    >
                        {loading ? 'Cargando...' : 'Ver Reporte'}
                    </button>
                    <button
                        className="btn btn-secondary"
                        onClick={() => loadReport('csv')}
                        disabled={loading}
                    >
                        Exportar CSV
                    </button>
                </div>
            </div>

            {error && <div className="error">{error}</div>}

            {data.length > 0 && (
                <div className="form-section">
                    <h3>Resultados ({data.length} registros)</h3>

                    {selectedReport === 'acopios-activos' && (
                        <div className="table">
                            <table>
                                <thead>
                                    <tr>
                                        <th>Número</th>
                                        <th>Obra</th>
                                        <th>Cliente</th>
                                        <th>Estado</th>
                                        <th>Saldo m²</th>
                                        <th>Saldo ml</th>
                                        <th>Saldo $</th>
                                    </tr>
                                </thead>
                                <tbody>
                                    {data.map((item, idx) => (
                                        <tr key={idx}>
                                            <td>{item.numero}</td>
                                            <td>{item.obra}</td>
                                            <td>{item.cliente}</td>
                                            <td>{item.estado}</td>
                                            <td>{Number(item.saldo_m2).toFixed(2)}</td>
                                            <td>{Number(item.saldo_ml).toFixed(2)}</td>
                                            <td>${Number(item.saldo_pesos).toFixed(2)}</td>
                                        </tr>
                                    ))}
                                </tbody>
                            </table>
                        </div>
                    )}

                    {selectedReport === 'excedentes' && (
                        <div className="table">
                            <table>
                                <thead>
                                    <tr>
                                        <th>Pedido</th>
                                        <th>Acopio</th>
                                        <th>Obra</th>
                                        <th>m²</th>
                                        <th>ml</th>
                                        <th>$</th>
                                        <th>Fecha</th>
                                    </tr>
                                </thead>
                                <tbody>
                                    {data.map((item, idx) => (
                                        <tr key={idx}>
                                            <td>{item.pedido_numero}</td>
                                            <td>{item.acopio_numero}</td>
                                            <td>{item.obra}</td>
                                            <td>{Number(item.cantidad_m2).toFixed(2)}</td>
                                            <td>{Number(item.cantidad_ml).toFixed(2)}</td>
                                            <td>${Number(item.cantidad_pesos).toFixed(2)}</td>
                                            <td>{new Date(item.fecha).toLocaleDateString()}</td>
                                        </tr>
                                    ))}
                                </tbody>
                            </table>
                        </div>
                    )}

                    {selectedReport === 'vencimientos-precio' && (
                        <div className="table">
                            <table>
                                <thead>
                                    <tr>
                                        <th>Número</th>
                                        <th>Obra</th>
                                        <th>Cliente</th>
                                        <th>Fecha Vencimiento</th>
                                        <th>Días Restantes</th>
                                        <th>Saldo $</th>
                                    </tr>
                                </thead>
                                <tbody>
                                    {data.map((item, idx) => (
                                        <tr key={idx}>
                                            <td>{item.numero}</td>
                                            <td>{item.obra}</td>
                                            <td>{item.cliente}</td>
                                            <td>{new Date(item.fecha_vencimiento).toLocaleDateString()}</td>
                                            <td>{item.dias_restantes}</td>
                                            <td>${Number(item.saldo_pesos).toFixed(2)}</td>
                                        </tr>
                                    ))}
                                </tbody>
                            </table>
                        </div>
                    )}
                </div>
            )}
        </div>
    );
}

export default Reportes;
