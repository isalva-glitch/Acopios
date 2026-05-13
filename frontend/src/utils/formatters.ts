export const formatNumberAR = (
    value: number | string | null | undefined,
    fractionDigits = 2
) => Number(value || 0).toLocaleString('es-AR', {
    minimumFractionDigits: fractionDigits,
    maximumFractionDigits: fractionDigits
});

export const formatCurrencyAR = (
    value: number | string | null | undefined
) => `$ ${formatNumberAR(value, 2)}`;
