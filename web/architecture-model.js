/* Measured model helpers shared by the studio and its regression tests. */
(function(root){
 'use strict';
 const escape=value=>String(value??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&apos;'}[c]));
 function furnitureValues(values){
  const next={name:String(values.name||'').trim().slice(0,100)};
  if(!next.name)throw Error('Nesne adı boş bırakılamaz.');
  for(const key of ['x','y','width','depth','height','angle']){
   const value=Number(values[key]);
   if(String(values[key]).trim()===''||!Number.isFinite(value))throw Error('Bütün ölçüler geçerli sayı olmalı.');
   const min=['width','depth','height'].includes(key)?.02:key==='angle'?-360:-1000;
   const max=['width','depth','height'].includes(key)?100:key==='angle'?360:1000;
   if(value<min||value>max)throw Error(key+' değeri '+min+' ile '+max+' arasında olmalı.');
   next[key]=value;
  }
  return next;
 }
 function planSvg(state){
  const points=[];
  for(const r of state.rooms||[])points.push(...r.points);
  for(const w of state.walls||[])points.push(w.start,w.end);
  // Rotated furniture corners, including objects outside the building footprint.
  for(const f of state.furniture||[]){
   const a=f.angle*Math.PI/180;
   for(const dx of [-f.width/2,f.width/2])for(const dy of [-f.depth/2,f.depth/2])points.push([f.x+dx*Math.cos(a)-dy*Math.sin(a),f.y+dx*Math.sin(a)+dy*Math.cos(a)]);
  }
  if(!points.length)throw Error('Dışa aktarılacak plan henüz yok.');
  if(points.some(p=>!p||p.length<2||!p.every(Number.isFinite)))throw Error('Proje geometrisi geçersiz.');
  const xs=points.map(p=>p[0]),ys=points.map(p=>p[1]);
  const x=Math.min(...xs)-1,y=Math.min(...ys)-1,width=Math.max(...xs)-x+1,height=Math.max(...ys)-y+1;
  const rooms=(state.rooms||[]).map(r=>{
   const cx=r.points.reduce((s,p)=>s+p[0],0)/r.points.length,cy=r.points.reduce((s,p)=>s+p[1],0)/r.points.length;
   return `<polygon points="${r.points.map(p=>p.join(',')).join(' ')}" fill="#edf0e9" stroke="#bdc7c9" stroke-width=".015"/><text x="${cx}" y="${cy}" text-anchor="middle" font-size=".18">${escape(r.name)}</text><text x="${cx}" y="${cy+.25}" text-anchor="middle" font-size=".13">${Number(r.area_m2).toFixed(2)} m²</text>`;
  }).join('');
  const walls=(state.walls||[]).map(w=>`<line x1="${w.start[0]}" y1="${w.start[1]}" x2="${w.end[0]}" y2="${w.end[1]}" stroke="#263f50" stroke-width="${w.thickness}" stroke-linecap="square"/>`).join('');
  const furniture=(state.furniture||[]).map(f=>`<g transform="translate(${f.x} ${f.y}) rotate(${f.angle})"><rect x="${-f.width/2}" y="${-f.depth/2}" width="${f.width}" height="${f.depth}" rx=".03" fill="#96bac7" fill-opacity=".65" stroke="#466577" stroke-width=".025"/><title>${escape(f.name)} · ${f.width} × ${f.depth} m</title></g>`).join('');
  return `<svg xmlns="http://www.w3.org/2000/svg" width="${Math.ceil(width*100)}" height="${Math.ceil(height*100)}" viewBox="${x} ${y} ${width} ${height}" role="img"><title>${escape(state.name||'JARVIS Plan')}</title><desc>Metre tabanlı 2D plan; mobilyalar ölçülü ayak izleriyle gösterilir.</desc><rect x="${x}" y="${y}" width="${width}" height="${height}" fill="white"/><g font-family="system-ui,sans-serif" fill="#263f50">${rooms}${walls}${furniture}<text x="${x+.2}" y="${y+height-.2}" font-size=".16">${escape(state.name||'JARVIS')} · ${Number(state.area_m2||0).toFixed(2)} m² · 1 birim = 1 metre</text></g></svg>`;
 }
 const api={furnitureValues,planSvg};
 if(typeof module==='object'&&module.exports)module.exports=api;else root.JarvisArchitectureModel=api;
})(globalThis);
