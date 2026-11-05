/* Arayüz uçtan uca testi (geliştirici için): sahte model + gerçek JARVIS sunucusu açar, Chromium'da tüm dünyaları, panelleri ve
   araç → arayüz komutlarını dener; sayfa hatası olmamalı. Gerekir: npm i playwright (ve npx playwright install chromium).
   Çalıştır: node tests/test_ui.js */
const { spawn } = require("child_process");
const path = require("path");
const os = require("os");
const fs = require("fs");
const net = require("net");
let chromium;
try { ({ chromium } = require("playwright")); } catch (e) { console.log("playwright yok: npm i playwright"); process.exit(0); }

const ROOT = path.resolve(__dirname, "..");
const PY = process.platform === "win32" ? "python" : "python3";
const freePort = () => new Promise((res) => { const s = net.createServer(); s.listen(0, () => { const p = s.address().port; s.close(() => res(p)); }); });
const wait = (ms) => new Promise((r) => setTimeout(r, ms));
let ok = true;
const check = (name, cond, extra = "") => { console.log((cond ? "  ✓ " : "  ✗ ") + name + (!cond && extra ? `  [${extra}]` : "")); ok = ok && !!cond; };

(async () => {
  const fp = await freePort(), sp = await freePort();
  const data = fs.mkdtempSync(path.join(os.tmpdir(), "jv_ui_")), home = fs.mkdtempSync(path.join(os.tmpdir(), "jv_uih_"));
  const fake = spawn(PY, [path.join(ROOT, "tests", "fake_llm.py"), String(fp)], { stdio: "ignore" });
  const srv = spawn(PY, ["run.py", "--no-browser", "--port", String(sp)], { cwd: ROOT, stdio: "ignore",
    env: { ...process.env, JARVIS_DATA: data, HOME: home, USERPROFILE: home, CUSTOM_BASE_URL: `http://127.0.0.1:${fp}` } });
  for (let i = 0; i < 60; i++) { try { await fetch(`http://127.0.0.1:${sp}/api/node/hello`); break; } catch (e) { await wait(250); } }
  const b = await chromium.launch({ args: ["--autoplay-policy=no-user-gesture-required", "--use-fake-ui-for-media-stream", "--use-fake-device-for-media-stream"] });
  const p = await b.newPage({ viewport: { width: 1360, height: 860 } });
  const errs = []; p.on("pageerror", (e) => errs.push(e.message));
  await p.route(/cdn\.jsdelivr|unpkg|tile\.|arcgis|openstreetmap|fonts\.g|rainviewer|nasa\.gov/, (r) => r.abort());
  try {
    await p.goto(`http://127.0.0.1:${sp}/`); await wait(2000); await p.click("#boot-btn").catch(() => {}); await wait(800);
    console.log("DÜNYALAR");
    for (const v of ["globe", "lab", "science", "space", "city", "twin", "bio"]) {
      await p.click(`[data-view="${v}"]`); await wait(1800);
      check(`${v} görünümü açıldı`, (await p.evaluate(() => JV.getView())) === v);
    }
    await p.click('[data-view="core"]'); await wait(500);
    console.log("ARAÇ → ARAYÜZ KOMUTLARI");
    const cmds = [
      ["city_command", { ui: "city", action: "weather", value: "kar" }, () => JV.worlds.city.stats().hava === "kar"],
      ["digital_twin", { ui: "twin", kind: "pc" }, () => JV.getView() === "twin"],
      ["cell_show", { ui: "bio", kind: "cell", cell: "plant" }, () => JV.getView() === "bio"],
      ["knowledge_graph", { ui: "graph", title: "T", nodes: [{ id: "A" }, { id: "B" }], edges: [{ a: "A", b: "B" }] }, () => JV.getView() === "graph"],
      ["quiz_make", { ui: "quiz", title: "Q", questions: [{ q: "1+1?", options: ["1", "2"], answer: 1 }] }, () => !!document.querySelector("#quiz .qz-q")],
      ["set_mode", { ui: "mode", mode: "sessiz" }, () => JV.quiet === true],
      ["set_mode", { ui: "mode", mode: "normal" }, () => JV.quiet === false],
      ["command_center", { ui: "command", open: true }, () => JV.command.isOpen()],
      ["command_center", { ui: "command", open: false }, () => !JV.command.isOpen()],
      ["translator_mode", { ui: "translator", a: "tr", b: "de" }, () => document.querySelector("#tr-b").value === "de"],
      ["finlab", { ui: "finlab", tab: "loan" }, () => !!document.querySelector("#f-pr")],
      ["vr_mode", { ui: "xr", view: "globe", mode: "vr" }, () => !!document.querySelector("#xr-prompt")],
    ];
    for (const [name, r, test] of cmds) {
      await p.evaluate(([n, x]) => JV.uiCommand(n, {}, JSON.stringify(x)), [name, r]); await wait(900);
      check(`${name} → ${r.ui}`, await p.evaluate(test));
      await p.evaluate(() => ["#quiz", "#translator", "#finlab"].forEach((s) => { const e = document.querySelector(s); if (e) e.classList.add("hidden"); }));
    }
    console.log("PANELLER");
    await p.click("#t-library"); await wait(800); check("bilgi merkezi açıldı", await p.evaluate(() => !document.querySelector("#library").classList.contains("hidden")));
    await p.click("#kb-close");
    await p.click("#t-music"); await wait(2500); check("müzik besteledi ve çalıyor", (await p.textContent("#mu-play")).includes("DUR"));
    await p.click("#mu-x");
    const xr = await p.evaluate(() => JV.xr.enter("immersive-vr").then(() => "girdi", (e) => e.message));
    check("VR cihaz yokken anlaşılır hata", /VR|güvenli|WebXR/.test(xr), xr);
    const amb = await p.evaluate(async () => { const before = (await JV.api("/api/notifications?since=0")).length; JV.ambient._handle([{ categoryName: "Smoke detector, smoke alarm", score: 0.9 }]); await new Promise((r) => setTimeout(r, 600)); const ns = await JV.api("/api/notifications?since=0"); return ns.slice(before).map((n) => n.kind + ":" + n.text); });
    check("ortam sesi: duman alarmı güvenlik bildirimi", amb.some((x) => x.startsWith("security:") && x.includes("Duman")), JSON.stringify(amb));
    console.log("GOOGLE SİHİRBAZI");
    await p.click("text=AYARLAR"); await wait(500); await p.click('[data-tab="links"]'); await wait(900);
    check("adım 1 görünüyor", (await p.textContent(".gw-body")).includes("JARVIS") && (await p.$$(".gw-dots span")).length === 5);
    for (let i = 0; i < 3; i++) { await p.click(".gw-nav button:last-child"); await wait(400); }
    check("adım 4: anahtar alanları", (await p.$$(".gw-body input")).length === 2);
    const ins = await p.$$(".gw-body input");
    await ins[0].fill("GOCSPX-yanlis-kutuya"); await ins[1].fill("123-abc.apps.googleusercontent.com");
    check("yer değiştirmiş anahtarlar uyarılır", await p.waitForFunction(() => document.querySelector(".gwiz .gtest").textContent.includes("Secret yapıştırılmış"), null, { timeout: 6000 }).then(() => true, () => false));
    await ins[0].fill("123456789012-abcdefghijklmnopqrstuvwxyz123456.apps.googleusercontent.com"); await ins[1].fill("GOCSPX-abcdefghijklmnopqrstu");
    check("doğru biçim onaylanır", await p.waitForFunction(() => document.querySelector(".gwiz .gtest").textContent.includes("biçim doğru"), null, { timeout: 6000 }).then(() => true, () => false));
    await p.click(".gw-nav button:last-child"); await wait(400);
    check("adım 5: bağlan düğmesi (anahtarsız kapalı)", await p.$eval(".gw-body .btn-primary", (b) => b.textContent.includes("BAĞLAN") && b.disabled));
    await p.click(".gw-dots span:first-child"); await wait(300);
    check("adım çiplerine tıklayınca o adıma gider", (await p.textContent(".gw-nav .note")).includes("1 / 5"));
    await p.keyboard.press("Escape");
    check("sayfa hatası yok", errs.length === 0, errs.slice(0, 3).join(" | "));
  } finally {
    await b.close(); srv.kill(); fake.kill();
  }
  console.log("\nSONUÇ:", ok ? "BAŞARILI" : "HATA VAR");
  process.exit(ok ? 0 : 1);
})();
