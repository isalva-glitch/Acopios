export function glasswareRequest(action: 'ping' | 'collect', budgetId?: string): Promise<any> {
    return new Promise((resolve, reject) => {
        const requestId = crypto.randomUUID();
        const timer = window.setTimeout(() => {
            window.removeEventListener('message', listener);
            reject(new Error(action === 'ping'
                ? 'Instalá el conector de Glassware y recargá esta página en Chrome.'
                : 'La consulta no respondió a tiempo. Revisá Glassware y volvé a consultar.'));
        }, action === 'ping' ? 2500 : 240000);
        function listener(event: MessageEvent) {
            if (event.source !== window || event.origin !== window.location.origin
                || event.data?.channel !== 'acopios-glassware-response' || event.data.requestId !== requestId) return;
            clearTimeout(timer);
            window.removeEventListener('message', listener);
            if (event.data.ok) resolve(event.data.data ?? event.data);
            else reject(new Error(event.data.error || 'No se pudo consultar Glassware.'));
        }
        window.addEventListener('message', listener);
        window.postMessage({channel: 'acopios-glassware-request', requestId, action, budgetId}, window.location.origin);
    });
}

export function glasswareId(input: string): string {
    try {
        const u = new URL(input.trim());
        const match = u.pathname.match(/^\/budgets\/([1-9]\d{0,15})\/?$/);
        if (u.origin !== 'https://glassware.fontela.com.ar' || u.search || u.hash || !match)
            throw new Error();
        return match[1];
    } catch { throw new Error('Pegá el enlace completo del presupuesto de Glassware.'); }
}
