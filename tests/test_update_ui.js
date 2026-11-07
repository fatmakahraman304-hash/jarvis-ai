/* Execute the shipped updater with a minimal DOM and deterministic network/timers. */
const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const vm = require("node:vm");
const source = fs.readFileSync(path.join(__dirname, "../web/update.js"), "utf8");
const flush = async () => { for (let i = 0; i < 10; i++) await Promise.resolve(); };

async function setup() {
  const elements = new Map();
  function element(id) {
    if (!elements.has(id)) elements.set(id, {
      style: {}, disabled: false, textContent: "", innerHTML: "",
      classList: { add() {}, remove() {}, toggle() {} },
      querySelector: element,
    });
    return elements.get(id);
  }
  const timers = new Map();
  let next = 0, reloads = 0;
  const network = {
    api: async (url, options) => options?.body
      ? { durum: "hata", hata: "Geri dönülecek yedek yok." }
      : url.includes("state=1") ? { ilerleme: 10, adım: "indiriliyor" }
      : { yerel: "4.6.47", uzak: "4.6.48", yeni_var: true, yedekler: ["v4.6.47.zip"] },
    fetch: async () => ({ ok: true, json: async () => ({ version: "4.6.48" }) }),
  };
  const schedule = (kind) => (fn, delay) => { const id = ++next; timers.set(id, { kind, fn, delay }); return id; };
  const context = {
    window: { JV: { api: (...args) => network.api(...args), token: "local-test-token" }, confirm: () => true },
    document: { createElement: () => element("root"), querySelector: element, body: { append() {} }, addEventListener() {} },
    location: { protocol: "http:", href: "http://127.0.0.1:8765/", reload: () => reloads++, replace: () => { throw Error("unexpected origin change"); } },
    setInterval: schedule("interval"), setTimeout: schedule("timeout"),
    clearInterval: (id) => timers.delete(id), clearTimeout: (id) => timers.delete(id),
    fetch: (...args) => network.fetch(...args), AbortController,
  };
  vm.runInNewContext(source, context);
  context.window.JV.updater.open();
  await flush();
  return { element, network, timers, reloads: () => reloads };
}

(async () => {
  let h = await setup();
  await h.element("#up-back").onclick();
  assert.match(h.element("#up-step").textContent, /yedek yok/);
  assert.equal(h.timers.size, 0, "failed rollback must not start restart polling");
  assert.equal(h.element("#up-check").disabled, false);
  h.network.api = async () => { throw Error("bağlantı kesildi"); };
  await h.element("#up-back").onclick();
  assert.match(h.element("#up-step").textContent, /bağlantı kesildi/);
  assert.equal(h.timers.size, 0);

  h = await setup();
  let resolveRollback;
  let calls = 0;
  h.network.api = async () => { calls++; return new Promise(resolve => { resolveRollback = resolve; }); };
  const rollback = h.element("#up-back").onclick();
  await h.element("#up-go").onclick();
  await h.element("#up-back").onclick();
  assert.equal(calls, 1, "busy controls must prevent concurrent writes");
  resolveRollback({ durum: "geri alındı" });
  await rollback;
  const interval = [...h.timers.values()].find(t => t.kind === "interval");
  h.network.fetch = async (url, options) => {
    assert.equal(options.headers["x-token"], "local-test-token");
    throw Error("restarting");
  };
  await interval.fn();
  assert.equal(h.reloads(), 0);
  h.network.fetch = async () => ({ ok: true, json: async () => ({ version: "4.6.46" }) });
  const fallback = [...h.timers.values()].find(t => t.delay === 60000);
  await interval.fn();
  assert.equal(h.reloads(), 1, "successful restart should reload existing HTTP origin");
  assert.equal(h.timers.size, 0, "all restart timers must be cleared");
  fallback.fn();
  assert.equal(h.reloads(), 1, "late fallback must not reload twice");

  h = await setup();
  let resolvePoll;
  h.network.api = async (url, options) => options?.body
    ? { durum: "güncellendi", yeni: "4.6.48" }
    : new Promise(resolve => { resolvePoll = resolve; });
  await h.element("#up-go").onclick();
  resolvePoll({ ilerleme: 20, adım: "stale progress" });
  await flush();
  assert.match(h.element("#up-step").textContent, /4.6.48 kuruldu/);
  const fastRestart = [...h.timers.values()].find(t => t.kind === "interval");
  let resolveFetch;
  let fetches = 0;
  h.network.fetch = async () => { fetches++; return new Promise(resolve => { resolveFetch = resolve; }); };
  const pending = fastRestart.fn();
  await fastRestart.fn();
  assert.equal(fetches, 1, "slow health checks must not overlap");
  resolveFetch({ ok: true, json: async () => ({ version: "4.6.48" }) });
  await pending;
  assert.equal(h.reloads(), 1, "new version should be detected even if downtime was missed");
  assert.equal(h.timers.size, 0);
  console.log("Updater UI recovery regressions passed.");
})().catch(error => { console.error(error); process.exitCode = 1; });
