// Exercise the actual patched production method with a drawing-buffer double.
const assert = require('node:assert/strict');
const fs = require('node:fs');
const code = fs.readFileSync(0, 'utf8');
const start = code.indexOf('async renderTopView(');
const end = code.indexOf('destroy(){', start);
assert(start > 0 && end > start, 'Pinned icon method missing');
const pn = class { constructor() { this.position = {}; } };
const renderTopView = new Function('pn', `return ({${code.slice(start, end)}}).renderTopView`)(pn);
let ratio = 2, sizes = [], viewports = [], copies = [];
const renderer = {
  domElement: {width: 300, height: 150},
  getPixelRatio: () => ratio,
  setPixelRatio(value) { ratio = value; },
  setSize(width, height) { sizes.push([width,height]); Object.assign(this.domElement,{width,height}); },
  setViewport(...args) { viewports.push(args); },
  render() {},
};
const position = {set() {}};
const host = {
  renderer,
  modelManager: {getModel: () => ({}), applyPieceTransform() {}},
  canvasFactory: () => ({getContext: () => ({drawImage: (...args) => copies.push(args.slice(1))})}),
  scene: {add() {}, remove() {}},
  camera: {position,up:position,lookAt() {},updateProjectionMatrix() {}},
};
const piece = {getModel: () => ({}),getHeight: () => 90,getWidth: () => 80,getDepth: () => 60};
(async () => {
  for (const [width,height] of [[64,32],[32,64],[64,32],[400,32],[32,240],[64,32]]) {
    const icon = await renderTopView.call(host,piece,width,height);
    assert.deepEqual([icon.width,icon.height],[width,height]);
    assert.deepEqual(viewports.at(-1),[0,0,width,height]);
    assert.deepEqual(copies.at(-1),[0,renderer.domElement.height-height,width,height,0,0,width,height]);
  }
  assert.equal(ratio,1);
  assert.deepEqual(sizes,[[400,150],[400,240]], 'Alternating small icons must reuse the buffer');
  assert.deepEqual([renderer.domElement.width,renderer.domElement.height],[400,240]);
  assert.equal(await renderTopView.call({...host,renderer:null},piece,32,32),null);
  assert.equal(await renderTopView.call(host,{...piece,getModel:()=>null},32,32),null);
  assert.equal(await renderTopView.call({...host,modelManager:{getModel:(_,done)=>{done(null);return null;}}},piece,32,32),null);
  console.log('Actual icon method: bounded buffer growth, exact viewport/crop and missing models passed');
})().catch(error => {console.error(error);process.exitCode=1;});
