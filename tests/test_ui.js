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
    for (const v of ["globe", "lab", "science", "space", "twin", "bio"]) {
      await p.click(`[data-view="${v}"]`); await wait(1800);
      check(`${v} görünümü açıldı`, (await p.evaluate(() => JV.getView())) === v);
    }
    await p.click('[data-view="core"]'); await wait(500);
    console.log("ARAÇ → ARAYÜZ KOMUTLARI");
    const cmds = [
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
    await p.click("#t-apps"); await wait(300); await p.click(".ln-tile:has-text('Bilgi Merkezi')"); await wait(800); check("bilgi merkezi açıldı", await p.evaluate(() => !document.querySelector("#library").classList.contains("hidden")));
    await p.click("#kb-close");
    await p.click("#t-apps"); await wait(300); await p.click(".ln-tile:has-text('Müzik')"); await wait(2500); check("müzik besteledi ve çalıyor", (await p.textContent("#mu-play")).includes("DUR"));
    await p.click("#mu-x");
    const xr = await p.evaluate(() => JV.xr.enter("immersive-vr").then(() => "girdi", (e) => e.message));
    check("VR cihaz yokken anlaşılır hata", /VR|güvenli|WebXR/.test(xr), xr);
    const amb = await p.evaluate(async () => { const before = (await JV.api("/api/notifications?since=0")).length; JV.ambient._handle([{ categoryName: "Smoke detector, smoke alarm", score: 0.9 }]); await new Promise((r) => setTimeout(r, 600)); const ns = await JV.api("/api/notifications?since=0"); return ns.slice(before).map((n) => n.kind + ":" + n.text); });
    check("ortam sesi: duman alarmı güvenlik bildirimi", amb.some((x) => x.startsWith("security:") && x.includes("Duman")), JSON.stringify(amb));
    console.log("AR EFEKT + UYKU");
    const ar = await p.evaluate(async () => {
      const H = JV.handfx, C = JV.GestureCore, out = {}; H.setProfile("fire"); H.show(null);
      const run = async (n, mk) => { for (let i = 0; i < n; i++) { H.frame(mk(i), null); await new Promise((r) => setTimeout(r, 16)); } };
      await run(8, (i) => [{ lm: H._synth(0.4 + i * 0.03, 0.5, 0.5, "open"), handed: "Right" }]); out.fire = H.stats().parts;
      H.setProfile("trail"); await run(20, (i) => [{ lm: H._synth(0.3 + i * 0.02, 0.5, 0.5, "point"), handed: "Right" }]); out.trail = H.stats().trail;
      H.setProfile("planet"); await run(10, () => [{ lm: H._synth(0.5, 0.5, 0.5, "pinch"), handed: "Right" }]); out.planet = H.stats().planets.length;
      H.setProfile("blast"); await run(1, () => [{ lm: H._synth(0.5, 0.5, 0.5, "fist"), handed: "Right" }]); await run(2, () => [{ lm: H._synth(0.5, 0.5, 0.5, "open"), handed: "Right" }]); out.blast = H.stats().planets.length;
      H.setProfile("lightning"); await run(6, () => [{ lm: H._synth(0.3, 0.5, 0.4, "point"), handed: "Right" }, { lm: H._synth(0.7, 0.5, 0.4, "point"), handed: "Left" }]); out.bolts = H.stats().bolts;
      JV.uiCommand("ar_effects", {}, JSON.stringify({ ui: "handfx", action: "planet", planet: "jupiter" }));
      await run(10, () => [{ lm: H._synth(0.5, 0.5, 0.5, "pinch"), handed: "Right" }]); out.jup = H.stats().planets.slice(-1)[0];
      const face = []; for (let i = 0; i < 40; i++) face.push({ x: 0.45 + (i % 8) * 0.015, y: 0.3 + Math.floor(i / 8) * 0.03 });
      H.setProfile("face"); for (let i = 0; i < 90; i++) { H.frame([], [face]); await new Promise((r) => setTimeout(r, 16)); } out.locked = H.stats().locked;
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
      const H = JV.handfx, out = {}; H.setProfile("library");
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
    const cp2 = await b.newPage({ viewport: { width: 400, height: 800 } });
    await cp2.goto(`http://127.0.0.1:${sp}/?rol=kamera`); await wait(400);
    await cp2.evaluate(() => Object.defineProperty(navigator, "mediaDevices", { value: undefined, configurable: true }));
    await cp2.click("#cn-start");
    const camHelp = await cp2.textContent("#cn-note");
    check("kamera API'si HTTP'de yoksa anlaşılır HTTPS yönergesi", camHelp.includes("start-lan.bat") && camHelp.includes("https://"), camHelp);
    await cp2.close();
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
      const H = JV.handfx; H.setProfile("palm"); H.show(null); const out = {};
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
    console.log("TOPLANTI + ODAK + GÜNDEM + BİTKİ + OYUNLAR");
    await p.route("**/api/life/meeting_chunk", (r) => r.fulfill({ json: { text: "Ahmet cuma günü teklifi hazırlayacak." } }));
    await p.route("**/api/life/meeting_finish", (r) => r.fulfill({ json: { başlık: "Bütçe", özet: "Bütçe konuşuldu.", kararlar: ["Reklam artacak"], yapılacaklar: [{ iş: "Teklif", kim: "Ahmet" }], eklenen_iş: 1, dosya: "C:/Belgeler/x.md" } }));
    await p.route("**/api/life/plant", (r) => r.fulfill({ json: { bitki: "Monstera deliciosa", emin: true, sağlık: "dikkat", sorunlar: ["sararma"], neden: "fazla su", yapılacaklar: ["Sulamayı azalt"], sulama_gün: 7, ışık: "dolaylı", ipucu: "" } }));
    const lf = await p.evaluate(async () => {
      const out = {};
      await JV.meeting.start("Bütçe"); await new Promise((r) => setTimeout(r, 1500)); out.meetOn = JV.meeting.active;
      await JV.meeting.finish(); out.meetSum = document.querySelector("#mt-sum").textContent; document.querySelector("#mt-x").click();
      JV.focus.start(1, "rapor"); out.focusRing = !document.querySelector("#focusring").classList.contains("hidden") && JV.quiet === true;
      JV.focus._finishNow(); await new Promise((r) => setTimeout(r, 800)); out.focusPhase = JV.focus.phase; out.quietAfter = JV.quiet; JV.focus.stop(true);
      const st = await JV.api("/api/life/focus_stats"); out.focusMin = st.bugün_dk;
      JV.uiCommand("news_show", {}, JSON.stringify({ ui: "newsshow", giriş: "Gündem.", sahneler: [{ başlık: "Faiz", anlatım: "Faiz sabit.", büyük: "%45", etiket: "ekonomi", kaynaklar: ["AA"] }, { başlık: "Maç", anlatım: "Galibiyet.", büyük: "3-1", etiket: "spor", kaynaklar: ["TRT"] }], kapanış: "" }));
      await new Promise((r) => setTimeout(r, 400)); JV.newsshow.go(0); await new Promise((r) => setTimeout(r, 900));
      out.newsBig = (document.querySelector(".ns-card.on .ns-big") || {}).textContent; JV.newsshow.go(1); await new Promise((r) => setTimeout(r, 900));
      out.newsBig2 = (document.querySelector(".ns-card.on .ns-big") || {}).textContent; JV.newsshow.close();
      await JV.scan.open("plant"); for (let i = 0; i < 30 && !((document.querySelector("#pl-out") || {}).textContent || "").includes("Monstera"); i++) await new Promise((r) => setTimeout(r, 300)); out.plant = (document.querySelector("#pl-out") || {}).textContent || ""; JV.scan.close();
      const H = JV.handfx; H.show(null); const run = async (n, mk) => { for (let i = 0; i < n; i++) { H.frame(mk(i), null); await new Promise((r) => setTimeout(r, 30)); } };
      H._startGame("rps"); const t0 = performance.now();
      while (performance.now() - t0 < 5200 && !(H._game() && H._game().phase === "result")) await run(1, () => [{ lm: H._synth(0.5, 0.55, 0.5, "fist"), handed: "Right" }]);
      out.rps = H._game();
      H._startGame("balloons", 60000); let popped = 0;
      for (let i = 0; i < 200 && !popped; i++) {
        const g = H._game(); const b = g.balloons && g.balloons.find((x) => x.y < innerHeight - 40);
        let hand = [];
        if (b) { const probe = H._synth(0.5, 0.5, 0.5, "point"), dx = probe[8].x - 0.5, dy = probe[8].y - 0.5, l = H._toLm(b.x, b.y); hand = [{ lm: H._synth(l.x - dx, l.y - dy, 0.5, "point"), handed: "Right" }]; }
        await run(1, () => hand); popped = H._game().score;
      }
      out.popped = popped; H.stop();
      return out;
    });
    check("🎙 toplantı: kayıt → canlı döküm → özet/kararlar/yapılacaklar", lf.meetOn && lf.meetSum.includes("Reklam artacak") && lf.meetSum.includes("Teklif"), JSON.stringify(lf));
    check("⏳ odak: halka + sessiz mod → bitince mola, istatistik", lf.focusRing && lf.focusPhase === "mola" && lf.quietAfter === false && lf.focusMin >= 1, JSON.stringify(lf));
    check("📰 gündem sahneleri (büyük sayı, geçiş)", lf.newsBig === "%45" && lf.newsBig2 === "3-1", JSON.stringify(lf));
    check("🌱 bitki doktoru kartı", lf.plant.includes("Monstera") && lf.plant.includes("7 günde bir"), lf.plant);
    check("✊✋✌ taş-kağıt-makas: elin okunur, tur sonuçlanır", lf.rps && lf.rps.phase === "result" && lf.rps.pick === "taş" && ["KAZANDIN", "KAYBETTİN", "BERABERE"].includes(lf.rps.res), JSON.stringify(lf.rps));
    check("🎈 balon patlatma: parmakla patlar", lf.popped >= 1, JSON.stringify(lf));
    console.log("HAVA PANELİ + AR MASAÜSTÜ + KASK");
    await p.route("**/api/hud/system", (r) => r.fulfill({ json: { cpu: 6, ram: 56, gpu: 27, disk: 91 } }));
    const wx = { şehir: "İstanbul", ülke: "Türkiye", derece: 18, hissedilen: 15, nem: 63, rüzgar: 14, durum: "Parçalı bulutlu", ikon: "partly", yüksek: 19, düşük: 16, yağmur: 63, uv: 5, doğuş: "07:01", batış: "18:44", kaynak: "Open-Meteo",
      saatlik: Array.from({ length: 24 }, (_, i) => ({ saat: i + ":00", derece: 17 + (i % 4), yağmur: 10, ikon: "cloud" })), günler: Array.from({ length: 7 }, (_, i) => ({ gün: i ? "CUM" : "BUGÜN", max: 20, min: 14, yağmur: 0, ikon: "sun" })) };
    await p.route("**/api/hud/weather*", (r) => r.fulfill({ json: wx }));
    const hd = await p.evaluate(async (wx) => {
      const out = {};
      JV.uiCommand("weather_panel", {}, JSON.stringify({ ui: "weather", data: wx })); await new Promise((r) => setTimeout(r, 300));
      out.wx = { t: (document.querySelector(".wx-t") || {}).textContent, days: document.querySelectorAll(".wx-day").length, curve: !!document.querySelector(".wx-curve path") };
      JV.weather.close();
      const H = JV.handfx; H.setProfile("desktop"); H.show(null);
      const run = async (n, mk) => { for (let i = 0; i < n; i++) { H.frame(mk(i), null); await new Promise((r) => setTimeout(r, 30)); } };
      await run(40, () => [{ lm: H._synth(0.62, 0.55, 0.55, "open"), handed: "Right" }]); out.menu = JV.ardesk._menu();
      const probe = H._synth(0.5, 0.5, 0.5, "point"), dx = probe[8].x - 0.5, dy = probe[8].y - 0.5;
      const at = async (sel, n = 30) => { const b = document.querySelector(sel).getBoundingClientRect(), l = H._toLm(b.x + b.width / 2, b.y + b.height / 2); await run(n, () => [{ lm: H._synth(l.x - dx, l.y - dy, 0.5, "point"), handed: "Right" }]); };
      await at('.ad-mi[data-air="system"]'); out.p1 = JV.ardesk._panels();
      await at('.ad-dock [data-air="music"]'); out.p2 = JV.ardesk._panels();
      await new Promise((r) => setTimeout(r, 2500)); out.rings = document.querySelectorAll('.ad-panel[data-panel="system"] .ad-ring').length;
      const sp = document.querySelector('.ad-panel[data-panel="system"]'), r3 = sp.getBoundingClientRect(), x0 = r3.left;
      const pin = H._synth(0.5, 0.5, 0.5, "pinch"), pdx = (pin[4].x + pin[8].x) / 2 - 0.5, pdy = (pin[4].y + pin[8].y) / 2 - 0.5, l3 = H._toLm(r3.x + 60, r3.y + 70);
      await run(3, () => [{ lm: H._synth(l3.x - pdx, l3.y - pdy, 0.5, "point"), handed: "Right" }]);
      await run(20, (i) => [{ lm: H._synth(l3.x - pdx - i * 0.01, l3.y - pdy, 0.5, "pinch"), handed: "Right" }]);
      out.moved = Math.round(sp.getBoundingClientRect().left - x0);
      await at('.ad-panel[data-panel="music"] .ad-pc'); out.p3 = JV.ardesk._panels();
      JV.ardesk.toggle(false); H.stop();
      return out;
    }, wx);
    check("⛅ büyük hava paneli (derece, 7 gün, saatlik eğri)", hd.wx.t === "18°" && hd.wx.days === 7 && hd.wx.curve, JSON.stringify(hd));
    check("✋ sabit avuç → dairesel menü → ☝ dokun → panel", hd.menu && hd.p1.includes("system"), JSON.stringify(hd));
    check("dock'tan panel + sistem halkaları", hd.p2.includes("music") && hd.rings === 4, JSON.stringify(hd));
    check("🤏 paneli çimdikle tut-taşı", hd.moved > 100, JSON.stringify(hd));
    check("☝ ✕ ile panel kapanır", !hd.p3.includes("music"), JSON.stringify(hd));
    console.log("ARAYÜZ KABUĞU");
    const sh = await p.evaluate(() => ({ core: [...document.querySelectorAll(".ctrl-row .tog")].filter((b) => getComputedStyle(b).display !== "none").map((b) => b.id), tiles: document.querySelectorAll(".ln-tile").length, chips: document.querySelectorAll("#chips .chip").length, date: (document.querySelector("#hdr-date") || {}).textContent || "" }));
    const cc = await p.evaluate(() => ({ cc: document.body.classList.contains("cc"), log: !!document.querySelector("#right #log"), ask: !!document.querySelector("#right .cc-cmd #ask"), gauges: !!document.querySelector("#left .cc-box .gauge[data-k=cpu]"), stage: !!document.querySelector("#cc-stage"), foot: (document.querySelector("#cc-f-model") || {}).textContent || "", views: !!document.querySelector("#top #views") }));
    check("komuta düzeni: sütunlar, sahne, alt şerit", cc.cc && cc.log && cc.ask && cc.gauges && cc.stage && cc.views && cc.foot !== "", JSON.stringify(cc));
    console.log("ORTA SAHNE");
    const sg = await p.evaluate(async () => {
      const o = {}; const w = (ms) => new Promise((r) => setTimeout(r, ms));
      JV.setCoreStyle("reactor"); await w(300); o.reactor = getComputedStyle(document.getElementById("three")).visibility === "hidden";
      JV.uiCommand("stage_animation", { preset: "solar" }, JSON.stringify({ ui: "stage", kind: "anim", preset: "solar", title: "Güneş" })); await w(400);
      o.anim = document.body.classList.contains("stage-busy") && !!document.querySelector("#stage-host #sg-anim") && document.querySelector("#sg-anim").getAttribute("sandbox") === "allow-scripts";
      o.csp = (document.querySelector("#sg-anim").srcdoc || "").includes("Content-Security-Policy");
      o.coreGone = getComputedStyle(document.getElementById("hud")).opacity === "0" || document.body.classList.contains("stage-busy");
      JV.uiCommand("youtube_play", {}, JSON.stringify({ ui: "video", id: "abcDEF12345", title: "T" })); await w(300);
      o.video = JV.stage.current() === "VİDEO" && !!document.querySelector("#stage-host #vp-if") && !document.querySelector("#sg-anim");
      document.dispatchEvent(new KeyboardEvent("keydown", { key: "Escape" })); window.dispatchEvent(new KeyboardEvent("keydown", { key: "Escape" })); await w(300);
      o.back = !document.body.classList.contains("stage-busy") && !JV.stage.current();
      JV.uiCommand("stage_animation", { code: "function draw(t,w,h){g.fillRect(0,0,10,10)}" }, JSON.stringify({ ui: "stage", kind: "anim", preset: "" })); await w(300);
      o.custom = !!document.querySelector("#sg-anim"); JV.uiCommand("stage_clear", {}, JSON.stringify({ ui: "stage", kind: "clear" })); await w(200);
      o.cleared = !JV.stage.current();
      JV.uiCommand("core_style", {}, JSON.stringify({ ui: "core", style: "wave" })); await w(200); o.wave = JV.settings.visual === "wave"; JV.setCoreStyle("reactor");
      return o;
    });
    check("yeni reaktör çekirdeği (2D)", sg.reactor, JSON.stringify(sg));
    check("animasyon ortada, korumalı çerçevede (CSP)", sg.anim && sg.csp && sg.coreGone, JSON.stringify(sg));
    check("YouTube videosu çekirdeğin yerine ortaya gelir", sg.video, JSON.stringify(sg));
    check("Esc → çekirdeğe dönüş", sg.back, JSON.stringify(sg));
    check("modelin yazdığı animasyon + sahneyi kapat", sg.custom && sg.cleared, JSON.stringify(sg));
    check("sesle çekirdek görünümü değişir", sg.wave, JSON.stringify(sg));
    console.log("TELEFON EKRANLARI · ARAMA · KİLİT");
    const ph = await b.newPage({ viewport: { width: 390, height: 844 } }); ph.on("pageerror", (e) => errs.push("ph:" + e.message));
    await ph.route(/youtube|cdn\.jsdelivr|unpkg|fonts\.g|storage\.googleapis/, (r) => r.abort());
    await ph.goto(`http://127.0.0.1:${sp}/?rol=ekran`); await wait(1200); await ph.fill("#sn-nm", "SALON"); await ph.click("#sn-go"); await wait(2200);
    const reg = await p.evaluate(() => JV.api("/api/screens/list"));
    check("telefon ekranı bağlanır", (reg.telefonlar || []).some((x) => x.ad === "SALON"), JSON.stringify(reg));
    await p.evaluate(() => JV.api("/api/screens/send", { body: { type: "show", text: "Yemek hazır", target: "SALON" } })); await wait(2200);
    check("bilgisayardan telefona yazı", await ph.evaluate(() => !document.querySelector("#sn-text").classList.contains("hidden") && document.querySelector("#sn-text").textContent.includes("Yemek")));
    await p.evaluate(() => JV.api("/api/screens/send", { body: { type: "anim", preset: "galaxy" } })); await wait(2200);
    check("telefonda animasyon", await ph.evaluate(() => JV.stage.current() === "ANİMASYON"));
    await p.evaluate(() => JV.api("/api/screens/send", { body: { type: "ring", text: "Toplantı" } })); await wait(2200);
    check("JARVIS telefonu arar (gelen arama)", await ph.evaluate(() => JV.call.ringing()));
    await ph.click("#cl-yes"); await wait(600);
    check("cevapla → sesli görüşme", await ph.evaluate(() => JV.call.active()));
    await ph.click("#cl-end"); await wait(300);
    await ph.evaluate(() => JV._screenRun({ type: "video", id: "abcDEF12345", title: "T" })); await wait(400);
    check("telefonda YouTube tam ekran", await ph.evaluate(() => JV.stage.current() === "VİDEO" && !!document.querySelector("#vp-if")));
    await ph.close();
    const lk = await p.evaluate(async () => { const w = (ms) => new Promise((r) => setTimeout(r, ms)); JV.uiCommand("system_lock", {}, JSON.stringify({ ui: "lock", on: true })); await w(300);
      const on = JV.lock.locked() && !document.getElementById("lockui").classList.contains("hidden"); JV.lock.off(); await w(1000); return { on, off: !JV.lock.locked() }; });
    check("sistem kilidi açılır/kapanır", lk.on && lk.off, JSON.stringify(lk));
    const pin = await p.evaluate(async () => { const w = (ms) => new Promise((r) => setTimeout(r, ms)); await JV.setLockPin("1234"); JV.lock.on(); await w(200); JV.lock.off(); await w(900);
      const still = JV.lock.locked(); document.getElementById("lk-pin").value = "9999"; document.getElementById("lk-go").click(); await w(300); const wrong = JV.lock.locked();
      document.getElementById("lk-pin").value = "1234"; document.getElementById("lk-go").click(); await w(1100); const ok = !JV.lock.locked(); await JV.setLockPin(""); return { still, wrong, ok }; });
    check("PIN varsa komutla açılmaz, yanlış PIN reddedilir, doğru PIN açar", pin.still && pin.wrong && pin.ok, JSON.stringify(pin));
    const cl = await p.evaluate(async () => { JV.uiCommand("call_me", {}, JSON.stringify({ ui: "call", incoming: true, message: "Merhaba" })); await new Promise((r) => setTimeout(r, 300)); const r = JV.call.ringing(); JV.call.end(); return r; });
    check("telefon yoksa bilgisayarda gelen arama", cl);
    check("alt şerit sade (temel düğmeler + UYGULAMALAR)", sh.core.length <= 9 && sh.core.includes("t-apps") && sh.core.includes("t-estop"), JSON.stringify(sh));
    check("başlatıcıda tüm uygulamalar", sh.tiles >= 20, sh.tiles);
    check("üst barda tarih + öneri çipleri", sh.date.length > 5 && sh.chips >= 4, JSON.stringify(sh));
    await p.keyboard.press("Control+k"); await wait(300);
    await p.fill("#pl-q", "hava"); await wait(200);
    const pl = await p.evaluate(() => [...document.querySelectorAll("#pl-list li b")].map((x) => x.textContent));
    check("Ctrl+K komut paleti arar", pl.some((t) => t.includes("Hava")), JSON.stringify(pl));
    await p.press("#pl-q", "Enter"); await wait(1200);
    check("Enter → özellik çalışır (hava paneli)", await p.evaluate(() => !document.querySelector("#wxpanel").classList.contains("hidden")));
    await p.keyboard.press("Escape"); await wait(300);
    const tt = await p.evaluate(async () => { JV.toast("Kaydedildi ✓", 2000); await new Promise((r) => setTimeout(r, 100)); const t = [...document.querySelectorAll(".toast")].pop(); return { ok: t.classList.contains("t-ok"), bar: !!t.querySelector(".t-bar") }; });
    check("HUD bildirimi (renk + süre çizgisi)", tt.ok && tt.bar, JSON.stringify(tt));
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
    await p.click(".gw-dots span:first-child", { force: true }); await p.waitForFunction(() => (document.querySelector(".gw-nav .note") || {}).textContent.includes("1 / 5"), null, { timeout: 4000 }).catch(() => {});
    check("adım çiplerine tıklayınca o adıma gider", (await p.textContent(".gw-nav .note")).includes("1 / 5"));
    await p.keyboard.press("Escape");
    check("sayfa hatası yok", errs.length === 0, errs.slice(0, 3).join(" | "));
  } finally {
    await b.close(); srv.kill(); fake.kill();
  }
  console.log("\nSONUÇ:", ok ? "BAŞARILI" : "HATA VAR");
  process.exit(ok ? 0 : 1);
})();
