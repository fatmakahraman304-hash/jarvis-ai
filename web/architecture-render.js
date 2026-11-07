/* Native render preference adapter for the pinned editor; no model conversion. */
(function(root){
 'use strict';
 const modes=['technical','design'];
 const pause=()=>new Promise(resolve=>root.setTimeout(resolve,50));
 const settle=()=>new Promise(resolve=>root.requestAnimationFrame(()=>root.requestAnimationFrame(resolve)));
 async function waitFor(win,home,style,timeout,after){
  const until=Date.now()+timeout;
  do{
   const stats=win.jarvisRenderStats;
   if(win.__homeScene?.getHome()===home&&stats?.style===style&&stats.frames>0&&(!after||stats!==after.stats||stats.frames>after.frames))return stats;
   if(Date.now()>until)throw Error('3D görünüm çizilemedi; teknik görünüme dönmeyi dene.');
   await pause();
  }while(true);
 }
 async function setStyle(frame,style,{timeout=45000}={}){
  if(!modes.includes(style))throw Error('Görünüm technical veya design olmalı.');
  const win=frame.contentWindow,preferences=win?.__preferences,home=win?.__homeController?.getHome();
  if(!preferences||!home)throw Error('3D editör henüz hazır değil.');
  const previous=preferences.getView3DStyle(),observer=home.getObserverCamera(),active=home.getCamera();
  const fields=['X','Y','Z','Yaw','Pitch','FieldOfView'];
  const pose=fields.map(key=>observer['get'+key]());
  const restore=()=>{fields.forEach((key,i)=>observer['set'+key](pose[i]));home.setCamera(active);};
  try{
   preferences.setView3DStyle(style);
   const stats=await waitFor(win,home,style,timeout);
   // The native view's initial camera callback runs on its next frame.
   await settle();
   if(win.__homeController.getHome()!==home)throw Error('Görünüm değişirken proje değişti; tekrar dene.');
   restore();
   return {render_style:preferences.getView3DStyle(),frames:stats.frames,shadows:stats.shadows,ambient_occlusion:stats.ao};
  }catch(error){
   const after={stats:win.jarvisRenderStats,frames:win.jarvisRenderStats?.frames};
   preferences.setView3DStyle(previous);
   try{await waitFor(win,home,previous,5000,after);await settle();}catch(_){}
   restore();throw error;
  }
 }
 const api={setStyle};
 if(typeof module==='object'&&module.exports)module.exports=api;else root.JarvisArchitectureRender=api;
})(globalThis);
