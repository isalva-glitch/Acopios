import React, { useState, useEffect } from 'react';
import apiClient from '../api/client';
import { PrecioReferencia } from '../types';
import {
    PRECIO_REFERENCIA_PROCESOS,
    type PrecioReferenciaProcesoKey
} from '../constants/preciosReferencia';
import { formatDecimalInput, formatNumberAR, parseDecimalInput } from '../utils/formatters';

interface Props {
    acopioId: number;
    onClose: () => void;
    onSave: (data: PrecioReferencia) => void;
    initialPrecios?: PrecioReferencia | null;
}

type PrecioReferenciaInputValues = Record<PrecioReferenciaProcesoKey, string>;

const createDefaultPrecios = (acopioId: number): PrecioReferencia => ({
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

const createInputValues = (precios: PrecioReferencia): PrecioReferenciaInputValues =>
    PRECIO_REFERENCIA_PROCESOS.reduce((values, proceso) => {
        values[proceso.key] = formatNumberAR(precios[proceso.key], 2);
        return values;
    }, {} as PrecioReferenciaInputValues);

const PreciosReferenciaModal: React.FC<Props> = ({ acopioId, onClose, onSave, initialPrecios }) => {
    const defaultPrecios = createDefaultPrecios(acopioId);
    const [formData, setFormData] = useState<PrecioReferencia>(defaultPrecios);
    const [inputValues, setInputValues] = useState<PrecioReferenciaInputValues>(
        createInputValues(defaultPrecios)
    );
    const [loading, setLoading] = useState(true);

    useEffect(() => {
        if (initialPrecios) {
            setFormData(initialPrecios);
            setInputValues(createInputValues(initialPrecios));
            setLoading(false);
            return;
        }

        const fetchPrecios = async () => {
            try {
                const response = await apiClient.get(`/acopios/${acopioId}/precios-referencia`);
                if (response.data) {
                    setFormData(response.data);
                    setInputValues(createInputValues(response.data));
                } else {
                    const emptyPrecios = createDefaultPrecios(acopioId);
                    setFormData(emptyPrecios);
                    setInputValues(createInputValues(emptyPrecios));
                }
            } catch (err) {
                console.error('Error fetching reference prices:', err);
            } finally {
                setLoading(false);
            }
        };
        fetchPrecios();
    }, [acopioId, initialPrecios]);

    const handleChange = (e: React.ChangeEvent<HTMLInputElement>) => {
        const { name, value } = e.target;
        const precioKey = name as PrecioReferenciaProcesoKey;

        setInputValues(prev => ({
            ...prev,
            [precioKey]: value
        }));
        setFormData(prev => ({
            ...prev,
            [precioKey]: parseDecimalInput(value)
        }));
    };

    const handleFocus = (key: PrecioReferenciaProcesoKey) => {
        setInputValues(prev => ({
            ...prev,
            [key]: formatDecimalInput(formData[key])
        }));
    };

    const handleBlur = (key: PrecioReferenciaProcesoKey) => {
        setInputValues(prev => ({
            ...prev,
            [key]: formatNumberAR(formData[key], 2)
        }));
    };

    const handleSubmit = async (e: React.FormEvent) => {
        e.preventDefault();
        onSave(formData);
        onClose();
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
                        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '1rem' }}>
                            {PRECIO_REFERENCIA_PROCESOS.map((proceso) => (
                                <div className="form-group" key={proceso.key}>
                                    <label>{proceso.label}</label>
                                    <div className="currency-input-wrapper">
                                        <span>$</span>
                                        <input
                                            type="text"
                                            inputMode="decimal"
                                            name={proceso.key}
                                            value={inputValues[proceso.key]}
                                            onChange={handleChange}
                                            onFocus={() => handleFocus(proceso.key)}
                                            onBlur={() => handleBlur(proceso.key)}
                                            placeholder="0,00"
                                        />
                                    </div>
                                </div>
                            ))}
                        </div>
                    </div>
                    <div className="modal-footer">
                        <button type="button" className="btn btn-secondary" onClick={onClose}>Cancelar</button>
                        <button type="submit" className="btn btn-primary">
                            Guardar
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
                .currency-input-wrapper {
                    display: flex;
                    align-items: center;
                    border: 1px solid #ccc;
                    border-radius: 4px;
                    background: #fff;
                    overflow: hidden;
                }
                .currency-input-wrapper span {
                    padding: 0 0.5rem;
                    color: #555;
                    white-space: nowrap;
                }
                .currency-input-wrapper input {
                    flex: 1;
                    width: 100%;
                    padding: 0.5rem 0.5rem 0.5rem 0;
                    border: 0;
                    outline: none;
                    min-width: 0;
                }
                .form-group input {
                    width: 100%;
                    padding: 0.5rem;
                    border: 1px solid #ccc;
                    border-radius: 4px;
                }
                .form-group .currency-input-wrapper input {
                    padding: 0.5rem 0.5rem 0.5rem 0;
                    border: 0;
                    border-radius: 0;
                }
                .currency-input-wrapper:focus-within {
                    border-color: #3498db;
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
