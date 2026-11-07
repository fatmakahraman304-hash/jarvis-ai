/* The first model command must bootstrap the editor; a save must precede ACK. */
const assert = require('node:assert/strict');
const vm = require('node:vm');
const fs = require('node:fs');
const path = require('node:path');
async function main() {
  let poll, queued, saved = false, fail = false;
  const events = [], nodes = {};
  const engine = {
    run: async c => { events.push('run:'+c.op); if(fail)throw Error('Invalid operation'); return {counts:{rooms:1},area_m2:20}; },
    save: async () => new Uint8Array([80,75]),
    state: () => ({counts:{rooms:1},area_m2:20}),
    saved: () => {saved=true;}, modified:()=>false
  };
  const frame = {contentWindow:{}};
  Object.defineProperty(frame,'src',{set(value){assert.equal(value,'/designer/');frame.contentWindow.jarvisDesigner=engine;}});
  nodes['architecture-frame']=frame;
  for(const name of ['architecture-status','architecture-close','architecture-download','architecture-expand','studio-metrics','studio-house','studio-undo','studio-redo','studio-width','studio-depth','studio-bedrooms','studio-bathrooms','studio-preset'])nodes[name]={textContent:'',setAttribute:()=>{},addEventListener:()=>{},disabled:false,value:'2'};
  const document = {hidden:false,getElementById:id=>nodes[id],addEventListener:()=>{},body:{classList:{contains:()=>false,toggle:()=>false,remove:()=>{}}}};
  const JV = {token:'',setView:mode=>{events.push('view:'+mode);JV.architecture.open();}};
  const ctx = {window:{JV},document,crypto:require('node:crypto'),Uint8Array,console,setTimeout,
    setInterval:fn=>{poll=fn;},fetch:async(url,options={})=>{
      if(url.includes('command?')) {const job=queued;queued=null;return Response.json({job});}
      if(url.endsWith('/info'))return Response.json({revision:0});
      if(url.endsWith('/project'))return new Response(null,{status:204});
      if(url.endsWith('/save')){events.push('save');return Response.json({revision:1});}
      if(url.endsWith('/ack')){events.push('ack');events.push(JSON.parse(options.body));return Response.json({ok:true});}
      throw Error('Unexpected URL '+url);
    }};
  vm.runInNewContext(fs.readFileSync(path.join(__dirname,'../web/architecture.js'),'utf8'),ctx);
  queued={id:'first',command:{op:'catalog'}};
  await poll();
  assert.deepEqual(events.slice(0,3),['view:design','run:catalog','ack']);
  assert.equal(events[3].id,'first');assert.equal(events[3].error,undefined);
  events.length=0;
  queued={id:'edit',command:{op:'apply',operations:[]}};
  await poll();
  assert.deepEqual(events.slice(0,4),['view:design','run:apply','save','ack']);assert(saved);
  events.length=0;fail=true;
  queued={id:'bad',command:{op:'apply',operations:[]}};
  await poll();
  assert(!events.includes('save'));assert.equal(events.at(-1).error,'Invalid operation');
  events.length=0;document.hidden=true;
  queued={id:'hidden',command:{op:'state'}};await poll();assert.equal(events.length,0);assert(queued);
  console.log('Architecture bridge: cold command bootstrap, save before ACK, failed operation and hidden-tab lease passed.');
}
main().catch(error=>{console.error(error);process.exitCode=1;});
