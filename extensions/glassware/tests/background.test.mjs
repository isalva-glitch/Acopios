import assert from 'node:assert/strict';
import {test} from 'node:test';

const sender = {id:'acopios-test',frameId:0,url:'http://localhost:5173/acopios/alta'};
let sequence = 0;
async function worker({tabs = [{id:1,url:'https://glassware.fontela.com.ar/budgets/16882'}], result = {url:'budget'}, pending} = {}) {
  let listener;
  let queried = 0;
  let injected = 0;
  globalThis.chrome = {
    runtime: {id:'acopios-test',onMessage:{addListener:fn=>{listener=fn;}}},
    tabs:{query:async query=>{queried++;assert.deepEqual(query,{url:'https://glassware.fontela.com.ar/*'});return tabs;}},
    scripting:{executeScript:async request=>{injected++;assert.equal(request.world,'ISOLATED');
      assert.deepEqual(request.args,['16882']);if(pending)await pending;return [{result}];}}
  };
  await import(`../background.js?case=${sequence++}`);
  return {send:(message,from=sender)=>new Promise(resolve=>listener(message,from,resolve)),
    raw:(message,from,reply)=>listener(message,from,reply),counts:()=>({queried,injected})};
}

test('worker rejects unexpected origins, frames, extension identities and actions',async()=>{
  const w=await worker();
  for(const from of [
    {...sender,url:'https://evil.test/'},
    {...sender,url:'http://localhost:8000/'},
    {...sender,url:'http://localhost.evil.test:5173/'},
    {...sender,frameId:1},
    {...sender,id:'another-extension'}
  ]) assert.equal(w.raw({action:'ping'},from,()=>assert.fail('unexpected reply')),false);
  assert.equal(w.raw({action:'pay'},sender,()=>assert.fail()),false);
  assert.equal(w.raw({action:'collect',budgetId:'../state'},sender,()=>assert.fail()),false);
  assert.deepEqual(w.counts(),{queried:0,injected:0});
});

test('ping does not touch Glassware',async()=>{
  const w=await worker();
  assert.equal((await w.send({action:'ping'})).ok,true);
  assert.deepEqual(w.counts(),{queried:0,injected:0});
});

test('missing signed-in tab returns actionable error',async()=>{
  const w=await worker({tabs:[]});
  const response=await w.send({action:'collect',budgetId:'16882'});
  assert.equal(response.ok,false);assert.match(response.error,/Abrí Glassware/);
  assert.equal(w.counts().injected,0);
});

test('collector errors are returned without accepting partial data',async()=>{
  const w=await worker({result:{error:'Falta el detalle del ítem'}});
  const response=await w.send({action:'collect',budgetId:'16882'});
  assert.equal(response.ok,false);assert.match(response.error,/Falta el detalle/);
  assert.equal(response.data,undefined);
});

test('two overlapping requests use only one collector',async()=>{
  let release;
  const pending=new Promise(resolve=>{release=resolve;});
  const w=await worker({pending});
  const first=w.send({action:'collect',budgetId:'16882'});
  const second=await w.send({action:'collect',budgetId:'16882'});
  assert.equal(second.ok,false);assert.match(second.error,/en curso/);
  release();
  assert.equal((await first).ok,true);
  assert.deepEqual(w.counts(),{queried:1,injected:1});
});
