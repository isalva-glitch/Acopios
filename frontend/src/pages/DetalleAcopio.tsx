import { useState, useEffect } from 'react';
import { useParams } from 'react-router-dom';
import apiClient from '../api/client';

function DetalleAcopio() {
    const { id } = useParams<{ id: string }>();
    const [acopio, setAcopio] = useState<any>(null);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState<string | null>(null);

    useEffect(() => {
        loadAcopio();
    }, [id]);

    const loadAcopio = async () => {
        setLoading(true);
        setError(null);

        try {
            const response = await apiClient.get(`/acopios/${id}`);
            setAcopio(response.data);
        } catch (err: any) {
            setError(err.response?.data?.detail || 'Error al cargar el acopio');
        } finally {
            setLoading(false);
        }
    };

    if (loading) {
        return <div className="loading">Cargando detalle...</div>;
    }

    if (error || !acopio) {
        return <div className="error">{error || 'Acopio no encontrado'}</div>;
    }

    return (
        <div className="detalle-acopio">
            <h2>Detalle de Acopio #{acopio.numero}</h2>

            <div className="form-section">
                <h3>Información General</h3>
                <div style={{ display: 'grid', gridTemplateColumns: 'repeat(2, 1fr)', gap: '1rem' }}>
                    <div>
                        <strong>Cliente:</strong> {acopio.obra?.cliente?.nombre || `SPF ID: ${acopio.cliente_id}`}<br />
                        <strong>Obra:</strong> {acopio.obra?.nombre || 'Presupuesto Externo (SPF)'}<br />
                        <strong>Fecha Alta:</strong> {new Date(acopio.fecha_alta).toLocaleDateString()}
                    </div>
                    <div>
                        <strong>Estado:</strong> {acopio.estado}<br />
                    </div>
                </div>
            </div>

            <div className="form-section">
                <h3>Totales y Saldos</h3>
                <div className="table">
                    <table>
                        <thead>
                            <tr>
                                <th></th>
                                <th>Total Contratado</th>
                                <th>Saldo Disponible</th>
                            </tr>
                        </thead>
                        <tbody>
                            <tr>
                                <td><strong>Cantidad</strong></td>
                                <td>{acopio.totals.unidades}</td>
                                <td>{acopio.saldos.unidades}</td>
                            </tr>
                            <tr>
                                <td><strong>m²</strong></td>
                                <td>{acopio.totals.m2.toFixed(2)}</td>
                                <td>{acopio.saldos.m2.toFixed(2)}</td>
                            </tr>
                            <tr>
                                <td><strong>ml</strong></td>
                                <td>{acopio.totals.ml.toFixed(2)}</td>
                                <td>{acopio.saldos.ml.toFixed(2)}</td>
                            </tr>
                            <tr>
                                <td><strong>Pesos</strong></td>
                                <td>${acopio.totals.pesos.toFixed(2)}</td>
                                <td>${acopio.saldos.pesos.toFixed(2)}</td>
                            </tr>
                        </tbody>
                    </table>
                </div>
            </div>

            <div className="form-section">
                <h3>Total Items ({acopio.items.length})</h3>
                {acopio.items.map((item: any, idx: number) => (
                    <div key={item.id} style={{ marginBottom: '1.5rem', padding: '1rem', backgroundColor: '#f8f9fa', borderRadius: '4px' }}>
                        <h4>Item Nº {idx + 1}</h4>
                        <p>
                            <strong>Material:</strong> {item.descripcion}
                        </p>
                        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: '1rem', marginTop: '0.5rem' }}>
                            <div>
                                <strong>m²:</strong> {item.totals.m2.toFixed(2)} (saldo: {item.saldos.m2.toFixed(2)})
                            </div>
                            <div>
                                <strong>ml:</strong> {item.totals.ml.toFixed(2)} (saldo: {item.saldos.ml.toFixed(2)})
                            </div>
                            <div>
                                <strong>$:</strong> {item.totals.pesos.toFixed(2)} (saldo: {item.saldos.pesos.toFixed(2)})
                            </div>
                        </div>

                        {item.panos.length > 0 && (
                            <details style={{ marginTop: '0.5rem' }}>
                                <summary style={{ cursor: 'pointer', fontWeight: 'bold' }}>
                                    Paños ({item.panos.length})
                                </summary>
                                <div className="table" style={{ marginTop: '0.5rem' }}>
                                    <table>
                                        <thead>
                                            <tr>
                                                <th>Cantidad</th>
                                                <th>Ancho</th>
                                                <th>Alto</th>
                                                <th>m²</th>
                                                <th>ml</th>
                                            </tr>
                                        </thead>
                                        <tbody>
                                            {item.panos.map((pano: any) => (
                                                <tr key={pano.id}>
                                                    <td>{pano.cantidad}</td>
                                                    <td>{pano.ancho}</td>
                                                    <td>{pano.alto}</td>
                                                    <td>{pano.superficie_m2}</td>
                                                    <td>{pano.perimetro_ml}</td>
                                                </tr>
                                            ))}
                                        </tbody>
                                    </table>
                                </div>
                            </details>
                        )}
                    </div>
                ))}
            </div>

            {acopio.imputaciones.length > 0 && (
                <div className="form-section">
                    <h3>Imputaciones ({acopio.imputaciones.length})</h3>
                    <div className="table">
                        <table>
                            <thead>
                                <tr>
                                    <th>Pedido</th>
                                    <th>m²</th>
                                    <th>ml</th>
                                    <th>$</th>
                                    <th>Excedente</th>
                                </tr>
                            </thead>
                            <tbody>
                                {acopio.imputaciones.map((imp: any) => (
                                    <tr key={imp.id}>
                                        <td>{imp.pedido_numero}</td>
                                        <td>{imp.cantidad_m2}</td>
                                        <td>{imp.cantidad_ml}</td>
                                        <td>${imp.cantidad_pesos}</td>
                                        <td>{imp.es_excedente ? '⚠️ Sí' : 'No'}</td>
                                    </tr>
                                ))}
                            </tbody>
                        </table>
                    </div>
                </div>
            )}
        </div>
    );
}

export default DetalleAcopio;
