// Serialized by chrome.scripting: keep all dependencies inside this function.
export async function collectBudget(budgetId) {
  try {
  const origin = 'https://glassware.fontela.com.ar';
  if (location.origin !== origin || !/^[1-9]\d*$/.test(budgetId)) throw new Error('Destino Glassware inválido.');
  const clean = node => {
    const copy = node.cloneNode(true);
    copy.querySelectorAll('script,style,input,meta,button,svg,iframe,form').forEach(n => n.remove());
    for (const element of [copy, ...copy.querySelectorAll('*')]) {
      for (const attr of [...element.attributes]) {
        if (!['id', 'class', 'data-url', 'data-price', 'data-adjustment'].includes(attr.name)) element.removeAttribute(attr.name);
      }
    }
    return copy.outerHTML;
  };
  const read = async (path, frame) => {
    const response = await fetch(origin + path, {method: 'GET', credentials: 'same-origin',
      redirect: 'error', cache: 'no-store', headers: {'Accept': 'text/html', ...(frame ? {'Turbo-Frame': frame} : {})},
      signal: AbortSignal.timeout(20000)});
    if (!response.ok) throw new Error(`Glassware respondió ${response.status}. Revisá tu sesión y el presupuesto.`);
    const html = await response.text();
    if (html.length > 2000000) throw new Error('La respuesta de Glassware es demasiado grande.');
    return new DOMParser().parseFromString(html, 'text/html');
  };
  const path = '/budgets/' + budgetId;
  const page = await read(path);
  const root = page.querySelector('.budget-detail');
  if (!root) throw new Error('No se encontró el presupuesto. Iniciá sesión en Glassware y volvé a consultar.');
  const state = root.querySelector('.chip--budget-detail')?.textContent.trim();
  if (!['Aceptado','Parcial'].includes(state)) throw new Error(`El presupuesto está «${state || 'sin estado'}». Solo se importan presupuestos Aceptados; un Parcial requiere verificar su aprobación en Acopios.`);
  const ids = [...root.querySelectorAll('#items > turbo-frame[id^="item_"]')].map(n => n.id.slice(5));
  if (!ids.length || ids.length > 200 || new Set(ids).size !== ids.length || ids.some(id => !/^[1-9]\d*$/.test(id))) {
    throw new Error('No se pudo identificar la lista completa de ítems.');
  }
  const items = [];
  let totalSize = 0;
  for (const id of ids) {
    const doc = await read(path + '/items/' + id, 'aside_modal_content');
    const item = doc.querySelector('#item-' + id);
    if (!item) throw new Error('Falta el detalle del ítem ' + id + '. Volvé a consultar.');
    const scripts = [...item.querySelectorAll('script')].map(s => s.textContent);
    const arrays = scripts.map(s => s.match(/const\s+data\s*=\s*(\[\[.*?\]\]|\[\])\s*(?:;|\r?\n)/s)).filter(Boolean);
    if (arrays.length !== 1) throw new Error('No se encontraron las medidas completas del ítem ' + id + '.');
    const measures = JSON.parse(arrays[0][1]); // Parse data, never execute Glassware scripts.
    const html = clean(item);
    totalSize += html.length + JSON.stringify(measures).length;
    if (totalSize > 7000000) throw new Error('El presupuesto supera el tamaño admitido.');
    items.push({id, html, measures});
  }
  // A second GET detects edits during a multi-item consultation, without changing the open tab.
  const budgetHtml = clean(root);
  const latest = (await read(path)).querySelector('.budget-detail');
  if (!latest || clean(latest) !== budgetHtml) throw new Error('El presupuesto cambió durante la consulta. Volvé a consultar.');
  return {url: origin + path, budget_html: budgetHtml, items};
  } catch (error) {
    return {error: error.message || 'No se pudo consultar Glassware.'};
  }
}
