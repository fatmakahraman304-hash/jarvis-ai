/* Kamera canlı algılama (tarayıcıda, MediaPipe): nesneler ve insanlar (sayım, hareket yönü, yer değiştirme),
   vücut iskeleti, yüz tanıma (sadece kayıtlı/izinli kişiler), ortam ışığı, periyodik sesli anlatım. */
(function () {
  const JV = (window.JV = window.JV || {});
  const $ = (s) => document.querySelector(s);
  const TR = { person: "insan", bicycle: "bisiklet", car: "araba", motorcycle: "motosiklet", bus: "otobüs", truck: "kamyon", cat: "kedi", dog: "köpek", bird: "kuş",
    backpack: "sırt çantası", umbrella: "şemsiye", handbag: "el çantası", bottle: "şişe", "wine glass": "kadeh", cup: "fincan", fork: "çatal", knife: "bıçak", spoon: "kaşık",
    bowl: "kase", banana: "muz", apple: "elma", orange: "portakal", chair: "sandalye", couch: "kanepe", "potted plant": "saksı bitkisi", bed: "yatak", "dining table": "masa",
    toilet: "tuvalet", tv: "televizyon", laptop: "dizüstü bilgisayar", mouse: "fare", remote: "kumanda", keyboard: "klavye", "cell phone": "telefon", microwave: "mikrodalga",
    oven: "fırın", sink: "lavabo", refrigerator: "buzdolabı", book: "kitap", clock: "saat", vase: "vazo", scissors: "makas", "teddy bear": "oyuncak ayı", "toothbrush": "diş fırçası",
    "sports ball": "top", "tennis racket": "raket", tie: "kravat", suitcase: "bavul", "hair drier": "saç kurutma makinesi", door: "kapı" };
  const tr = (n) => TR[n] || n;
  let on = { det: false, pose: false, face: false, narrate: false };
  let raf = 0, last = 0, narrateT = 0, overlay, octx;
  const tracks = {}; // nesne takibi: etiket → {x,y,t}
  const memory = {}; // son görülen konumlar (yer değiştirme tespiti)
  let faceDb = [];

  function video() { return $("#cam-video"); }
  async function ensure(kind) { try { return await JV.mp.load(kind, { numFaces: 4 }); } catch (e) { JV.toast && JV.toast("Algılama modeli yüklenemedi (internet gerekli)."); throw e; } }

  function toggle(k, btn) {
    on[k] = !on[k]; btn.classList.toggle("on", on[k]);
    if (on[k] && k !== "narrate") ensure({ det: "object", pose: "pose", face: "face" }[k]).catch(() => { on[k] = false; btn.classList.remove("on"); });
    if (Object.values(on).some(Boolean)) { cancelAnimationFrame(raf); loop(); } else { cancelAnimationFrame(raf); clear(); }
  }
  function clear() { if (octx) octx.clearRect(0, 0, overlay.width, overlay.height); $("#cam-info").textContent = ""; }

  // yüz parmak izi (landmark geometrisi) — basit tanıma, güvenlik kilidi olarak kullanılmamalı
  const FIDX = [33, 133, 362, 263, 1, 4, 61, 291, 199, 10, 152, 234, 454, 70, 300, 105, 334, 168, 6, 197, 2, 98, 327, 13, 14, 78, 308, 159, 145, 386, 374];
  function faceVec(f) {
    const io = Math.hypot(f[33].x - f[263].x, f[33].y - f[263].y) || 1e-6, v = [];
    for (let i = 0; i < FIDX.length; i++) for (let j = i + 1; j < FIDX.length; j += 3) { const a = f[FIDX[i]], b = f[FIDX[j]]; v.push(Math.hypot(a.x - b.x, a.y - b.y, (a.z - b.z) * 0.5) / io); }
    return v;
  }
  const vd = (a, b) => Math.sqrt(a.reduce((s, x, i) => s + (x - b[i]) ** 2, 0) / a.length);
  function whoIs(vec) { let best = null, bd = 1e9; faceDb.forEach((p) => { const d = vd(vec, p.vec); if (d < bd) { bd = d; best = p; } }); return best && bd < 0.045 ? best.name : null; }

  async function enrollFace() {
    const name = prompt("Bu kişinin adı? (yalnızca izni olan kişileri kaydet)"); if (!name) return;
    const fl = await ensure("face"); const v = video(); const vecs = [];
    JV.toast && JV.toast("Kameraya düz bak, 2 saniye…");
    const t0 = performance.now();
    await new Promise((res) => (function g() { const r = fl.detectForVideo(v, performance.now()); if (r.faceLandmarks && r.faceLandmarks.length === 1) vecs.push(faceVec(r.faceLandmarks[0])); if (performance.now() - t0 < 2200) requestAnimationFrame(g); else res(); })());
    if (vecs.length < 10) return JV.toast && JV.toast("Tek bir yüz net görülmedi, tekrar dene.");
    const avg = vecs[0].map((_, i) => vecs.reduce((s, x) => s + x[i], 0) / vecs.length);
    faceDb = (JV.settings.faces || []).filter((f) => f.name !== name).concat([{ name, vec: avg.map((x) => +x.toFixed(4)) }]);
    JV.settings.faces = faceDb; await JV.api("/api/settings", { body: { faces: faceDb } });
    JV.toast && JV.toast(`Yüz kaydedildi: ${name}`);
  }

  const POSE_LINKS = [[11, 12], [11, 13], [13, 15], [12, 14], [14, 16], [11, 23], [12, 24], [23, 24], [23, 25], [25, 27], [24, 26], [26, 28]];
  function loop() {
    raf = requestAnimationFrame(loop);
    const v = video(); if (!v || v.readyState < 2) return;
    const now = performance.now(); if (now - last < 90) return; last = now;
    overlay.width = v.clientWidth; overlay.height = v.clientHeight;
    const sx = overlay.width / v.videoWidth, sy = overlay.height / v.videoHeight;
    octx.clearRect(0, 0, overlay.width, overlay.height);
    const col = getComputedStyle(document.documentElement).getPropertyValue("--c").trim() || "#38d6ff";
    octx.lineWidth = 2; octx.font = "13px Share Tech Mono, monospace";
    const lines = [];
    // ışık seviyesi
    const c = document.createElement("canvas"); c.width = 32; c.height = 24; const g = c.getContext("2d"); g.drawImage(v, 0, 0, 32, 24);
    const px = g.getImageData(0, 0, 32, 24).data; let lum = 0; for (let i = 0; i < px.length; i += 4) lum += 0.2126 * px[i] + 0.7152 * px[i + 1] + 0.0722 * px[i + 2];
    lum = lum / (px.length / 4) / 2.55;
    lines.push(`ışık: %${lum.toFixed(0)} ${lum < 20 ? "(karanlık)" : lum > 75 ? "(çok aydınlık)" : ""}`);

    if (on.det) {
      const od = cache("object");
      if (od) {
        const r = od.detectForVideo(v, now), counts = {};
        (r.detections || []).forEach((d) => {
          const b = d.boundingBox, name = tr(d.categories[0].categoryName), score = d.categories[0].score;
          counts[name] = (counts[name] || 0) + 1;
          const cx = (b.originX + b.width / 2) / v.videoWidth, cy = (b.originY + b.height / 2) / v.videoHeight;
          const key = name + "#" + Math.round(cx * 4); let dir = "";
          const prev = tracks[key];
          if (prev && now - prev.t < 1500) { const dx = cx - prev.x, dy = cy - prev.y; if (Math.hypot(dx, dy) > 0.02) dir = Math.abs(dx) > Math.abs(dy) ? (dx > 0 ? "→ sola" : "← sağa") : (dy > 0 ? "↓" : "↑"); }
          tracks[key] = { x: cx, y: cy, t: now };
          const m = memory[name];
          if (name !== "insan" && m && Math.hypot(m.x - cx, m.y - cy) > 0.15 && now - m.t > 3000) lines.push(`⚠ ${name} yer değiştirdi`);
          memory[name] = { x: cx, y: cy, t: now };
          octx.strokeStyle = name === "insan" ? "#5dff9a" : col; octx.fillStyle = octx.strokeStyle;
          octx.strokeRect(b.originX * sx, b.originY * sy, b.width * sx, b.height * sy);
          octx.fillText(`${name} ${(score * 100).toFixed(0)}% ${dir}`, b.originX * sx + 4, b.originY * sy + 14);
        });
        lines.unshift("görülen: " + (Object.entries(counts).map(([k, n]) => `${n} ${k}`).join(", ") || "—"));
        JV.camState = { counts, light: lum, time: Date.now() };
      }
    }
    if (on.pose && cache("pose")) {
      const r = cache("pose").detectForVideo(v, now);
      octx.strokeStyle = "#ffd34d";
      (r.landmarks || []).forEach((lm) => {
        POSE_LINKS.forEach(([a, b2]) => { octx.beginPath(); octx.moveTo(lm[a].x * overlay.width, lm[a].y * overlay.height); octx.lineTo(lm[b2].x * overlay.width, lm[b2].y * overlay.height); octx.stroke(); });
        const handsUp = lm[15].y < lm[11].y && lm[16].y < lm[12].y;
        if (handsUp) lines.push("🙌 eller yukarıda");
      });
      lines.push(`vücut: ${(r.landmarks || []).length} kişi`);
    }
    if (on.face && cache("face")) {
      const r = cache("face").detectForVideo(v, now);
      (r.faceLandmarks || []).forEach((f) => {
        const xs = f.map((p) => p.x), ys = f.map((p) => p.y), x0 = Math.min(...xs), y0 = Math.min(...ys), x1 = Math.max(...xs), y1 = Math.max(...ys);
        const who = whoIs(faceVec(f));
        octx.strokeStyle = who ? "#5dff9a" : "#ff9a3c"; octx.fillStyle = octx.strokeStyle;
        octx.strokeRect(x0 * overlay.width, y0 * overlay.height, (x1 - x0) * overlay.width, (y1 - y0) * overlay.height);
        octx.fillText(who || "tanınmıyor", x0 * overlay.width + 4, y0 * overlay.height - 4);
        if (who) lines.push(`👤 ${who}`);
      });
    }
    if (on.narrate && now - narrateT > 15000 && !JV.speaking) { narrateT = now; narrate(); }
    $("#cam-info").textContent = lines.join("  ·  ");
  }
  function cache(k) { JV.mp.load(k, { numFaces: 4 }).then((m) => (window["__mp_" + k] = m)).catch(() => {}); return window["__mp_" + k]; }

  async function narrate() {
    const v = video(); const c = document.createElement("canvas"); c.width = 640; c.height = Math.round(v.videoHeight * 640 / v.videoWidth);
    c.getContext("2d").drawImage(v, 0, 0, c.width, c.height);
    const r = await JV.api("/api/vision", { body: { image: c.toDataURL("image/jpeg", 0.8), question: "Kameradaki sahnede ne değişti, ne görüyorsun? Tek kısa cümleyle söyle.", persona: JV.persona ? JV.persona() : "jarvis" } });
    if (r.text) { JV.say(r.text, JV.persona ? JV.persona() : "jarvis"); $("#cam-info").textContent = "🔊 " + r.text; }
  }

  function init() {
    overlay = $("#cam-overlay"); if (!overlay) return; octx = overlay.getContext("2d");
    $("#cam-det").onclick = (e) => toggle("det", e.target);
    $("#cam-pose").onclick = (e) => toggle("pose", e.target);
    $("#cam-face").onclick = (e) => { toggle("face", e.target); faceDb = JV.settings.faces || []; };
    $("#cam-narr").onclick = (e) => toggle("narrate", e.target);
    $("#cam-enroll").onclick = enrollFace;
  }
  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", init); else init();
})();
