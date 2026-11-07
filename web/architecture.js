/* Public SH3D bridge: native project operations; no screenshot or external account. */
(function(){
 const JV=window.JV,frame=document.getElementById('architecture-frame'),status=document.getElementById('architecture-status');
 const client=crypto.randomUUID();let running=false,loaded=false,revision=0,lastSave=0,savePromise=null,initPromise=null;
 const headers=()=>({'x-token':JV.token||''});
 const api=async(path,options={})=>{const r=await fetch('/api/architecture/'+path,{...options,headers:{...headers(),...(options.headers||{})}});if(!r.ok){let e;try{e=await r.json();}catch(_){e={error:'HTTP '+r.status};}throw Error(e.error||'HTTP '+r.status);}return r;};
 const json=async(path,body)=>{const r=await api(path,body?{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(body)}:{});return r.json();};
 const bridge=()=>frame.contentWindow && frame.contentWindow.jarvisDesigner;
 async function init(){
  if(loaded)return;
  if(initPromise)return initPromise;
  initPromise=(async()=>{
   frame.src='/designer/';status.textContent='2D/3D editör ve model kataloğu yükleniyor…';
   const end=Date.now()+30000;while(!bridge()){if(Date.now()>end)throw Error('Editör yüklenemedi. WebGL ve yerel dosyaları kontrol et.');await new Promise(r=>setTimeout(r,150));}
   const info=await json('info');revision=info.revision;
   const r=await api('project');if(r.status!==204)await bridge().load(new Uint8Array(await r.arrayBuffer()));
   const doc=frame.contentDocument;
   if(doc&&!doc.getElementById('jarvis-designer-theme')){const link=doc.createElement('link');link.id='jarvis-designer-theme';link.rel='stylesheet';link.href='/static/designer-theme.css';doc.head.appendChild(link);}
   loaded=true;await refreshHistory();status.textContent='Hazır · metre birimi · 2D ve 3D birlikte';
  })();try{await initPromise;}catch(e){status.textContent=e.message;initPromise=null;throw e;}
 }
 function save(){
  if(savePromise)return savePromise;
  savePromise=(async()=>{
   await init();
   const bytes=new Uint8Array(await bridge().save()),report=bridge().state();
   const r=await api('save',{method:'POST',headers:{'Content-Type':'application/octet-stream','x-revision':String(revision),'x-project-report':JSON.stringify({counts:report.counts,area_m2:report.area_m2})},body:bytes});
   const saved=await r.json();revision=saved.revision;lastSave=Date.now();
   // A manual edit may happen while the network write is pending. Only clear
   // the dirty flag when the model still serializes to the saved snapshot.
   const current=new Uint8Array(await bridge().save());
   const unchanged=current.length===bytes.length&&current.every((value,i)=>value===bytes[i]);
   if(unchanged)bridge().saved();
   status.textContent='Yerel kayıt · sürüm '+revision+' · '+report.counts.rooms+' oda · '+report.area_m2.toFixed(2)+' m²'+(unchanged?'':' · yeni değişiklikler kayıt bekliyor');
   await refreshHistory();return saved;
  })().finally(()=>{savePromise=null;});
  return savePromise;
 }
 async function poll(){
  if(running||document.hidden)return;running=true;
  try{
   // Complete an autosave before mutating the scene for the next command.
   if(savePromise)await savePromise;
   const next=await json('command?client='+encodeURIComponent(client));
   if(next.busy){if(loaded)status.textContent='Başka JARVIS penceresi bu projeyi düzenliyor.';return;}
   if(next.job){
    const job=next.job;let result,error;
    try{JV.setView('design');await init();if(job.command.op==='restore'){
     // Preserve pending manual edits before replacing the model. save_project
     // retains the previous file as a new history entry on the next save.
     const snapshot=await api('version?revision='+encodeURIComponent(job.command.revision));
     const bytes=new Uint8Array(await snapshot.arrayBuffer());
     await save();const before=await bridge().save();
     try{await bridge().load(bytes);}
     catch(e){await bridge().load(before);throw e;}
     result=bridge().state();await save();
    }else{result=await bridge().run(job.command);if(['apply','undo','redo'].includes(job.command.op))await save();}}
    catch(e){console.error('[architecture] command failed: '+job.command.op, e && (e.stack || e.message || e));error=e.message;status.textContent='İşlem uygulanmadı / kayıt başarısız: '+error;}
    await json('ack',{client,id:job.id,result,error});
   }else if(loaded&&Date.now()-lastSave>4000&&bridge().modified())await save();
  }catch(e){status.textContent=e.message;}finally{running=false;}
 }
 JV.architecture={open:()=>init().catch(e=>{status.textContent=e.message;}),save,state:()=>bridge()?.state(true)};
 const expand=document.getElementById('architecture-expand');
 expand.onclick=()=>{
  const active=document.body.classList.toggle('architecture-expanded');
  expand.setAttribute('aria-pressed',String(active));
  expand.textContent=active?'⊟ Küçült':'⛶ Tam ekran';
  frame.contentWindow?.dispatchEvent(new Event('resize'));
 };
 document.addEventListener('keydown',e=>{
  if(e.key==='Escape'&&document.body.classList.contains('architecture-expanded')){
   document.body.classList.remove('architecture-expanded');
   expand.setAttribute('aria-pressed','false');expand.textContent='⛶ Tam ekran';
  }
 });
 const studioMetrics=document.getElementById('studio-metrics');
 const studioHouse=document.getElementById('studio-house');
 const studioButtons=['studio-house','studio-undo','studio-redo','studio-top','studio-walk','studio-svg','studio-restore'].map(id=>document.getElementById(id));
 const updateMetrics=()=>{try{const report=bridge()?.state();if(report?.counts)studioMetrics.textContent=[report.counts.rooms+' oda',report.counts.walls+' duvar',report.counts.furniture+' eşya',Number(report.area_m2||0).toFixed(1)+' m²'].join(' · ');}catch(_){}};
 let studioBusy=false;
 async function studioRun(op,args={}){
  if(studioBusy)return false;studioBusy=true;studioButtons.forEach(b=>b.disabled=true);
  status.textContent='JARVIS tasarımı uyguluyor…';
  try{await init();const r=await json('run',{op,args});if(!r?.verified)throw Error('Tasarım işlemi doğrulanamadı');updateMetrics();status.textContent='Tasarım uygulandı ve kaydedildi.';refreshInspector();return true;}
  catch(e){status.textContent='Tasarım hatası: '+e.message;console.warn('[studio] '+op,e);return false;}
  finally{studioBusy=false;studioButtons.forEach(b=>b.disabled=false);}
 }
 const presets={compact:{width:8,depth:9,bedrooms:1,bathrooms:1},family:{width:10,depth:12,bedrooms:2,bathrooms:1},villa:{width:16,depth:18,bedrooms:4,bathrooms:2}};
 const preset=document.getElementById('studio-preset');
 preset.onchange=()=>{
  const p=presets[preset.value];if(!p)return;
  for(const [key,value] of Object.entries(p)){
   const id=key==='bedrooms'?'studio-bedrooms':key==='bathrooms'?'studio-bathrooms':'studio-'+key;
   document.getElementById(id).value=String(value);
  }
  studioMetrics.textContent='Şablon hazır · '+p.width*p.depth+' m² dış alan';
 };
 for(const id of ['studio-width','studio-depth','studio-bedrooms','studio-bathrooms']){
  document.getElementById(id).addEventListener('change',()=>{preset.value='custom';});
 }
 studioHouse.onclick=async()=>{
  const width=Number(document.getElementById('studio-width').value),depth=Number(document.getElementById('studio-depth').value);
  const bedrooms=Number(document.getElementById('studio-bedrooms').value),bathrooms=Number(document.getElementById('studio-bathrooms').value);
  if(!Number.isFinite(width)||!Number.isFinite(depth)||width<7||width>40||depth<7||depth>40){status.textContent='Ölçüler 7 ile 40 metre arasında olmalı.';return;}
  // Loading the saved project must precede the replacement confirmation.
  try{await init();}catch(e){status.textContent=e.message;return;}
  const current=bridge().state();
  if(Object.values(current?.counts||{}).some(count=>count>0)&&!window.confirm('Mevcut çizimin yerine yeni bir ev planı oluşturulsun mu?'))return;
  return studioRun('house',{width,depth,bedrooms,bathrooms,name:'JARVIS '+width+' × '+depth+' m',replace:true});
 };
 const inspector=document.getElementById('studio-inspector');
 const objects=document.getElementById('studio-object');
 const properties=document.getElementById('studio-properties');
 const objectStatus=document.getElementById('studio-object-status');
 let inspectorItems=[];
 function fillInspector(){
  const selected=inspectorItems.find(item=>item.id===objects.value);
  properties.querySelector('fieldset').disabled=!selected;
  if(!selected){objectStatus.textContent='Varlık listesinden düzenlenecek mobilyayı seç.';return;}
  for(const key of ['name','x','y','width','depth','height','angle'])properties.elements.namedItem(key).value=selected[key];
  objectStatus.textContent=selected.id;
 }
 function refreshInspector(){
  if(inspector.hidden||!loaded)return;
  const selected=objects.value;
  inspectorItems=bridge().state(true).furniture||[];
  objects.replaceChildren(new Option('Mobilya seç', ''));
  for(const [i,item] of inspectorItems.entries())objects.add(new Option((i+1)+'. '+item.name,item.id));
  objects.value=inspectorItems.some(item=>item.id===selected)?selected:'';
  fillInspector();
 }
 objects.onchange=fillInspector;
 document.getElementById('studio-inspect').onclick=async()=>{
  inspector.hidden=!inspector.hidden;
  document.getElementById('studio-inspect').setAttribute('aria-expanded',String(!inspector.hidden));
  if(!inspector.hidden){try{await init();refreshInspector();}catch(e){objectStatus.textContent=e.message;}}
  frame.contentWindow?.dispatchEvent(new Event('resize'));
 };
 properties.onsubmit=async e=>{
  e.preventDefault();
  if(studioBusy)return;
  const id=objects.value;
  try{
   // Re-read IDs so a deleted object cannot be replaced by a stale selection.
   if(!bridge().state(true).furniture.some(item=>item.id===id))throw Error('Nesne artık projede yok; listeyi yenile.');
   const values=window.JarvisArchitectureModel.furnitureValues(Object.fromEntries(new FormData(properties)));
   properties.querySelector('fieldset').disabled=true;
   const ok=await studioRun('apply',{operations:[{kind:'update',id,values}]});
   objectStatus.textContent=ok?'Ölçüler doğrulandı ve kaydedildi.':'İşlem tamamlanmadı; ayrıntı üst durum çubuğunda.';
  }catch(error){objectStatus.textContent=error.message;}
  finally{properties.querySelector('fieldset').disabled=!objects.value;}
 };
 document.getElementById('studio-top').onclick=()=>studioRun('apply',{operations:[{kind:'camera',mode:'top'}]});
 document.getElementById('studio-walk').onclick=()=>studioRun('apply',{operations:[{kind:'camera',mode:'walk'}]});
 document.getElementById('studio-svg').onclick=async()=>{
  try{
   await init();
   const svg=window.JarvisArchitectureModel.planSvg(bridge().state(true));
   const url=URL.createObjectURL(new Blob([svg],{type:'image/svg+xml;charset=utf-8'}));
   const a=document.createElement('a');a.href=url;a.download='JARVIS-Plan.svg';a.click();setTimeout(()=>URL.revokeObjectURL(url),1000);
   status.textContent='Vektörel 2D plan indirildi · mobilyalar ölçülü ayak izleriyle gösterilir.';
  }catch(e){status.textContent=e.message;}
 };
 const history=document.getElementById('studio-history');
 async function refreshHistory(){
  try{
   const rows=await json('history'),selected=history.value;
   history.replaceChildren(new Option('Kayıtlı sürümler',''));
   for(const row of rows)history.add(new Option('Sürüm '+row.revision+' · '+new Date(row.saved_at*1000).toLocaleString('tr-TR'),String(row.revision)));
   history.value=rows.some(row=>String(row.revision)===selected)?selected:'';
  }catch(e){status.textContent=e.message;}
 }
 // Populate at load/save, rather than replacing options during native focus.
 document.getElementById('studio-restore').onclick=async()=>{
  if(!history.value){status.textContent='Önce kayıtlı bir sürüm seç.';return;}
  if(!window.confirm('Proje sürüm '+history.value+' ile değiştirilsin mi? Mevcut çizim ayrıca yedeklenecek.'))return;
  await studioRun('restore',{revision:Number(history.value)});await refreshHistory();
 };
 document.getElementById('studio-undo').onclick=()=>studioRun('undo');
 document.getElementById('studio-redo').onclick=()=>studioRun('redo');
 setInterval(()=>{if(loaded&&document.body.classList.contains('view-design')){updateMetrics();if(!inspector.hidden&&!inspector.contains(document.activeElement))refreshInspector();}},3000);
 document.getElementById('architecture-close').onclick=()=>JV.setView('core');
 document.getElementById('architecture-download').onclick=async()=>{try{await save();const r=await api('project');const url=URL.createObjectURL(await r.blob());const a=document.createElement('a');a.href=url;a.download='JARVIS-Proje.sh3d';a.click();setTimeout(()=>URL.revokeObjectURL(url),1000);}catch(e){status.textContent=e.message;}};
 setInterval(poll,400);
})();
