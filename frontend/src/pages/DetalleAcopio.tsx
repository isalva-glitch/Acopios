import { Fragment, useState, useEffect } from 'react';
import { Link, useParams, useBlocker } from 'react-router-dom';
import apiClient from '../api/client';
import type {
    AcopioItemsPreciosReferencia,
    ConceptoPrecioReferencia,
    EstadoPreciosReferencia,
    ResumenCompensacion
} from '../types';
import { formatCurrencyAR, formatDecimalInput, formatNumberAR, parseDecimalInput } from '../utils/formatters';
import {
    PRECIO_REFERENCIA_PROCESOS,
    type PrecioReferenciaProcesoKey,
    type PrecioReferenciaProcesoUnidad
} from '../constants/preciosReferencia';

// Grupos de exclusión mutua: solo puede estar marcado uno por grupo a la vez
const PROCESO_EXCLUSION_GROUPS: PrecioReferenciaProcesoKey[][] = [
    ['camara_estructural', 'camara_normal', 'camara_offset'],
    ['opacificado_perimetral', 'opacificado_total'],
];

const PRECIO_STATUS_LABELS: Record<EstadoPreciosReferencia, string> = {
    completo: 'Completo',
    incompleto: 'Incompleto',
    sin_conceptos: 'Sin conceptos',
    revisar: 'Revisar',
};

type PrecioCampo = 'precio_base' | 'precio_actual';

const itemPrecioInputKey = (
    itemId: number,
    concepto: string,
    field: PrecioCampo
) => `${itemId}:${concepto}:${field}`;

const formatPrecioInputValue = (value: number | null | undefined) =>
    value === null || value === undefined ? '' : formatNumberAR(value, 2);

const formatPrecioFocusValue = (value: number | null | undefined) =>
    value === null || value === undefined ? '' : formatDecimalInput(value);

const parseNullableDecimalInput = (value: string): number | null => {
    if (!value.trim()) return null;
    return parseDecimalInput(value);
};

const toNullableNumber = (value: number | string | null | undefined): number | null => {
    if (value === null || value === undefined || value === '') return null;
    const parsed = Number(value);
    return Number.isFinite(parsed) ? parsed : null;
};

const normalizeItemsPreciosReferencia = (
    matrix: AcopioItemsPreciosReferencia | null
): AcopioItemsPreciosReferencia | null => {
    if (!matrix) return null;

    return {
        ...matrix,
        items: matrix.items.map((item) => ({
            ...item,
            total_m2: Number(item.total_m2 || 0),
            total_ml: Number(item.total_ml || 0),
            total_pesos: Number(item.total_pesos || 0),
            conceptos: item.conceptos.map((concepto) => ({
                ...concepto,
                precio_base: toNullableNumber(concepto.precio_base),
                precio_actual: toNullableNumber(concepto.precio_actual),
            })),
        })),
    };
};

const buildItemPrecioInputs = (
    matrix: AcopioItemsPreciosReferencia | null
): Record<string, string> => {
    const inputs: Record<string, string> = {};
    matrix?.items.forEach((item) => {
        item.conceptos.forEach((concepto) => {
            inputs[itemPrecioInputKey(item.item_id, concepto.concepto, 'precio_base')] =
                formatPrecioInputValue(concepto.precio_base);
            inputs[itemPrecioInputKey(item.item_id, concepto.concepto, 'precio_actual')] =
                formatPrecioInputValue(concepto.precio_actual);
        });
    });
    return inputs;
};

function DetalleAcopio() {
    const { id } = useParams<{ id: string }>();
    const [acopio, setAcopio] = useState<any>(null);
    const [originalAcopio, setOriginalAcopio] = useState<any>(null);
    const [itemsPreciosReferencia, setItemsPreciosReferencia] = useState<AcopioItemsPreciosReferencia | null>(null);
    const [itemPrecioInputs, setItemPrecioInputs] = useState<Record<string, string>>({});
    const [expandedPriceItems, setExpandedPriceItems] = useState<Record<number, boolean>>({});
    const [hasChanges, setHasChanges] = useState(false);
    const [isSavingAll, setIsSavingAll] = useState(false);

    const [avanceComercial, setAvanceComercial] = useState<any>(null);
    const [loading, setLoading] = useState(true);
    const [loadingAvance, setLoadingAvance] = useState(false);
    const [error, setError] = useState<string | null>(null);
    const [resumenCompensacion, setResumenCompensacion] = useState<ResumenCompensacion | null>(null);
    const [loadingResumenCompensacion, setLoadingResumenCompensacion] = useState(false);
    const [resumenCompensacionError, setResumenCompensacionError] = useState<string | null>(null);

    // Imputation states
    const [showImputer, setShowImputer] = useState(false);
    const [nroPedidoBusqueda, setNroPedidoBusqueda] = useState('');
    const [imputationPreview, setImputationPreview] = useState<any>(null);
    const [imputationLoading, setImputationLoading] = useState(false);
    const [imputationError, setImputationError] = useState<string | null>(null);
    const [imputationSuccess, setImputationSuccess] = useState(false);
    const [anulandoId, setAnulandoId] = useState<number | null>(null);
    const [anulacionError, setAnulacionError] = useState<string | null>(null);
    const [itemProcessError, setItemProcessError] = useState<string | null>(null);
    const [fechaVencimientoError, setFechaVencimientoError] = useState<string | null>(null);

    // React Router navigation blocker
    const blocker = useBlocker(
        ({ currentLocation, nextLocation }) =>
            hasChanges && currentLocation.pathname !== nextLocation.pathname
    );

    // Tab close / reload browser listener
    useEffect(() => {
        const handleBeforeUnload = (e: BeforeUnloadEvent) => {
            if (hasChanges) {
                e.preventDefault();
                e.returnValue = 'Tiene modificaciones sin guardar en el acopio. ¿Desea salir?';
            }
        };
        window.addEventListener('beforeunload', handleBeforeUnload);
        return () => {
            window.removeEventListener('beforeunload', handleBeforeUnload);
        };
    }, [hasChanges]);

    useEffect(() => {
        loadAcopio();
    }, [id]);

    const loadAcopio = async () => {
        setLoading(true);
        setError(null);
        setHasChanges(false);
        setFechaVencimientoError(null);

        try {
            const response = await apiClient.get(`/acopios/${id}`);
            const data = response.data;
            setAcopio(data);
            setOriginalAcopio(JSON.parse(JSON.stringify(data)));

            // Fetch item-scoped reference prices for the Total Items panel
            try {
                const preciosResponse = await apiClient.get<AcopioItemsPreciosReferencia>(`/acopios/${id}/items-precios-referencia`);
                const preciosData = normalizeItemsPreciosReferencia(preciosResponse.data || null);
                setItemsPreciosReferencia(preciosData);
                setItemPrecioInputs(buildItemPrecioInputs(preciosData));
            } catch (err) {
                console.error('Error fetching item reference prices:', err);
                setItemsPreciosReferencia(null);
                setItemPrecioInputs({});
            }

            loadResumenCompensacion(id!);
            
            if (data.v_presupuesto_id) {
                loadAvanceComercial(id!);
            }
        } catch (err: any) {
            setError(err.response?.data?.detail || 'Error al cargar el acopio');
        } finally {
            setLoading(false);
        }
    };

    const loadResumenCompensacion = async (acopioId: string) => {
        setLoadingResumenCompensacion(true);
        setResumenCompensacionError(null);
        try {
            const response = await apiClient.get<ResumenCompensacion>(`/acopios/${acopioId}/resumen-compensacion`);
            setResumenCompensacion(response.data);
        } catch (err: any) {
            setResumenCompensacion(null);
            setResumenCompensacionError(err.response?.data?.detail || 'No se pudo cargar el resumen de compensacion.');
        } finally {
            setLoadingResumenCompensacion(false);
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
            const response = await apiClient.get(`/integrations/spf/pedidos/${nroPedidoBusqueda}/imputation-preview`, {
                params: { acopio_id: id }
            });
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

    const handleFechaVencimientoChange = (value: string) => {
        setAcopio((prev: any) => prev ? { ...prev, fecha_vencimiento: value } : prev);
        setFechaVencimientoError(value ? null : 'La fecha de vencimiento del acopio es obligatoria.');
        setHasChanges(true);
    };

    const getItemProcesoCantidad = (
        item: any,
        unidad: PrecioReferenciaProcesoUnidad
    ) => Number(item?.totals?.[unidad] || 0);

    const formatProcesoCantidad = (value: number) => value.toFixed(2);
    const formatCantidad = (value: number, unidad: string) => `${formatNumberAR(value, 2)} ${unidad}`;
    const formatSignedCurrency = (value: number) => {
        if (value < 0) return `- ${formatCurrencyAR(Math.abs(value))}`;
        return formatCurrencyAR(value);
    };
    const getPedidosDocumentados = () => {
        if (!avanceComercial?.pedidos) return [];

        return avanceComercial.pedidos
            .map((pedido: any) => {
                const documentos: any[] = [];
                const seen = new Set<string>();
                const addDocumento = (doc: any) => {
                    const key = `${doc?.nro_factura || ''}-${doc?.nro_remito || ''}-${doc?.empresa || ''}`;
                    if (key === '--' || seen.has(key)) return;
                    seen.add(key);
                    documentos.push(doc);
                };

                pedido.comprobantes?.forEach(addDocumento);
                pedido.items?.forEach((item: any) => {
                    item.comprobantes?.forEach(addDocumento);
                });

                return {
                    id: pedido.id,
                    nro_pedido: pedido.nro_pedido,
                    estado: pedido.estado,
                    documentos,
                };
            });
    };

    const calculateItemPrecioStatus = (
        conceptos: ConceptoPrecioReferencia[]
    ): EstadoPreciosReferencia => {
        const enabledConcepts = conceptos.filter((concepto) => concepto.habilitado);
        if (enabledConcepts.length === 0) return 'sin_conceptos';

        return enabledConcepts.some((concepto) =>
            concepto.precio_actual === null ||
            concepto.precio_actual === undefined ||
            (Number(concepto.precio_actual) === 0 && concepto.origen !== 'manual')
        )
            ? 'incompleto'
            : 'completo';
    };

    const getItemPrecioRow = (itemId: number) =>
        itemsPreciosReferencia?.items.find((item) => item.item_id === itemId) || null;

    const getItemPrecioConcepto = (
        itemId: number,
        concepto: PrecioReferenciaProcesoKey
    ) => getItemPrecioRow(itemId)?.conceptos.find((current) => current.concepto === concepto) || null;

    const createPendingConcepto = (
        proceso: typeof PRECIO_REFERENCIA_PROCESOS[number]
    ): ConceptoPrecioReferencia => ({
        concepto: proceso.key,
        unidad: proceso.unidad,
        habilitado: true,
        precio_base: null,
        precio_actual: null,
        origen: 'autodetectado',
    });

    const updateItemsPreciosReferencia = (
        updater: (matrix: AcopioItemsPreciosReferencia) => AcopioItemsPreciosReferencia
    ) => {
        setItemsPreciosReferencia((prev) => {
            if (!prev) return prev;
            const next = updater(prev);
            setItemPrecioInputs(buildItemPrecioInputs(next));
            return next;
        });
    };

    const syncLocalPrecioConcepto = (
        itemId: number,
        processKey: PrecioReferenciaProcesoKey,
        checked: boolean
    ) => {
        const proceso = PRECIO_REFERENCIA_PROCESOS.find((current) => current.key === processKey);
        if (!proceso) return;

        updateItemsPreciosReferencia((matrix) => ({
            ...matrix,
            items: matrix.items.map((item) => {
                if (item.item_id !== itemId) return item;

                const conceptos = [...item.conceptos];
                const index = conceptos.findIndex((concepto) => concepto.concepto === processKey);
                if (index >= 0) {
                    conceptos[index] = {
                        ...conceptos[index],
                        habilitado: checked,
                        unidad: proceso.unidad,
                    };
                } else if (checked) {
                    conceptos.push(createPendingConcepto(proceso));
                }

                return {
                    ...item,
                    conceptos,
                    estado_precios_referencia: calculateItemPrecioStatus(conceptos),
                };
            }),
        }));
    };

    const handleToggleItemProceso = (
        itemId: number,
        processKey: PrecioReferenciaProcesoKey,
        checked: boolean
    ) => {
        const item = acopio.items.find((current: any) => current.id === itemId);
        if (!item) return;

        // Determina qué keys cambiarán: la seleccionada + las que hay que desmarcar por exclusión mutua
        const exclusionGroup = PROCESO_EXCLUSION_GROUPS.find(group => group.includes(processKey));
        const keysToUncheck: PrecioReferenciaProcesoKey[] = checked && exclusionGroup
            ? exclusionGroup.filter(k => k !== processKey && Boolean(item?.procesos?.[k]))
            : [];

        // Construye el payload con todos los cambios del grupo
        const payload: Partial<Record<PrecioReferenciaProcesoKey, boolean>> = {
            [processKey]: checked,
            ...Object.fromEntries(keysToUncheck.map(k => [k, false])),
        };

        setItemProcessError(null);
        syncLocalPrecioConcepto(itemId, processKey, checked);
        keysToUncheck.forEach((key) => syncLocalPrecioConcepto(itemId, key, false));
        setHasChanges(true);

        // Actualización local de procesos y procesos_detalle
        setAcopio((prev: any) => {
            if (!prev) return prev;
            return {
                ...prev,
                items: prev.items.map((current: any) => {
                    if (current.id !== itemId) return current;

                    const newProcesos = { ...(current.procesos || {}), ...payload };
                    const newProcesosDetalle = { ...(current.procesos_detalle || {}) };

                    // Recalcular localmente processes details
                    Object.keys(newProcesos).forEach((key) => {
                        const val = newProcesos[key];
                        const detail = newProcesosDetalle[key] || { activo: false, cantidad: 0, cantidad_item: 0, unidad: '' };
                        const unit = detail.unidad || (['pulido', 'camara_offset'].includes(key) ? 'ml' : 'm2');
                        const itemTotal = unit === 'm2' ? Number(current.totals.m2) : Number(current.totals.ml);

                        newProcesosDetalle[key] = {
                            ...detail,
                            activo: val,
                            unidad: unit,
                            cantidad: val ? itemTotal : 0,
                            cantidad_item: itemTotal
                        };
                    });

                    return {
                        ...current,
                        procesos: newProcesos,
                        procesos_detalle: newProcesosDetalle
                    };
                }),
            };
        });
    };

    const updateConceptoPrecio = (
        itemId: number,
        concepto: string,
        updater: (concepto: ConceptoPrecioReferencia) => ConceptoPrecioReferencia
    ) => {
        setItemsPreciosReferencia((prev) => {
            if (!prev) return prev;

            return {
                ...prev,
                items: prev.items.map((item) => {
                    if (item.item_id !== itemId) return item;

                    const conceptos = item.conceptos.map((current) =>
                        current.concepto === concepto ? updater(current) : current
                    );

                    return {
                        ...item,
                        conceptos,
                        estado_precios_referencia: calculateItemPrecioStatus(conceptos),
                    };
                }),
            };
        });
    };

    const handleItemPrecioChange = (
        itemId: number,
        concepto: string,
        field: PrecioCampo,
        value: string
    ) => {
        setItemPrecioInputs((prev) => ({
            ...prev,
            [itemPrecioInputKey(itemId, concepto, field)]: value,
        }));

        const parsedValue = parseNullableDecimalInput(value);
        updateConceptoPrecio(itemId, concepto, (current) => ({
            ...current,
            [field]: parsedValue,
            origen: 'manual',
        }));
        setHasChanges(true);
    };

    const handleItemPrecioFocus = (
        itemId: number,
        concepto: PrecioReferenciaProcesoKey,
        field: PrecioCampo
    ) => {
        const current = getItemPrecioConcepto(itemId, concepto);
        setItemPrecioInputs((prev) => ({
            ...prev,
            [itemPrecioInputKey(itemId, concepto, field)]: formatPrecioFocusValue(current?.[field]),
        }));
    };

    const handleItemPrecioBlur = (
        itemId: number,
        concepto: PrecioReferenciaProcesoKey,
        field: PrecioCampo
    ) => {
        const current = getItemPrecioConcepto(itemId, concepto);
        setItemPrecioInputs((prev) => ({
            ...prev,
            [itemPrecioInputKey(itemId, concepto, field)]: formatPrecioInputValue(current?.[field]),
        }));
    };

    const handleCopyBaseToActual = (
        itemId: number,
        concepto: PrecioReferenciaProcesoKey
    ) => {
        const current = getItemPrecioConcepto(itemId, concepto);
        if (!current || current.precio_base === null || current.precio_base === undefined) return;

        updateConceptoPrecio(itemId, concepto, (itemConcepto) => ({
            ...itemConcepto,
            precio_actual: current.precio_base,
            origen: 'manual',
        }));
        setItemPrecioInputs((prev) => ({
            ...prev,
            [itemPrecioInputKey(itemId, concepto, 'precio_actual')]: formatPrecioInputValue(current.precio_base),
        }));
        setHasChanges(true);
    };

    const handleCompleteMissingPrices = (itemId?: number) => {
        setItemsPreciosReferencia((prev) => {
            if (!prev) return prev;

            const next = {
                ...prev,
                items: prev.items.map((item) => {
                    if (itemId && item.item_id !== itemId) return item;

                    const conceptos = item.conceptos.map((concepto) => {
                        const missing = concepto.habilitado && (
                            concepto.precio_actual === null ||
                            concepto.precio_actual === undefined ||
                            (Number(concepto.precio_actual) === 0 && concepto.origen !== 'manual')
                        );
                        if (!missing || concepto.precio_base === null || concepto.precio_base === undefined) {
                            return concepto;
                        }
                        return {
                            ...concepto,
                            precio_actual: concepto.precio_base,
                            origen: 'manual' as const,
                        };
                    });

                    return {
                        ...item,
                        conceptos,
                        estado_precios_referencia: calculateItemPrecioStatus(conceptos),
                    };
                }),
            };
            setItemPrecioInputs(buildItemPrecioInputs(next));
            return next;
        });
        setHasChanges(true);
    };

    const normalizeSimilarityText = (value: unknown) =>
        String(value || '')
            .normalize('NFD')
            .replace(/[\u0300-\u036f]/g, '')
            .toLowerCase()
            .replace(/[^a-z0-9]+/g, ' ')
            .trim();

    const getItemSimilarityKey = (item: any) => {
        const enabledProcesos = PRECIO_REFERENCIA_PROCESOS
            .filter((proceso) => Boolean(item.procesos?.[proceso.key]))
            .map((proceso) => proceso.key)
            .sort()
            .join('|');
        const compositionText = [
            item.descripcion,
            item.material,
            item.tipologia,
        ].map(normalizeSimilarityText).join('|');

        return `${enabledProcesos}::${compositionText}`;
    };

    const handleApplyPriceToSimilar = (
        itemId: number,
        concepto: PrecioReferenciaProcesoKey
    ) => {
        const sourceItem = acopio.items.find((item: any) => item.id === itemId);
        const sourceConcepto = getItemPrecioConcepto(itemId, concepto);
        if (!sourceItem || !sourceConcepto || sourceConcepto.precio_actual === null) return;

        const sourceKey = getItemSimilarityKey(sourceItem);
        const similarItemIds = new Set(
            acopio.items
                .filter((item: any) =>
                    item.id !== itemId &&
                    Boolean(item.procesos?.[concepto]) &&
                    getItemSimilarityKey(item) === sourceKey
                )
                .map((item: any) => item.id)
        );
        if (similarItemIds.size === 0) return;

        setItemsPreciosReferencia((prev) => {
            if (!prev) return prev;

            const next = {
                ...prev,
                items: prev.items.map((item) => {
                    if (!similarItemIds.has(item.item_id)) return item;

                    const conceptos = item.conceptos.map((current) =>
                        current.concepto === concepto
                            ? {
                                ...current,
                                precio_actual: sourceConcepto.precio_actual,
                                origen: 'manual' as const,
                            }
                            : current
                    );

                    return {
                        ...item,
                        conceptos,
                        estado_precios_referencia: calculateItemPrecioStatus(conceptos),
                    };
                }),
            };
            setItemPrecioInputs(buildItemPrecioInputs(next));
            return next;
        });
        setHasChanges(true);
    };

    const scrollToResumenCompensacion = () => {
        document
            .querySelector('.resumen-compensacion-section')
            ?.scrollIntoView({ behavior: 'smooth', block: 'start' });
    };

    const scrollToTotalItems = () => {
        document
            .querySelector('.total-items-section')
            ?.scrollIntoView({ behavior: 'smooth', block: 'start' });
    };

    const validateItemsPreciosBeforeSave = (): boolean => {
        if (!itemsPreciosReferencia) return false;

        const missing: string[] = [];
        const negative: string[] = [];
        const zeroPrices: string[] = [];

        itemsPreciosReferencia.items.forEach((item) => {
            item.conceptos
                .filter((concepto) => concepto.habilitado)
                .forEach((concepto) => {
                    const label = `Item ${item.numero_item} - ${concepto.concepto}`;
                    if (concepto.precio_actual === null || concepto.precio_actual === undefined) {
                        missing.push(label);
                    }
                    if ((concepto.precio_actual ?? 0) < 0 || (concepto.precio_base ?? 0) < 0) {
                        negative.push(label);
                    }
                    if (Number(concepto.precio_actual) === 0) {
                        zeroPrices.push(label);
                    }
                });
        });

        if (missing.length > 0) {
            throw new Error(`Faltan precios de referencia: ${missing.slice(0, 4).join(', ')}`);
        }
        if (negative.length > 0) {
            throw new Error(`Hay precios negativos: ${negative.slice(0, 4).join(', ')}`);
        }
        if (zeroPrices.length > 0) {
            const confirmed = window.confirm(`Confirma guardar precio 0 en: ${zeroPrices.slice(0, 4).join(', ')}?`);
            if (!confirmed) {
                throw new Error('Debe confirmar los precios 0 para poder guardar.');
            }
            return true;
        }

        return false;
    };

    const buildItemsPreciosPayload = (confirmarCero: boolean) => ({
        items: (itemsPreciosReferencia?.items || []).map((item) => ({
            item_id: item.item_id,
            conceptos: item.conceptos.map((concepto) => ({
                concepto: concepto.concepto,
                unidad: concepto.unidad,
                precio_base: concepto.precio_base,
                precio_actual: concepto.precio_actual,
                habilitado: concepto.habilitado,
                confirmar_cero: confirmarCero,
            })),
        })),
    });

    const handleSaveChanges = async () => {
        const fechaVencimiento = acopio?.fecha_vencimiento || '';
        if (!fechaVencimiento) {
            setFechaVencimientoError('La fecha de vencimiento del acopio es obligatoria.');
            throw new Error('La fecha de vencimiento del acopio es obligatoria.');
        }

        let confirmarPrecioCero = false;
        try {
            confirmarPrecioCero = validateItemsPreciosBeforeSave();
        } catch (err: any) {
            setItemProcessError(err.message || 'Revise los precios de referencia por item.');
            throw err;
        }

        setIsSavingAll(true);
        setItemProcessError(null);
        try {
            // 1. Guardar fecha de vencimiento del acopio
            if (fechaVencimiento !== originalAcopio?.fecha_vencimiento) {
                await apiClient.patch(`/acopios/${id}`, {
                    fecha_vencimiento: fechaVencimiento
                });
            }

            // 2. Guardar cambios en procesos de items modificados
            const savePromises = [];
            for (const item of acopio.items) {
                const originalItem = originalAcopio.items.find((oi: any) => oi.id === item.id);
                if (!originalItem) continue;

                const changedProcesses: any = {};
                let hasItemChanges = false;
                for (const key of Object.keys(item.procesos)) {
                    if (item.procesos[key] !== originalItem.procesos[key]) {
                        changedProcesses[key] = item.procesos[key];
                        hasItemChanges = true;
                    }
                }

                if (hasItemChanges) {
                    savePromises.push(
                        apiClient.patch(`/acopios/${id}/items/${item.id}/procesos`, changedProcesses)
                    );
                }
            }
            await Promise.all(savePromises);

            // 3. Guardar precios de referencia por item
            if (itemsPreciosReferencia) {
                await apiClient.put(
                    `/acopios/${id}/items-precios-referencia`,
                    buildItemsPreciosPayload(confirmarPrecioCero)
                );
            }

            // Recargar acopio desde la base de datos para refrescar todo
            setHasChanges(false);
            await loadAcopio();
        } catch (err: any) {
            setItemProcessError(err.response?.data?.detail || 'Error al guardar los cambios en la base de datos.');
            throw err;
        } finally {
            setIsSavingAll(false);
        }
    };

    const handleDiscardChanges = () => {
        if (window.confirm('¿Está seguro de que desea descartar todas las modificaciones no guardadas?')) {
            if (originalAcopio) {
                setAcopio(JSON.parse(JSON.stringify(originalAcopio)));
                setHasChanges(false);
                loadAcopio();
            }
        }
    };

    const renderTotalItemsPanel = () => (
        <div className="form-section total-items-section">
            <div className="total-items-header">
                <h3>Total Items ({acopio.items.length})</h3>
                <div className="total-items-actions">
                    <button
                        type="button"
                        className="btn btn-secondary"
                        onClick={() => handleCompleteMissingPrices()}
                        disabled={isSavingAll || !itemsPreciosReferencia}
                    >
                        Completar faltantes
                    </button>
                    <button
                        type="button"
                        className="btn btn-secondary"
                        onClick={scrollToResumenCompensacion}
                    >
                        Ver impacto
                    </button>
                </div>
            </div>
            {itemProcessError && (
                <div className="item-process-error">
                    {itemProcessError}
                </div>
            )}
            <div className="table total-items-table">
                <table>
                    <thead>
                        <tr>
                            <th>Item</th>
                            <th>Descripcion</th>
                            <th>Cantidad</th>
                            <th>m2</th>
                            <th>ml</th>
                            <th>Panos</th>
                            <th>Importe</th>
                            <th>Precios ref.</th>
                            <th>Acciones</th>
                        </tr>
                    </thead>
                    <tbody>
                        {acopio.items.map((item: any, idx: number) => {
                            const precioRow = getItemPrecioRow(item.id);
                            const estado = precioRow?.estado_precios_referencia || 'revisar';
                            const expanded = Boolean(expandedPriceItems[item.id]);
                            const panosCount = item.panos.reduce((acc: number, p: any) => acc + p.cantidad, 0);

                            return (
                                <Fragment key={item.id}>
                                    <tr className="total-item-row">
                                        <td>{precioRow?.numero_item || idx + 1}</td>
                                        <td className="total-item-description">{item.descripcion}</td>
                                        <td>{item.totals.unidades}</td>
                                        <td>{formatNumberAR(item.totals.m2, 2)}</td>
                                        <td>{formatNumberAR(item.totals.ml, 2)}</td>
                                        <td>{panosCount}</td>
                                        <td>{formatCurrencyAR(item.totals.pesos)}</td>
                                        <td>
                                            <span className={`reference-price-status ${estado}`}>
                                                {PRECIO_STATUS_LABELS[estado]}
                                            </span>
                                        </td>
                                        <td>
                                            <button
                                                type="button"
                                                className="btn btn-secondary total-item-expand"
                                                onClick={() => setExpandedPriceItems((prev) => ({
                                                    ...prev,
                                                    [item.id]: !prev[item.id],
                                                }))}
                                            >
                                                {expanded ? 'Cerrar' : 'Editar'}
                                            </button>
                                        </td>
                                    </tr>
                                    {expanded && (
                                        <tr className="item-reference-editor-row">
                                            <td colSpan={9}>
                                                <div className="item-reference-editor">
                                                    <div className="item-reference-editor-header">
                                                        <strong>Item {precioRow?.numero_item || idx + 1} - {item.descripcion}</strong>
                                                        <button
                                                            type="button"
                                                            className="btn btn-secondary"
                                                            onClick={() => handleCompleteMissingPrices(item.id)}
                                                            disabled={isSavingAll}
                                                        >
                                                            Completar faltantes
                                                        </button>
                                                    </div>
                                                    <div className="item-reference-grid">
                                                        {PRECIO_REFERENCIA_PROCESOS.map((proceso) => {
                                                            const checked = Boolean(item.procesos?.[proceso.key]);
                                                            const cantidad = getItemProcesoCantidad(item, proceso.unidad);
                                                            const concepto = getItemPrecioConcepto(item.id, proceso.key);
                                                            const missing = checked && (
                                                                !concepto ||
                                                                concepto.precio_actual === null ||
                                                                concepto.precio_actual === undefined ||
                                                                (Number(concepto.precio_actual) === 0 && concepto.origen !== 'manual')
                                                            );
                                                            const baseKey = itemPrecioInputKey(item.id, proceso.key, 'precio_base');
                                                            const actualKey = itemPrecioInputKey(item.id, proceso.key, 'precio_actual');

                                                            return (
                                                                <div
                                                                    className={`reference-concept-row${checked ? ' is-enabled' : ' is-disabled'}${missing ? ' has-warning' : ''}`}
                                                                    key={proceso.key}
                                                                >
                                                                    <label
                                                                        className={`item-process-check${checked ? ' is-checked' : ''}`}
                                                                        title={`${proceso.label}: ${formatProcesoCantidad(cantidad)} ${proceso.unidad}`}
                                                                    >
                                                                        <input
                                                                            type="checkbox"
                                                                            checked={checked}
                                                                            disabled={isSavingAll}
                                                                            onChange={(event) => handleToggleItemProceso(
                                                                                item.id,
                                                                                proceso.key,
                                                                                event.target.checked
                                                                            )}
                                                                        />
                                                                        <span className="item-process-label">
                                                                            <span className="item-process-name">{proceso.shortLabel}</span>
                                                                            <span className="item-process-value">
                                                                                {checked
                                                                                    ? `${formatProcesoCantidad(cantidad)} ${proceso.unidad}`
                                                                                    : proceso.unidad}
                                                                            </span>
                                                                        </span>
                                                                    </label>
                                                                    {checked ? (
                                                                        <div className="reference-concept-fields">
                                                                            <label>
                                                                                <span>Base</span>
                                                                                <input
                                                                                    type="text"
                                                                                    inputMode="decimal"
                                                                                    value={itemPrecioInputs[baseKey] ?? formatPrecioInputValue(concepto?.precio_base)}
                                                                                    onChange={(event) => handleItemPrecioChange(item.id, proceso.key, 'precio_base', event.target.value)}
                                                                                    onFocus={() => handleItemPrecioFocus(item.id, proceso.key, 'precio_base')}
                                                                                    onBlur={() => handleItemPrecioBlur(item.id, proceso.key, 'precio_base')}
                                                                                    disabled={isSavingAll}
                                                                                />
                                                                            </label>
                                                                            <label>
                                                                                <span>Actual</span>
                                                                                <input
                                                                                    type="text"
                                                                                    inputMode="decimal"
                                                                                    value={itemPrecioInputs[actualKey] ?? formatPrecioInputValue(concepto?.precio_actual)}
                                                                                    onChange={(event) => handleItemPrecioChange(item.id, proceso.key, 'precio_actual', event.target.value)}
                                                                                    onFocus={() => handleItemPrecioFocus(item.id, proceso.key, 'precio_actual')}
                                                                                    onBlur={() => handleItemPrecioBlur(item.id, proceso.key, 'precio_actual')}
                                                                                    disabled={isSavingAll}
                                                                                    aria-invalid={missing}
                                                                                />
                                                                            </label>
                                                                            <div className="reference-concept-actions">
                                                                                <button
                                                                                    type="button"
                                                                                    className="btn btn-secondary"
                                                                                    onClick={() => handleCopyBaseToActual(item.id, proceso.key)}
                                                                                    disabled={isSavingAll || !concepto || concepto.precio_base === null}
                                                                                >
                                                                                    Copiar base
                                                                                </button>
                                                                                <button
                                                                                    type="button"
                                                                                    className="btn btn-secondary"
                                                                                    onClick={() => handleApplyPriceToSimilar(item.id, proceso.key)}
                                                                                    disabled={isSavingAll || !concepto || concepto.precio_actual === null}
                                                                                >
                                                                                    Aplicar similares
                                                                                </button>
                                                                            </div>
                                                                        </div>
                                                                    ) : (
                                                                        <div className="reference-concept-disabled">No aplica</div>
                                                                    )}
                                                                </div>
                                                            );
                                                        })}
                                                    </div>
                                                    <div className="item-reference-details">
                                                        {item.panos.length > 0 && (
                                                            <details>
                                                                <summary>Ver detalle de panos ({panosCount})</summary>
                                                                <div className="table compact-detail-table">
                                                                    <table>
                                                                        <thead>
                                                                            <tr>
                                                                                <th>Cantidad</th>
                                                                                <th>Ancho</th>
                                                                                <th>Alto</th>
                                                                                <th>m2</th>
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
                                                            <details>
                                                                <summary>Adicionales / Servicios ({item.adicionales.length})</summary>
                                                                <div className="table compact-detail-table">
                                                                    <table>
                                                                        <thead>
                                                                            <tr>
                                                                                <th>Cantidad</th>
                                                                                <th>Descripcion</th>
                                                                                <th>Unitario</th>
                                                                                <th>Total</th>
                                                                            </tr>
                                                                        </thead>
                                                                        <tbody>
                                                                            {item.adicionales.map((adc: any) => (
                                                                                <tr key={adc.id}>
                                                                                    <td>{adc.cantidad}</td>
                                                                                    <td>{adc.descripcion}</td>
                                                                                    <td>{formatCurrencyAR(adc.precio_unitario)}</td>
                                                                                    <td>{formatCurrencyAR(adc.precio_total)}</td>
                                                                                </tr>
                                                                            ))}
                                                                        </tbody>
                                                                    </table>
                                                                </div>
                                                            </details>
                                                        )}
                                                    </div>
                                                </div>
                                            </td>
                                        </tr>
                                    )}
                                </Fragment>
                            );
                        })}
                    </tbody>
                </table>
            </div>
        </div>
    );

    if (loading) {
        return <div className="loading">Cargando detalle...</div>;
    }

    if (error || !acopio) {
        return <div className="error">{error || 'Acopio no encontrado'}</div>;
    }

    const fechaVencimientoMissing = !acopio.fecha_vencimiento;
    const canSaveChanges = !isSavingAll && !fechaVencimientoMissing;

    return (
        <div className="detalle-acopio">
            <h2>Acopio - Presupuesto SPF #{acopio.v_presupuesto_id || acopio.numero}</h2>

            {hasChanges && (
                <div style={{
                    backgroundColor: '#fffbe6',
                    border: '1px solid #ffe58f',
                    borderRadius: '8px',
                    padding: '1rem 1.5rem',
                    marginBottom: '1.5rem',
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'space-between',
                    boxShadow: '0 2px 8px rgba(0, 0, 0, 0.05)',
                }}>
                    <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
                        <span style={{ fontSize: '1.5rem' }}>⚠️</span>
                        <div>
                            <strong style={{ color: '#d46b08' }}>Modificaciones sin guardar</strong>
                            <div style={{ fontSize: '0.85rem', color: '#8c8c8c', marginTop: '2px' }}>
                                Los cambios en la fecha de vencimiento, composición o precios de referencia no se guardarán en la base de datos hasta que los confirme.
                            </div>
                        </div>
                    </div>
                    <div style={{ display: 'flex', gap: '0.75rem' }}>
                        <button 
                            className="btn btn-secondary" 
                            onClick={handleDiscardChanges}
                            disabled={isSavingAll}
                            style={{ padding: '0.5rem 1rem', fontSize: '0.9rem' }}
                        >
                            Descartar
                        </button>
                        <button 
                            className="btn btn-success" 
                            onClick={handleSaveChanges}
                            disabled={!canSaveChanges}
                            style={{ padding: '0.5rem 1.25rem', fontSize: '0.9rem', fontWeight: 'bold' }}
                        >
                            {isSavingAll ? 'Guardando...' : '✓ Guardar Cambios'}
                        </button>
                    </div>
                </div>
            )}

            {blocker.state === 'blocked' && (
                <div className="modal-overlay" style={{ zIndex: 1100 }}>
                    <div className="modal-content" style={{ maxWidth: '500px', border: '2px solid #f39c12' }}>
                        <div className="modal-header" style={{ backgroundColor: '#fffbe6', borderBottom: '1px solid #ffe58f' }}>
                            <h3 style={{ color: '#d46b08', display: 'flex', alignItems: 'center', gap: '8px', margin: 0 }}>
                                ⚠️ Cambios sin guardar
                            </h3>
                        </div>
                        <div className="modal-body" style={{ padding: '1.5rem', lineHeight: '1.6', color: '#333' }}>
                            Realizó modificaciones en la fecha de vencimiento, composición (procesos) o precios de referencia del acopio. ¿Desea guardar estos cambios de forma permanente antes de salir?
                        </div>
                        <div className="modal-footer" style={{ padding: '1rem', borderTop: '1px solid #eee', display: 'flex', justifyContent: 'flex-end', gap: '0.5rem' }}>
                            <button 
                                className="btn btn-secondary" 
                                onClick={() => blocker.reset()}
                                style={{ marginRight: 'auto' }}
                            >
                                Seguir Editando
                            </button>
                            <button 
                                className="btn" 
                                style={{ backgroundColor: '#e74c3c', color: 'white' }}
                                onClick={() => blocker.proceed()}
                            >
                                Salir sin Guardar
                            </button>
                            <button 
                                className="btn btn-success" 
                                disabled={!canSaveChanges}
                                onClick={async () => {
                                    try {
                                        await handleSaveChanges();
                                        blocker.proceed();
                                    } catch (err) {
                                        console.error('Error saving before exit:', err);
                                    }
                                }}
                            >
                                Guardar y Salir
                            </button>
                        </div>
                    </div>
                </div>
            )}

            <div className="form-section detalle-general-section">
                <div className="detalle-general-header">
                    <h3>Información General</h3>
                </div>
                <div className="detalle-general-grid">
                    <div className="detalle-general-data">
                        <strong>Cliente:</strong> {avanceComercial?.cliente || acopio.obra?.cliente?.nombre || `SPF ID: ${acopio.cliente_id}`}<br />
                        <strong>Obra:</strong> {avanceComercial?.obra || acopio.obra?.nombre || `Presupuesto: ${acopio.v_presupuesto_id}`}<br />
                        {acopio.paquete && (
                            <>
                                <strong>Paquete de obras:</strong>{' '}
                                <Link to={`/paquetes/${acopio.paquete.id}`}>
                                    {acopio.paquete.numero || acopio.paquete.nombre}
                                </Link><br />
                            </>
                        )}
                        <strong>Fecha Alta:</strong> {new Date(acopio.fecha_alta).toLocaleDateString()}<br />
                        <strong>Estado:</strong> {acopio.estado}
                        <div className="detalle-vencimiento-field">
                            <label htmlFor="fecha-vencimiento-acopio">
                                Fecha de vencimiento <span aria-hidden="true">*</span>
                            </label>
                            <input
                                id="fecha-vencimiento-acopio"
                                type="date"
                                required
                                value={acopio.fecha_vencimiento || ''}
                                onChange={(event) => handleFechaVencimientoChange(event.target.value)}
                                aria-invalid={fechaVencimientoMissing}
                            />
                            {(fechaVencimientoError || fechaVencimientoMissing) && (
                                <div className="detalle-field-error">
                                    {fechaVencimientoError || 'La fecha de vencimiento del acopio es obligatoria.'}
                                </div>
                            )}
                        </div>
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
                                    <p><strong>Importe:</strong> {formatCurrencyAR(imputationPreview.spf_pedido.totals.pesos)}</p>
                                </div>
                            </div>
                            {imputationPreview.composicion_warnings?.length > 0 && (
                                <div className="warning-box" style={{ marginTop: '1rem' }}>
                                    <h4>Advertencias de composicion</h4>
                                    {imputationPreview.composicion_warnings.map((warning: string, index: number) => (
                                        <div className="warning-item warning" key={`${warning}-${index}`}>
                                            {warning}
                                        </div>
                                    ))}
                                </div>
                            )}
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

            {/* === LAYOUT DUAL: Totales + Consumos === */}
            <div className="form-section" style={{ padding: '1.5rem 2rem' }}>
                <div className="totales-consumos-grid">
                    {/* Panel izquierdo: Totales y Saldos */}
                    <div className="totales-panel">
                        <h3 style={{ marginBottom: '1rem', color: '#2c3e50' }}>Totales y Saldos</h3>
                        <div className="table">
                            <table>
                                <thead>
                                    <tr>
                                        <th></th>
                                        <th>Contratado</th>
                                        <th>Saldo</th>
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
                                        <td>{formatCurrencyAR(acopio.totals.pesos)}</td>
                                        <td>{formatCurrencyAR(acopio.saldos.pesos)}</td>
                                    </tr>
                                </tbody>
                            </table>
                        </div>
                    </div>

                    {/* Panel derecho: Consumos Aplicados */}
                    <div className="consumos-panel">
                        <div className="consumos-panel-title">
                            <span>Consumos Aplicados</span>
                            {loadingAvance && <span className="consumos-loading">Actualizando...</span>}
                        </div>

                        {acopio.imputaciones.length === 0 ? (
                            <div className="consumos-empty">Sin consumos registrados</div>
                        ) : (
                            <ul className="consumos-list">
                                {acopio.imputaciones.map((imp: any) => {
                                    const fecha = imp.fecha
                                        ? new Date(imp.fecha + 'T00:00:00').toLocaleDateString('es-AR', { day: '2-digit', month: '2-digit' })
                                        : '';
                                    const isNegativo = imp.cantidad_pesos < 0;
                                    return (
                                        <li key={imp.id} className="consumos-list-item">
                                            <span className="consumos-pedido-num">Ped. {imp.pedido_numero}</span>
                                            <span className={`consumos-importe${isNegativo ? ' negativo' : ''}`}>
                                                {formatCurrencyAR(imp.cantidad_pesos)}
                                            </span>
                                            <span className="consumos-fecha">{fecha}</span>
                                            {imp.es_excedente && imp.excedente_tipo !== 'ITEM' && imp.excedente_tipo !== 'COMPOSICION' && (
                                                <span className="consumos-badge-excedente" title={imp.excedente_motivo || ''}>⚠ {imp.excedente_tipo === 'ACOPIO' ? 'Excedente acopio' : 'Excedente'}</span>
                                            )}
                                            {imp.excedente_tipo === 'ITEM' && (
                                                <span className="consumos-badge-excedente" title={imp.excedente_motivo || ''} style={{ backgroundColor: '#fff3cd', color: '#856404' }}>⚠ Excedente ítem</span>
                                            )}
                                            {imp.excedente_tipo === 'COMPOSICION' && (
                                                <span className="consumos-badge-excedente" title={imp.excedente_motivo || ''} style={{ backgroundColor: '#fff3cd', color: '#856404' }}>⚠ Revisar composición</span>
                                            )}
                                        </li>
                                    );
                                })}
                            </ul>
                        )}

                        {/* Colapsable documental asociado a los pedidos imputados */}
                        {acopio.imputaciones.length > 0 && (
                            <details className="remitos-collapsible">
                                <summary>
                                    {(() => {
                                        const documentosCount = getPedidosDocumentados()
                                            .reduce((acc: number, pedido: any) => acc + pedido.documentos.length, 0);
                                        return documentosCount > 0
                                            ? `Remitos y facturas relacionados (${documentosCount})`
                                            : 'Remitos y facturas relacionados';
                                    })()}
                                </summary>
                                <div className="remitos-collapsible-body">
                                    {(() => {
                                        if (loadingAvance) {
                                            return <div className="remito-empty">Actualizando documentos...</div>;
                                        }

                                        const pedidosDocumentados = getPedidosDocumentados();
                                        if (!avanceComercial || pedidosDocumentados.length === 0) {
                                            return <div className="remito-empty">Sin documentos asignados</div>;
                                        }

                                        return pedidosDocumentados.map((pedido: any) => (
                                            <div key={pedido.id || pedido.nro_pedido} className="remito-pedido-group">
                                                <div className="remito-pedido-title">
                                                    <span>Pedido {pedido.nro_pedido}</span>
                                                    {pedido.estado && <span>{pedido.estado}</span>}
                                                </div>
                                                {pedido.documentos.length === 0 ? (
                                                    <div className="remito-empty">Sin facturas ni remitos asociados</div>
                                                ) : (
                                                    pedido.documentos.map((doc: any, idx: number) => (
                                                        <div key={`${pedido.id || pedido.nro_pedido}-${idx}`} className="remito-row">
                                                            {doc.nro_factura && <span>Factura {doc.nro_factura}</span>}
                                                            {doc.nro_remito && <span>Remito {doc.nro_remito}</span>}
                                                            {doc.empresa && <span>{doc.empresa}</span>}
                                                        </div>
                                                    ))
                                                )}
                                            </div>
                                        ));
                                    })()}
                                </div>
                            </details>
                        )}

                        {acopio.imputaciones.length > 0 && (
                            <div className="consumos-footer">
                                <div className="consumos-footer-row">
                                    <span className="consumos-footer-label">Consumido</span>
                                    <span className="consumos-footer-valor consumido">
                                        {formatCurrencyAR(
                                            acopio.imputaciones.reduce((acc: number, imp: any) => acc + imp.cantidad_pesos, 0)
                                        )}
                                    </span>
                                </div>
                                <div className="consumos-footer-row">
                                    <span className="consumos-footer-label">Disponible</span>
                                    <span className="consumos-footer-valor disponible">
                                        {formatCurrencyAR(acopio.saldos.pesos)}
                                    </span>
                                </div>
                            </div>
                        )}
                    </div>
                </div>
            </div>


            {renderTotalItemsPanel()}

            {false && (
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
                                    <strong>Paños:</strong> {item.totals.unidades} (saldo: {item.saldos.unidades})
                                </div>
                                <div>
                                    <strong>m²:</strong> {Number(item.totals.m2).toFixed(2)} (saldo: {Number(item.saldos.m2).toFixed(2)})
                                </div>
                                <div>
                                    <strong>ml:</strong> {Number(item.totals.ml).toFixed(2)} (saldo: {Number(item.saldos.ml).toFixed(2)})
                                </div>
                                <div>
                                    <strong>$:</strong> {formatCurrencyAR(item.totals.pesos)} (saldo: {formatCurrencyAR(item.saldos.pesos)})
                                </div>
                            </div>

                            {item.panos.length > 0 && (
                                <details style={{ marginTop: '0.5rem' }}>
                                    <summary style={{ cursor: 'pointer', fontWeight: 'bold' }}>
                                        Ver detalle de paños ({item.panos.reduce((acc: number, p: any) => acc + p.cantidad, 0)})
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
                                                        <td>{formatCurrencyAR(adc.precio_unitario)}</td>
                                                        <td>{formatCurrencyAR(adc.precio_total)}</td>
                                                    </tr>
                                                ))}
                                            </tbody>
                                        </table>
                                    </div>
                                </details>
                            )}
                        </div>

                        <div className="item-processes-panel">
                            <div className="item-processes-title">Composicion</div>
                            <div className="item-processes-list">
                                {PRECIO_REFERENCIA_PROCESOS.map((proceso) => {
                                    const checked = Boolean(item.procesos?.[proceso.key]);
                                    const cantidad = getItemProcesoCantidad(item, proceso.unidad);

                                    return (
                                        <label
                                            className={`item-process-check${checked ? ' is-checked' : ''}`}
                                            key={proceso.key}
                                            title={`${proceso.label}: ${formatProcesoCantidad(cantidad)} ${proceso.unidad}`}
                                        >
                                            <input
                                                type="checkbox"
                                                checked={checked}
                                                disabled={isSavingAll}
                                                onChange={(event) => handleToggleItemProceso(
                                                    item.id,
                                                    proceso.key,
                                                    event.target.checked
                                                )}
                                            />
                                            <span className="item-process-label">
                                                <span className="item-process-name">{proceso.shortLabel}</span>
                                                <span className="item-process-value">
                                                    {checked
                                                        ? `${formatProcesoCantidad(cantidad)} ${proceso.unidad}`
                                                        : proceso.unidad}
                                                </span>
                                            </span>
                                        </label>
                                    );
                                })}
                            </div>
                        </div>
                    </div>
                ))}
            </div>
            )}

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
                                    <th>Composicion</th>
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
                                        <td>{formatCurrencyAR(imp.cantidad_pesos)}</td>
                                        <td>
                                            {imp.composicion_advertencia ? (
                                                <span className="composition-warning">
                                                    {imp.composicion_advertencia}
                                                </span>
                                            ) : (
                                                imp.composicion_match_estado || 'S/D'
                                            )}
                                        </td>
                                        <td title={imp.excedente_motivo || ''}>
                                            {imp.excedente_tipo === 'ACOPIO' ? '⚠️ Sí (Acopio)' :
                                             imp.excedente_tipo === 'ITEM' ? '⚠️ Sí (Ítem)' :
                                             imp.excedente_tipo === 'COMPOSICION' ? '⚠️ Composición' :
                                             imp.es_excedente ? '⚠️ Sí' : 'No'}
                                        </td>
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

            <div className="form-section resumen-compensacion-section">
                <div className="resumen-compensacion-header">
                    <div style={{ display: 'flex', alignItems: 'center', gap: '1rem' }}>
                        <h3 style={{ margin: 0 }}>Resumen de compensacion</h3>
                        <button 
                            className="btn btn-secondary" 
                            onClick={scrollToTotalItems}
                            style={{ padding: '0.3rem 0.8rem', fontSize: '0.85rem' }}
                        >
                            Precios por item
                        </button>
                    </div>
                    {loadingResumenCompensacion && <span>Actualizando...</span>}
                </div>

                {resumenCompensacionError && (
                    <div className="item-process-error">
                        {resumenCompensacionError}
                    </div>
                )}

                {resumenCompensacion && (
                    <>
                        <div className="resumen-compensacion-totals">
                            <div>
                                <span>Total positivo</span>
                                <strong className="amount-positive">{formatCurrencyAR(resumenCompensacion.totals.positivo)}</strong>
                            </div>
                            <div>
                                <span>Total negativo</span>
                                <strong className="amount-negative">{formatSignedCurrency(resumenCompensacion.totals.negativo)}</strong>
                            </div>
                            <div>
                                <span>Saldo</span>
                                <strong className={resumenCompensacion.totals.saldo < 0 ? 'amount-negative' : 'amount-positive'}>
                                    {formatSignedCurrency(resumenCompensacion.totals.saldo)}
                                </strong>
                            </div>
                        </div>

                        {resumenCompensacion.warnings.length > 0 && (
                            <div className="warning-box resumen-compensacion-warnings">
                                {resumenCompensacion.warnings.map((warning, index) => (
                                    <div className="warning-item warning" key={`${warning}-${index}`}>
                                        {warning}
                                    </div>
                                ))}
                            </div>
                        )}

                        <div className="table resumen-compensacion-table">
                            <table>
                                <thead>
                                    <tr>
                                        <th>Composicion</th>
                                        <th>Acopio</th>
                                        <th>Pedidos imputados</th>
                                        <th>Diferencia</th>
                                        <th>Precio ref.</th>
                                        <th>Importe</th>
                                        <th>Detalle</th>
                                    </tr>
                                </thead>
                                <tbody>
                                    {resumenCompensacion.rows.map((row) => (
                                        <tr className={`compensacion-row ${row.estado}`} key={row.proceso}>
                                            <td>
                                                <strong>{row.label}</strong>
                                                {row.precio_faltante && <span className="missing-price">Sin precio</span>}
                                            </td>
                                            <td>{formatCantidad(row.cantidad_acopio, row.unidad)}</td>
                                            <td>{formatCantidad(row.cantidad_pedidos, row.unidad)}</td>
                                            <td className={row.diferencia < 0 ? 'amount-negative' : row.diferencia > 0 ? 'amount-positive' : ''}>
                                                {formatCantidad(row.diferencia, row.unidad)}
                                            </td>
                                            <td>{formatCurrencyAR(row.precio_referencia)}</td>
                                            <td className={row.importe < 0 ? 'amount-negative' : row.importe > 0 ? 'amount-positive' : ''}>
                                                {formatSignedCurrency(row.importe)}
                                            </td>
                                            <td>
                                                <details>
                                                    <summary>Ver</summary>
                                                    <div className="compensacion-detail">
                                                        <strong>Acopio</strong>
                                                        {row.items_acopio.length > 0 ? (
                                                            row.items_acopio.map((item) => (
                                                                <div key={item.item_id}>
                                                                    Item {item.item_id}: {formatCantidad(item.cantidad, row.unidad)}
                                                                </div>
                                                            ))
                                                        ) : (
                                                            <div>Sin cantidad asignada</div>
                                                        )}
                                                        <strong>Pedidos</strong>
                                                        {row.pedidos.length > 0 ? (
                                                            row.pedidos.map((pedido) => (
                                                                <div key={`${pedido.imputacion_id}-${pedido.pedido_numero || 'pedido'}`}>
                                                                    Pedido {pedido.pedido_numero || pedido.pedido_id}: {formatCantidad(pedido.cantidad, row.unidad)}
                                                                </div>
                                                            ))
                                                        ) : (
                                                            <div>Sin cantidad imputada</div>
                                                        )}
                                                    </div>
                                                </details>
                                            </td>
                                        </tr>
                                    ))}
                                </tbody>
                            </table>
                        </div>
                    </>
                )}
            </div>

        </div>
    );
}

export default DetalleAcopio;
