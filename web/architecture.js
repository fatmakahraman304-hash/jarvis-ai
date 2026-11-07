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
    catch(e){error=e.message;status.textContent='İşlem uygulanmadı / kayıt başarısız: '+error;}
    await json('ack',{client,id:job.id,result,error});
   }else if(loaded&&Date.now()-lastSave>4000&&bridge().modified())await save();
  }catch(e){status.textContent=e.message;}finally{running=false;}
 }
 JV.architecture={open:()=>init().catch(e=>{status.textContent=e.message;}),save,state:()=>bridge()?.state(true)};
 document.getElementById('architecture-close').onclick=()=>JV.setView('core');
 document.getElementById('architecture-download').onclick=async()=>{try{await save();const r=await api('project');const url=URL.createObjectURL(await r.blob());const a=document.createElement('a');a.href=url;a.download='JARVIS-Proje.sh3d';a.click();setTimeout(()=>URL.revokeObjectURL(url),1000);}catch(e){status.textContent=e.message;}};
 setInterval(poll,400);
})();
