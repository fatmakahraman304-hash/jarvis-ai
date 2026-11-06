/* Preferences and local schematic floor-plan workspace. */
(function () {
  const JV=window.JV; if(!JV)return;
  const $=s=>document.querySelector(s), ns='http://www.w3.org/2000/svg';
  let plan={units:'m',rooms:[],furniture:[]},catalog={},pid='',dirty=false,currentRevision=0;
  const api=(action,args={})=>JV.api('/api/architecture',{body:{action,...args}}).then(r=>{if(r.error)throw Error(r.error);return r;});
  const output=t=>$('#adv-result').textContent=typeof t==='string'?t:JSON.stringify(t,null,2);
  const guard=fn=>async()=>{try{await fn();}catch(e){output(e.message);}};
  function shape(tag,attrs){const e=document.createElementNS(ns,tag);for(const[k,v]of Object.entries(attrs))e.setAttribute(k,v);return e;}
  function draw(){
    const svg=$('#plan-preview');svg.replaceChildren();
    const pts=plan.rooms.flatMap(r=>r.points);
    if(!pts.length){svg.setAttribute('viewBox','0 0 10 8');return;}
    const xs=pts.map(p=>p[0]),ys=pts.map(p=>p[1]),x=Math.min(...xs)-1,y=Math.min(...ys)-1;
    svg.setAttribute('viewBox',`${x} ${y} ${Math.max(...xs)-x+1} ${Math.max(...ys)-y+1}`);
    for(const room of plan.rooms){
      svg.append(shape('polygon',{points:room.points.map(p=>p.join(',')).join(' '),fill:'#eef7ff',stroke:'#135','stroke-width':'.06'}));
      const t=shape('text',{x:room.points[0][0]+.15,y:room.points[0][1]+.4,'font-size':'.22',fill:'#123'});t.textContent=room.name||room.id;svg.append(t);
    }
    for(const item of plan.furniture){const c=catalog[item.kind];if(c)svg.append(shape('rect',{x:item.x,y:item.y,width:c.width,height:c.depth,fill:'#b7dccd',stroke:'#345','stroke-width':'.025'}));}
    const rooms=$('#plan-room');rooms.replaceChildren();for(const r of plan.rooms){const o=document.createElement('option');o.value=r.id;o.textContent=r.name||r.id;rooms.append(o);}
  }
  JV.applyPreferences=()=>{
    const pref=JV.settings.theme||'dark';document.documentElement.dataset.theme=pref==='system'?(matchMedia('(prefers-color-scheme: light)').matches?'light':'dark'):pref;
    if($('#adv-theme'))$('#adv-theme').value=pref;
    if($('#adv-length'))$('#adv-length').value=JV.settings.response_length||'normal';
  };
  $('#adv-theme').onchange=e=>JV.saveSettings({theme:e.target.value});
  $('#adv-length').onchange=e=>JV.saveSettings({response_length:e.target.value});
  matchMedia('(prefers-color-scheme: light)').addEventListener('change',()=>JV.applyPreferences());
  $('#plan-add-room').onclick=guard(async()=>{
    const w=Number($('#plan-width').value),d=Number($('#plan-depth').value),x=Number($('#plan-x').value),y=Number($('#plan-y').value);
    if(!(w>0&&d>0))throw Error('Genişlik ve derinlik pozitif olmalı.');
    const next=JSON.parse(JSON.stringify(plan));next.rooms.push({id:'r_'+Date.now(),name:$('#plan-name').value||'Oda',points:[[x,y],[x+w,y],[x+w,y+d],[x,y+d]]});
    const report=await api('analyze',{document:next});plan=next;dirty=true;draw();output(report);
  });
  $('#plan-add-item').onclick=guard(async()=>{
    if(!plan.rooms.length)throw Error('Önce oda ekle.');
    const next=JSON.parse(JSON.stringify(plan));next.furniture.push({id:'f_'+Date.now(),room:$('#plan-room').value,kind:$('#plan-kind').value,x:Number($('#item-x').value),y:Number($('#item-y').value)});
    const report=await api('analyze',{document:next});plan=next;dirty=true;draw();output(report);
  });
  $('#plan-save').onclick=guard(async()=>{const r=await api('save',{project_id:$('#plan-id').value.trim(),document:plan});pid=r.project_id;currentRevision=r.revision;dirty=false;$('#plan-id').value=pid;output(`Kaydedildi: ${pid}, sürüm ${r.revision}`);});
  $('#plan-load').onclick=guard(async()=>{const r=await api('load',{project_id:$('#plan-id').value,revision:Number($('#plan-revision').value)||0});plan=r.document;pid=r.project_id;currentRevision=r.revision;dirty=false;draw();output(`Sürüm ${r.revision} açıldı.`);});
  $('#plan-history').onclick=guard(async()=>output(await api('history',{project_id:$('#plan-id').value})));
  $('#plan-list').onclick=guard(async()=>output(await api('list')));
  $('#plan-analyze').onclick=guard(async()=>output(await api('analyze',{document:plan})));
  $('#plan-export').onclick=guard(async()=>{if(!pid||dirty)throw Error('Önce değişiklikleri yeni sürüm olarak kaydet.');const r=await api('export',{project_id:pid,format:$('#plan-format').value,revision:currentRevision});output('Dosya hazır: ');const a=document.createElement('a');a.textContent='İNDİR';a.href='/api/files/download?path='+encodeURIComponent(r.path)+'&token='+encodeURIComponent(JV.token||'');a.target='_blank';$('#adv-result').append(a);});
  $('#offline-save').onclick=guard(async()=>{await JV.api('/api/keys',{body:{VOSK_MODEL_PATH:$('#offline-path').value}});output('Model yolu kaydedildi. SES sekmesinden Vosk seçebilirsin.');});
  $('#adv-status').onclick=guard(async()=>{const r=await JV.api('/api/features');const names={implemented:'Uygulandı',partial:'Kısmi',pending:'Bekliyor',requires_setup:'Kurulum/test gerekli',requires_hardware:'Donanım/ortam gerekli'};output(r.features.map(f=>`${f.id}. ${f.feature} — ${names[f.status]}\n${f.detail}`).join('\n\n'));});
  $('#adv-metrics').onclick=guard(async()=>{output(await JV.api('/api/diagnostics'));});
  const tab=$('.s-tabs button[data-tab="advanced"]');tab.addEventListener('click',guard(async()=>{
    if(Object.keys(catalog).length)return;
    catalog=(await api('catalog')).furniture;for(const k of Object.keys(catalog)){const o=document.createElement('option');o.value=k;o.textContent=k;$('#plan-kind').append(o);}
  }));
  JV.applyPreferences();draw();
})();
