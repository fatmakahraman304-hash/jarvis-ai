/* Recognition lifecycle regression; no microphone or model needed. */
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const source = fs.readFileSync('web/app.js', 'utf8');
const speech = source.slice(source.indexOf('  // ---------- konuşma tanıma'), source.indexOf('  // Web Speech yoksa'));
let next = 0, pending = new Map(), instances = [], listeners = {};
class Recognition {
  constructor() { instances.push(this); }
  start() { this.onstart?.(); }
  abort() { this.onend?.(); }
}
const context = vm.createContext({
  window: { SpeechRecognition: Recognition },
  document: { hidden: false, addEventListener: (k,f) => listeners[k] = f, querySelectorAll: () => [] },
  JV: { settings: {}, speaking: false, stt: { busy: () => false } },
  setTimeout: (f) => { pending.set(++next, f); return next; },
  clearTimeout: (i) => pending.delete(i),
  addEventListener: (k,f) => listeners[k] = f,
  setStatus: () => {}, toast: () => {}, updateToggles: () => {}, busy: false,
});
vm.runInContext(speech + `\nthis.test = {
  enable() { wakeMode=true; startRec(false); }, single() { startRec(true); },
  stop: stopRec, enabled: () => wakeMode, active: () => recognizing
};`, context);
function tick() { const work=[...pending.values()]; pending.clear(); work.forEach(f=>f()); }
const t = context.test;
t.enable(); assert(t.active());
instances.at(-1).onend(); tick(); assert.equal(instances.length,2); assert(t.active());
t.single(); instances.at(-1).onend(); tick();
assert.equal(instances.at(-1).continuous,true, 'single command must return to continuous mode');
instances.at(-1).onerror({error:'network'}); instances.at(-1).onend(); tick(); assert(t.active());
context.JV.stt.busy=()=>true; instances.at(-1).onend(); tick(); assert(!t.active());
context.JV.stt.busy=()=>false; listeners.focus(); tick(); assert(t.active());
const before=instances.length; t.stop(); listeners.focus(); tick(); assert.equal(instances.length,before);
t.enable(); instances.at(-1).onerror({error:'not-allowed'}); instances.at(-1).onend(); tick(); assert(!t.enabled());
console.log('Continuous listening: restart, one-shot, network, STT handoff, manual stop and permission checks passed.');
