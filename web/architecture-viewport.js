/* Adapter for the pinned SweetHomeJS integration hooks and public model API. */
(function(root){
 'use strict';
 function bounds(home){
  const min=[Infinity,Infinity,Infinity],max=[-Infinity,-Infinity,-Infinity];let count=0;
  const add=(...points)=>{for(const point of points){count++;point.forEach((n,i)=>{if(!Number.isFinite(n))throw Error('Görünüm sınırlarında geçersiz ölçü var.');min[i]=Math.min(min[i],n);max[i]=Math.max(max[i],n);});}};
  const levelZ=item=>item.getLevel?.()?.getElevation?.()||0;
  for(const wall of home.getWalls()){
   const z=levelZ(wall),h=Math.max(wall.getHeight?.()??home.getWallHeight(),wall.getHeightAtEnd?.()??0);
   for(const [x,y] of wall.getPoints())add([x,y,z],[x,y,z+h]);
  }
  for(const room of home.getRooms())for(const [x,y] of room.getPoints())add([x,y,levelZ(room)]);
  for(const piece of home.getFurniture()){
   if(piece.isVisible?.()===false)continue;
   const z=levelZ(piece)+piece.getElevation();
   for(const [x,y] of piece.getPoints())add([x,y,z],[x,y,z+piece.getHeight()]);
  }
  if(!count)return {min:[-200,-200,0],max:[200,200,280]};
  return {min,max};
 }
 function cameraPose(box,aspect,yaw=Math.PI*.22,pitch=.85){
  if(!Number.isFinite(aspect)||aspect<=0)throw Error('Görünüm boyutu geçersiz.');
  const center=box.min.map((v,i)=>(v+box.max[i])/2),fov=55*Math.PI/180;
  const back=[-Math.sin(yaw)*Math.cos(pitch),-Math.cos(yaw)*Math.cos(pitch),Math.sin(pitch)];
  const right=[Math.cos(yaw),-Math.sin(yaw),0],up=[Math.sin(yaw)*Math.sin(pitch),Math.cos(yaw)*Math.sin(pitch),Math.cos(pitch)];
  const dot=(a,b)=>a.reduce((sum,v,i)=>sum+v*b[i],0);
  let distance=100;
  for(const x of [box.min[0],box.max[0]])for(const y of [box.min[1],box.max[1]])for(const z of [box.min[2],box.max[2]]){
   const d=[x-center[0],y-center[1],z-center[2]];
   distance=Math.max(distance,dot(d,back)+Math.max(Math.abs(dot(d,right))/(Math.tan(fov/2)*aspect),Math.abs(dot(d,up))/Math.tan(fov/2)));
  }
  distance*=1.12;
  return {position:center.map((v,i)=>v+back[i]*distance),center,yaw,pitch,fov,distance};
 }
 async function fit(frame){
  const win=frame.contentWindow,doc=frame.contentDocument;
  if(!win||!doc)throw Error('Editör görünümü henüz hazır değil.');
  // React replaces views after Open/New/Undo. Wait for the view belonging to
  // the current home, then let its initial camera callback complete.
  const until=Date.now()+5000;
  let controller,home,view;
  do{
   await new Promise(resolve=>root.requestAnimationFrame(()=>root.requestAnimationFrame(resolve)));
   controller=win.__homeController;home=controller?.getHome();view=win.__planView;
   if(home&&view?.home===home)break;
   if(Date.now()>until)throw Error('Plan görünümü yeni projeye bağlanamadı.');
  }while(true);
  const plan=doc.querySelector('.sh-plan canvas'),scene=doc.querySelector('[data-testid="view3d"]');
  if(!plan||!scene||!plan.clientWidth||!scene.clientWidth||!scene.clientHeight)throw Error('2D/3D görünüm boyutu okunamadı.');
  const pose=cameraPose(bounds(home),scene.clientWidth/scene.clientHeight);
  view.updatePlanBounds();view.fitHome(plan.clientWidth,plan.clientHeight);
  // The pinned view's fitHome ignores PlanViewport's margin translation.
  // Recenter using its actual public model-to-pixel transform.
  const viewport=view.getViewport(),box=viewport.getPlanBounds();
  viewport.setPan(viewport.getPanX()+plan.clientWidth/2-(viewport.convertXModelToPixel(box.minX)+viewport.convertXModelToPixel(box.maxX))/2,
   viewport.getPanY()+plan.clientHeight/2-(viewport.convertYModelToPixel(box.minY)+viewport.convertYModelToPixel(box.maxY))/2);
  view.paint();
  controller.getHomeController3D().viewFromObserver();
  const camera=home.getObserverCamera();
  camera.setX(pose.position[0]);camera.setY(pose.position[1]);camera.setZ(pose.position[2]);
  camera.setYaw(pose.yaw);camera.setPitch(pose.pitch);camera.setFieldOfView(pose.fov);
  return {scale:view.getScale(),camera:pose,viewport:{width:scene.clientWidth,height:scene.clientHeight}};
 }
 const api={bounds,cameraPose,fit};
 if(typeof module==='object'&&module.exports)module.exports=api;else root.JarvisArchitectureViewport=api;
})(globalThis);
