const assert=require('node:assert/strict');
const {furnitureValues,planSvg}=require('../web/architecture-model.js');
const values={name:'  Sofa  ',x:'-1.25',y:'3',width:'2',depth:'.8',height:'.9',angle:'45'};
assert.deepEqual(furnitureValues(values),{name:'Sofa',x:-1.25,y:3,width:2,depth:.8,height:.9,angle:45});
for(const patch of [{x:''},{width:'0'},{angle:'361'},{height:'NaN'},{name:''}])assert.throws(()=>furnitureValues({...values,...patch}));
const plan={name:'<script>alert(1)</script>',area_m2:20,rooms:[{name:'A&B',area_m2:20,points:[[0,0],[5,0],[5,4],[0,4]]}],walls:[{start:[0,0],end:[5,0],thickness:.2}],furniture:[{name:'"<img>',x:2,y:2,width:2,depth:1,height:1,angle:45}]};
const svg=planSvg(plan);
assert(svg.includes('&lt;script&gt;'));
assert(!svg.includes('<script>')&&!svg.includes('<img>'));
assert(svg.includes('A&amp;B')&&svg.includes('rotate(45)')&&svg.includes('stroke-width="0.2"'));
assert.throws(()=>planSvg({}));
assert.throws(()=>planSvg({rooms:[{points:[[NaN,0]]}]}));
// A rotated item outside the building must fit within the SVG view box.
const far=planSvg({furniture:[{...plan.furniture[0],x:-20,y:30}],rooms:[],walls:[]});
const [,x,y,w,h]=far.match(/viewBox="([^ ]+) ([^ ]+) ([^ ]+) ([^"]+)"/).map(Number);
assert(x<-21&&y<29&&x+w>-19&&y+h>31);
console.log('Architecture model: validated measurements, vector geometry, rotated bounds, XML escaping and empty-plan rejection passed.');
