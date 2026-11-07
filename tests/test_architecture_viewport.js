const assert=require('node:assert/strict');
const {bounds,cameraPose}=require('../web/architecture-viewport.js');
const box={min:[-500,-600,-250],max:[900,1200,650]};
for(const aspect of [.2,.6,1,2,4]){
 const pose=cameraPose(box,aspect),{yaw,pitch,position,fov}=pose;
 const back=[-Math.sin(yaw)*Math.cos(pitch),-Math.cos(yaw)*Math.cos(pitch),Math.sin(pitch)];
 const right=[Math.cos(yaw),-Math.sin(yaw),0],up=[Math.sin(yaw)*Math.sin(pitch),Math.cos(yaw)*Math.sin(pitch),Math.cos(pitch)];
 const dot=(a,b)=>a.reduce((n,v,i)=>n+v*b[i],0);
 // Every corner must lie inside the actual perspective frustum, with padding.
 for(const x of [box.min[0],box.max[0]])for(const y of [box.min[1],box.max[1]])for(const z of [box.min[2],box.max[2]]){
  const v=[x-position[0],y-position[1],z-position[2]],depth=-dot(v,back);
  assert(depth>0);assert(Math.abs(dot(v,right))/(depth*Math.tan(fov/2)*aspect)<.96);assert(Math.abs(dot(v,up))/(depth*Math.tan(fov/2))<.96);
 }
}
assert.throws(()=>cameraPose(box,0));
const points=()=>[[0,0],[100,0],[100,200],[0,200]];
const home={getWalls:()=>[{getPoints:points,getHeight:()=>280,getLevel:()=>({getElevation:()=>300})}],getRooms:()=>[],getFurniture:()=>[{getPoints:()=>[[-200,-100],[-100,-100],[-100,0],[-200,0]],getElevation:()=>20,getHeight:()=>50}],getWallHeight:()=>250};
assert.deepEqual(bounds(home),{min:[-200,-100,20],max:[100,200,580]});
home.getFurniture=()=>[];home.getWalls=()=>[];assert.deepEqual(bounds(home),{min:[-200,-200,0],max:[200,200,280]});
console.log('Architecture viewport: perspective containment across aspect ratios, negative coordinates and elevated floors passed.');
