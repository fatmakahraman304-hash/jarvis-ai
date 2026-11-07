/* El / baş / göz kontrolü (MediaPipe, tarayıcıda çalışır; görüntü bilgisayardan çıkmaz).
   Modlar: nesne (3D dünyalar), fare (gerçek fare), klavye (hava klavyesi), komut (pozlar → eylem), robot, bas (baş + göz kırpma). */
(function () {
  const JV = (window.JV = window.JV || {});
  const MP_VER = "0.10.14";
  const MP = `https://cdn.jsdelivr.net/npm/@mediapipe/tasks-vision@${MP_VER}`;
  const MODELS = {
    hand: "https://storage.googleapis.com/mediapipe-models/hand_landmarker/hand_landmarker/float16/1/hand_landmarker.task",
    face: "https://storage.googleapis.com/mediapipe-models/face_landmarker/face_landmarker/float16/1/face_landmarker.task",
    object: "https://storage.googleapis.com/mediapipe-models/object_detector/efficientdet_lite0/float16/1/efficientdet_lite0.tflite",
    pose: "https://storage.googleapis.com/mediapipe-models/pose_landmarker/pose_landmarker_lite/float16/1/pose_landmarker_lite.task",
  };
  let vision = null, fileset = null;
  const cache = {};
  JV.mp = {
    _cache: (k) => cache[k],
    async load(kind, opts = {}) {
      if (cache[kind]) return cache[kind];
      if (!vision) { vision = await import(`${MP}/vision_bundle.mjs`); fileset = await vision.FilesetResolver.forVisionTasks(`${MP}/wasm`); }
      const base = (delegate) => ({ baseOptions: { modelAssetPath: MODELS[kind], delegate }, runningMode: "VIDEO" });
      const make = async (delegate) => {
        if (kind === "hand") return vision.HandLandmarker.createFromOptions(fileset, { ...base(delegate), numHands: 2, minHandDetectionConfidence: 0.6, minTrackingConfidence: 0.5 });
        if (kind === "face") return vision.FaceLandmarker.createFromOptions(fileset, { ...base(delegate), numFaces: opts.numFaces || 1, outputFaceBlendshapes: true });
        if (kind === "object") return vision.ObjectDetector.createFromOptions(fileset, { ...base(delegate), scoreThreshold: 0.45, maxResults: 15 });
        if (kind === "pose") return vision.PoseLandmarker.createFromOptions(fileset, { ...base(delegate), numPoses: 3 });
      };
      try { cache[kind] = await make("GPU"); } catch (e) { cache[kind] = await make("CPU"); }
      return cache[kind];
    },
  };

  const $ = (s) => document.querySelector(s);
  const G = JV.GestureCore;
  const engine = new G.Engine({ holdMs: 900 });
  let video = null, stream = null, running = false, mode = "nesne", raf = 0, lastTs = -1;
  let hud, hctx, cursorEl;
  const smooth = { x: 0.5, y: 0.5 };

  // ---------- sunucuya gerçek fare/klavye komutu ----------
  let lastMouse = 0;
  function os(path, body, force) {
    const now = performance.now();
    if (!force && path === "mouse" && body.action === "move" && now - lastMouse < 33) return;
    if (path === "mouse") lastMouse = now;
    return fetch("/api/gesture/" + path, { method: "POST", headers: { "Content-Type": "application/json", "x-token": JV.token || "" }, body: JSON.stringify(body) }).catch(() => {});
  }
  const map = (v, lo = 0.15, hi = 0.85) => Math.min(1, Math.max(0, (v - lo) / (hi - lo)));

  // ---------- başlat / durdur ----------
  async function start(m) {
    if (m) setMode(m);
    if (running) return;
    // Camera inspection and gesture/AR are separate activities.
    if (JV.camera && JV.camera.close) JV.camera.close();
    showHud(true); status("Model yükleniyor…");
    try {
      stream = await navigator.mediaDevices.getUserMedia({ video: { width: 640, height: 480, facingMode: "user" }, audio: false });
      video = video || Object.assign(document.createElement("video"), { muted: true, playsInline: true });
      video.srcObject = stream; await video.play();
      await JV.mp.load("hand");
      if (mode === "bas") await JV.mp.load("face");
      running = true; status(""); loop();
      if (mode === "efekt" && JV.handfx) { JV.handfx.show(stream); JV.mp.load("face", { numFaces: 3 }).catch(() => {}); }
      JV.toast && JV.toast("El kontrolü açık. Modu panelden seç.");
    } catch (e) {
      status("Başlatılamadı: " + (e.message || e)); console.warn(e);
      JV.toast && JV.toast("El kontrolü başlatılamadı (kamera izni ve internet gerekli: " + (e.message || e) + ")");
    }
  }
  function stop() {
    running = false; cancelAnimationFrame(raf);
    if (JV.handfx && JV.handfx.active) { const h = JV.handfx; mode = "nesne"; h.stop(); }
    if (stream) stream.getTracks().forEach((t) => t.stop()); stream = null;
    showHud(false); cursorEl.style.display = "none"; $("#air-kb").classList.add("hidden");
    if (grabbing) { os("mouse", { action: "up" }, true); grabbing = false; }
  }

  function setMode(m) {
    mode = m;
    document.querySelectorAll("#g-modes button").forEach((b) => b.classList.toggle("on", b.dataset.m === m));
    $("#air-kb").classList.toggle("hidden", m !== "klavye");
    if (m === "bas" && running) JV.mp.load("face").catch(() => {});
    if (JV.handfx) {
      if (m === "efekt" && running && !JV.handfx.active) { JV.handfx.show(stream); JV.mp.load("face", { numFaces: 3 }).catch(() => {}); }
      if (m !== "efekt" && JV.handfx.active) JV.handfx.stop();
    }
    $("#g-help").textContent = HELP[m] || "";
  }
  const HELP = {
    nesne: "Açık el: döndür · Başparmak+işaret aç/kapa: yakınlaştır · Yumruk: tut/taşı · Çabuk kıstır: tıkla · Hızlı el savur: mod değiştir · İki elle kıstır-aç: büyüt",
    fare: "İşaret parmağı: fare · Kıstır: tıkla / basılı tut-sürükle (pencere taşıma) · Yumruk+yukarı/aşağı: kaydır · Rock 🤘 bekle: sağ tık",
    klavye: "İşaret parmağını tuşun üstüne getir, kıstırarak bas. Hedef: JARVIS kutusu veya bilgisayar.",
    komut: "Sol el kıstır+yukarı/aşağı: ses · Sağ el kıstır+yukarı/aşağı: parlaklık · Pozlar: ✋ dur · ✌ mikrofon · 👍 onayla · ✊(2sn) kilitle · kendi hareketlerin",
    efekt: "✋ ateş · ✋✋ mühür halkası · 🤏 gezegen (taşı/fırlat) · 🤏🤏 büyüt · ✊→✋ patlat · ☝☝ şimşek · ☝ ışık izi · 👍 1sn komut · ✌ mikrofon · ✊ 2sn sus · Esc kapat",
    robot: "Elin konumu: taban/omuz · Elin büyüklüğü (kameraya uzaklık): dirsek · Kıstır: kıskaç",
    bas: "Başını çevir: imleç · Uzun göz kırp (yarım sn): tıkla · Sağa/sola bak (1 sn): mod değiştir",
  };

  // ---------- ana döngü ----------
  function loop() {
    if (!running) return;
    raf = requestAnimationFrame(loop);
    if (video.readyState < 2) return;
    const ts = performance.now();
    if (ts - lastTs < 30) return; lastTs = ts;
    let res = null, face = null;
    try {
      if (mode === "bas") face = cache.face && cache.face.detectForVideo(video, ts);
      else res = cache.hand.detectForVideo(video, ts);
    } catch (e) { return; }
    drawHud(res, face);
    if (face) return headMode(face, ts);
    if (mode === "efekt" && JV.handfx && JV.handfx.active) {
      let faces = null;
      if (cache.face && (JV.handfx.opts.face || JV.handfx.opts.mask) && ts - (loop.faceT || 0) > 140) { loop.faceT = ts; try { faces = cache.face.detectForVideo(video, ts + 0.5).faceLandmarks; } catch (e) {} }
      const hs2 = (res.landmarks || []).map((lm, i) => ({ lm, handed: (((res.handedness || res.handednesses || [])[i] || [{}])[0].categoryName === "Left") ? "Right" : "Left" }));
      JV.handfx.frame(hs2, faces);
      return;
    }
    const hands = (res.landmarks || []).map((lm, i) => {
      const lab = ((res.handedness || res.handednesses || [])[i] || [{}])[0].categoryName || "Right";
      return { lm, handed: lab === "Left" ? "Right" : "Left" }; // MediaPipe aynalı görüntü varsayar
    });
    const evs = engine.update(hands, ts);
    evs.forEach(dispatch);
  }

  // ---------- olay → eylem ----------
  let grabbing = false, volAcc = 0, briAcc = 0, kbHover = null, lastRobot = 0;
  function screenXY(e) { return [map(e.x) * innerWidth, map(e.y, 0.12, 0.8) * innerHeight]; }

  function dispatch(e) {
    if (e.type === "cursor" && (e.hand === "Right" || engine.h.Left === undefined)) {
      smooth.x += (map(e.x) - smooth.x) * 0.45; smooth.y += (map(e.y, 0.12, 0.8) - smooth.y) * 0.45;
      cursorEl.style.display = mode === "robot" ? "none" : "block";
      cursorEl.style.left = smooth.x * innerWidth + "px"; cursorEl.style.top = smooth.y * innerHeight + "px";
      cursorEl.dataset.pose = e.pose;
      if (mode === "fare") os("mouse", { action: "move", x: smooth.x, y: smooth.y });
      if (mode === "klavye") kbHoverAt(smooth.x * innerWidth, smooth.y * innerHeight);
      if (mode === "robot") robot(e);
    }
    if (e.type === "swipe" && (mode === "nesne" || mode === "komut")) {
      const order = ["core", "globe", "lab", "science", "space"], cur = order.indexOf(JV.getView ? JV.getView() : "core");
      JV.setView(order[(cur + (e.dir === "left" ? 1 : order.length - 1)) % order.length]);
    }
    if (mode === "nesne") objectMode(e);
    else if (mode === "fare") mouseMode(e);
    else if (mode === "klavye") { if (e.type === "click" && kbHover) kbPress(kbHover); }
    else if (mode === "komut") commandMode(e);
    if (e.type === "custom") runAction(e.gesture.action, e.gesture.name);
  }

  function objectMode(e) {
    const v = JV.getView ? JV.getView() : "core";
    if (e.type === "rotate") {
      if (v === "lab") JV.lab.rotate(e.dx * 7, e.dy * 4);
      else if (v === "science") JV.science.rotate(e.dx * 5, e.dy * 3);
      else if (v === "globe" || v === "space") JV.world.orbit(e.dx * 5, e.dy * 4);
    }
    if (e.type === "zoom" || e.type === "two_hand_scale") {
      if (v === "lab") JV.lab.scale(e.f); else if (JV.world.active()) JV.world.zoom(1 / e.f);
    }
    if (e.type === "grab_start") { grabbing = true; if (v === "lab") JV.lab.grab(true, ...screenXY(e)); }
    if (e.type === "grab_move") { if (v === "lab") JV.lab.move(...screenXY(e)); else if (v === "globe") JV.world.orbit(e.dx * 4, e.dy * 3); else if (v === "science") JV.science.rotate(e.dx * 5, e.dy * 3); }
    if (e.type === "grab_end") { grabbing = false; if (v === "lab") JV.lab.grab(false); }
    if (e.type === "click") clickAt(smooth.x * innerWidth, smooth.y * innerHeight);
    if (e.type === "pose_hold") poseAction(e.pose);
  }

  function clickAt(x, y) {
    const el = document.elementFromPoint(x, y);
    if (!el) return;
    if (el.id === "world" || el.id === "three") {
      const opt = { clientX: x, clientY: y, bubbles: true };
      el.dispatchEvent(new PointerEvent("pointerdown", opt)); el.dispatchEvent(new PointerEvent("pointerup", opt));
    } else el.click();
    ripple(x, y);
  }

  let scrollAcc = 0;
  function mouseMode(e) {
    if (e.type === "pinch_start") { os("mouse", { action: "down", x: smooth.x, y: smooth.y }, true); grabbing = true; ripple(smooth.x * innerWidth, smooth.y * innerHeight); }
    if (e.type === "pinch_end") { os("mouse", { action: "up", x: smooth.x, y: smooth.y }, true); grabbing = false; }
    if (e.type === "grab_move") { scrollAcc += e.dy; if (Math.abs(scrollAcc) > 0.03) { os("mouse", { action: "scroll", amount: scrollAcc > 0 ? -2 : 2 }, true); scrollAcc = 0; } }
    if (e.type === "pose_hold" && e.pose === "rock") os("mouse", { action: "right", x: smooth.x, y: smooth.y }, true);
  }

  function commandMode(e) {
    if (e.type === "pinch_move") {
      if (e.hand === "Left") { volAcc += e.dy; if (Math.abs(volAcc) > 0.035) { os("media", { action: volAcc < 0 ? "volume_up" : "volume_down", steps: 1 }, true); volAcc = 0; } }
      else { briAcc += e.dy; if (Math.abs(briAcc) > 0.03) { os("brightness", { delta: briAcc < 0 ? 5 : -5 }, true); briAcc = 0; } }
    }
    if (e.type === "pose_hold") poseAction(e.pose);
  }

  function poseAction(p) {
    const map2 = (JV.settings.gesture_poses) || { open: "stop", peace: "mic", thumbs_up: "approve", fist: "lock", three: "screenshot" };
    const a = map2[p]; if (!a) return;
    flash(p);
    if (a === "stop") JV.stopSpeaking && JV.stopSpeaking();
    else if (a === "mic") $("#mic").click();
    else if (a === "approve") { const b = document.querySelector(".confirm .btn-danger"); if (b) b.click(); }
    else if (a === "lock" && mode === "komut") JV.sendCommand && JV.sendCommand("Bilgisayarı kilitle");
    else if (a === "screenshot" && mode === "komut") os("key", { keys: "win+printscreen" }, true);
  }

  function runAction(action, name) {
    flash("★ " + name);
    if (!action) return;
    if (action.type === "command") JV.sendCommand && JV.sendCommand(action.arg);
    else if (action.type === "key") os("key", { keys: action.arg }, true);
    else if (action.type === "view") JV.setView(action.arg);
    else if (action.type === "stop") JV.stopSpeaking();
  }

  // ---------- robot kol ----------
  function robot(e) {
    const now = performance.now(); if (now - lastRobot < 120) return; lastRobot = now;
    const st = engine.h[e.hand]; if (!st) return;
    const base = Math.round(map(e.x) * 180), shoulder = Math.round((1 - map(e.y, 0.12, 0.8)) * 180);
    const elbow = Math.round(Math.max(0, Math.min(180, ((lastPalm || 0.2) - 0.1) / 0.2 * 180))); // el kameraya yaklaştıkça dirsek açılır
    const grip = e.pose === "pinch" || e.pose === "fist" ? 20 : 90;
    os("robot", { base, shoulder, elbow, gripper: grip }, true);
    $("#g-status").textContent = `taban ${base}° · omuz ${shoulder}° · kıskaç ${grip === 20 ? "kapalı" : "açık"}`;
  }
  let lastPalm = 0;

  // ---------- baş + göz ----------
  let blinkStart = 0, lookDir = null, lookSince = 0, headRef = null;
  function headMode(face, ts) {
    const f = (face.faceLandmarks || [])[0];
    if (!f) return;
    const nose = f[1], l = f[234], r = f[454], top = f[10], bot = f[152];
    const hx = (nose.x - l.x) / (r.x - l.x), hy = (nose.y - top.y) / (bot.y - top.y);
    if (!headRef) headRef = { x: hx, y: hy };
    const x = Math.min(1, Math.max(0, 0.5 - (hx - headRef.x) * 4)), y = Math.min(1, Math.max(0, 0.5 + (hy - headRef.y) * 5));
    smooth.x += (x - smooth.x) * 0.3; smooth.y += (y - smooth.y) * 0.3;
    cursorEl.style.display = "block"; cursorEl.style.left = smooth.x * innerWidth + "px"; cursorEl.style.top = smooth.y * innerHeight + "px";
    if ($("#g-os").checked) os("mouse", { action: "move", x: smooth.x, y: smooth.y });
    const bs = ((face.faceBlendshapes || [])[0] || { categories: [] }).categories;
    const g = (n) => (bs.find((c) => c.categoryName === n) || { score: 0 }).score;
    const blink = g("eyeBlinkLeft") > 0.5 && g("eyeBlinkRight") > 0.5;
    if (blink && !blinkStart) blinkStart = ts;
    if (!blink && blinkStart) {
      const dur = ts - blinkStart; blinkStart = 0;
      if (dur > 380 && dur < 1500) { if ($("#g-os").checked) { os("mouse", { action: "down", x: smooth.x, y: smooth.y }, true); os("mouse", { action: "up", x: smooth.x, y: smooth.y }, true); } else clickAt(smooth.x * innerWidth, smooth.y * innerHeight); flash("göz kırpma: tık"); }
    }
    // bakış yönü (göz bebeği): sağa/sola bakış
    const lookL = g("eyeLookOutLeft") + g("eyeLookInRight"), lookR = g("eyeLookInLeft") + g("eyeLookOutRight");
    const dir = lookL > 0.9 ? "left" : lookR > 0.9 ? "right" : null;
    if (dir !== lookDir) { lookDir = dir; lookSince = ts; }
    else if (dir && ts - lookSince > 1000) { lookSince = ts + 1e9; dispatch({ type: "swipe", dir: dir === "left" ? "right" : "left" }); flash("bakış: " + (dir === "left" ? "sol" : "sağ")); }
    $("#g-status").textContent = `bakış: ${dir ? (dir === "left" ? "sol" : "sağ") : "orta"} · göz kırp: ${blink ? "kapalı" : "açık"}`;
  }

  // ---------- hava klavyesi ----------
  const ROWS = ["1234567890", "QWERTYUIOPĞÜ", "ASDFGHJKLŞİ", "ZXCVBNMÖÇ.,"];
  function buildKb() {
    const kb = $("#air-kb"); kb.innerHTML = "";
    ROWS.forEach((r) => { const row = document.createElement("div"); row.className = "kb-row"; [...r].forEach((k) => row.append(key(k, k))); kb.append(row); });
    const row = document.createElement("div"); row.className = "kb-row";
    row.append(key("⌫", "back"), key("BOŞLUK", "space", "wide"), key("↵ GÖNDER", "enter"), key("HEDEF: JARVIS", "target"));
    kb.append(row);
    const out = document.createElement("div"); out.id = "kb-out"; kb.prepend(out);
  }
  function key(label, val, cls) { const b = document.createElement("button"); b.textContent = label; b.dataset.k = val; if (cls) b.className = cls; b.onclick = () => kbPress(b); return b; }
  let kbOS = false, kbText = "";
  function kbHoverAt(x, y) {
    const el = document.elementFromPoint(x, y);
    const k = el && el.closest && el.closest("#air-kb button");
    if (kbHover && kbHover !== k) kbHover.classList.remove("hover");
    kbHover = k; if (k) k.classList.add("hover");
  }
  function kbPress(b) {
    const k = b.dataset.k; b.classList.add("press"); setTimeout(() => b.classList.remove("press"), 150);
    if (k === "target") { kbOS = !kbOS; b.textContent = kbOS ? "HEDEF: BİLGİSAYAR" : "HEDEF: JARVIS"; return; }
    if (kbOS) {
      if (k === "back") os("key", { keys: "backspace" }, true); else if (k === "enter") os("key", { keys: "enter" }, true);
      else os("type", { text: k === "space" ? " " : k.toLowerCase() }, true);
    } else {
      if (k === "back") kbText = kbText.slice(0, -1); else if (k === "space") kbText += " ";
      else if (k === "enter") { if (kbText.trim()) JV.sendCommand(kbText); kbText = ""; } else kbText += k.toLocaleLowerCase("tr");
      $("#q").value = kbText;
    }
    $("#kb-out").textContent = kbOS ? "(bilgisayara yazılıyor)" : kbText || " ";
  }

  // ---------- HUD ----------
  function showHud(on) { $("#gesture-hud").classList.toggle("hidden", !on); document.getElementById("t-gesture").classList.toggle("on", on); }
  function status(t) { $("#g-status").textContent = t; }
  function flash(t) { const f = $("#g-flash"); f.textContent = t; f.classList.add("on"); clearTimeout(f._t); f._t = setTimeout(() => f.classList.remove("on"), 900); }
  function ripple(x, y) { const r = document.createElement("div"); r.className = "g-ripple"; r.style.left = x + "px"; r.style.top = y + "px"; document.body.append(r); setTimeout(() => r.remove(), 500); }
  const LINKS = [[0, 1], [1, 2], [2, 3], [3, 4], [0, 5], [5, 6], [6, 7], [7, 8], [5, 9], [9, 10], [10, 11], [11, 12], [9, 13], [13, 14], [14, 15], [15, 16], [13, 17], [17, 18], [18, 19], [19, 20], [0, 17]];
  function drawHud(res, face) {
    const w = hud.width, h = hud.height;
    hctx.save(); hctx.scale(-1, 1); hctx.drawImage(video, -w, 0, w, h); hctx.restore();
    hctx.fillStyle = "rgba(0,10,20,.35)"; hctx.fillRect(0, 0, w, h);
    const col = getComputedStyle(document.documentElement).getPropertyValue("--c").trim() || "#38d6ff";
    hctx.strokeStyle = col; hctx.fillStyle = "#fff"; hctx.lineWidth = 2;
    (res && res.landmarks || []).forEach((lm, i) => {
      if (i === 0) lastPalm = Math.hypot(lm[0].x - lm[9].x, lm[0].y - lm[9].y);
      LINKS.forEach(([a, b]) => { hctx.beginPath(); hctx.moveTo((1 - lm[a].x) * w, lm[a].y * h); hctx.lineTo((1 - lm[b].x) * w, lm[b].y * h); hctx.stroke(); });
      lm.forEach((p) => { hctx.beginPath(); hctx.arc((1 - p.x) * w, p.y * h, 2.2, 0, 7); hctx.fill(); });
      hctx.fillStyle = col; hctx.font = "12px Share Tech Mono, monospace";
      hctx.fillText(G.pose(lm), (1 - lm[0].x) * w + 6, lm[0].y * h + 14); hctx.fillStyle = "#fff";
    });
    (face && face.faceLandmarks || []).forEach((f) => { [1, 33, 263, 468, 473, 61, 291, 10, 152].forEach((k) => { if (f[k]) { hctx.beginPath(); hctx.arc((1 - f[k].x) * w, f[k].y * h, 2.5, 0, 7); hctx.fill(); } }); });
    hctx.fillStyle = col; hctx.font = "11px Share Tech Mono, monospace"; hctx.fillText("MOD: " + mode.toUpperCase(), 6, 14);
  }

  // ---------- özel hareket öğretme ----------
  async function teach() {
    const name = prompt("Hareketin adı (örn. 'tabanca')"); if (!name) return;
    const cmd = prompt("Bu hareketi yapınca JARVIS ne yapsın? (örn. 'Spotify'ı aç', 'müziği durdur', 'ses kaydını başlat')"); if (!cmd) return;
    if (!running) await start();
    flash("Hareketi göster ve 2 sn tut"); await new Promise((r) => setTimeout(r, 1200));
    const vecs = [];
    const t0 = performance.now();
    await new Promise((resolve) => {
      (function grab() {
        const r = cache.hand.detectForVideo(video, performance.now());
        if (r.landmarks && r.landmarks[0]) vecs.push(G.normVec(r.landmarks[0]));
        if (performance.now() - t0 < 2000) requestAnimationFrame(grab); else resolve();
      })();
    });
    if (vecs.length < 10) { flash("El görülmedi, tekrar dene"); return; }
    const avg = vecs[0].map((_, i) => vecs.reduce((s, v) => s + v[i], 0) / vecs.length);
    const list = (JV.settings.custom_gestures || []).filter((g) => g.name !== name);
    list.push({ name, vec: avg.map((x) => +x.toFixed(4)), action: { type: "command", arg: cmd } });
    JV.settings.custom_gestures = list; engine.custom = list;
    await JV.api("/api/settings", { body: { custom_gestures: list } });
    flash("Öğrenildi: " + name); renderCustom();
  }
  function renderCustom() {
    const ul = $("#g-custom"); ul.innerHTML = "";
    (JV.settings.custom_gestures || []).forEach((g) => {
      const li = document.createElement("li"); li.textContent = `★ ${g.name} → ${g.action.arg}`;
      const d = document.createElement("button"); d.className = "mini"; d.textContent = "SİL";
      d.onclick = async () => { const l = JV.settings.custom_gestures.filter((x) => x.name !== g.name); JV.settings.custom_gestures = l; engine.custom = l; await JV.api("/api/settings", { body: { custom_gestures: l } }); renderCustom(); };
      li.append(d); ul.append(li);
    });
  }

  // ---------- arayüz bağlantıları ----------
  function init() {
    hud = $("#g-canvas"); hctx = hud.getContext("2d"); cursorEl = $("#g-cursor");
    buildKb();
    document.querySelectorAll("#g-modes button").forEach((b) => (b.onclick = () => setMode(b.dataset.m)));
    $("#g-close").onclick = stop;
    $("#g-teach").onclick = teach;
    $("#t-gesture").onclick = () => (running ? stop() : start());
    setMode("nesne");
    setTimeout(() => { engine.custom = JV.settings.custom_gestures || []; renderCustom(); }, 1500);
  }
  JV.gesture = { start, stop, setMode, isRunning: () => running, mode: () => mode };
  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", init); else init();
})();
