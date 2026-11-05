/* SESLİ ARAMA — "JARVIS'i ara" / "beni ara".
   Telefon görüşmesi gibi tam ekran: kişilik adı, süre, sessize al, hoparlör, kapat. Eller serbest döngü: dinle → düşün → konuş → tekrar dinle.
   Gelen arama: zil sesi (tarayıcıda üretilir) + titreşim, YEŞİL aç / KIRMIZI reddet; açınca JARVIS mesajını söyler.
   "kapat", "görüşürüz", "hoşça kal" deyince görüşme biter. */
(function () {
  const JV = (window.JV = window.JV || {});
  const $ = (s, r = document) => r.querySelector(s);
  let el, cv, raf = 0, active = false, muted = false, t0 = 0, tick = 0, ring = null, prevVoice = null, phase = "";
  const BYE = /\b(kapat|görüşürüz|hoşça ?kal|güle güle|bitir|aramayı kapat|kapatabilirsin|bye)\b/i;
  function build() {
    if (el) return;
    el = document.createElement("div"); el.id = "callui"; el.className = "hidden";
    el.innerHTML = `<div class="cl-top"><span id="cl-kind">SESLİ GÖRÜŞME</span><span id="cl-time">00:00</span></div>
      <canvas id="cl-orb"></canvas>
      <div class="cl-name" id="cl-name">J.A.R.V.I.S.</div>
      <div class="cl-state" id="cl-state">BAĞLANIYOR…</div>
      <div class="cl-said" id="cl-said"></div>
      <div class="cl-btns cl-live"><button id="cl-mute" title="Mikrofonu kapat"><i>🎙</i><small>SESSİZ</small></button><button id="cl-end" class="red" title="Kapat"><i>✆</i><small>KAPAT</small></button><button id="cl-spk" title="Sesli cevap"><i>🔊</i><small>HOPARLÖR</small></button></div>
      <div class="cl-btns cl-ring"><button id="cl-no" class="red"><i>✆</i><small>REDDET</small></button><button id="cl-yes" class="green"><i>✆</i><small>CEVAPLA</small></button></div>`;
    document.body.append(el); cv = $("#cl-orb", el);
    $("#cl-end", el).onclick = () => end();
    $("#cl-no", el).onclick = () => end();
    $("#cl-yes", el).onclick = () => accept();
    $("#cl-mute", el).onclick = () => { muted = !muted; $("#cl-mute", el).classList.toggle("on", muted); if (muted && JV.stt && JV.stt.busy()) JV.stt.stop(); state(muted ? "SESSİZDE" : "DİNLİYOR"); };
    $("#cl-spk", el).onclick = () => { JV.settings.voice_enabled = !JV.settings.voice_enabled; $("#cl-spk", el).classList.toggle("on", !JV.settings.voice_enabled); if (!JV.settings.voice_enabled) JV.stopSpeaking && JV.stopSpeaking(); };
  }
  const state = (s) => { const e = $("#cl-state", el); if (e) e.textContent = s; };
  const said = (s) => { const e = $("#cl-said", el); if (e) e.textContent = s || ""; };
  function draw() {
    const d = Math.min(devicePixelRatio || 1, 2), w = cv.clientWidth, h = cv.clientHeight;
    if (cv.width !== Math.round(w * d)) { cv.width = w * d; cv.height = h * d; }
    const g = cv.getContext("2d"); g.setTransform(d, 0, 0, d, 0, 0); g.clearRect(0, 0, w, h);
    const hex = (getComputedStyle(document.documentElement).getPropertyValue("--c").trim() || "#38d6ff").slice(0, 7);
    const lvl = phase === "ring" ? 0.35 + 0.35 * Math.abs(Math.sin(performance.now() / 180)) : JV.level || 0;
    if (JV.core2d) JV.core2d.reactor(g, { t: performance.now() / 1000, lvl, cx: w / 2, cy: h / 2, R: Math.min(w, h) * 0.27, hex, noLabel: true });
    if (active || phase === "ring") raf = requestAnimationFrame(draw);
  }
  function timer() { const s = Math.floor((Date.now() - t0) / 1000); $("#cl-time", el).textContent = String(Math.floor(s / 60)).padStart(2, "0") + ":" + String(s % 60).padStart(2, "0"); }
  // --------- zil sesi (özgün, tarayıcıda üretilen iki tonlu çalma) ---------
  function ringStart() {
    try {
      const ctx = new (window.AudioContext || window.webkitAudioContext)(); const gain = ctx.createGain(); gain.gain.value = 0; gain.connect(ctx.destination);
      [523, 659].forEach((f) => { const o = ctx.createOscillator(); o.type = "sine"; o.frequency.value = f; o.connect(gain); o.start(); });
      let n = 0; const iv = setInterval(() => { const on = n % 10 < 4 && n % 2 === 0; gain.gain.setTargetAtTime(on ? 0.12 : 0, ctx.currentTime, 0.02); n++; }, 120);
      if (navigator.vibrate) navigator.vibrate([400, 200, 400, 1200, 400, 200, 400]);
      ring = { ctx, iv };
    } catch (e) {}
  }
  function ringStop() { if (!ring) return; clearInterval(ring.iv); ring.ctx.close().catch(() => {}); ring = null; if (navigator.vibrate) navigator.vibrate(0); }
  // --------- dinle ---------
  function listen() {
    return new Promise((res) => {
      if (JV.stt && JV.stt.available()) {
        JV.stt.record({ waitMs: 12000, silenceMs: 1100, maxMs: 30000, onText: (t) => res((t || "").trim()), onError: () => res(""), onLevel: (v) => (JV.level = v) });
        return;
      }
      const SR = window.SpeechRecognition || window.webkitSpeechRecognition;
      if (!SR) { state("BU TARAYICIDA SES TANIMA YOK"); return setTimeout(() => res(""), 3000); }
      const r = new SR(); r.lang = (JV.settings && JV.settings.stt_lang) || "tr-TR"; r.interimResults = false; r.maxAlternatives = 1;
      let out = ""; r.onresult = (e) => (out = e.results[0][0].transcript); r.onend = () => res(out.trim()); r.onerror = () => res("");
      try { r.start(); } catch (e) { res(""); }
    });
  }
  const waitQuiet = async () => { const s = Date.now(); while ((JV.speaking || document.body.classList.contains("thinking")) && active && Date.now() - s < 120000) await new Promise((r) => setTimeout(r, 200)); await new Promise((r) => setTimeout(r, 350)); };
  async function loop() {
    let empty = 0;
    while (active) {
      if (muted) { await new Promise((r) => setTimeout(r, 300)); continue; }
      state("DİNLİYOR"); said("");
      const text = await listen();
      if (!active) break;
      if (!text) { empty++; if (empty >= 4) { state("ORADA MISINIZ?"); await new Promise((r) => setTimeout(r, 1200)); empty = 0; } continue; }
      empty = 0; said("“" + text + "”");
      if (BYE.test(text) && text.split(/\s+/).length <= 5) { JV.say && JV.say("Görüşmek üzere efendim.", JV.settings.persona, null, true); await waitQuiet(); return end(); }
      state("DÜŞÜNÜYOR");
      try { await JV.sendCommand(text); } catch (e) {}
      state("KONUŞUYOR"); await waitQuiet();
    }
  }
  function show(kind) {
    build(); el.classList.remove("hidden"); el.classList.toggle("ringing", kind === "ring");
    const pn = $("#p-name"); $("#cl-name", el).textContent = pn ? pn.textContent : "J.A.R.V.I.S.";
    cancelAnimationFrame(raf); raf = requestAnimationFrame(draw);
  }
  async function start(greeting) {
    if (active) return;
    show("live"); phase = "live"; active = true; muted = false; t0 = Date.now(); clearInterval(tick); tick = setInterval(timer, 500); timer();
    $("#cl-kind", el).textContent = "SESLİ GÖRÜŞME";
    prevVoice = JV.settings.voice_enabled; JV.settings.voice_enabled = true; $("#cl-spk", el).classList.remove("on");
    JV.stopSpeaking && JV.stopSpeaking(false);
    const g = greeting || "Buyurun efendim, dinliyorum.";
    state("KONUŞUYOR"); said(g); JV.say && JV.say(g, JV.settings.persona, null, true);
    await new Promise((r) => setTimeout(r, 300)); await waitQuiet();
    loop();
  }
  function incoming(msg) {
    if (active) return;
    show("ring"); phase = "ring"; $("#cl-kind", el).textContent = "GELEN ARAMA"; state("ARIYOR…"); said(msg ? "“" + msg + "”" : ""); $("#cl-time", el).textContent = "";
    el.dataset.msg = msg || ""; ringStart();
    clearTimeout(el._miss); el._miss = setTimeout(() => { if (phase === "ring") { end(); JV.toast && JV.toast("📞 Cevapsız arama: " + (msg || "JARVIS aradı"), 8000); } }, 30000);
  }
  function accept() { ringStop(); clearTimeout(el._miss); el.classList.remove("ringing"); phase = ""; start(el.dataset.msg || ""); }
  function end() {
    ringStop(); active = false; phase = ""; clearInterval(tick); cancelAnimationFrame(raf);
    if (JV.stt && JV.stt.busy()) JV.stt.stop();
    if (prevVoice !== null) { JV.settings.voice_enabled = prevVoice; prevVoice = null; }
    if (el) { el.classList.add("hidden"); el.classList.remove("ringing"); clearTimeout(el._miss); }
  }
  JV.call = { start, incoming, end, active: () => active, ringing: () => phase === "ring" };
})();
