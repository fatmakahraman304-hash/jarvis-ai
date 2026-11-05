/* UYKU MODU + İKİ ALKIŞLA UYANMA
   Uyku: ekran kararır, ortada nefes alan bir nokta. Mikrofon yalnızca uykudayken ve yalnızca alkışı dinler (ses kaydı yok,
   hiçbir yere gönderilmez). Keskin, kısa bir ses patlaması = alkış; 0,15–0,7 sn arayla iki alkış = uyan.
   Konuşma, müzik, kapı sesi gibi uzun/yumuşak sesler tetiklemez. Tıklama ya da tuş da uyandırır.
   Ayarlar: sleep_idle_min (boşta kalınca uyku, dk; 0 = kapalı), clap_threshold (0.15–0.8). */
(function () {
  const JV = (window.JV = window.JV || {});
  let el, dot, lvl, asleep = false, stream = null, ctx = null, iv = 0, lastAct = Date.now();
  const st = { base: 0.01, claps: [], prev: 0, decayCheck: null };

  function build() {
    if (el) return;
    el = document.createElement("div"); el.id = "sleepov"; el.className = "hidden";
    el.innerHTML = `<div class="sl-dot"></div><div class="sl-ring"></div><div class="sl-txt">UYKU MODU · uyandırmak için iki kez alkışla ya da tıkla</div><div class="sl-lvl"><i></i></div>`;
    document.body.append(el);
    dot = el.querySelector(".sl-dot"); lvl = el.querySelector(".sl-lvl i");
    el.addEventListener("click", () => wake("tık"));
  }
  const thr = () => Math.max(0.12, Math.min(0.9, (JV.settings && +JV.settings.clap_threshold) || 0.35));

  async function listen() {
    try {
      stream = await navigator.mediaDevices.getUserMedia({ audio: { echoCancellation: false, noiseSuppression: false, autoGainControl: false } });
    } catch (e) { el.querySelector(".sl-txt").textContent = "UYKU MODU · (mikrofon izni yok — uyandırmak için tıkla)"; return; }
    ctx = new (window.AudioContext || window.webkitAudioContext)();
    const an = ctx.createAnalyser(); an.fftSize = 512; ctx.createMediaStreamSource(stream).connect(an);
    const buf = new Float32Array(an.fftSize);
    iv = setInterval(() => {
      an.getFloatTimeDomainData(buf);
      let peak = 0, s = 0; for (const v of buf) { const a = Math.abs(v); if (a > peak) peak = a; s += v * v; }
      const rms = Math.sqrt(s / buf.length), now = performance.now();
      lvl.style.width = Math.min(100, (peak / thr()) * 100) + "%";
      const onset = peak > thr() && rms > st.base * 6 && rms > st.prev * 2.5;
      if (st.decayCheck && now - st.decayCheck.t > 110) { // alkış kısa olmalı: 110 ms sonra ses düşmüş mü?
        if (rms < st.decayCheck.rms * 0.45) clap(now); st.decayCheck = null;
      }
      if (onset && !st.decayCheck) st.decayCheck = { t: now, rms };
      if (!onset) st.base = st.base * 0.97 + rms * 0.03;
      st.prev = rms;
    }, 20);
  }
  function clap(now) {
    st.claps = st.claps.filter((t) => now - t < 900); st.claps.push(now);
    dot.classList.add("hit"); setTimeout(() => dot.classList.remove("hit"), 180);
    const n = st.claps.length;
    if (n >= 2) { const gap = st.claps[n - 1] - st.claps[n - 2]; if (gap > 150 && gap < 700) wake("alkış"); }
  }
  function unlisten() { clearInterval(iv); iv = 0; if (stream) stream.getTracks().forEach((t) => t.stop()); stream = null; if (ctx) ctx.close().catch(() => {}); ctx = null; }

  function sleep() {
    build(); if (asleep) return;
    asleep = true; el.classList.remove("hidden", "waking"); document.body.classList.add("asleep");
    JV.stopSpeaking && JV.stopSpeaking(); st.claps = [];
    listen();
  }
  function wake(how) {
    if (!asleep) return;
    asleep = false; unlisten(); el.classList.add("waking"); lastAct = Date.now();
    setTimeout(() => { el.classList.add("hidden"); el.classList.remove("waking"); document.body.classList.remove("asleep"); }, 1400);
    const h = new Date().getHours(), g = h < 6 ? "İyi geceler" : h < 12 ? "Günaydın" : h < 18 ? "İyi günler" : "İyi akşamlar";
    setTimeout(() => JV.say && JV.say(`${g}. Sistemler çevrimiçi.`, JV.currentPersona && JV.currentPersona()), 500);
    console.log("[uyku] uyandı:", how);
  }
  ["mousemove", "keydown", "pointerdown", "touchstart"].forEach((e) => addEventListener(e, () => { lastAct = Date.now(); if (asleep && e === "keydown") wake("tuş"); }, { passive: true }));
  setInterval(() => {
    const m = +(JV.settings && JV.settings.sleep_idle_min) || 0;
    if (m > 0 && !asleep && !JV.speaking && Date.now() - lastAct > m * 60000 && !(JV.handfx && JV.handfx.active)) sleep();
  }, 15000);
  JV.sleep = { enter: sleep, wake, get asleep() { return asleep; }, touch: () => (lastAct = Date.now()), _clap: clap };
})();
