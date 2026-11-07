/* AR EFEKT SAHNESİ — kamera görüntüsünün üstünde ellerle büyü (tamamen özgün, prosedürel; dosya/video kullanılmaz).
   ✋ açık el: parmak uçları alev alır, parmaklar arasında kıvılcım · ✋✋ iki açık el: dönen mühür halkaları (el yana dönünce daralır)
   🤏 çimdik: parmak ucunda parçacık gezegen (Dünya, Mars, Jüpiter, Satürn, Ay, Güneş) — taşı, bırak süzülsün, savur fırlasın
   🤏🤏 iki elle çimdik: gezegeni iki elin arasında büyüt · ✊→✋ yumruğu hızla aç: patlama + ekran sarsıntısı
   ☝☝ iki işaret parmağı: arada şimşek · ☝ tek işaret: ışık izi
   Basılı tut (halka dolar): 👍 1 sn komut · ✌ 0,9 sn mikrofon · ✊ 1,8 sn JARVIS sussun
   Yüz kilidi: en yakın yüzün çevresinde hedef çerçevesi kapanır, kilitlenince karşılar (yüz ALGILAMA — kimlik tanıma değil).
   Görüntü bilgisayardan çıkmaz. */
(function () {
  const JV = (window.JV = window.JV || {});
  const G = () => JV.GestureCore;
  const TAU = Math.PI * 2;
  const OPT_KEY = "jv_handfx_opts";
  const PROFILE_KEY = "jv_handfx_profile_v1";
  // These are mutually exclusive AR experiences. The 3D globe lives in the
  // independent "nesne" gesture mode, never inside camera effects.
  const PROFILES = {
    fire: ["🔥 Ateş", "✋ Açık el: yalnızca ateş"],
    seal: ["⭕ Mühür", "✋✋ İki açık el: mühür halkası"],
    planet: ["🪐 Avuçta gezegen", "🤏 Çimdikle gezegeni tut / bırak"],
    lightning: ["⚡ Şimşek", "☝☝ İki işaret parmağını göster"],
    blast: ["💥 Patlama", "✊ Yumruk yapıp hızla elini aç"],
    trail: ["✨ Işık izi", "☝ İşaret parmağınla iz çiz"],
    palm: ["🖐 Avuç HUD", "✋ Avucunu sabit tut: HUD"],
    face: ["🎯 Yüz takip", "Kameraya bak: yüz hedef çerçevesi"],
    mask: ["🛡 Kask HUD", "Kameraya bak: Iron Man kaskı"],
    draw: ["✏️ Havaya çizim", "☝ Çiz · ✌ yorumla · ✊ temizle"],
    skeleton: ["🦴 El iskeleti", "El eklemlerini ve çizgilerini göster"],
    library: ["📚 Kitaplık AR", "Rafa bak: kitabı seç ve aç"],
    desktop: ["🖥 AR masaüstü", "✋ Avuçla menüyü ve panelleri kontrol et"],
    controls: ["🎙 El komutları", "👍 komut · ✌ mikrofon · ✊ sustur"],
    game: ["🎮 El oyunu", "Oyunu uygulamalar menüsünden başlat"],
    none: ["📷 Sade görüntü", "Hiçbir efekt etkin değil"]
  };
  const EXCLUSIVE = ["fire", "seal", "planet", "lightning", "blast", "trail",
                     "palm", "face", "mask", "draw", "library", "controls", "skeleton"];
  let profile = "fire";
  try { const saved = localStorage.getItem(PROFILE_KEY); if (Object.prototype.hasOwnProperty.call(PROFILES, saved)) profile = saved; } catch (e) {}

  const DEF = { helmet: true, palm: true, draw: false, mask: false, library: true, fire: true, seal: true, planet: true, blast: true, lightning: true, trail: true, controls: true, face: true, sound: true, skeleton: false };
  let opts = { ...DEF };
  try { Object.assign(opts, JSON.parse(localStorage.getItem(OPT_KEY) || "{}")); } catch (e) {}
  const saveOpts = () => { try { localStorage.setItem(OPT_KEY, JSON.stringify(opts)); } catch (e) {} };

  let stage, cv, ctx, vid, W = 0, H = 0, on = false, raf = 0, demoT = 0, demo = false;
  let parts = [], planets = [], bolts = [], waves = [], trail = [], shakeUntil = 0, fps = 0, fpsN = 0, fpsT = 0;
  const hs = {}; // el durumu (Left/Right)
  let face = { box: null, since: 0, locked: false, lastGreet: 0, others: [] };
  let nextPlanet = 0, forcePlanet = "";
  const ORDER = ["saturn", "earth", "mars", "jupiter", "moon", "sun"];
  const PAL = {
    earth: [[40, 110, 255], [30, 200, 120], [235, 245, 255]], mars: [[220, 80, 40], [255, 140, 70], [150, 50, 30]],
    jupiter: [[220, 180, 130], [180, 120, 80], [245, 225, 190]], saturn: [[230, 200, 140], [200, 165, 100], [255, 235, 180]],
    moon: [[190, 190, 195], [140, 140, 150], [230, 230, 235]], sun: [[255, 210, 60], [255, 140, 20], [255, 250, 200]],
  };
  const NAMES = { earth: "DÜNYA", mars: "MARS", jupiter: "JÜPİTER", saturn: "SATÜRN", moon: "AY", sun: "GÜNEŞ" };
  const SPHERE = (() => { const n = 520, out = []; const g = Math.PI * (3 - Math.sqrt(5)); for (let i = 0; i < n; i++) { const y = 1 - (i / (n - 1)) * 2, r = Math.sqrt(1 - y * y), t = g * i; out.push([Math.cos(t) * r, y, Math.sin(t) * r, Math.random()]); } return out; })();

  // ---------------- ses (anında sentez) ----------------
  let ac = null;
  function snd(kind) {
    if (!opts.sound) return;
    try {
      ac = ac || new (window.AudioContext || window.webkitAudioContext)();
      const t = ac.currentTime, o = ac.createOscillator(), g = ac.createGain();
      o.connect(g); g.connect(ac.destination);
      const set = { lock: [880, 1320, 0.18, "triangle"], boom: [120, 30, 0.5, "sawtooth"], pop: [520, 260, 0.12, "sine"], zap: [1800, 400, 0.08, "square"], tick: [1200, 1200, 0.04, "sine"] }[kind] || [440, 440, 0.1, "sine"];
      o.type = set[3]; o.frequency.setValueAtTime(set[0], t); o.frequency.exponentialRampToValueAtTime(Math.max(20, set[1]), t + set[2]);
      g.gain.setValueAtTime(kind === "boom" ? 0.35 : 0.12, t); g.gain.exponentialRampToValueAtTime(0.0001, t + set[2] + 0.05);
      o.start(t); o.stop(t + set[2] + 0.08);
      if (kind === "boom") { const n = ac.createBufferSource(), b = ac.createBuffer(1, ac.sampleRate * 0.4, ac.sampleRate), d = b.getChannelData(0); for (let i = 0; i < d.length; i++) d[i] = (Math.random() * 2 - 1) * (1 - i / d.length) ** 2; n.buffer = b; const ng = ac.createGain(); ng.gain.value = 0.25; n.connect(ng); ng.connect(ac.destination); n.start(t); }
    } catch (e) {}
  }

  // ---------------- sahne ----------------
  function build() {
    if (stage) return;
    stage = document.createElement("div"); stage.id = "arstage"; stage.className = "hidden";
    stage.innerHTML = `<video id="ar-video" muted playsinline></video><canvas id="ar-canvas"></canvas>
      <div id="ar-top"><b>AR · TEK MOD</b><label class="ar-mode-label">MOD <select id="ar-profile" aria-label="Aktif AR efekti"></select></label><span id="ar-fps"></span><span id="ar-hint"></span>
        <button class="mini" id="ar-world-b">🌍 DÜNYA</button><button class="mini" id="ar-camera-b">📷 KAMERA</button>
        <button class="mini" id="ar-desk-b">🖥 MASAÜSTÜ</button><button class="mini" id="ar-opts-b">⚙ AYARLAR</button><button class="mini" id="ar-close">✕ KAPAT</button></div>
      <div id="ar-opts" class="hidden"></div><div id="ar-msg"></div>`;
    document.body.append(stage);
    cv = stage.querySelector("#ar-canvas"); ctx = cv.getContext("2d"); vid = stage.querySelector("#ar-video");
    stage.querySelector("#ar-close").onclick = () => api.stop();
    stage.querySelector("#ar-world-b").onclick = () => { if (JV.setView) JV.setView("globe"); if (JV.gesture) JV.gesture.start("nesne"); };
    stage.querySelector("#ar-camera-b").onclick = () => { if (JV.camera) JV.camera.open(); };
    stage.querySelector("#ar-desk-b").onclick = () => setProfile("desktop");
    stage.querySelector("#ar-opts-b").onclick = () => stage.querySelector("#ar-opts").classList.toggle("hidden");
    const picker = stage.querySelector("#ar-profile");
    for (const [key, info] of Object.entries(PROFILES)) {
      const option = document.createElement("option"); option.value = key; option.textContent = info[0]; picker.append(option);
    }
    picker.value = profile;
    picker.onchange = () => setProfile(picker.value);
    stage.querySelector("#ar-hint").textContent = PROFILES[profile][1];
    const box = stage.querySelector("#ar-opts");
    const note = document.createElement("p"); note.textContent = "Efektler ayrı modlardır. Aynı anda yalnızca biri çalışır. Dünya döndürme için DÜNYA + EL/NESNE kullan."; box.append(note);
    const soundLabel = document.createElement("label"), soundCheckbox = document.createElement("input");
    soundCheckbox.type = "checkbox"; soundCheckbox.checked = !!opts.sound;
    soundCheckbox.onchange = () => { opts.sound = soundCheckbox.checked; saveOpts(); };
    soundLabel.append(soundCheckbox, " Sesli efektler"); box.append(soundLabel);
    const pl = document.createElement("div"); pl.className = "ar-planets";
    ["sıradaki", ...ORDER].forEach((p) => { const b = document.createElement("button"); b.className = "mini"; b.textContent = p === "sıradaki" ? "↻ sıradaki" : NAMES[p]; b.onclick = () => { forcePlanet = p === "sıradaki" ? "" : p; if (planets[0] && forcePlanet) morph(planets[0], forcePlanet); }; pl.append(b); });
    box.append(pl);
    const lb = document.createElement("div"); lb.className = "ar-planets";
    [["📚 Kitaplığı tara (K)", () => JV.library && JV.library.scan()], ["📖 Kitaplık paneli (B)", () => JV.library && JV.library.openPanel()]].forEach(([t, fn]) => { const b = document.createElement("button"); b.className = "mini"; b.textContent = t; b.onclick = fn; lb.append(b); });
    box.append(lb);
    addEventListener("resize", size);
    addEventListener("keydown", (e) => {
      if (!on || e.target.tagName === "INPUT") return;
      if (e.key === "Escape") api.stop();
      if (e.key === "e" || e.key === "E") stage.querySelector("#ar-opts").classList.toggle("hidden");
      if (e.key === "f" || e.key === "F") setProfile("face");
      if (e.key === "d" || e.key === "D") setProfile("draw");
      if (e.key === "m" || e.key === "M") { opts.sound = !opts.sound; saveOpts(); const c = stage.querySelector('#ar-opts input[type="checkbox"]'); if (c) c.checked = opts.sound; }
      if ((e.key === "k" || e.key === "K") && JV.library) JV.library.scan();
      if ((e.key === "b" || e.key === "B") && JV.library) JV.library.openPanel();
      if (e.key === "p" || e.key === "P") { const p = ORDER[(ORDER.indexOf((planets[0] || {}).type) + 1) % ORDER.length]; if (planets[0]) morph(planets[0], p); else forcePlanet = p; }
    });
  }
  function size() { if (!cv) return; W = cv.width = innerWidth; H = cv.height = innerHeight; }
  function msg(t, ms = 1600) { const m = stage.querySelector("#ar-msg"); m.textContent = t; m.classList.add("on"); clearTimeout(m._t); m._t = setTimeout(() => m.classList.remove("on"), ms); }

  // landmark (0..1, aynasız) → ekran (aynalı, 'cover' kırpmasıyla)
  function mapper() {
    const vw = (vid && vid.videoWidth) || 640, vh = (vid && vid.videoHeight) || 480;
    const s = Math.max(W / vw, H / vh), dw = vw * s, dh = vh * s, ox = (W - dw) / 2, oy = (H - dh) / 2;
    return (p) => ({ x: ox + (1 - p.x) * dw, y: oy + p.y * dh, z: p.z || 0 });
  }

  // ---------------- parçacıklar ----------------
  function emit(x, y, o) { if (parts.length > 2600) return; parts.push({ x, y, vx: o.vx || 0, vy: o.vy || 0, life: 0, max: o.max || 40, size: o.size || 4, c: o.c || [255, 160, 40], g: o.g == null ? -0.02 : o.g, drag: o.drag || 0.97 }); }
  function stepParts() {
    ctx.globalCompositeOperation = "lighter";
    for (let i = parts.length - 1; i >= 0; i--) {
      const p = parts[i]; p.life++; if (p.life > p.max) { parts.splice(i, 1); continue; }
      p.vx *= p.drag; p.vy = p.vy * p.drag + p.g; p.x += p.vx; p.y += p.vy;
      const k = 1 - p.life / p.max, r = p.size * (0.4 + k);
      ctx.fillStyle = `rgba(${p.c[0]},${p.c[1]},${p.c[2]},${(k * 0.9).toFixed(3)})`;
      ctx.beginPath(); ctx.arc(p.x, p.y, r, 0, TAU); ctx.fill();
    }
    ctx.globalCompositeOperation = "source-over";
  }
  const fireCol = (k) => (k < 0.3 ? [255, 240, 170] : k < 0.6 ? [255, 160, 40] : [230, 60, 20]);

  // ---------------- efektler ----------------
  function fire(P, sc) {
    [4, 8, 12, 16, 20].forEach((i, n) => {
      const p = P[i];
      for (let k = 0; k < 2; k++) emit(p.x + (Math.random() - 0.5) * sc * 0.08, p.y, { vx: (Math.random() - 0.5) * 1.2, vy: -1.5 - Math.random() * 2.5, max: 22 + Math.random() * 18, size: sc * (0.05 + Math.random() * 0.04), c: fireCol(Math.random()), g: -0.06 });
      if (n < 4 && Math.random() < 0.12) { const q = P[[8, 12, 16, 20][n]]; bolt(p, q, sc * 0.08, 2, [255, 200, 120], 0.6); }
    });
    const c = P[9]; if (Math.random() < 0.6) emit(c.x, c.y, { vx: (Math.random() - 0.5) * 2, vy: -1 - Math.random() * 2, max: 30, size: sc * 0.08, c: fireCol(Math.random() * 0.6), g: -0.05 });
  }

  function seal(P, sc, t, idx) {
    const c = P[9], w = Math.hypot(P[5].x - P[17].x, P[5].y - P[17].y), l = Math.hypot(P[0].x - P[9].x, P[0].y - P[9].y) || 1;
    const squash = Math.max(0.18, Math.min(1, (w / l) / 0.85)); // el yana dönünce halka perspektifle daralır
    const roll = Math.atan2(P[9].y - P[0].y, P[9].x - P[0].x) + Math.PI / 2;
    const R = sc * 1.35;
    ctx.save(); ctx.translate(c.x, c.y); ctx.rotate(roll); ctx.scale(squash, 1);
    ctx.shadowColor = "rgba(255,150,40,0.9)"; ctx.shadowBlur = 18; ctx.strokeStyle = "rgba(255,170,60,0.95)"; ctx.fillStyle = "rgba(255,190,90,0.95)";
    const dir = idx ? -1 : 1;
    [[1, 2.2], [0.82, 1.2], [0.62, 1.6]].forEach(([k, lw], j) => { ctx.lineWidth = lw; ctx.beginPath(); ctx.arc(0, 0, R * k, 0, TAU); ctx.stroke(); });
    ctx.save(); ctx.rotate(t * 0.0009 * dir); // dış kertikler
    for (let i = 0; i < 72; i++) { const a = (i / 72) * TAU, r1 = R * (i % 6 ? 0.96 : 0.92); ctx.beginPath(); ctx.moveTo(Math.cos(a) * r1, Math.sin(a) * r1); ctx.lineTo(Math.cos(a) * R, Math.sin(a) * R); ctx.stroke(); }
    ctx.restore();
    ctx.save(); ctx.rotate(-t * 0.0013 * dir); ctx.font = `${Math.max(10, R * 0.12)}px serif`; ctx.textAlign = "center"; ctx.textBaseline = "middle";
    const RUNES = "ᚠᚢᚦᚨᚱᚲᚷᚹᚺᚾᛁᛃᛇᛈᛉᛊᛏᛒᛖᛗᛚᛜᛞᛟ";
    for (let i = 0; i < 16; i++) { const a = (i / 16) * TAU; ctx.save(); ctx.rotate(a); ctx.fillText(RUNES[(i * 3 + idx * 5) % RUNES.length], 0, -R * 0.72); ctx.restore(); }
    ctx.restore();
    ctx.save(); ctx.rotate(t * 0.0021 * dir); ctx.lineWidth = 1.4; // iç yıldız ve kare
    for (const n of [4, 8]) { ctx.beginPath(); for (let i = 0; i <= n; i++) { const a = (i / n) * TAU * (n === 8 ? 3 : 1), r = R * 0.58; i ? ctx.lineTo(Math.cos(a) * r, Math.sin(a) * r) : ctx.moveTo(Math.cos(a) * r, Math.sin(a) * r); } ctx.stroke(); ctx.rotate(Math.PI / 4); }
    ctx.restore();
    ctx.restore(); ctx.shadowBlur = 0;
  }

  function newPlanet(x, y, r) {
    const type = forcePlanet || ORDER[nextPlanet++ % ORDER.length];
    const p = { x, y, r, vx: 0, vy: 0, type, held: true, form: 0, rot: Math.random() * TAU, tilt: 0.35, morphTo: "", born: performance.now() };
    planets.push(p); if (planets.length > 4) planets.shift(); snd("pop"); msg(NAMES[type]); return p;
  }
  function morph(p, type) { if (p.type === type) return; p.morphTo = type; p.form = Math.min(p.form, 1); msg(NAMES[type]); }
  function drawPlanet(p, t) {
    if (p.morphTo) { p.form -= 0.06; if (p.form <= 0) { p.type = p.morphTo; p.morphTo = ""; p.form = 0; } }
    else p.form = Math.min(1, p.form + 0.05);
    p.rot += 0.012;
    const pal = PAL[p.type], spread = (1 - p.form) * p.r * 1.6, ct = Math.cos(p.tilt), st = Math.sin(p.tilt);
    ctx.globalCompositeOperation = "lighter";
    if (p.type === "sun") { const g = ctx.createRadialGradient(p.x, p.y, p.r * 0.3, p.x, p.y, p.r * 2); g.addColorStop(0, "rgba(255,200,80,0.45)"); g.addColorStop(1, "rgba(255,120,20,0)"); ctx.fillStyle = g; ctx.beginPath(); ctx.arc(p.x, p.y, p.r * 2, 0, TAU); ctx.fill(); }
    const ring = [];
    if (p.type === "saturn") for (let i = 0; i < 260; i++) { const a = (i / 260) * TAU + p.rot * 0.6, rr = p.r * (1.45 + (i % 5) * 0.09); ring.push([Math.cos(a) * rr, 0, Math.sin(a) * rr, i]); }
    const pts = SPHERE.map(([x, y, z, rnd]) => { const cx = Math.cos(p.rot), sx = Math.sin(p.rot); const X = x * cx - z * sx, Z = x * sx + z * cx; return [X, y, Z, rnd, y]; });
    const all = pts.concat(ring.map((q) => [q[0] / p.r, q[1], q[2] / p.r, -1, 0]));
    for (const [x, y0, z0, rnd, lat] of all) {
      const y = y0 * ct - z0 * st, z = y0 * st + z0 * ct;
      const isRing = rnd < 0; if (!isRing && z < -0.15) continue;
      if (isRing && z < 0 && Math.hypot(x, y) < 1) continue; // halkanın arka yarısı gezegenin arkasında kalır
      const jitter = spread ? ((rnd > 0 ? rnd : 0.5) - 0.5) * spread : 0;
      const sx = p.x + x * p.r + jitter, sy = p.y + y * p.r + jitter * 0.7;
      let c;
      if (isRing) c = pal[2];
      else if (p.type === "jupiter" || p.type === "saturn") c = pal[Math.floor((lat + 1) * 6) % 2];
      else if (p.type === "earth") c = rnd < 0.33 ? pal[1] : rnd > 0.93 ? pal[2] : pal[0];
      else c = rnd < 0.25 ? pal[1] : rnd > 0.9 ? pal[2] : pal[0];
      const b = isRing ? (z > 0 ? 0.95 : 0.45) : 0.5 + 0.5 * Math.max(0, z);
      ctx.fillStyle = `rgba(${c[0]},${c[1]},${c[2]},${b.toFixed(2)})`;
      const s = Math.max(1.2, p.r * 0.035);
      ctx.fillRect(sx - s / 2, sy - s / 2, s, s);
    }
    ctx.globalCompositeOperation = "source-over";
    if (p.held) { ctx.fillStyle = "rgba(255,210,140,0.9)"; ctx.font = "11px Share Tech Mono, monospace"; ctx.textAlign = "center"; ctx.fillText(NAMES[p.type], p.x, p.y + p.r * (p.type === "saturn" ? 1.9 : 1.35) + 14); }
  }
  function stepPlanets(t) {
    for (const p of planets) {
      if (!p.held) {
        p.vx *= 0.985; p.vy *= 0.985; p.x += p.vx; p.y += p.vy + Math.sin(t / 600 + p.born) * 0.15;
        if (p.x < p.r || p.x > W - p.r) { p.vx *= -0.7; p.x = Math.max(p.r, Math.min(W - p.r, p.x)); }
        if (p.y < p.r || p.y > H - p.r) { p.vy *= -0.7; p.y = Math.max(p.r, Math.min(H - p.r, p.y)); }
      }
      drawPlanet(p, t);
    }
  }
  function explode(x, y, sc) {
    let near = null, dmin = 1e9;
    planets.forEach((p) => { const d = Math.hypot(p.x - x, p.y - y); if (d < dmin) { dmin = d; near = p; } });
    if (near && dmin < sc * 4) {
      const pal = PAL[near.type];
      for (let i = 0; i < 420; i++) { const a = Math.random() * TAU, v = 2 + Math.random() * 9; emit(near.x, near.y, { vx: Math.cos(a) * v, vy: Math.sin(a) * v, max: 40 + Math.random() * 40, size: 2 + Math.random() * 3, c: pal[i % 3], g: 0.03, drag: 0.965 }); }
      planets.splice(planets.indexOf(near), 1); msg(NAMES[near.type] + " PATLADI");
    } else {
      waves.push({ x, y, r: sc * 0.4, life: 0 });
      for (let i = 0; i < 160; i++) { const a = Math.random() * TAU, v = 3 + Math.random() * 7; emit(x, y, { vx: Math.cos(a) * v, vy: Math.sin(a) * v, max: 30 + Math.random() * 20, size: 2.5, c: [120, 220, 255], g: 0, drag: 0.95 }); }
    }
    shakeUntil = performance.now() + 380; snd("boom");
  }
  function stepWaves() {
    for (let i = waves.length - 1; i >= 0; i--) {
      const w = waves[i]; w.life++; w.r += 14; const a = 1 - w.life / 32; if (a <= 0) { waves.splice(i, 1); continue; }
      ctx.strokeStyle = `rgba(140,230,255,${a})`; ctx.lineWidth = 6 * a + 1; ctx.shadowColor = "#6cf"; ctx.shadowBlur = 20;
      ctx.beginPath(); ctx.arc(w.x, w.y, w.r, 0, TAU); ctx.stroke(); ctx.shadowBlur = 0;
    }
  }
  function bolt(a, b, amp, depth, col = [170, 220, 255], alpha = 1) { bolts.push({ pts: zig(a, b, amp, depth), col, alpha, life: 0 }); }
  function zig(a, b, amp, depth) {
    let pts = [a, b];
    for (let d = 0; d < depth + 3; d++) {
      const n = [pts[0]];
      for (let i = 1; i < pts.length; i++) { const p = pts[i - 1], q = pts[i], mx = (p.x + q.x) / 2, my = (p.y + q.y) / 2, dx = q.y - p.y, dy = p.x - q.x, L = Math.hypot(dx, dy) || 1, o = (Math.random() - 0.5) * amp; n.push({ x: mx + (dx / L) * o, y: my + (dy / L) * o }, q); }
      pts = n; amp *= 0.55;
    }
    return pts;
  }
  function stepBolts() {
    ctx.globalCompositeOperation = "lighter";
    for (let i = bolts.length - 1; i >= 0; i--) {
      const b = bolts[i]; b.life++; if (b.life > 3) { bolts.splice(i, 1); continue; }
      const a = b.alpha * (1 - b.life / 4);
      [[8, 0.18], [3, 0.6], [1.2, 1]].forEach(([lw, k]) => { ctx.strokeStyle = `rgba(${b.col[0]},${b.col[1]},${b.col[2]},${a * k})`; ctx.lineWidth = lw; ctx.beginPath(); b.pts.forEach((p, j) => (j ? ctx.lineTo(p.x, p.y) : ctx.moveTo(p.x, p.y))); ctx.stroke(); });
    }
    ctx.globalCompositeOperation = "source-over";
  }
  function drawTrail(now) {
    trail = trail.filter((p, i) => now - p.t < 600 || i >= trail.length - 6).slice(-40);
    if (trail.length < 2) return;
    ctx.globalCompositeOperation = "lighter"; ctx.lineCap = "round";
    for (let i = 1; i < trail.length; i++) { const k = 1 - (now - trail[i].t) / 600; ctx.strokeStyle = `rgba(90,220,255,${k * 0.9})`; ctx.lineWidth = 2 + k * 9; ctx.shadowColor = "#5df"; ctx.shadowBlur = 16; ctx.beginPath(); ctx.moveTo(trail[i - 1].x, trail[i - 1].y); ctx.lineTo(trail[i].x, trail[i].y); ctx.stroke(); }
    ctx.shadowBlur = 0; ctx.globalCompositeOperation = "source-over";
  }
  function holdRing(x, y, k, label) {
    ctx.strokeStyle = "rgba(255,255,255,0.25)"; ctx.lineWidth = 5; ctx.beginPath(); ctx.arc(x, y, 34, 0, TAU); ctx.stroke();
    ctx.strokeStyle = "rgba(80,230,255,0.95)"; ctx.shadowColor = "#4df"; ctx.shadowBlur = 12; ctx.beginPath(); ctx.arc(x, y, 34, -Math.PI / 2, -Math.PI / 2 + TAU * k); ctx.stroke(); ctx.shadowBlur = 0;
    ctx.fillStyle = "#bff"; ctx.font = "12px Share Tech Mono, monospace"; ctx.textAlign = "center"; ctx.fillText(label, x, y + 52);
  }
  const HOLDS = { thumbs_up: [1000, "KOMUT"], peace: [900, "MİKROFON"], fist: [1800, "SUS"] };
  function control(pose, h) {
    if (pose === "thumbs_up") { const cmd = (JV.settings && JV.settings.ar_thumb_command) || "Bana bugün için kısa bir brifing ver"; msg("👍 " + cmd, 2500); JV.sendCommand ? JV.sendCommand(cmd) : null; }
    else if (pose === "peace") { msg("🎙 Dinliyorum"); const m = document.getElementById("mic"); if (m) m.click(); }
    else if (pose === "fist") { msg("🤫 Sustu"); JV.stopSpeaking && JV.stopSpeaking(); }
    snd("lock");
  }
  function skeleton(P) {
    const L = [[0, 1], [1, 2], [2, 3], [3, 4], [0, 5], [5, 6], [6, 7], [7, 8], [5, 9], [9, 10], [10, 11], [11, 12], [9, 13], [13, 14], [14, 15], [15, 16], [13, 17], [17, 18], [18, 19], [19, 20], [0, 17]];
    ctx.strokeStyle = "rgba(0,229,255,0.7)"; ctx.lineWidth = 1.5; L.forEach(([a, b]) => { ctx.beginPath(); ctx.moveTo(P[a].x, P[a].y); ctx.lineTo(P[b].x, P[b].y); ctx.stroke(); });
  }

  // ---------------- yüz kilidi HUD ----------------
  function faceHud(now) {
    if (!opts.face || !face.box) return;
    const b = face.box, k = face.locked ? 1 : Math.min(1, (now - face.since) / 1200);
    const pad = (1.35 - 0.35 * k), cx = b.x + b.w / 2, cy = b.y + b.h / 2, w = b.w * pad, h = b.h * pad, x = cx - w / 2, y = cy - h / 2, L = Math.min(w, h) * 0.22;
    const col = face.locked ? "rgba(80,230,255,0.95)" : "rgba(255,180,60,0.95)";
    ctx.strokeStyle = col; ctx.lineWidth = 2.5; ctx.shadowColor = col; ctx.shadowBlur = 10;
    [[x, y, 1, 1], [x + w, y, -1, 1], [x, y + h, 1, -1], [x + w, y + h, -1, -1]].forEach(([px, py, sx, sy]) => { ctx.beginPath(); ctx.moveTo(px, py + sy * L); ctx.lineTo(px, py); ctx.lineTo(px + sx * L, py); ctx.stroke(); });
    ctx.lineWidth = 1; ctx.beginPath(); ctx.moveTo(cx - 8, cy); ctx.lineTo(cx + 8, cy); ctx.moveTo(cx, cy - 8); ctx.lineTo(cx, cy + 8); ctx.stroke(); ctx.shadowBlur = 0;
    ctx.fillStyle = col; ctx.font = "13px Share Tech Mono, monospace"; ctx.textAlign = "left";
    const name = ((JV.settings && (JV.settings.user_name || JV.settings.owner_name)) || "SAHİP").toUpperCase();
    if (face.locked) { ctx.fillText(`${name} · YÜZ KİLİTLENDİ · YETKİ: TAM`, x, y - 10); }
    else { ctx.fillText(`KİLİTLENİYOR… %${Math.round(k * 100)}`, x, y - 10); if (Math.random() < 0.06) snd("tick"); }
    ctx.fillStyle = "rgba(255,255,255,0.55)"; ctx.font = "11px Share Tech Mono, monospace";
    face.others.forEach((o) => { ctx.strokeStyle = "rgba(255,255,255,0.35)"; ctx.strokeRect(o.x, o.y, o.w, o.h); ctx.fillText("KİŞİ · TANIMLANMADI", o.x, o.y - 6); });
    if (!face.locked && k >= 1) {
      face.locked = true; snd("lock");
      if (now - face.lastGreet > 60000 && !JV.speaking && JV.say) { face.lastGreet = now; const h = new Date().getHours(); JV.say(`${h < 12 ? "Günaydın" : h < 18 ? "İyi günler" : "İyi akşamlar"}. Yüz kilitlendi, tam yetki verildi.`, JV.currentPersona && JV.currentPersona()); }
    }
  }
  function onFaces(list, M) {
    if (!list || !list.length) { if (face.box && performance.now() - face.seen > 1200) { face.box = null; face.locked = false; } return; }
    const boxes = list.map((lm) => { let x0 = 1e9, y0 = 1e9, x1 = -1e9, y1 = -1e9; for (const p of lm) { const q = M(p); x0 = Math.min(x0, q.x); x1 = Math.max(x1, q.x); y0 = Math.min(y0, q.y); y1 = Math.max(y1, q.y); } return { x: x0, y: y0, w: x1 - x0, h: y1 - y0 }; });
    boxes.sort((a, b) => b.w * b.h - a.w * a.h);
    const b = boxes[0];
    if (!face.box || Math.hypot(face.box.x - b.x, face.box.y - b.y) > b.w * 0.6) { face.since = performance.now(); face.locked = false; }
    face.box = face.box ? { x: face.box.x * 0.6 + b.x * 0.4, y: face.box.y * 0.6 + b.y * 0.4, w: face.box.w * 0.6 + b.w * 0.4, h: face.box.h * 0.6 + b.h * 0.4 } : b;
    face.others = boxes.slice(1); face.seen = performance.now();
  }

  // ---------------- AR OYUNLARI ----------------
  let game = null;

  function setProfile(name, silent = false) {
    if (!Object.prototype.hasOwnProperty.call(PROFILES, name)) name = "fire";
    profile = name;
    // Migrate old installations which saved ALL effects as enabled.
    // Preserve only unrelated preferences such as sound.
    for (const key of EXCLUSIVE) opts[key] = key === name;
    if (name === "mask") opts.helmet = true;
    if (name !== "desktop" && JV.ardesk && JV.ardesk.on) JV.ardesk.toggle(false);
    if (name === "desktop" && JV.ardesk && !JV.ardesk.on) JV.ardesk.toggle(true);
    if (name !== "game") game = null;
    parts = []; planets = []; bolts = []; waves = []; trail = []; shakeUntil = 0;
    strokes = []; curStroke = null;
    Object.keys(hs).forEach((k) => delete hs[k]);
    face.box = null; face.locked = false;
    if (stage) {
      const picker = stage.querySelector("#ar-profile"), hint = stage.querySelector("#ar-hint");
      if (picker) picker.value = profile;
      if (hint) hint.textContent = PROFILES[profile][1];
    }
    saveOpts();
    try { localStorage.setItem(PROFILE_KEY, profile); } catch (e) {}
    if (!silent && on) msg(PROFILES[profile][0] + " modu", 1800);
  }

  const RPS = { fist: "taş", open: "kağıt", peace: "makas" }, RPS_ICON = { taş: "✊", kağıt: "✋", makas: "✌" };
  const beats = (a, b) => (a === "taş" && b === "makas") || (a === "kağıt" && b === "taş") || (a === "makas" && b === "kağıt");
  const sayG = (t) => JV.say && JV.say(t, JV.currentPersona && JV.currentPersona());
  function startGame(kind) {
    parts = []; planets = []; trail = [];
    if (kind === "balloons") { game = { kind, t0: performance.now(), dur: 30000, balloons: [], score: 0, last: 0 }; msg("🎈 30 saniye! İşaret parmağınla patlat", 2500); sayG("Balon patlatma başlıyor. Otuz saniye!"); }
    else { game = { kind: "rps", phase: "count", t0: performance.now() + 1200, round: 1, you: 0, me: 0, pick: null, mine: null }; sayG("Taş kağıt makas! Beş tur. Sayınca elini göster."); }
  }
  async function endGame(score, text) {
    const g = game; game = null;
    let r = {}; try { r = await (await fetch("/api/life/game_score", { method: "POST", headers: { "x-token": JV.token || "", "Content-Type": "application/json" }, body: JSON.stringify({ game: g.kind, score }) })).json(); } catch (e) {}
    const t = text + (r.yeni_rekor ? " Yeni rekor!" : r.rekor != null ? ` Rekorun ${r.rekor}.` : "");
    msg(t, 5000); sayG(t);
  }
  function bigText(t, y, size, col) { ctx.font = `${size}px Orbitron, Share Tech Mono, monospace`; ctx.textAlign = "center"; ctx.fillStyle = col; ctx.shadowColor = col; ctx.shadowBlur = 18; ctx.fillText(t, W / 2, y); ctx.shadowBlur = 0; ctx.textAlign = "left"; }
  function gameStep(H2, now) {
    const g = game;
    if (g.kind === "balloons") {
      const left = Math.max(0, g.dur - (now - g.t0));
      if (now - g.last > 650 && left > 0) { g.last = now; const r = 28 + Math.random() * 22; g.balloons.push({ x: r + Math.random() * (W - 2 * r), y: H + r, r, vy: -(1.4 + Math.random() * 1.8), ph: Math.random() * 6, c: [[255, 80, 90], [80, 200, 255], [255, 210, 70], [120, 255, 140], [220, 120, 255]][Math.floor(Math.random() * 5)] }); }
      const tips = H2.filter((h) => h.pointing || h.pose === "open").map((h) => h.P[8]);
      for (let i = g.balloons.length - 1; i >= 0; i--) {
        const b = g.balloons[i]; b.y += b.vy; b.x += Math.sin(now / 400 + b.ph) * 0.8;
        if (tips.some((t) => Math.hypot(t.x - b.x, t.y - b.y) < b.r)) { g.score++; g.balloons.splice(i, 1); snd("pop"); for (let k = 0; k < 40; k++) { const a = Math.random() * TAU, v = 2 + Math.random() * 5; emit(b.x, b.y, { vx: Math.cos(a) * v, vy: Math.sin(a) * v, max: 30, size: 3, c: b.c, g: 0.08 }); } continue; }
        if (b.y < -b.r * 2) { g.balloons.splice(i, 1); continue; }
        ctx.fillStyle = `rgba(${b.c[0]},${b.c[1]},${b.c[2]},0.85)`; ctx.beginPath(); ctx.ellipse(b.x, b.y, b.r * 0.85, b.r, 0, 0, TAU); ctx.fill();
        ctx.fillStyle = "rgba(255,255,255,0.5)"; ctx.beginPath(); ctx.ellipse(b.x - b.r * 0.3, b.y - b.r * 0.35, b.r * 0.18, b.r * 0.28, -0.5, 0, TAU); ctx.fill();
        ctx.strokeStyle = "rgba(255,255,255,0.5)"; ctx.beginPath(); ctx.moveTo(b.x, b.y + b.r); ctx.quadraticCurveTo(b.x + 8, b.y + b.r * 1.6, b.x, b.y + b.r * 2.2); ctx.stroke();
      }
      tips.forEach((t) => { ctx.strokeStyle = "#fff"; ctx.beginPath(); ctx.arc(t.x, t.y, 10, 0, TAU); ctx.stroke(); });
      bigText(`🎈 ${g.score}   ⏱ ${Math.ceil(left / 1000)}`, 70, 30, "#bff");
      if (left <= 0 && !g.ending) { g.ending = true; endGame(g.score, `Süre doldu! ${g.score} balon patlattınız.`); }
      return;
    }
    // taş-kağıt-makas
    const t = now - g.t0, beat = 650;
    if (g.phase === "count") {
      if (t < 0) { bigText(`TUR ${g.round} / 5`, H / 2, 42, "#bff"); }
      else if (t < beat * 3) { const w = ["TAŞ", "KAĞIT", "MAKAS"][Math.floor(t / beat)]; bigText(w + "…", H / 2, 64, "#ffcf8a"); if (Math.floor(t / beat) !== g.lastBeat) { g.lastBeat = Math.floor(t / beat); snd("tick"); } }
      else if (t < beat * 3 + 700) { bigText("ÇEK!", H / 2, 80, "#5aff9c"); const h = H2[0]; if (h && RPS[h.pose] && !g.pick) g.pick = RPS[h.pose]; }
      else {
        g.mine = ["taş", "kağıt", "makas"][Math.floor(Math.random() * 3)];
        if (!g.pick) { const h = H2[0]; g.pick = h && RPS[h.pose] ? RPS[h.pose] : null; }
        g.res = !g.pick ? "?" : g.pick === g.mine ? "BERABERE" : beats(g.pick, g.mine) ? "KAZANDIN" : "KAYBETTİN";
        if (g.res === "KAZANDIN") g.you++; else if (g.res === "KAYBETTİN") g.me++;
        g.phase = "result"; g.rt = now; snd(g.res === "KAZANDIN" ? "lock" : "pop");
        sayG(!g.pick ? "Elini göremedim, bu turu tekrar edelim." : `${g.pick} ile ${g.mine}. ${g.res === "BERABERE" ? "Berabere" : g.res === "KAZANDIN" ? "Bu tur sizin" : "Bu tur benim"}.`);
        if (!g.pick) g.round--;
      }
    } else if (g.phase === "result") {
      ctx.font = "120px serif"; ctx.textAlign = "center";
      ctx.fillText(g.pick ? RPS_ICON[g.pick] : "❔", W * 0.3, H / 2); ctx.fillText(RPS_ICON[g.mine], W * 0.7, H / 2); ctx.textAlign = "left";
      bigText("SEN", H / 2 + 70, 20, "#bff"); ctx.save(); ctx.translate(W * 0.4, 0); ctx.restore();
      ctx.font = "18px Share Tech Mono, monospace"; ctx.fillStyle = "#bff"; ctx.textAlign = "center"; ctx.fillText("SEN", W * 0.3, H / 2 + 70); ctx.fillText("JARVIS", W * 0.7, H / 2 + 70); ctx.textAlign = "left";
      bigText(g.res, H / 2 - 120, 46, g.res === "KAZANDIN" ? "#5aff9c" : g.res === "KAYBETTİN" ? "#ff6b6b" : "#ffcf8a");
      if (now - g.rt > 2600) {
        if (g.round >= 5 || g.you >= 3 || g.me >= 3) { endGame(g.you, g.you > g.me ? `Oyunu ${g.you}-${g.me} kazandınız, tebrikler!` : g.you < g.me ? `Oyunu ${g.me}-${g.you} ben kazandım. Rövanş?` : `Oyun ${g.you}-${g.me} berabere bitti.`); return; }
        Object.assign(g, { phase: "count", t0: now + 900, round: g.round + 1, pick: null, mine: null, lastBeat: -1 });
      }
    }
    bigText(`SEN ${g.you}  —  ${g.me} JARVIS`, 70, 24, "#bff");
  }

  // ---------------- AVUÇTA HUD ----------------
  let palmData = { t: 0, d: {} };
  function palmInfo() {
    if (performance.now() - palmData.t > 60000) { palmData.t = performance.now(); fetch("/api/scene/palm", { headers: { "x-token": JV.token || "" } }).then((r) => r.json()).then((d) => (palmData.d = d)).catch(() => {}); }
    return palmData.d;
  }
  function palmHud(P, sc, k) {
    const d = palmInfo(), c = P[9], now = new Date(), lines = [now.toLocaleTimeString("tr-TR", { hour: "2-digit", minute: "2-digit" }), now.toLocaleDateString("tr-TR", { weekday: "long", day: "numeric", month: "long" }), d.hava, d.etkinlik && "📅 " + d.etkinlik, d.sistem].filter(Boolean);
    const w = sc * 2.4, h = sc * (0.75 + lines.length * 0.27), x = c.x - w / 2, y = P[12].y - h - sc * 0.4;
    ctx.save(); ctx.globalAlpha = Math.min(1, k);
    ctx.fillStyle = "rgba(0,30,45,0.45)"; ctx.strokeStyle = "rgba(90,230,255,0.9)"; ctx.shadowColor = "#4df"; ctx.shadowBlur = 16; ctx.lineWidth = 1.5;
    ctx.beginPath(); ctx.moveTo(x + 12, y); ctx.lineTo(x + w, y); ctx.lineTo(x + w, y + h - 12); ctx.lineTo(x + w - 12, y + h); ctx.lineTo(x, y + h); ctx.lineTo(x, y + 12); ctx.closePath(); ctx.fill(); ctx.stroke(); ctx.shadowBlur = 0;
    ctx.beginPath(); ctx.moveTo(c.x, y + h); ctx.lineTo(c.x, P[12].y - sc * 0.1); ctx.setLineDash([3, 4]); ctx.stroke(); ctx.setLineDash([]);
    ctx.fillStyle = "#bff"; ctx.textAlign = "left";
    lines.forEach((t, i) => { ctx.font = i === 0 ? `${Math.max(16, sc * 0.42)}px Orbitron, Share Tech Mono, monospace` : `${Math.max(10, sc * 0.17)}px Share Tech Mono, monospace`; ctx.fillText(String(t).slice(0, 34), x + 12, y + (i === 0 ? sc * 0.5 : sc * 0.55 + i * sc * 0.25)); });
    ctx.restore();
  }

  // ---------------- HAVAYA ÇİZİM ----------------
  let strokes = [], curStroke = null;
  function drawStrokes() {
    ctx.save(); ctx.globalCompositeOperation = "lighter"; ctx.lineCap = ctx.lineJoin = "round";
    for (const s of strokes) { if (s.length < 2) continue; [[12, "rgba(255,120,220,0.18)"], [5, "rgba(255,170,240,0.6)"], [2, "rgba(255,235,255,0.95)"]].forEach(([lw, c]) => { ctx.strokeStyle = c; ctx.lineWidth = lw; ctx.beginPath(); s.forEach((p, i) => (i ? ctx.lineTo(p.x, p.y) : ctx.moveTo(p.x, p.y))); ctx.stroke(); }); }
    ctx.restore();
  }
  async function askDrawing() {
    const pts = strokes.flat(); if (pts.length < 5) { msg("Önce işaret parmağınla bir şey çiz"); return; }
    const xs = pts.map((p) => p.x), ys = pts.map((p) => p.y), x0 = Math.min(...xs) - 20, y0 = Math.min(...ys) - 20, w = Math.max(...xs) - x0 + 20, h = Math.max(...ys) - y0 + 20;
    const c = document.createElement("canvas"), k = 512 / Math.max(w, h); c.width = w * k; c.height = h * k; const g = c.getContext("2d");
    g.fillStyle = "#000"; g.fillRect(0, 0, c.width, c.height); g.strokeStyle = "#fff"; g.lineWidth = 8; g.lineCap = g.lineJoin = "round";
    strokes.forEach((s) => { g.beginPath(); s.forEach((p, i) => (i ? g.lineTo((p.x - x0) * k, (p.y - y0) * k) : g.moveTo((p.x - x0) * k, (p.y - y0) * k))); g.stroke(); });
    msg("🤔 Bakıyorum…", 4000);
    try { const b = await new Promise((r) => c.toBlob(r, "image/png")); const r = await (await fetch("/api/scene/drawing", { method: "POST", headers: { "x-token": JV.token || "", "Content-Type": "image/png" }, body: b })).json(); const t = r.cevap || r.error || "Anlayamadım."; msg(t, 6000); JV.say && JV.say(t, JV.currentPersona && JV.currentPersona()); }
    catch (e) { msg("Hata: " + e.message); }
  }
  function clearDrawing() { strokes = []; curStroke = null; msg("Çizim silindi"); }

  // ---------------- IRON MAN KASK HUD ----------------
  const OVAL = [10, 338, 297, 332, 284, 251, 389, 356, 454, 323, 361, 288, 397, 365, 379, 378, 400, 377, 152, 148, 176, 149, 150, 136, 172, 58, 132, 93, 234, 127, 162, 21, 54, 103, 67, 109];
  function helmet(F, ew) { // yüze oturan özgün kask çizimi: kırmızı kabuk, altın yüz plakası, parlayan göz yarıkları
    const c = F[1], ov = OVAL.map((i) => F[i]).filter(Boolean); if (ov.length < 30) return;
    const grow = (p, k) => ({ x: c.x + (p.x - c.x) * k, y: c.y + (p.y - c.y) * k });
    ctx.save(); ctx.shadowBlur = 0;
    const shell = ov.map((p) => grow(p, 1.12)); // kabuk (yüzden biraz büyük)
    const g = ctx.createLinearGradient(c.x - ew * 1.5, c.y - ew * 2, c.x + ew * 1.5, c.y + ew * 2); g.addColorStop(0, "rgba(190,20,25,0.92)"); g.addColorStop(0.5, "rgba(140,10,15,0.92)"); g.addColorStop(1, "rgba(90,5,10,0.92)");
    ctx.fillStyle = g; ctx.beginPath(); shell.forEach((p, i) => (i ? ctx.lineTo(p.x, p.y) : ctx.moveTo(p.x, p.y))); ctx.closePath(); ctx.fill();
    const browY = Math.min(F[105].y, F[334].y) - ew * 0.15; // yüz plakası: kaşların biraz üstünden çeneye
    const plate = ov.map((p) => grow(p, 0.86)).map((p) => ({ x: p.x, y: Math.max(p.y, browY) }));
    const gp = ctx.createLinearGradient(0, browY, 0, F[152].y); gp.addColorStop(0, "rgba(255,205,90,0.95)"); gp.addColorStop(1, "rgba(200,140,40,0.95)");
    ctx.fillStyle = gp; ctx.beginPath(); plate.forEach((p, i) => (i ? ctx.lineTo(p.x, p.y) : ctx.moveTo(p.x, p.y))); ctx.closePath(); ctx.fill();
    ctx.strokeStyle = "rgba(90,40,0,0.6)"; ctx.lineWidth = 1.5; ctx.stroke();
    ctx.fillStyle = "rgba(220,250,255,0.95)"; ctx.shadowColor = "#9ef"; ctx.shadowBlur = 18; // göz yarıkları
    [[33, 133, 159, 145], [362, 263, 386, 374]].forEach(([a, b, t, bt]) => { const A = F[a], B = F[b], T = F[t], Bt = F[bt]; if (!A || !B) return; const h = Math.max(3, Math.abs((Bt || A).y - (T || A).y) * 0.6);
      ctx.beginPath(); ctx.moveTo(A.x, A.y); ctx.lineTo((A.x + B.x) / 2, (A.y + B.y) / 2 - h); ctx.lineTo(B.x, B.y); ctx.lineTo((A.x + B.x) / 2, (A.y + B.y) / 2 + h * 0.5); ctx.closePath(); ctx.fill(); });
    ctx.shadowBlur = 0; ctx.strokeStyle = "rgba(80,30,0,0.75)"; ctx.lineWidth = 2; // ağız çizgisi ve yanak hatları
    if (F[61] && F[291]) { ctx.beginPath(); ctx.moveTo(F[61].x, F[61].y + 2); ctx.lineTo(F[291].x, F[291].y + 2); ctx.stroke(); }
    [[F[234], F[61]], [F[454], F[291]]].forEach(([a, b]) => { if (a && b) { ctx.beginPath(); ctx.moveTo(grow(a, 0.88).x, grow(a, 0.88).y); ctx.lineTo(b.x, b.y); ctx.stroke(); } });
    ctx.restore();
  }
  let lastFaces = null;
  function maskHud(now, M) {
    if (!lastFaces || !lastFaces[0]) return;
    const F = lastFaces[0].map(M), L = F[33], R = F[263], nose = F[1], chin = F[152], top = F[10], ew = Math.hypot(R.x - L.x, R.y - L.y);
    const roll = Math.atan2(R.y - L.y, R.x - L.x);
    if (opts.helmet !== false && F.length > 400) helmet(F, ew);
    ctx.save(); ctx.strokeStyle = "rgba(255,90,60,0.9)"; ctx.fillStyle = "rgba(255,200,120,0.95)"; ctx.shadowColor = "#f53"; ctx.shadowBlur = 12; ctx.lineWidth = 1.5;
    [F[468] || L, F[473] || R].forEach((e, i) => { // göz nişangâhları (dönen halkalar)
      ctx.save(); ctx.translate(e.x, e.y); ctx.rotate(now / 700 * (i ? -1 : 1));
      ctx.beginPath(); ctx.arc(0, 0, ew * 0.28, 0, 4.4); ctx.stroke(); ctx.beginPath(); ctx.arc(0, 0, ew * 0.18, 1, 5.6); ctx.stroke();
      for (let k = 0; k < 4; k++) { ctx.rotate(Math.PI / 2); ctx.beginPath(); ctx.moveTo(ew * 0.31, 0); ctx.lineTo(ew * 0.38, 0); ctx.stroke(); }
      ctx.restore();
    });
    ctx.save(); ctx.translate(top.x, top.y); ctx.rotate(roll); // alın yayı + yazılar
    ctx.beginPath(); ctx.arc(0, ew * 0.9, ew * 1.25, Math.PI * 1.15, Math.PI * 1.85); ctx.stroke();
    ctx.font = `${Math.max(9, ew * 0.11)}px Share Tech Mono, monospace`; ctx.textAlign = "center";
    ctx.fillText(`MARK LXXXV · GÜÇ %${97 + Math.round(Math.sin(now / 2000) * 2)} · ${new Date().toLocaleTimeString("tr-TR")}`, 0, -ew * 0.12);
    ctx.restore();
    ctx.beginPath(); ctx.moveTo(L.x - ew * 0.5, L.y + ew * 0.55); ctx.lineTo(nose.x, chin.y - ew * 0.15); ctx.lineTo(R.x + ew * 0.5, R.y + ew * 0.55); ctx.stroke(); // çene hattı
    ctx.font = `${Math.max(9, ew * 0.1)}px Share Tech Mono, monospace`; ctx.textAlign = "left";
    ["SİSTEMLER ÇEVRİMİÇİ", "HEDEF: YOK", `İRTİFA ${(120 + Math.sin(now / 900) * 3).toFixed(1)} m`].forEach((t, i) => ctx.fillText(t, R.x + ew * 0.75, R.y - ew * 0.2 + i * ew * 0.16));
    ctx.restore();
  }

  // ---------------- kare işleme ----------------
  function frame(hands, faces) {
    if (!on) return;
    const now = performance.now(), M = mapper();
    fpsN++; if (now - fpsT > 1000) { fps = fpsN; fpsN = 0; fpsT = now; const f = stage.querySelector("#ar-fps"); if (f) f.textContent = `${fps} FPS · ${hands.length} el`; }
    ctx.clearRect(0, 0, W, H);
    if (now < shakeUntil) stage.style.transform = `translate(${(Math.random() - 0.5) * 18}px,${(Math.random() - 0.5) * 18}px)`; else stage.style.transform = "";
    if (faces) { onFaces(faces, M); lastFaces = faces; }
    const core = G();
    const seen = {};
    const H2 = hands.map((h) => {
      const P = h.lm.map(M), sc = Math.hypot(P[0].x - P[9].x, P[0].y - P[9].y) || 60;
      const pose = core.pose(h.lm), f = core.fingers(h.lm), pinch = core.pinchRatio(h.lm) < 0.33 && pose !== "fist"; // yumrukta başparmak işarete değer: çimdik sayılmasın
      const pointing = f[1] && !f[2] && !f[3] && !f[4];
      const st = hs[h.handed] || (hs[h.handed] = { pose: "", since: now, fired: false, fistAt: 0, pinch: false, planet: null, last: null, vel: [0, 0] });
      seen[h.handed] = true;
      const pp = { x: (P[4].x + P[8].x) / 2, y: (P[4].y + P[8].y) / 2 };
      if (st.last) { st.vel = [(pp.x - st.last.x) * 0.6 + st.vel[0] * 0.4, (pp.y - st.last.y) * 0.6 + st.vel[1] * 0.4]; }
      st.last = pp;
      if (pose !== st.pose) { if (st.pose === "fist" && pose === "open" && now - st.since < 900 && opts.blast && !game && !(JV.library && JV.library.open)) explode(P[9].x, P[9].y, sc); st.pose = pose; st.since = now; st.fired = false; }
      return { ...h, P, sc, pose, pinch, pointing, st, pp };
    });
    Object.keys(hs).forEach((k) => { if (!seen[k]) { const st = hs[k]; if (st.planet) { st.planet.held = false; st.planet.vx = st.vel[0]; st.planet.vy = st.vel[1]; st.planet = null; } delete hs[k]; } });

    // kitaplık (raf haritası varsa): seçim, çekme, açık kitap — açıkken diğer efektler susar
    const L = (JV.library && opts.library !== false) ? JV.library.arFrame(ctx, H2, M, now) : { busy: false };
    const D = (JV.ardesk && JV.ardesk.on) ? JV.ardesk.frame(ctx, H2, M, now) : { busy: false };
    const calm = L.busy || L.inShelf || !!game || D.busy;
    if (game) gameStep(H2, now);
    const holds = L.holds || null;
    // iki elle çimdik → gezegeni büyüt
    const both = !calm && H2.length === 2 && H2[0].pinch && H2[1].pinch && opts.planet;
    if (both) {
      const a = H2[0].pp, b = H2[1].pp, mx = (a.x + b.x) / 2, my = (a.y + b.y) / 2, r = Math.max(20, Math.hypot(a.x - b.x, a.y - b.y) / 2 * 0.8);
      let p = H2[0].st.planet || H2[1].st.planet;
      if (!p) p = newPlanet(mx, my, r);
      Object.assign(p, { x: mx, y: my, r, held: true }); H2[0].st.planet = H2[1].st.planet = p;
    }
    for (const h of H2) {
      const { P, sc, pose, st } = h;
      if (opts.skeleton) skeleton(P);
      // çimdik: gezegen
      if (opts.planet && !both && !calm) {
        if (h.pinch) {
          if (!st.planet) {
            const near = planets.find((p) => !p.held && Math.hypot(p.x - h.pp.x, p.y - h.pp.y) < p.r * 1.3);
            st.planet = near || newPlanet(h.pp.x, h.pp.y, Math.max(26, sc * 0.55));
            st.planet.held = true;
          }
          const p = st.planet; p.x += (h.pp.x - p.x) * 0.5; p.y += (h.pp.y - p.y) * 0.5;
          p.tilt = 0.35 + Math.atan2(P[8].y - P[4].y, P[8].x - P[4].x) * 0.25;
        } else if (st.planet) { // bırakınca süzülür; hızlı savrulduysa fırlar
          const p = st.planet; p.held = false; p.vx = st.vel[0]; p.vy = st.vel[1]; st.planet = null;
          if (Math.hypot(p.vx, p.vy) > 14) { p.vx *= 1.6; p.vy *= 1.6; snd("pop"); }
        }
        if (!h.pinch && H2.length === 2 && H2[0].st.planet === H2[1].st.planet && st.planet) st.planet = null;
      }
      const still = Math.hypot(st.vel[0], st.vel[1]) < 3.5, upright = h.lm[12].y < h.lm[0].y - 0.08;
      if (pose === "open" && still && upright) { st.stillSince = st.stillSince || now; } else st.stillSince = 0;
      const palmOn = opts.palm && !calm && !(JV.ardesk && JV.ardesk.on) && pose === "open" && st.stillSince && now - st.stillSince > 1000 && H2.length === 1;
      if (palmOn) palmHud(P, sc, (now - st.stillSince - 1000) / 300);
      if (opts.draw && !calm) {
        if (h.pointing) { if (!curStroke) { curStroke = []; strokes.push(curStroke); } const lp = curStroke[curStroke.length - 1]; if (!lp || Math.hypot(lp.x - P[8].x, lp.y - P[8].y) > 3) curStroke.push({ x: P[8].x, y: P[8].y }); }
        else curStroke = null;
      }
      if (pose === "open" && opts.fire && !calm && !palmOn && !opts.draw) fire(P, sc);
      if (h.pointing && opts.trail && !calm && !opts.draw && H2.filter((x) => x.pointing).length === 1) trail.push({ x: P[8].x, y: P[8].y, t: now });
      // basılı tutma kontrolleri (kitap açıkken: ✊ rafa koy, 👍 özeti oku)
      const HD = holds || (opts.draw ? { peace: [900, "NE ÇİZDİM?", askDrawing], fist: [1200, "SİL", clearDrawing], thumbs_up: [1000, "ÇİZİMİ BİTİR", () => { opts.draw = false; saveOpts(); msg("Çizim modu kapandı"); }] } : HOLDS);
      if ((opts.controls || holds || opts.draw) && HD[pose] && !h.pinch && !game) {
        const [ms, label, fn] = HD[pose], k = (now - st.since) / ms;
        if (!st.fired && k > 0.15) holdRing(P[9].x, P[9].y - sc * 1.2, Math.min(1, k), label);
        if (!st.fired && k >= 1) { st.fired = true; fn ? (fn(), snd("lock")) : control(pose, h); }
      }
    }
    // iki açık el → mühür; iki işaret → şimşek
    if (opts.seal && !calm && H2.length === 2 && H2.every((h) => h.pose === "open")) H2.forEach((h, i) => seal(h.P, h.sc, now, i));
    if (opts.lightning && !calm && H2.length === 2 && H2.every((h) => h.pointing)) { const a = H2[0].P[8], b = H2[1].P[8], d = Math.hypot(a.x - b.x, a.y - b.y); bolt(a, b, d * 0.35, 3); if (Math.random() < 0.3) bolt(a, b, d * 0.5, 2, [200, 160, 255], 0.6); if (Math.random() < 0.15) snd("zap"); }
    stepPlanets(now); stepParts(); stepWaves(); stepBolts(); if (opts.trail) drawTrail(now);
    if (strokes.length) drawStrokes();
    if (opts.mask) maskHud(now, M); else faceHud(now);
  }

  // ---------------- kamerasız deneme (sentetik eller) ----------------
  function synthHand(cx, cy, s, kind, t) {
    const lm = []; const P = (x, y) => ({ x: cx + x * s, y: cy + y * s, z: 0 });
    lm[0] = P(0, 0.35);
    const fingersX = [-0.13, -0.04, 0.05, 0.13];
    lm[1] = P(-0.12, 0.28); lm[2] = P(-0.2, 0.2);
    const pinch = kind === "pinch", fist = kind === "fist", point = kind === "point";
    if (pinch) { lm[3] = P(-0.16, 0.05); lm[4] = P(-0.1, -0.08); } else if (fist) { lm[3] = P(-0.12, 0.16); lm[4] = P(-0.05, 0.16); } else { lm[3] = P(-0.27, 0.12); lm[4] = P(-0.33, 0.05); }
    fingersX.forEach((fx, i) => {
      const b = 5 + i * 4; lm[b] = P(fx, 0.08);
      const ext = kind === "open" || (pinch && i > 0) || (point && i === 0);
      if (pinch && i === 0) { lm[b + 1] = P(fx - 0.01, -0.05); lm[b + 2] = P(-0.08, -0.09); lm[b + 3] = P(-0.09, -0.085); }
      else if (ext) { lm[b + 1] = P(fx, -0.08); lm[b + 2] = P(fx, -0.17); lm[b + 3] = P(fx, -0.25); }
      else { lm[b + 1] = P(fx, 0.0); lm[b + 2] = P(fx, 0.08); lm[b + 3] = P(fx, 0.12); }
    });
    return lm;
  }
  function demoHands(t) {
    const ph = Math.floor(t / 2500) % 6, x = 0.5 + Math.sin(t / 900) * 0.15;
    if (ph === 0) return [{ lm: synthHand(x, 0.55, 0.5, "open", t), handed: "Right" }];
    if (ph === 1) return [{ lm: synthHand(0.32, 0.55, 0.45, "open", t), handed: "Right" }, { lm: synthHand(0.68, 0.55, 0.45, "open", t), handed: "Left" }];
    if (ph === 2) return [{ lm: synthHand(x, 0.55 + Math.cos(t / 700) * 0.1, 0.5, "pinch", t), handed: "Right" }];
    if (ph === 3) return [{ lm: synthHand(0.5, 0.55, 0.5, (t % 2500) < 1200 ? "fist" : "open", t), handed: "Right" }];
    if (ph === 4) return [{ lm: synthHand(0.3, 0.6, 0.45, "point", t), handed: "Right" }, { lm: synthHand(0.7, 0.5, 0.45, "point", t), handed: "Left" }];
    return [{ lm: synthHand(x, 0.5 + Math.sin(t / 300) * 0.1, 0.5, "point", t), handed: "Right" }];
  }
  function demoLoop() { if (!on || !demo) return; raf = requestAnimationFrame(demoLoop); const t = performance.now() - demoT; frame(demoHands(t), null); }

  const api = {
    get active() { return on; },
    get profile() { return profile; },
    setProfile,
    video: () => vid,
    opts, frame,
    show(stream) {
      build(); size(); on = true; stage.classList.remove("hidden"); document.body.classList.add("ar-on");
      setProfile(profile, true);
      if (stream) { vid.srcObject = stream; vid.play().catch(() => {}); }
      msg("AR EFEKT · ellerini kameraya göster", 2200);
    },
    stop() {
      on = false; demo = false; game = null; cancelAnimationFrame(raf); parts = []; planets = []; bolts = []; waves = []; trail = [];
      if (JV.ardesk && JV.ardesk.on) JV.ardesk.toggle(false);
      if (stage) { stage.classList.add("hidden"); stage.style.transform = ""; } document.body.classList.remove("ar-on");
      Object.keys(hs).forEach((k) => delete hs[k]); face.box = null; face.locked = false;
      if (JV.gesture && JV.gesture.isRunning() && JV.gesture.mode && JV.gesture.mode() === "efekt") JV.gesture.stop();
    },
    _synth: (cx, cy, s, kind) => synthHand(cx, cy, s, kind, 0),
    demo() { build(); size(); on = true; demo = true; demoT = performance.now(); setProfile(profile, true); stage.classList.remove("hidden"); demoLoop(); },
    _setFaces: (f) => (lastFaces = f),
    _startGame: (k, dur) => { setProfile("game"); startGame(k); if (dur && game) game.dur = dur; },
    _game: () => game && { kind: game.kind, phase: game.phase, score: game.score, you: game.you, me: game.me, round: game.round, pick: game.pick, res: game.res, balloons: game.balloons && game.balloons.map((b) => ({ x: b.x, y: b.y, r: b.r })) },
    _toLm: (xs, ys) => { const vw = (vid && vid.videoWidth) || 640, vh = (vid && vid.videoHeight) || 480, sc = Math.max(W / vw, H / vh), dw = vw * sc, dh = vh * sc; return { x: 1 - (xs - (W - dw) / 2) / dw, y: (ys - (H - dh) / 2) / dh }; },
    stats: () => ({ strokes: strokes.length, palm: !!palmData.t, trail: trail.length, parts: parts.length, planets: planets.map((p) => p.type), bolts: bolts.length, face: !!face.box, locked: face.locked }),
    planet(type) { forcePlanet = type || ""; if (planets[0] && type) morph(planets[0], type); else if (type) msg("Sonraki çimdik: " + NAMES[type]); },
    cmd(r) {
      if (r.action === "close") return api.stop();
      if (r.action === "face") { setProfile(profile === "face" ? "none" : "face"); return; }
      if (r.action === "desktop") { setProfile("desktop"); if (!on && JV.gesture) JV.gesture.start("efekt"); if (r.panel && JV.ardesk) JV.ardesk.openPanel(r.panel); return; }
      if (r.action === "game") { setProfile("game"); if (!on && JV.gesture) JV.gesture.start("efekt"); startGame(r.game || "rps"); return; }
      if (r.action === "extra") {
        if (r.extra === "draw") { setProfile("draw"); msg("✏ Havaya çiz: ☝ çiz · ✌ ne çizdim? · ✊ sil · 👍 bitir", 4000); }
        if (r.extra === "mask") { setProfile(profile === "mask" ? "none" : "mask"); }
        if (r.extra === "palm") { setProfile("palm"); msg("✋ Avucunu kameraya aç ve sabit tut", 3000); }
      }
      if (!on && JV.gesture) JV.gesture.start("efekt");
      if (r.action === "planet" || r.planet) setProfile("planet");
      if (r.planet) api.planet(r.planet);
    },
  };
  // A saved pre-isolation setting must never reactivate several effects.
  setProfile(profile, true);
  JV.handfx = api;
})();
