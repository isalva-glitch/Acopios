import {collectBudget} from './collect.js';

const allowed = url => {
  try {
    const u = new URL(url);
    return u.protocol === 'http:' && ['localhost', '127.0.0.1'].includes(u.hostname) && u.port === '5173';
  } catch { return false; }
};
let busy = false;
chrome.runtime.onMessage.addListener((message, sender, reply) => {
  if (!allowed(sender.url) || sender.frameId !== 0 || sender.id !== chrome.runtime.id) return false;
  if (message?.action === 'ping') { reply({ok: true, version: '1.0.0'}); return false; }
  if (message?.action !== 'collect' || !/^[1-9]\d{0,15}$/.test(String(message.budgetId))) return false;
  if (busy) { reply({ok: false, error: 'Ya hay una consulta a Glassware en curso. Esperá a que termine.'}); return false; }
  busy = true;
  (async () => {
    try {
      const tabs = await chrome.tabs.query({url: 'https://glassware.fontela.com.ar/*'});
      const target = tabs.find(t => t.url === `https://glassware.fontela.com.ar/budgets/${message.budgetId}`) || tabs.find(t => t.active) || tabs[0];
      if (!target) throw new Error('Abrí Glassware e iniciá sesión en este mismo perfil de Chrome.');
      const result = await chrome.scripting.executeScript({target: {tabId: target.id},
        world: 'ISOLATED', func: collectBudget, args: [String(message.budgetId)]});
      if (!result[0]?.result) throw new Error('No se pudo leer Glassware. Revisá la sesión y volvé a consultar.');
      if (result[0].result.error) throw new Error(result[0].result.error);
      reply({ok: true, data: result[0].result});
    } catch (err) {
      // Chrome wraps page errors; never return page HTML, cookies or stack traces.
      reply({ok: false, error: err.message || 'No se pudo consultar Glassware.'});
    } finally { busy = false; }
  })();
  return true;
});
