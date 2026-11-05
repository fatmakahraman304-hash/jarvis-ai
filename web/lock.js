/* SİSTEM KİLİDİ — "sistemi kilitle".
   Tam ekran: dönen nokta küresi + ağ çizgileri, ortada kilit halkası, saat/tarih.
   Açma yolları: ✋✋ İKİ ELLE ÇİMDİKLE ve ellerini AÇ (kamera, MediaPipe — kare bir yere gitmez) · PIN (Ayarlar'da belirlenirse) · basılı tut.
   PIN belirlenmişse açmak için PIN gerekir (hareket PIN'i atlamaz). Not: bu bir EKRAN kilididir; Windows kilidi için "bilgisayarı kilitle". */
(function () {
  const JV = (window.JV = window.JV || {});
  const $ = (s, r = document) => r.querySelector(s);
  const LS = (k, v) => { try { if (v === undefined) return localStorage.getItem(k); if (v === null) localStorage.removeItem(k); else localStorage.setItem(k, v); } catch (e) { return null; } };
  let el, cv, raf = 0, on = false, cam = null, camRaf = 0, spread0 = 0, prog = 0, holdT = 0, unlocking = 0, lastTs = -1;
  const pts = [...Array(900)].map(() => { const u = Math.random() * 2 - 1, a = Math.random() * Math.PI * 2, s = Math.sqrt(1 - u * u); return [s * Math.cos(a), u, s * Math.sin(a), Math.random()]; });
  async function sha(s) { const b = await crypto.subtle.digest("SHA-256", new TextEncoder().encode("jv-lock:" + s)); return [...new Uint8Array(b)].map((x) => x.toString(16).padStart(2, "0")).join(""); }
  const hasPin = () => !!LS("jv_lock_pin");
  JV.setLockPin = async (pin) => { pin = String(pin || "").trim(); if (!pin) { LS("jv_lock_pin", null); return false; } LS("jv_lock_pin", await sha(pin)); return true; };
  function build() {
    if (el) return;
    el = document.createElement("div"); el.id = "lockui"; el.className = "hidden";
    el.innerHTML = `<canvas id="lk-bg"></canvas>
      <div class="lk-top"><span>J.A.R.V.I.S. // GÜVENLİK</span><span id="lk-date"></span></div>
      <div class="lk-mid"><div class="lk-ring" id="lk-ring"><svg viewBox="0 0 200 200"><circle cx="100" cy="100" r="92" class="lk-r0"/><circle cx="100" cy="100" r="92" class="lk-r1" id="lk-prog"/></svg>
        <div class="lk-in"><b>SİSTEM KİLİTLİ</b><small id="lk-clock"></small></div></div>
        <div class="lk-msg" id="lk-msg">✋✋ İki elle çimdikle, sonra ellerini aç</div>
        <div class="lk-pin hidden" id="lk-pinbox"><input id="lk-pin" type="password" inputmode="numeric" maxlength="12" placeholder="PIN" autocomplete="off"><button class="btn-primary" id="lk-go">AÇ</button></div>
        <div class="lk-btns"><button class="mini" id="lk-cam">✋ ELLE AÇ (KAMERA)</button><button class="mini" id="lk-hold">⏻ BASILI TUT</button></div></div>
      <video id="lk-v" playsinline muted></video><canvas id="lk-hands"></canvas>
      <div class="lk-foot">Bu ekran kilidi; Windows'u kilitlemek için "bilgisayarı kilitle" de.</div>`;
    document.body.append(el); cv = $("#lk-bg", el);
    $("#lk-cam", el).onclick = () => (cam ? stopCam() : startCam());
    const hb = $("#lk-hold", el);
    const down = () => { if (hasPin()) return pinMode(); holdT = performance.now(); }, up = () => (holdT = 0);
    hb.addEventListener("pointerdown", down); ["pointerup", "pointerleave", "pointercancel"].forEach((e) => hb.addEventListener(e, up));
    $("#lk-go", el).onclick = tryPin; $("#lk-pin", el).addEventListener("keydown", (e) => { if (e.key === "Enter") tryPin(); });
  }
  function pinMode() { $("#lk-pinbox", el).classList.remove("hidden"); $("#lk-pin", el).focus(); msg("PIN gir"); }
  async function tryPin() {
    const v = $("#lk-pin", el).value; $("#lk-pin", el).value = "";
    if (v && (await sha(v)) === LS("jv_lock_pin")) return unlock("PIN");
    msg("✗ Yanlış PIN", true); el.classList.add("lk-shake"); setTimeout(() => el.classList.remove("lk-shake"), 500);
  }
  const msg = (t, bad) => { const m = $("#lk-msg", el); m.textContent = t; m.classList.toggle("bad", !!bad); };
  function setProg(p) { prog = Math.max(0, Math.min(1, p)); const c = $("#lk-prog", el); c.style.strokeDashoffset = String(578 * (1 - prog)); }
  // ---------- arka plan: dönen nokta küresi + ağ yayları ----------
  function draw(now) {
    const d = Math.min(devicePixelRatio || 1, 2), w = innerWidth, h = innerHeight;
    if (cv.width !== Math.round(w * d)) { cv.width = w * d; cv.height = h * d; }
    const g = cv.getContext("2d"); g.setTransform(d, 0, 0, d, 0, 0); g.clearRect(0, 0, w, h);
    const col = (getComputedStyle(document.documentElement).getPropertyValue("--c").trim() || "#38d6ff").slice(0, 7);
    const n = parseInt(col.slice(1), 16), rgb = `${(n >> 16) & 255},${(n >> 8) & 255},${n & 255}`;
    const t = now / 1000, R = Math.min(w, h) * (0.42 + prog * 0.25 + unlocking * 0.8), cx = w / 2, cy = h / 2, rot = t * 0.12 + prog * 2;
    g.globalCompositeOperation = "lighter";
    const proj = [];
    pts.forEach(([x, y, z, s]) => { const X = x * Math.cos(rot) + z * Math.sin(rot), Z = -x * Math.sin(rot) + z * Math.cos(rot); const k = 1 / (1.9 - Z * 0.6); proj.push([cx + X * R * k, cy + y * R * k, Z, s]); });
    proj.forEach(([x, y, z, s]) => { g.fillStyle = `rgba(${rgb},${(0.12 + (z + 1) * 0.3) * (1 - unlocking)})`; g.fillRect(x, y, 1.6 + s, 1.6 + s); });
    g.strokeStyle = `rgba(${rgb},${0.09 * (1 - unlocking)})`; g.lineWidth = 1;
    for (let i = 0; i < 70; i++) { const a = proj[i * 7], b = proj[(i * 13 + 5) % proj.length]; if (a[2] > 0 && b[2] > 0) { g.beginPath(); g.moveTo(a[0], a[1]); g.quadraticCurveTo(cx, cy - R * 0.2, b[0], b[1]); g.stroke(); } }
    g.globalCompositeOperation = "source-over";
    if (holdT) { const p = (now - holdT) / 1200; setProg(p); if (p >= 1) { holdT = 0; unlock("BASILI TUT"); } } else if (!cam && !unlocking) setProg(prog * 0.9);
    const dt = new Date(); $("#lk-clock", el).textContent = dt.toLocaleTimeString("tr-TR", { hour: "2-digit", minute: "2-digit" });
    $("#lk-date", el).textContent = dt.toLocaleDateString("tr-TR", { weekday: "long", day: "numeric", month: "long" }).toUpperCase();
    if (on) raf = requestAnimationFrame(draw);
  }
  // ---------- iki elle çimdikle-aç ----------
  async function startCam() {
    if (hasPin()) { pinMode(); msg("PIN ayarlı: önce PIN gir"); return; }
    msg("Kamera açılıyor…");
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ video: { width: 640, height: 480, facingMode: "user" } });
      const v = $("#lk-v", el); v.srcObject = stream; await v.play(); cam = { stream, v };
      el.classList.add("lk-camon"); $("#lk-cam", el).textContent = "✕ KAMERAYI KAPAT";
      msg("El modeli yükleniyor…");
      const hands = await JV.mp.load("hand");
      msg("✋✋ İki elinle çimdikle (başparmak + işaret), sonra ellerini aç");
      const hc = $("#lk-hands", el);
      const loop = () => {
        if (!cam) return;
        const ts = performance.now(); if (ts <= lastTs) { camRaf = requestAnimationFrame(loop); return; } lastTs = ts;
        let res = null; try { res = hands.detectForVideo(v, ts); } catch (e) {}
        const L = (res && res.landmarks) || [];
        const g2 = hc.getContext("2d"); hc.width = hc.clientWidth; hc.height = hc.clientHeight; g2.clearRect(0, 0, hc.width, hc.height);
        L.forEach((lm) => lm.forEach((p, i) => { g2.fillStyle = i === 4 || i === 8 ? "#fff" : "rgba(56,214,255,.7)"; g2.beginPath(); g2.arc((1 - p.x) * hc.width, p.y * hc.height, i === 4 || i === 8 ? 4 : 2, 0, 7); g2.fill(); }));
        const pinch = (lm) => Math.hypot(lm[4].x - lm[8].x, lm[4].y - lm[8].y) < 0.07;
        if (L.length === 2 && pinch(L[0]) && pinch(L[1])) {
          const mid = (lm) => [(lm[4].x + lm[8].x) / 2, (lm[4].y + lm[8].y) / 2], a = mid(L[0]), b = mid(L[1]), dd = Math.hypot(a[0] - b[0], a[1] - b[1]);
          if (!spread0) spread0 = dd;
          setProg((dd - spread0) / 0.3); msg(prog > 0.05 ? "AÇILIYOR… " + Math.round(prog * 100) + "%" : "Şimdi ellerini birbirinden uzaklaştır");
          if (prog >= 1) return unlock("EL HAREKETİ");
        } else { spread0 = 0; if (L.length < 2) msg(L.length ? "İkinci eli de göster" : "✋✋ İki elini kameraya göster"); }
        camRaf = requestAnimationFrame(loop);
      };
      loop();
    } catch (e) { msg("Kamera/el modeli açılamadı: " + e.message, true); stopCam(); }
  }
  function stopCam() { cancelAnimationFrame(camRaf); if (cam) cam.stream.getTracks().forEach((t) => t.stop()); cam = null; spread0 = 0; if (el) { el.classList.remove("lk-camon"); $("#lk-cam", el).textContent = "✋ ELLE AÇ (KAMERA)"; } }
  function lock() {
    build(); if (on) return; on = true; unlocking = 0; setProg(0);
    el.classList.remove("hidden", "lk-open"); $("#lk-pinbox", el).classList.toggle("hidden", !hasPin());
    msg(hasPin() ? "PIN gir" : "✋✋ İki elle çimdikle, sonra ellerini aç · ya da basılı tut");
    document.body.classList.add("locked"); JV.stopSpeaking && JV.stopSpeaking(false);
    if (JV.video) JV.video.close();
    cancelAnimationFrame(raf); raf = requestAnimationFrame(draw);
  }
  function unlock(how) {
    if (!on) return;
    stopCam(); setProg(1); msg("✓ ERİŞİM ONAYLANDI"); el.classList.add("lk-open");
    const s = performance.now(); const anim = (n) => { unlocking = Math.min(1, (n - s) / 700); if (unlocking < 1) requestAnimationFrame(anim); else finish(); }; requestAnimationFrame(anim);
    const name = (JV.settings && JV.settings.ar_name) || LS("jv_ar_name") || "";
    if (JV.say && JV.settings && JV.settings.voice_enabled) JV.say(`Erişim onaylandı. Tekrar hoş geldiniz${name ? " " + name : ""} efendim.`, JV.settings.persona);
    JV.lastUnlock = how;
  }
  function finish() { on = false; cancelAnimationFrame(raf); el.classList.add("hidden"); el.classList.remove("lk-open"); document.body.classList.remove("locked"); unlocking = 0; }
  const bindPin = () => { const i = document.getElementById("lk-pinset"); if (!i) return; i.placeholder = hasPin() ? "•••• (ayarlı)" : "yok";
    i.onchange = async () => { const ok = await JV.setLockPin(i.value); i.value = ""; i.placeholder = ok ? "•••• (ayarlı)" : "yok"; JV.toast && JV.toast(ok ? "🔒 Kilit PIN'i ayarlandı" : "Kilit PIN'i kaldırıldı"); }; };
  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", bindPin); else bindPin();
  JV.lock = { on: lock, off: () => { if (!on) return; if (hasPin()) return pinMode(); unlock("KOMUT"); }, locked: () => on, hasPin, _setProg: setProg };
})();
