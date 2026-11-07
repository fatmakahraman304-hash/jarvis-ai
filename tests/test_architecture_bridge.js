/* The first model command must bootstrap the editor; a save must precede ACK. */
const assert = require('node:assert/strict');
const vm = require('node:vm');
const fs = require('node:fs');
const path = require('node:path');
async function main() {
  let poll, queued, saved = false, fail = false, saveGate = null, failSave = false, snapshot = [80,75];
  const events = [], nodes = {};
  const engine = {
    run: async c => { events.push('run:'+c.op); if(fail)throw Error('Invalid operation'); return {counts:{rooms:1},area_m2:20}; },
    save: async () => new Uint8Array(snapshot),
    state: () => ({counts:{rooms:1},area_m2:20}),
    saved: () => {saved=true;}, modified:()=>false
  };
  const frame = {contentWindow:{}};
  Object.defineProperty(frame,'src',{set(value){assert.equal(value,'/designer/');frame.contentWindow.jarvisDesigner=engine;}});
  nodes['architecture-frame']=frame;
  for(const name of ['architecture-status','architecture-close','architecture-download','architecture-expand','studio-metrics','studio-house','studio-undo','studio-redo','studio-width','studio-depth','studio-bedrooms','studio-bathrooms','studio-preset','studio-inspector','studio-inspect','studio-object','studio-properties','studio-object-status','studio-top','studio-walk','studio-svg','studio-history','studio-restore','studio-fit','studio-history-refresh','studio-render-style'])nodes[name]={textContent:'',setAttribute:()=>{},addEventListener:()=>{},disabled:false,value:'2'};
  nodes['studio-inspector'].hidden=true;
  nodes['studio-history'].replaceChildren=()=>{};nodes['studio-history'].add=()=>{};
  const document = {hidden:false,getElementById:id=>nodes[id],addEventListener:()=>{},body:{classList:{contains:()=>false,toggle:()=>false,remove:()=>{}}}};
  const JV = {token:'',setView:mode=>{events.push('view:'+mode);JV.architecture.open();}};
  const ctx = {Option:function(text,value){this.text=text;this.value=value;},window:{JV,JarvisArchitectureViewport:{fit:async()=>({scale:1})}},clearTimeout,document,crypto:require('node:crypto'),Uint8Array,console,setTimeout,
    setInterval:fn=>{poll=fn;},fetch:async(url,options={})=>{
      if(url.includes('command?')) {const job=queued;queued=null;return Response.json({job});}
      if(url.endsWith('/history'))return Response.json([]);
      if(url.endsWith('/info'))return Response.json({revision:0});
      if(url.endsWith('/project'))return new Response(null,{status:204});
      if(url.endsWith('/save')){events.push('save');if(failSave)return Response.json({error:'Disk write failed'},{status:400});if(saveGate)await saveGate;return Response.json({revision:1});}
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
  // A second caller must wait for the exact same in-flight save, and an edit
  // during the network write must remain dirty for the next autosave.
  fail=false;saved=false;events.length=0;
  let finishSave;saveGate=new Promise(resolve=>{finishSave=resolve;});
  const firstSave=JV.architecture.save();
  const secondSave=JV.architecture.save();
  assert.equal(firstSave,secondSave,'Save callers must share completion');
  await new Promise(resolve=>setTimeout(resolve,0));
  assert.deepEqual(events,['save']);
  snapshot=[80,75,1];finishSave();await secondSave;
  assert.equal(saved,false,'Concurrent manual edit must remain dirty');
  saveGate=null;await JV.architecture.save();assert(saved);
  // A disk error must produce an error ACK, never a successful operation.
  events.length=0;saved=false;failSave=true;
  queued={id:'disk-error',command:{op:'apply',operations:[]}};await poll();
  assert.equal(events.at(-1).error,'Disk write failed');assert.equal(saved,false);
  failSave=false;await JV.architecture.save();assert(saved,'Failed save must be retryable');
  events.length=0;document.hidden=true;
  queued={id:'hidden',command:{op:'state'}};await poll();assert.equal(events.length,0);assert(queued);
  // Starting a new plan from a cold page must restore the saved drawing
  // before checking whether replacement requires confirmation.
  events.length=0;document.hidden=false;
  let loadedProject=false,confirmed=false;
  const previousState=engine.state;
  engine.state=()=>({counts:loadedProject?{walls:4,rooms:1,furniture:1}:{walls:0,rooms:0,furniture:0},area_m2:20});
  engine.load=async()=>{events.push('load');loadedProject=true;};
  for(const [key,value] of Object.entries({'studio-width':'10','studio-depth':'12','studio-bedrooms':'2','studio-bathrooms':'1'}))nodes[key].value=value;
  const coldFetch=ctx.fetch;
  const cold={...ctx,window:{JV,JarvisArchitectureViewport:{fit:async()=>({scale:1})},confirm:()=>{assert(loadedProject,'Replacement checked before saved project loaded');confirmed=true;return false;}},fetch:async(url,options)=>{
    if(url.endsWith('/project'))return new Response(new Uint8Array([80,75]));
    return coldFetch(url,options);
  }};
  vm.runInNewContext(fs.readFileSync(path.join(__dirname,'../web/architecture.js'),'utf8'),cold);
  await nodes['studio-house'].onclick();
  assert(confirmed);assert(events.includes('load'));assert(!events.some(e=>typeof e==='string'&&e.startsWith('run:')));
  engine.state=previousState;
  console.log('Architecture bridge: cold command bootstrap, save before ACK, failed operation, shared save completion, dirty edit preservation and hidden-tab lease passed.');
}
main().catch(error=>{console.error(error);process.exitCode=1;});
