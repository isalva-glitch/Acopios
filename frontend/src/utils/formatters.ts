export const formatNumberAR = (
    value: number | string | null | undefined,
    fractionDigits = 2
) => toDecimalNumber(value).toLocaleString('es-AR', {
    minimumFractionDigits: fractionDigits,
    maximumFractionDigits: fractionDigits
});

export const formatCurrencyAR = (
    value: number | string | null | undefined
) => `$ ${formatNumberAR(value, 2)}`;

export const parseDecimalInput = (
    value: number | string | null | undefined
): number => {
    if (typeof value === 'number') {
        return Number.isFinite(value) ? value : 0;
    }

    const rawValue = String(value ?? '').trim();
    if (!rawValue) return 0;

    const valueWithoutCurrency = rawValue
        .replace(/\s/g, '')
        .replace(/\$/g, '');
    const sign = valueWithoutCurrency.startsWith('-') ? -1 : 1;
    const unsignedValue = valueWithoutCurrency.replace(/^-/, '');
    const lastCommaIndex = unsignedValue.lastIndexOf(',');
    const lastDotIndex = unsignedValue.lastIndexOf('.');
    let normalizedValue = unsignedValue;

    if (lastCommaIndex >= 0 && lastDotIndex >= 0) {
        const decimalSeparator = lastCommaIndex > lastDotIndex ? ',' : '.';
        const thousandsSeparator = decimalSeparator === ',' ? '.' : ',';
        normalizedValue = unsignedValue
            .replace(new RegExp(`\\${thousandsSeparator}`, 'g'), '')
            .replace(decimalSeparator, '.');
    } else if (lastCommaIndex >= 0) {
        normalizedValue = unsignedValue.replace(/\./g, '').replace(',', '.');
    } else if (lastDotIndex >= 0) {
        const dotParts = unsignedValue.replace(/,/g, '').split('.');
        if (dotParts.length > 2) {
            const decimalPart = dotParts[dotParts.length - 1];
            const integerPart = dotParts.slice(0, -1).join('');
            normalizedValue = decimalPart.length === 3
                ? dotParts.join('')
                : `${integerPart}.${decimalPart}`;
        } else {
            normalizedValue = dotParts.join('.');
        }
    }

    const parsedValue = Number(normalizedValue.replace(/[^0-9.]/g, ''));
    return Number.isFinite(parsedValue) ? sign * parsedValue : 0;
};

export const formatDecimalInput = (
    value: number | string | null | undefined
): string => {
    const decimalValue = toDecimalNumber(value);
    return decimalValue ? String(decimalValue) : '';
};

const toDecimalNumber = (
    value: number | string | null | undefined
): number => {
    if (typeof value === 'number') {
        return Number.isFinite(value) ? value : 0;
    }

    if (typeof value === 'string') {
        return parseDecimalInput(value);
    }

    return 0;
};
