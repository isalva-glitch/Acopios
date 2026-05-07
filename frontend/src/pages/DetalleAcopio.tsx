import { useState, useEffect } from 'react';
import { useParams } from 'react-router-dom';
import apiClient from '../api/client';
import PreciosReferenciaModal from '../components/PreciosReferenciaModal';
import {
    PRECIO_REFERENCIA_PROCESOS,
    type PrecioReferenciaProcesoKey
} from '../constants/preciosReferencia';

function DetalleAcopio() {
    const { id } = useParams<{ id: string }>();
    const [acopio, setAcopio] = useState<any>(null);
    const [avanceComercial, setAvanceComercial] = useState<any>(null);
    const [loading, setLoading] = useState(true);
    const [loadingAvance, setLoadingAvance] = useState(false);
    const [error, setError] = useState<string | null>(null);

    // Imputation states
    const [showImputer, setShowImputer] = useState(false);
    const [nroPedidoBusqueda, setNroPedidoBusqueda] = useState('');
    const [imputationPreview, setImputationPreview] = useState<any>(null);
    const [imputationLoading, setImputationLoading] = useState(false);
    const [imputationError, setImputationError] = useState<string | null>(null);
    const [imputationSuccess, setImputationSuccess] = useState(false);
    const [anulandoId, setAnulandoId] = useState<number | null>(null);
    const [anulacionError, setAnulacionError] = useState<string | null>(null);
    const [showPreciosModal, setShowPreciosModal] = useState(false);
    const [itemProcessSaving, setItemProcessSaving] = useState<Record<string, boolean>>({});
    const [itemProcessError, setItemProcessError] = useState<string | null>(null);

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

    const [crossBudgetWarning, setCrossBudgetWarning] = useState<string | null>(null);

    const handleAnularImputacion = async (imputacionId: number, pedidoNumero: string) => {
        if (!window.confirm(`¿Confirma anular la imputación del pedido ${pedidoNumero}?\n\nEsta acción restaurará los saldos del acopio.`)) return;

        setAnulandoId(imputacionId);
        setAnulacionError(null);
        try {
            await apiClient.delete(`/imputaciones/${imputacionId}`);
            await loadAcopio(); // Reload to show updated saldos
        } catch (err: any) {
            setAnulacionError(err.response?.data?.detail || 'Error al anular la imputación');
        } finally {
            setAnulandoId(null);
        }
    };

    const handleSearchPedido = async () => {
        if (!nroPedidoBusqueda.trim()) return;
        setImputationLoading(true);
        setImputationError(null);
        setCrossBudgetWarning(null);
        setImputationSuccess(false);

        try {
            const response = await apiClient.get(`/integrations/spf/pedidos/${nroPedidoBusqueda}/imputation-preview`);
            const data = response.data;
            
            const acopioBudgetId = acopio.v_presupuesto_id || acopio.numero;
            const pedidoBudgetId = data.spf_pedido.v_presupuesto_id;
            
            const norm = (s: string) => s?.replace(/^0+/, '') || '';
            
            if (norm(pedidoBudgetId) !== norm(acopioBudgetId)) {
                setCrossBudgetWarning(`Atención: El pedido ${nroPedidoBusqueda} pertenece al presupuesto ${pedidoBudgetId}, pero lo está imputando a este acopio (${acopioBudgetId}).`);
            }
            
            setImputationPreview(data);
        } catch (err: any) {
            setImputationError(err.response?.data?.detail || 'No se encontró el pedido en SPF.');
            setImputationPreview(null);
        } finally {
            setImputationLoading(false);
        }
    };

    const handleConfirmImputation = async () => {
        if (!imputationPreview) return;
        setImputationLoading(true);
        try {
            await apiClient.post('/pedidos/from-spf', {
                nro_pedido: nroPedidoBusqueda,
                acopio_id: Number(id)
            });
            setImputationSuccess(true);
            setImputationPreview(null);
            setNroPedidoBusqueda('');
            setCrossBudgetWarning(null);
            setShowImputer(false);
            loadAcopio();
        } catch (err: any) {
            setImputationError(err.response?.data?.detail || 'Error al confirmar la imputación');
        } finally {
            setImputationLoading(false);
        }
    };

    const updateItemProcesoLocal = (
        itemId: number,
        processKey: PrecioReferenciaProcesoKey,
        checked: boolean
    ) => {
        setAcopio((prev: any) => {
            if (!prev) return prev;

            return {
                ...prev,
                items: prev.items.map((item: any) => (
                    item.id === itemId
                        ? {
                            ...item,
                            procesos: {
                                ...(item.procesos || {}),
                                [processKey]: checked
                            }
                        }
                        : item
                ))
            };
        });
    };

    const handleToggleItemProceso = async (
        itemId: number,
        processKey: PrecioReferenciaProcesoKey,
        checked: boolean
    ) => {
        const savingKey = `${itemId}:${processKey}`;
        const item = acopio.items.find((current: any) => current.id === itemId);
        const previousValue = Boolean(item?.procesos?.[processKey]);

        setItemProcessError(null);
        setItemProcessSaving(prev => ({ ...prev, [savingKey]: true }));
        updateItemProcesoLocal(itemId, processKey, checked);

        try {
            const response = await apiClient.patch(
                `/acopios/${id}/items/${itemId}/procesos`,
                { [processKey]: checked }
            );

            setAcopio((prev: any) => {
                if (!prev) return prev;

                return {
                    ...prev,
                    items: prev.items.map((current: any) => (
                        current.id === itemId
                            ? { ...current, procesos: response.data.procesos }
                            : current
                    ))
                };
            });
        } catch (err: any) {
            updateItemProcesoLocal(itemId, processKey, previousValue);
            setItemProcessError(err.response?.data?.detail || 'No se pudo guardar el proceso del item.');
        } finally {
            setItemProcessSaving(prev => {
                const next = { ...prev };
                delete next[savingKey];
                return next;
            });
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
            <h2>Acopio - Presupuesto SPF #{acopio.v_presupuesto_id || acopio.numero}</h2>

            <div className="form-section detalle-general-section">
                <div className="detalle-general-header">
                    <h3>Información General</h3>
                </div>
                <div className="detalle-general-grid">
                    <div className="detalle-general-data">
                        <strong>Cliente:</strong> {avanceComercial?.cliente || acopio.obra?.cliente?.nombre || `SPF ID: ${acopio.cliente_id}`}<br />
                        <strong>Obra:</strong> {avanceComercial?.obra || acopio.obra?.nombre || `Presupuesto: ${acopio.v_presupuesto_id}`}<br />
                        <strong>Fecha Alta:</strong> {new Date(acopio.fecha_alta).toLocaleDateString()}<br />
                        <strong>Estado:</strong> {acopio.estado}
                    </div>
                    <div className="detalle-actions">
                        {acopio.estado === 'CONSUMIDO' ? (
                            <span className="material-consumido">
                                ✓ Material Consumido
                            </span>
                        ) : (
                            <button 
                                className="btn btn-primary" 
                                onClick={() => setShowImputer(!showImputer)}
                            >
                                {showImputer ? 'Cancelar Imputación' : 'Imputar Nuevo Pedido'}
                            </button>
                        )}
                        <button 
                            className="btn btn-secondary" 
                            onClick={() => setShowPreciosModal(true)}
                        >
                            Precios de referencia
                        </button>
                    </div>
                </div>
            </div>

            {showImputer && acopio.estado !== 'CONSUMIDO' && (
                <div className="form-section" style={{ border: '2px solid #3498db', backgroundColor: '#ebf5fb' }}>
                    <h3>Nueva Imputación (Descarga de Material)</h3>
                    
                    {!imputationPreview && !imputationSuccess && (
                        <div className="form-group" style={{ display: 'flex', gap: '0.5rem' }}>
                            <input 
                                type="text"
                                value={nroPedidoBusqueda}
                                onChange={(e) => setNroPedidoBusqueda(e.target.value)}
                                placeholder="Ingrese Nro Pedido SPF o Nro OC..."
                                style={{ flex: 1, padding: '10px' }}
                                onKeyPress={(e) => e.key === 'Enter' && handleSearchPedido()}
                            />
                            <button className="btn btn-primary" onClick={handleSearchPedido} disabled={imputationLoading}>
                                {imputationLoading ? 'Buscando...' : 'Buscar'}
                            </button>
                        </div>
                    )}

                    {imputationError && (
                        <div style={{ color: '#721c24', backgroundColor: '#f8d7da', padding: '1rem', borderRadius: '4px', marginBottom: '1rem' }}>
                            {imputationError}
                        </div>
                    )}

                    {crossBudgetWarning && (
                        <div style={{ color: '#856404', backgroundColor: '#fff3cd', padding: '1rem', borderRadius: '4px', marginBottom: '1rem', border: '1px solid #ffeeba' }}>
                            {crossBudgetWarning}
                        </div>
                    )}

                    {imputationPreview && (
                        <div style={{ backgroundColor: '#fff', padding: '1rem', borderRadius: '8px', border: '1px solid #3498db' }}>
                            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '1rem' }}>
                                <div>
                                    <p><strong>Pedido SPF:</strong> {imputationPreview.spf_pedido.nro_pedido}</p>
                                    <p><strong>Referencia (OC):</strong> {imputationPreview.spf_pedido.nrooc || 'S/D'}</p>
                                    <p><strong>Empresa:</strong> {imputationPreview.spf_pedido.empresa}</p>
                                </div>
                                <div>
                                    <p><strong>Cant. Paños:</strong> {imputationPreview.spf_pedido.totals.unidades}</p>
                                    <p><strong>Superficie:</strong> {imputationPreview.spf_pedido.totals.m2.toFixed(2)} m²</p>
                                    <p><strong>Importe:</strong> ${imputationPreview.spf_pedido.totals.pesos.toLocaleString()}</p>
                                </div>
                            </div>
                            <div style={{ marginTop: '1rem', display: 'flex', gap: '1rem' }}>
                                <button className="btn btn-success" onClick={handleConfirmImputation} disabled={imputationLoading} style={{ flex: 1 }}>
                                    {imputationLoading ? 'Confirmando...' : 'Confirmar e Imputar'}
                                </button>
                                <button className="btn btn-secondary" onClick={() => setImputationPreview(null)}>
                                    Volver
                                </button>
                            </div>
                        </div>
                    )}
                </div>
            )}

            {imputationSuccess && (
                <div className="form-section" style={{ backgroundColor: '#d4edda', color: '#155724' }}>
                    <strong>✓ Imputación realizada con éxito.</strong> Los saldos se han actualizado.
                    <button className="btn btn-link" onClick={() => setImputationSuccess(false)}>Cerrar</button>
                </div>
            )}

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
                                <td>{Number(acopio.totals.m2).toFixed(2)}</td>
                                <td>{Number(acopio.saldos.m2).toFixed(2)}</td>
                            </tr>
                            <tr>
                                <td><strong>ml</strong></td>
                                <td>{Number(acopio.totals.ml).toFixed(2)}</td>
                                <td>{Number(acopio.saldos.ml).toFixed(2)}</td>
                            </tr>
                            <tr>
                                <td><strong>Pesos</strong></td>
                                <td>${Number(acopio.totals.pesos).toFixed(2)}</td>
                                <td>${Number(acopio.saldos.pesos).toFixed(2)}</td>
                            </tr>
                        </tbody>
                    </table>
                </div>
            </div>
            
            {avanceComercial && (
                <div className="form-section">
                    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '1rem' }}>
                        <h3>Avance Comercial y Documental</h3>
                        {loadingAvance && <span style={{ fontSize: '0.8rem', color: '#666' }}>Actualizando...</span>}
                    </div>
                    
                    <div style={{ border: '1px solid #ddd', borderRadius: '8px', padding: '1.2rem', backgroundColor: '#fff', boxShadow: '0 2px 4px rgba(0,0,0,0.05)' }}>
                        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: '1.5rem', alignItems: 'center' }}>
                            <div>
                                <div style={{ fontSize: '0.85rem', color: '#666', marginBottom: '0.3rem' }}>Total Presupuesto</div>
                                <div style={{ fontWeight: 'bold', fontSize: '1.1rem' }}>${avanceComercial.resumen.importe_total.toLocaleString()}</div>
                            </div>
                            
                            <div>
                                <div style={{ fontSize: '0.85rem', color: '#666', marginBottom: '0.3rem' }}>Avance Facturado</div>
                                <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                                    <div style={{ flex: 1, height: '12px', backgroundColor: '#e9ecef', borderRadius: '6px', overflow: 'hidden' }}>
                                        <div style={{ width: `${avanceComercial.resumen.porcentaje_facturado}%`, height: '100%', backgroundColor: '#3498db' }}></div>
                                    </div>
                                    <span style={{ fontWeight: 'bold', minWidth: '40px' }}>{avanceComercial.resumen.porcentaje_facturado.toFixed(0)}%</span>
                                </div>
                            </div>

                            <div>
                                <div style={{ fontSize: '0.85rem', color: '#666', marginBottom: '0.3rem' }}>Avance Remitido</div>
                                <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                                    <div style={{ flex: 1, height: '12px', backgroundColor: '#e9ecef', borderRadius: '6px', overflow: 'hidden' }}>
                                        <div style={{ width: `${avanceComercial.resumen.porcentaje_remitido}%`, height: '100%', backgroundColor: '#f39c12' }}></div>
                                    </div>
                                    <span style={{ fontWeight: 'bold', minWidth: '40px' }}>{avanceComercial.resumen.porcentaje_remitido.toFixed(0)}%</span>
                                </div>
                            </div>

                            <div style={{ textAlign: 'right' }}>
                                <details style={{ cursor: 'pointer' }}>
                                    <summary style={{ fontSize: '0.85rem', color: '#3498db' }}>Ver Detalle Pedidos</summary>
                                    <div style={{ marginTop: '1rem', textAlign: 'left', fontSize: '0.8rem', borderTop: '1px solid #eee', paddingTop: '0.5rem' }}>
                                        {avanceComercial.pedidos.map((p: any) => (
                                            <div key={p.id} style={{ marginBottom: '4px' }}>
                                                Pedido {p.nro_pedido}: <strong>{p.estado}</strong>
                                            </div>
                                        ))}
                                    </div>
                                </details>
                            </div>
                        </div>
                    </div>
                </div>
            )}


            <div className="form-section">
                <h3>Total Items ({acopio.items.length})</h3>
                {itemProcessError && (
                    <div className="item-process-error">
                        {itemProcessError}
                    </div>
                )}
                {acopio.items.map((item: any, idx: number) => (
                    <div key={item.id} className="acopio-item-card">
                        <div className="acopio-item-content">
                            <h4>Item Nº {idx + 1}</h4>
                            <p>
                                <strong>Material:</strong> {item.descripcion}
                            </p>
                            <div className="acopio-item-metrics">
                                <div>
                                    <strong>m²:</strong> {Number(item.totals.m2).toFixed(2)} (saldo: {Number(item.saldos.m2).toFixed(2)})
                                </div>
                                <div>
                                    <strong>ml:</strong> {Number(item.totals.ml).toFixed(2)} (saldo: {Number(item.saldos.ml).toFixed(2)})
                                </div>
                                <div>
                                    <strong>$:</strong> {Number(item.totals.pesos).toFixed(2)} (saldo: {Number(item.saldos.pesos).toFixed(2)})
                                </div>
                            </div>

                            {item.panos.length > 0 && (
                                <details style={{ marginTop: '0.5rem' }}>
                                    <summary style={{ cursor: 'pointer', fontWeight: 'bold' }}>
                                        Paños ({item.panos.reduce((acc: number, p: any) => acc + p.cantidad, 0)})
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

                            {item.adicionales && item.adicionales.length > 0 && (
                                <details style={{ marginTop: '0.5rem' }}>
                                    <summary style={{ cursor: 'pointer', fontWeight: 'bold', color: '#e67e22' }}>
                                        Adicionales / Servicios ({item.adicionales.length})
                                    </summary>
                                    <div className="table" style={{ marginTop: '0.5rem' }}>
                                        <table>
                                            <thead>
                                                <tr>
                                                    <th>Cantidad</th>
                                                    <th>Descripción</th>
                                                    <th>Unitario</th>
                                                    <th>Total</th>
                                                </tr>
                                            </thead>
                                            <tbody>
                                                {item.adicionales.map((adc: any) => (
                                                    <tr key={adc.id}>
                                                        <td>{adc.cantidad}</td>
                                                        <td>{adc.descripcion}</td>
                                                        <td>${Number(adc.precio_unitario).toFixed(2)}</td>
                                                        <td>${Number(adc.precio_total).toFixed(2)}</td>
                                                    </tr>
                                                ))}
                                            </tbody>
                                        </table>
                                    </div>
                                </details>
                            )}
                        </div>

                        <div className="item-processes-panel">
                            <div className="item-processes-title">Procesos</div>
                            <div className="item-processes-list">
                                {PRECIO_REFERENCIA_PROCESOS.map((proceso) => {
                                    const savingKey = `${item.id}:${proceso.key}`;

                                    return (
                                        <label className="item-process-check" key={proceso.key} title={proceso.label}>
                                            <input
                                                type="checkbox"
                                                checked={Boolean(item.procesos?.[proceso.key])}
                                                disabled={Boolean(itemProcessSaving[savingKey])}
                                                onChange={(event) => handleToggleItemProceso(
                                                    item.id,
                                                    proceso.key,
                                                    event.target.checked
                                                )}
                                            />
                                            <span>{proceso.shortLabel}</span>
                                        </label>
                                    );
                                })}
                            </div>
                        </div>
                    </div>
                ))}
            </div>

            {acopio.imputaciones.length > 0 && (
                <div className="form-section">
                    <h3>Pedidos de Producción / Consumos ({acopio.imputaciones.length})</h3>
                    {anulacionError && (
                        <div style={{ backgroundColor: '#f8d7da', padding: '8px', borderRadius: '4px', marginBottom: '10px', fontSize: '0.9rem', color: '#721c24' }}>
                            ⚠️ {anulacionError}
                        </div>
                    )}
                    <div className="table">
                        <table>
                            <thead>
                                <tr>
                                    <th>Pedido / OC</th>
                                    <th>m²</th>
                                    <th>ml</th>
                                    <th>$</th>
                                    <th>Excedente</th>
                                    <th>Acciones</th>
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
                                        <td>
                                            <button
                                                onClick={() => handleAnularImputacion(imp.id, imp.pedido_numero)}
                                                disabled={anulandoId === imp.id}
                                                style={{
                                                    background: 'none',
                                                    border: '1px solid #dc3545',
                                                    color: '#dc3545',
                                                    borderRadius: '4px',
                                                    padding: '2px 10px',
                                                    cursor: 'pointer',
                                                    fontSize: '0.85rem',
                                                    fontWeight: 'bold'
                                                }}
                                            >
                                                {anulandoId === imp.id ? 'Anulando...' : 'Anular'}
                                            </button>
                                        </td>
                                    </tr>
                                ))}
                            </tbody>
                        </table>
                    </div>
                </div>
            )}

            {showPreciosModal && (
                <PreciosReferenciaModal 
                    acopioId={Number(id)} 
                    onClose={() => setShowPreciosModal(false)}
                    onSave={(data) => {
                        console.log('Precios guardados:', data);
                        // Opcional: mostrar notificación de éxito
                    }}
                />
            )}
        </div>
    );
}

export default DetalleAcopio;
