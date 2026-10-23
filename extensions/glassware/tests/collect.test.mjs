import assert from 'node:assert/strict';
import {readFile} from 'node:fs/promises';
import {test} from 'node:test';
import vm from 'node:vm';
import {collectBudget} from '../collect.js';
const {DOMParser} = await import(process.env.GLASSWARE_TEST_DOM_MODULE || 'linkedom');

const base = 'https://glassware.fontela.com.ar';
async function fixture(name) {
  const data = JSON.parse(await readFile(new URL(`../../../backend/tests/fixtures/glassware/${name}.json`, import.meta.url), 'utf8'));
  const doc = new DOMParser().parseFromString(data.budget_html, 'text/html');
  const id = data.items[0].id;
  doc.querySelector('.chip--budget-detail').textContent = 'Aceptado';
  doc.querySelectorAll('#items > turbo-frame').forEach(n => {if(n.id !== 'item_'+id) n.remove();});
  const script = `<script>document.addEventListener('turbo:frame-load', function() { const data = ${JSON.stringify(data.items[0].measures)}\n window.table = new Handsontable(); });</script>`;
  const itemDoc = new DOMParser().parseFromString(data.items[0].html, 'text/html');
  itemDoc.querySelector('#item-'+id).insertAdjacentHTML('beforeend',script);
  const item = itemDoc.toString();
  return {data, html: doc.toString(), item: item.replace('</html>', '<input name="authenticity_token" value="DO-NOT-EXPORT"></html>')};
}

async function run(name, mutate) {
  const f = await fixture(name);
  globalThis.DOMParser = DOMParser;
  globalThis.location = {origin: base};
  const calls = [];
  globalThis.fetch = async (url, options) => {
    calls.push({url, options});
    assert.equal(options.method, 'GET');
    assert.equal(options.credentials, 'same-origin');
    assert.match(url, /^https:\/\/glassware\.fontela\.com\.ar\/budgets\/[1-9]\d*(\/items\/[1-9]\d*)?$/);
    return {ok: true, text: async () => url.includes('/items/') ? f.item : f.html};
  };
  if(mutate) mutate(f, calls);
  const result = await collectBudget(f.data.url.split('/').at(-1));
  return {result, calls, fixture: f};
}

for(const name of ['profilit', 'dvh']) {
  test(`collects sanitized ${name} data with GET only`, async () => {
    const {result, calls, fixture: f} = await run(name);
    assert.equal(result.error, undefined, result.error);
    assert.equal(calls.length, 3);
    assert.deepEqual(result.items[0].measures, f.data.items[0].measures);
    assert.ok(!/authenticity_token|DO-NOT-EXPORT|<script|<form|onclick=/.test(JSON.stringify(result)));
    assert.ok(result.items[0].html.includes('item_description'));
  });
}

test('rejects a non-accepted budget before fetching any item', async () => {
  const {result, calls} = await run('dvh', f => {f.html=f.html.replace('>Aceptado<', '>Enviado<');});
  assert.match(result.error, /Solo se importan/);
  assert.equal(calls.length, 1);
});

test('rejects a source modified during consultation', async () => {
  const {result} = await run('dvh', (f, calls) => {
    const fetchOriginal=globalThis.fetch;
    globalThis.fetch=async (...args) => {
      if(calls.length===2) f.html=f.html.replace('ALTERNATIVA 1:', 'CAMBIO:');
      return fetchOriginal(...args);
    };
  });
  assert.match(result.error, /cambió/);
});

test('never evaluates JavaScript instead of a JSON array', async () => {
  const {result} = await run('dvh', f => {f.item=f.item.replace('const data = ', 'const data = dangerousFunction() || ');});
  assert.match(result.error, /medidas completas/);
});

test('rejects wrong source origin', async () => {
  await run('dvh');
  globalThis.location={origin:'https://evil.test'};
  assert.match((await collectBudget('17292')).error, /Destino/);
});

test('local bridge ignores other pages, frames and actions', async () => {
  let handler;
  const calls=[];
  const fakeWindow={addEventListener: (event, cb) => {handler=cb;}, postMessage: result => calls.push(result)};
  fakeWindow.top=fakeWindow;
  const context={window:fakeWindow, location:{port:'5173', origin:'http://localhost:5173'},
    chrome:{runtime:{sendMessage: (msg, cb) => {calls.push(msg); cb({ok:true});}, lastError:null}}};
  vm.runInNewContext(await readFile(new URL('../bridge.js', import.meta.url),'utf8'), context);
  const data={channel:'acopios-glassware-request',action:'ping',requestId:'test'};
  handler({source:fakeWindow,origin:'https://evil.test',data});
  handler({source:fakeWindow,origin:'http://localhost:5173',data:{...data,action:'pay'}});
  assert.equal(calls.length,0);
  handler({source:fakeWindow,origin:'http://localhost:5173',data});
  assert.equal(calls.length,2);
  assert.equal(calls[1].channel,'acopios-glassware-response');
});
