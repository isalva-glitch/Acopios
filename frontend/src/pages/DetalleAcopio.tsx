import { useState, useEffect } from 'react';
import { useParams } from 'react-router-dom';
import apiClient from '../api/client';

function DetalleAcopio() {
    const { id } = useParams<{ id: string }>();
    const [acopio, setAcopio] = useState<any>(null);
    const [avanceComercial, setAvanceComercial] = useState<any>(null);
    const [loading, setLoading] = useState(true);
    const [loadingAvance, setLoadingAvance] = useState(false);
    const [error, setError] = useState<string | null>(null);

    useEffect(() => {
        loadAcopio();
    }, [id]);

    const loadAcopio = async () => {
        setLoading(true);
        setError(null);

        try {
            const response = await apiClient.get(`/acopios/${id}`);
            const data = response.data;
            setAcopio(data);
            
            if (data.v_presupuesto_id) {
                loadAvanceComercial(id!);
            }
        } catch (err: any) {
            setError(err.response?.data?.detail || 'Error al cargar el acopio');
        } finally {
            setLoading(false);
        }
    };

    const loadAvanceComercial = async (acopioId: string) => {
        setLoadingAvance(true);
        try {
            const response = await apiClient.get(`/acopios/${acopioId}/avance-comercial`);
            setAvanceComercial(response.data);
        } catch (err) {
            console.error('Error loading commercial advancement:', err);
        } finally {
            setLoadingAvance(false);
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
            
            {avanceComercial && (
                <div className="form-section">
                    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '1rem' }}>
                        <h3>Avance Comercial y Documental (SPF)</h3>
                        {loadingAvance && <span style={{ fontSize: '0.8rem', color: '#666' }}>Actualizando...</span>}
                    </div>
                    
                    {avanceComercial.pedidos.map((p: any) => (
                        <div key={p.id} style={{ border: '1px solid #eee', borderRadius: '8px', padding: '1rem', marginBottom: '1rem', backgroundColor: '#fff' }}>
                            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', borderBottom: '1px solid #f0f0f0', paddingBottom: '0.5rem', marginBottom: '0.8rem' }}>
                                <h4 style={{ margin: 0 }}>Pedido #{p.nro_pedido}</h4>
                                <div>
                                    <span style={{ backgroundColor: '#e9ecef', padding: '0.2rem 0.5rem', borderRadius: '4px', fontSize: '0.85rem', marginRight: '0.5rem' }}>
                                        {p.estado}
                                    </span>
                                    <span style={{ fontWeight: 'bold', fontSize: '0.9rem' }}>{p.cliente}</span>
                                </div>
                            </div>
                            
                            <div className="table">
                                <table style={{ fontSize: '0.9rem' }}>
                                    <thead>
                                        <tr>
                                            <th>Item / Complemento</th>
                                            <th>Cant.</th>
                                            <th>Unitario</th>
                                            <th>Facturado</th>
                                            <th>Remitido</th>
                                            <th>Comprobantes</th>
                                        </tr>
                                    </thead>
                                    <tbody>
                                        {p.items.map((it: any, iidx: number) => (
                                            <tr key={iidx}>
                                                <td>
                                                    <div style={{ fontWeight: 'bold' }}>{it.descripcion}</div>
                                                    <div style={{ fontSize: '0.75rem', color: '#666' }}>{it.tipo} {it.precio_m2 > 0 ? `| $${it.precio_m2.toFixed(2)}/m²` : ''}</div>
                                                </td>
                                                <td>{it.cantidad}</td>
                                                <td>${it.precio_unitario.toFixed(2)}</td>
                                                <td>
                                                    <div style={{ width: '80px', height: '10px', backgroundColor: '#e9ecef', borderRadius: '5px', overflow: 'hidden', position: 'relative' }}>
                                                        <div style={{ width: `${it.avance_facturado}%`, height: '100%', backgroundColor: it.avance_facturado >= 100 ? '#27ae60' : '#3498db' }}></div>
                                                    </div>
                                                    <span style={{ fontSize: '0.75rem' }}>{it.avance_facturado.toFixed(0)}%</span>
                                                </td>
                                                <td>
                                                    <div style={{ width: '80px', height: '10px', backgroundColor: '#e9ecef', borderRadius: '5px', overflow: 'hidden', position: 'relative' }}>
                                                        <div style={{ width: `${it.avance_remitido}%`, height: '100%', backgroundColor: it.avance_remitido >= 100 ? '#27ae60' : '#f39c12' }}></div>
                                                    </div>
                                                    <span style={{ fontSize: '0.75rem' }}>{it.avance_remitido.toFixed(0)}%</span>
                                                </td>
                                                <td>
                                                    <div style={{ display: 'flex', flexDirection: 'column', gap: '2px' }}>
                                                        {it.comprobantes.map((c: any, cidx: number) => (
                                                            <div key={cidx} style={{ fontSize: '0.75rem', whiteSpace: 'nowrap' }}>
                                                                <span style={{ 
                                                                    backgroundColor: c.empresa === 'Fontela' ? '#d1ecf1' : c.empresa === 'Viviana' ? '#fff3cd' : '#e2e3e5',
                                                                    padding: '2px 4px',
                                                                    borderRadius: '3px',
                                                                    marginRight: '4px',
                                                                    fontSize: '0.7rem',
                                                                    fontWeight: 'bold'
                                                                }}>
                                                                    {c.empresa}
                                                                </span>
                                                                {c.nro_factura && `F:${c.nro_factura}`} {c.nro_remito && `R:${c.nro_remito}`}
                                                            </div>
                                                        ))}
                                                        {it.comprobantes.length === 0 && <span style={{ color: '#999', fontSize: '0.75rem' }}>Sin comprobantes</span>}
                                                    </div>
                                                </td>
                                            </tr>
                                        ))}
                                    </tbody>
                                </table>
                            </div>
                        </div>
                    ))}
                </div>
            )}

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
