(() => {
  if (window.top !== window || location.port !== '5173') return;
  let collecting = false;
  window.addEventListener('message', event => {
    const msg = event.data;
    if (event.source !== window || event.origin !== location.origin || msg?.channel !== 'acopios-glassware-request'
        || !['ping', 'collect'].includes(msg.action) || typeof msg.requestId !== 'string' || msg.requestId.length > 80) return;
    if (msg.action === 'collect' && (collecting || !/^[1-9]\d{0,15}$/.test(String(msg.budgetId)))) return;
    if (msg.action === 'collect') collecting = true;
    chrome.runtime.sendMessage({action: msg.action, budgetId: msg.budgetId}, response => {
      if (msg.action === 'collect') collecting = false;
      const error = chrome.runtime.lastError;
      window.postMessage({channel: 'acopios-glassware-response', requestId: msg.requestId,
        ...(error ? {ok: false, error: 'Recargá Acopios después de instalar o actualizar el conector.'} : response)}, location.origin);
    });
  });
})();
