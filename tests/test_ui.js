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
    console.log("AR EFEKT + UYKU");
    const ar = await p.evaluate(async () => {
      const H = JV.handfx, C = JV.GestureCore, out = {}; H.show(null);
      const run = async (n, mk) => { for (let i = 0; i < n; i++) { H.frame(mk(i), null); await new Promise((r) => setTimeout(r, 16)); } };
      await run(8, (i) => [{ lm: H._synth(0.4 + i * 0.03, 0.5, 0.5, "open"), handed: "Right" }]); out.fire = H.stats().parts;
      await run(20, (i) => [{ lm: H._synth(0.3 + i * 0.02, 0.5, 0.5, "point"), handed: "Right" }]); out.trail = H.stats().trail;
      await run(10, () => [{ lm: H._synth(0.5, 0.5, 0.5, "pinch"), handed: "Right" }]); out.planet = H.stats().planets.length;
      await run(1, () => [{ lm: H._synth(0.5, 0.5, 0.5, "fist"), handed: "Right" }]); await run(2, () => [{ lm: H._synth(0.5, 0.5, 0.5, "open"), handed: "Right" }]); out.blast = H.stats().planets.length;
      await run(6, () => [{ lm: H._synth(0.3, 0.5, 0.4, "point"), handed: "Right" }, { lm: H._synth(0.7, 0.5, 0.4, "point"), handed: "Left" }]); out.bolts = H.stats().bolts;
      JV.uiCommand("ar_effects", {}, JSON.stringify({ ui: "handfx", action: "planet", planet: "jupiter" }));
      await run(10, () => [{ lm: H._synth(0.5, 0.5, 0.5, "pinch"), handed: "Right" }]); out.jup = H.stats().planets.slice(-1)[0];
      const face = []; for (let i = 0; i < 40; i++) face.push({ x: 0.45 + (i % 8) * 0.015, y: 0.3 + Math.floor(i / 8) * 0.03 });
      for (let i = 0; i < 90; i++) { H.frame([], [face]); await new Promise((r) => setTimeout(r, 16)); } out.locked = H.stats().locked;
      H.stop();
      JV.sleep.enter(); await new Promise((r) => setTimeout(r, 200)); out.asleep = JV.sleep.asleep;
      const t = performance.now(); JV.sleep._clap(t); JV.sleep._clap(t + 1200); out.slowClap = JV.sleep.asleep;
      JV.sleep._clap(t + 1400); JV.sleep._clap(t + 1750); out.woke = !JV.sleep.asleep;
      return out;
    });
    check("✋ açık el ateş", ar.fire > 30, JSON.stringify(ar));
    check("☝ ışık izi", ar.trail > 3, JSON.stringify(ar));
    check("🤏 çimdik gezegen + ✊→✋ patlatma", ar.planet === 1 && ar.blast === 0, JSON.stringify(ar));
    check("☝☝ şimşek", ar.bolts > 0);
    check("sesle gezegen seçimi (Jüpiter)", ar.jup === "jupiter");
    check("yüz kilidi kilitlenir", ar.locked === true);
    check("uyku modu + yavaş alkış uyandırmaz + iki alkış uyandırır", ar.asleep && ar.slowClap && ar.woke);
    console.log("KİTAPLIK (AR) + KAMERA + VİDEO");
    const lib = await p.evaluate(async () => {
      const H = JV.handfx, out = {};
      const probe = H._synth(0.5, 0.5, 0.5, "point"), tx = probe[8].x, ty = probe[8].y;
      await JV.api("/api/library/book", { body: { title: "Mülksüzler", author: "Ursula K. Le Guin", box: [tx - 0.03, ty - 0.2, tx + 0.03, ty + 0.2], notes: [{ t: "Anarres", d: "2026-11-05" }] } });
      await JV.api("/api/library/book", { body: { title: "Davranış", author: "Sapolsky", box: [tx + 0.08, ty - 0.2, tx + 0.14, ty + 0.2] } });
      await fetch("/api/library/scan", { method: "POST", body: "x" }).catch(() => {});
      await JV.library.load();
      const d = JV.library._data(); d.shelf = { region: [tx - 0.1, ty - 0.3, tx + 0.2, ty + 0.3] };
      H.show(null);
      const run = async (n, mk) => { for (let i = 0; i < n; i++) { H.frame(mk(i), null); await new Promise((r) => setTimeout(r, 30)); } };
      await run(15, () => [{ lm: H._synth(0.5, 0.5, 0.5, "point"), handed: "Right" }]);
      // seçim etiketi tuvalde çizildi mi: sahnede seçili kitap
      await run(4, () => [{ lm: H._synth(0.5, 0.5, 0.5, "pinch"), handed: "Right" }]);
      await run(6, () => [{ lm: H._synth(0.5, 0.5, 0.75, "pinch"), handed: "Right" }]); // çek: el kameraya yaklaşır
      await new Promise((r) => setTimeout(r, 1200));
      out.open = JV.library.open; out.page = document.querySelector("#hb-pn") && document.querySelector("#hb-pn").textContent;
      out.title = document.querySelector(".hb-l h3") && document.querySelector(".hb-l h3").textContent;
      JV.library.flip(1); out.page2 = document.querySelector("#hb-pn").textContent;
      out.planetsWhileOpen = H.stats().planets.length;
      await run(45, () => [{ lm: H._synth(0.5, 0.6, 0.5, "fist"), handed: "Right" }]); // ✊ basılı → rafa koy
      await new Promise((r) => setTimeout(r, 300)); out.closed = !JV.library.open;
      H.stop();
      await JV.library.openPanel(); out.rows = document.querySelectorAll("#lp-list .lp-row").length; document.querySelector("#lp-x").click();
      // kamera izleyici
      await fetch("/api/cams?id=t1&name=CAM-01&loc=Mutfak", { method: "POST", headers: { "Content-Type": "image/jpeg" }, body: new Uint8Array([255, 216, 255, 217]) });
      await new Promise((r) => setTimeout(r, 5600));
      out.badge = (document.querySelector(".cam-badge") || {}).textContent || "";
      JV.cams.open("t1"); await new Promise((r) => setTimeout(r, 600)); out.camImg = document.querySelector("#cp-img").src.includes("/api/cams/t1.jpg"); JV.cams.close();
      JV.uiCommand("youtube_play", {}, JSON.stringify({ ui: "video", id: "abcDEF12345", title: "Maç Özeti", url: "https://www.youtube.com/watch?v=abcDEF12345" }));
      out.video = document.querySelector("#vp-if").src.includes("youtube-nocookie.com/embed/abcDEF12345"); JV.video.close();
      return out;
    });
    check("☝ işaret + 🤏 çimdikle çek → kitap holografik açılır", lib.open === true && lib.title === "Mülksüzler", JSON.stringify(lib));
    check("sayfa çevrilir; kitap açıkken gezegen oluşmaz", lib.page === "1 / 4" && lib.page2 === "2 / 4" && lib.planetsWhileOpen === 0, JSON.stringify(lib));
    check("✊ basılı tut → kitap rafa döner", lib.closed === true);
    check("kitaplık paneli listeler", lib.rows >= 2);
    check("kamera rozeti + canlı izleme", lib.badge.includes("CAM-01") && lib.badge.includes("MUTFAK") && lib.camImg, JSON.stringify(lib));
    check("YouTube videosu JARVIS içinde", lib.video);
    const cp = await b.newPage({ viewport: { width: 400, height: 800 } });
    await cp.route(/cdn\.jsdelivr|unpkg|tile\.|arcgis|openstreetmap|fonts\.g|rainviewer|nasa\.gov/, (r) => r.abort());
    await cp.goto(`http://127.0.0.1:${sp}/?rol=kamera`); await wait(2500);
    const role = await cp.evaluate(() => ({ node: !!document.querySelector("#camnode"), hidden: getComputedStyle(document.querySelector("#settings") || document.body).display === "none" }));
    await cp.evaluate(() => { document.querySelector("#cn-name").value = "CAM-02"; document.querySelector("#cn-loc").value = "Salon"; document.querySelector("#cn-start").click(); });
    let camList = { cams: [] };
    for (let i = 0; i < 20; i++) { await wait(500); camList = await (await fetch(`http://127.0.0.1:${sp}/api/cams`)).json(); if (camList.cams.some((c) => c.name === "CAM-02" && c.online)) break; }
    check("telefon kamera sayfası (sade, diğer arayüz gizli)", role.node, JSON.stringify(role));
    check("kamera sayfası kare gönderiyor", camList.cams.some((c) => c.name === "CAM-02" && c.loc === "Salon" && c.online), JSON.stringify(camList));
    await cp.close();
    console.log("ODA TARAMA + HOLOGRAM + VÜCUT + AR EKSTRA");
    await p.route("**/api/scene/room*", (r) => r.fulfill({ json: { nesneler: [{ ad: "Kahve fincanı", tür: "mutfak", box: [0.15, 0.3, 0.38, 0.7], not: "beyaz" }, { ad: "Kumanda", tür: "elektronik", box: [0.55, 0.6, 0.7, 0.8] }] } }));
    await p.route("**/api/scene/object*", (r) => r.fulfill({ json: { ad: "Kahve fincanı", ne: "Porselen fincan.", ipucu: "Elde yıka.", arama: "porselen fincan" } }));
    await p.route("**/api/scene/drawing", (r) => r.fulfill({ json: { cevap: "Bir kalp çizmişsiniz!" } }));
    await p.evaluate(() => JV.uiCommand("room_scan", {}, JSON.stringify({ ui: "scan", mode: "room", location: "salon" })));
    for (let i = 0; i < 20 && (await p.evaluate(() => JV.scan._state().items)) < 2; i++) await wait(400);
    check("'odayı tara' → nesneler kutulanır", (await p.evaluate(() => JV.scan._state().items)) === 2);
    await p.evaluate(() => JV.scan._openHolo(0)); await wait(1500);
    const hol = await p.evaluate(() => ({ on: !!document.querySelector("#holo3d.on"), info: (document.querySelector("#h3-info") || {}).textContent || "", layers: document.querySelectorAll(".h3-obj img").length }));
    check("nesneye tıkla → hologram + bilgi kartı", hol.on && hol.layers === 4 && hol.info.includes("Porselen"), JSON.stringify(hol));
    await p.keyboard.press("Escape"); await wait(600); await p.keyboard.press("Escape"); await wait(300);
    check("Esc: hologram, sonra tarama kapanır", !(await p.evaluate(() => JV.scan.active)));
    const bd = await p.evaluate(async () => {
      await JV.body.start("squat", 0);
      const mk = (bent) => { const P = []; for (let i = 0; i < 33; i++) P.push({ x: 0.5, y: 0.5, visibility: 1 }); P[23] = { x: 0.45, y: 0.5, visibility: 1 }; P[24] = { x: 0.55, y: 0.5, visibility: 1 }; P[25] = { x: bent ? 0.25 : 0.45, y: 0.7, visibility: 1 }; P[26] = { x: bent ? 0.75 : 0.55, y: 0.7, visibility: 1 }; P[27] = { x: 0.45, y: 0.9, visibility: 1 }; P[28] = { x: 0.55, y: 0.9, visibility: 1 }; return P; };
      const n = performance.now(); for (let i = 0; i < 3; i++) { JV.body._feedPose(mk(true), n); JV.body._feedPose(mk(false), n); }
      const squats = JV.body._state().reps;
      await JV.body.start("mood");
      const bs = (o) => ({ categories: Object.entries(o).map(([categoryName, score]) => ({ categoryName, score })) });
      JV.body._feedMood(bs({ mouthSmileLeft: 0.8, mouthSmileRight: 0.8 }), performance.now()); const happy = document.querySelector("#bh-big").textContent;
      JV.body._feedMood(bs({ eyeBlinkLeft: 0.7, eyeBlinkRight: 0.7 }), performance.now()); const tired = document.querySelector("#bh-big").textContent;
      JV.body.stop();
      return { squats, happy, tired };
    });
    check("squat sayacı (diz açısı)", bd.squats === 3, JSON.stringify(bd));
    check("ruh hali: mutlu / yorgun", bd.happy.includes("MUTLU") && bd.tired.includes("YORGUN"), JSON.stringify(bd));
    const ax = await p.evaluate(async () => {
      const H = JV.handfx; H.show(null); const out = {};
      const run = async (n, mk) => { for (let i = 0; i < n; i++) { H.frame(mk(i), null); await new Promise((r) => setTimeout(r, 30)); } };
      await run(50, () => [{ lm: H._synth(0.5, 0.55, 0.5, "open"), handed: "Right" }]); out.palm = H.stats().palm;
      JV.uiCommand("ar_extra", {}, JSON.stringify({ ui: "handfx", action: "extra", extra: "draw" }));
      await run(20, (i) => [{ lm: H._synth(0.35 + i * 0.012, 0.5 + Math.sin(i / 3) * 0.05, 0.5, "point"), handed: "Right" }]); out.strokes = H.stats().strokes;
      const peace = () => { const l = H._synth(0.5, 0.5, 0.5, "point"); const m = H._synth(0.5, 0.5, 0.5, "open"); [9, 10, 11, 12].forEach((k) => (l[k] = m[k])); return l; };
      out.peacePose = JV.GestureCore.pose(peace());
      await run(45, () => [{ lm: peace(), handed: "Right" }]); await new Promise((r) => setTimeout(r, 800));
      out.msg = document.querySelector("#ar-msg").textContent;
      JV.uiCommand("ar_extra", {}, JSON.stringify({ ui: "handfx", action: "extra", extra: "mask" }));
      const face = []; for (let i = 0; i < 478; i++) face.push({ x: 0.4 + (i % 20) * 0.01, y: 0.3 + Math.floor(i / 20) * 0.01 });
      H._setFaces([face]); await run(3, () => []); out.mask = H.opts.mask;
      H.opts.draw = false; H.opts.mask = false; H.stop();
      return out;
    });
    check("✋ sabit avuç → HUD (saat/hava/etkinlik)", ax.palm === true, JSON.stringify(ax));
    check("✏ havaya çizim + ✌ 'ne çizdim?'", ax.strokes >= 1 && ax.msg.includes("kalp"), JSON.stringify(ax));
    check("🛡 kask HUD'u", ax.mask === true);
    console.log("GOOGLE SİHİRBAZI");
    await p.click("text=AYARLAR"); await wait(500); await p.click('[data-tab="links"]'); await wait(900);
    check("adım 1 görünüyor", (await p.textContent(".gw-body")).includes("JARVIS") && (await p.$$(".gw-dots span")).length === 5);
    for (let i = 0; i < 3; i++) { const before = await p.textContent(".gw-nav .note"); await p.click(".gw-nav button:last-child"); await p.waitForFunction((b) => document.querySelector(".gw-nav .note").textContent !== b, before, { timeout: 5000 }).catch(() => {}); }
    await p.waitForSelector(".gw-body input", { timeout: 5000 }).catch(() => {});
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
