import React, { useState, useEffect } from 'react';
import apiClient from '../api/client';
import { PrecioReferencia } from '../types';

interface Props {
    acopioId: number;
    onClose: () => void;
    onSave: (data: PrecioReferencia) => void;
}

const PreciosReferenciaModal: React.FC<Props> = ({ acopioId, onClose, onSave }) => {
    const [formData, setFormData] = useState<PrecioReferencia>({
        acopio_id: acopioId,
        vidrio_exterior: 0,
        vidrio_interior: 0,
        camara_estructural: 0,
        pulido: 0,
        fason_templado_exterior: 0,
        pegado_bastidor: 0,
        camara_normal: 0,
        opacificado_perimetral: 0,
        opacificado_total: 0,
        camara_offset: 0
    });
    const [loading, setLoading] = useState(true);
    const [saving, setSaving] = useState(false);
    const [error, setError] = useState<string | null>(null);

    useEffect(() => {
        const fetchPrecios = async () => {
            try {
                const response = await apiClient.get(`/acopios/${acopioId}/precios-referencia`);
                if (response.data) {
                    setFormData(response.data);
                }
            } catch (err) {
                console.error('Error fetching reference prices:', err);
            } finally {
                setLoading(false);
            }
        };
        fetchPrecios();
    }, [acopioId]);

    const handleChange = (e: React.ChangeEvent<HTMLInputElement>) => {
        const { name, value } = e.target;
        setFormData(prev => ({
            ...prev,
            [name]: parseFloat(value) || 0
        }));
    };

    const handleSubmit = async (e: React.FormEvent) => {
        e.preventDefault();
        setSaving(true);
        setError(null);
        try {
            const response = await apiClient.post(`/acopios/${acopioId}/precios-referencia`, formData);
            onSave(response.data);
            onClose();
        } catch (err: any) {
            setError(err.response?.data?.detail || 'Error al guardar los precios');
        } finally {
            setSaving(false);
        }
    };

    if (loading) return null;

    return (
        <div className="modal-overlay">
            <div className="modal-content" style={{ maxWidth: '600px' }}>
                <div className="modal-header">
                    <h3>Precios de Referencia</h3>
                    <button className="close-btn" onClick={onClose}>&times;</button>
                </div>
                <form onSubmit={handleSubmit}>
                    <div className="modal-body">
                        {error && <div className="error-message">{error}</div>}
                        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '1rem' }}>
                            <div className="form-group">
                                <label>Vidrio Exterior</label>
                                <input type="number" name="vidrio_exterior" value={formData.vidrio_exterior} onChange={handleChange} step="0.01" />
                            </div>
                            <div className="form-group">
                                <label>Vidrio Interior</label>
                                <input type="number" name="vidrio_interior" value={formData.vidrio_interior} onChange={handleChange} step="0.01" />
                            </div>
                            <div className="form-group">
                                <label>Cámara Estructural</label>
                                <input type="number" name="camara_estructural" value={formData.camara_estructural} onChange={handleChange} step="0.01" />
                            </div>
                            <div className="form-group">
                                <label>Pulido</label>
                                <input type="number" name="pulido" value={formData.pulido} onChange={handleChange} step="0.01" />
                            </div>
                            <div className="form-group">
                                <label>Fasón Templado Exterior</label>
                                <input type="number" name="fason_templado_exterior" value={formData.fason_templado_exterior} onChange={handleChange} step="0.01" />
                            </div>
                            <div className="form-group">
                                <label>Pegado a Bastidor</label>
                                <input type="number" name="pegado_bastidor" value={formData.pegado_bastidor} onChange={handleChange} step="0.01" />
                            </div>
                            <div className="form-group">
                                <label>Cámara Normal</label>
                                <input type="number" name="camara_normal" value={formData.camara_normal} onChange={handleChange} step="0.01" />
                            </div>
                            <div className="form-group">
                                <label>Opacificado Perimetral</label>
                                <input type="number" name="opacificado_perimetral" value={formData.opacificado_perimetral} onChange={handleChange} step="0.01" />
                            </div>
                            <div className="form-group">
                                <label>Opacificado Total</label>
                                <input type="number" name="opacificado_total" value={formData.opacificado_total} onChange={handleChange} step="0.01" />
                            </div>
                            <div className="form-group">
                                <label>Cámara Offset</label>
                                <input type="number" name="camara_offset" value={formData.camara_offset} onChange={handleChange} step="0.01" />
                            </div>
                        </div>
                    </div>
                    <div className="modal-footer">
                        <button type="button" className="btn btn-secondary" onClick={onClose}>Cancelar</button>
                        <button type="submit" className="btn btn-primary" disabled={saving}>
                            {saving ? 'Guardando...' : 'Guardar'}
                        </button>
                    </div>
                </form>
            </div>
            <style>{`
                .modal-overlay {
                    position: fixed;
                    top: 0;
                    left: 0;
                    right: 0;
                    bottom: 0;
                    background: rgba(0,0,0,0.5);
                    display: flex;
                    align-items: center;
                    justify-content: center;
                    z-index: 1000;
                }
                .modal-content {
                    background: white;
                    padding: 0;
                    border-radius: 8px;
                    width: 90%;
                    box-shadow: 0 4px 12px rgba(0,0,0,0.15);
                }
                .modal-header {
                    padding: 1rem;
                    border-bottom: 1px solid #eee;
                    display: flex;
                    justify-content: space-between;
                    align-items: center;
                }
                .modal-header h3 { margin: 0; }
                .close-btn {
                    background: none;
                    border: none;
                    font-size: 1.5rem;
                    cursor: pointer;
                }
                .modal-body {
                    padding: 1rem;
                    max-height: 70vh;
                    overflow-y: auto;
                }
                .modal-footer {
                    padding: 1rem;
                    border-top: 1px solid #eee;
                    display: flex;
                    justify-content: flex-end;
                    gap: 0.5rem;
                }
                .form-group {
                    margin-bottom: 1rem;
                }
                .form-group label {
                    display: block;
                    margin-bottom: 0.3rem;
                    font-weight: 500;
                    font-size: 0.9rem;
                }
                .form-group input {
                    width: 100%;
                    padding: 0.5rem;
                    border: 1px solid #ccc;
                    border-radius: 4px;
                }
                .error-message {
                    color: #721c24;
                    background: #f8d7da;
                    padding: 0.5rem;
                    border-radius: 4px;
                    margin-bottom: 1rem;
                }
            `}</style>
        </div>
    );
};

export default PreciosReferenciaModal;
