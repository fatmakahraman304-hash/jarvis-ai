/* Public SH3D bridge: native project operations; no screenshot or external account. */
(function(){
 const JV=window.JV,frame=document.getElementById('architecture-frame'),status=document.getElementById('architecture-status');
 const client=crypto.randomUUID();let running=false,loaded=false,revision=0,lastSave=0,saveBusy=false,initPromise=null;
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
   loaded=true;status.textContent='Hazır · metre birimi · 2D ve 3D birlikte';
  })();try{await initPromise;}catch(e){status.textContent=e.message;initPromise=null;throw e;}
 }
 async function save(){
  if(saveBusy)return;saveBusy=true;
  try{
   const bytes=new Uint8Array(await bridge().save()),report=bridge().state();
   const r=await api('save',{method:'POST',headers:{'Content-Type':'application/octet-stream','x-revision':String(revision),'x-project-report':JSON.stringify({counts:report.counts,area_m2:report.area_m2})},body:bytes});
   const saved=await r.json();revision=saved.revision;lastSave=Date.now();bridge().saved();status.textContent='Yerel kayıt · sürüm '+revision+' · '+report.counts.rooms+' oda · '+report.area_m2.toFixed(2)+' m²';
  }finally{saveBusy=false;}
 }
 async function poll(){
  if(running||document.hidden)return;running=true;
  try{
   const next=await json('command?client='+encodeURIComponent(client));
   if(next.busy){if(loaded)status.textContent='Başka JARVIS penceresi bu projeyi düzenliyor.';return;}
   if(next.job){
    const job=next.job;let result,error;
    try{JV.setView('design');await init();result=await bridge().run(job.command);if(['apply','undo','redo'].includes(job.command.op))await save();}
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
 const studioButtons=[studioHouse,document.getElementById('studio-undo'),document.getElementById('studio-redo')];
 const updateMetrics=()=>{try{const report=bridge()?.state();if(report?.counts)studioMetrics.textContent=[report.counts.rooms+' oda',report.counts.walls+' duvar',report.counts.furniture+' eşya',Number(report.area_m2||0).toFixed(1)+' m²'].join(' · ');}catch(_){}};
 let studioBusy=false;
 async function studioRun(op,args={}){
  if(studioBusy)return;studioBusy=true;studioButtons.forEach(b=>b.disabled=true);
  status.textContent='JARVIS tasarımı uyguluyor…';
  try{await init();const r=await json('run',{op,args});if(!r?.result?.verified)throw Error('Tasarım işlemi doğrulanamadı');updateMetrics();status.textContent='Tasarım uygulandı ve kaydedildi.';}
  catch(e){status.textContent='Tasarım hatası: '+e.message;console.warn('[studio] '+op,e);}
  finally{studioBusy=false;studioButtons.forEach(b=>b.disabled=false);}
 }
 studioHouse.onclick=()=>{
  const width=Number(document.getElementById('studio-width').value),depth=Number(document.getElementById('studio-depth').value);
  const bedrooms=Number(document.getElementById('studio-bedrooms').value),bathrooms=Number(document.getElementById('studio-bathrooms').value);
  if(!Number.isFinite(width)||!Number.isFinite(depth)||width<7||width>40||depth<7||depth>40){status.textContent='Ölçüler 7 ile 40 metre arasında olmalı.';return;}
  const current=bridge()?.state();
  if(current?.counts?.walls>0&&!window.confirm('Mevcut çizimin yerine yeni bir ev planı oluşturulsun mu?'))return;
  studioRun('house',{width,depth,bedrooms,bathrooms,name:'JARVIS '+width+' × '+depth+' m',replace:true});
 };
 document.getElementById('studio-undo').onclick=()=>studioRun('undo');
 document.getElementById('studio-redo').onclick=()=>studioRun('redo');
 setInterval(()=>{if(loaded&&document.body.classList.contains('view-design'))updateMetrics();},3000);
 document.getElementById('architecture-close').onclick=()=>JV.setView('core');
 document.getElementById('architecture-download').onclick=async()=>{try{await save();const r=await api('project');const url=URL.createObjectURL(await r.blob());const a=document.createElement('a');a.href=url;a.download='JARVIS-Proje.sh3d';a.click();setTimeout(()=>URL.revokeObjectURL(url),1000);}catch(e){status.textContent=e.message;}};
 setInterval(poll,400);
})();
