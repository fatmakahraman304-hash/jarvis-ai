/* Ses motoru: cümle cümle konuşma kuyruğu, kişiliğe göre film efekti, görsele seviye verisi. */
(function () {
  const JV = (window.JV = window.JV || {});
  JV.level = 0;           // 0..1 konuşma şiddeti (görsel bunu kullanır)
  JV.speaking = false;

  let ctx = null, analyser = null, master = null;
  let current = null;      // çalan kaynak
  let queue = [];          // {text, promise}
  let playing = false;
  let gen = 0;             // durdurulunca eski istekleri geçersiz kılar
  let currentItem = null;  // çalan cümle
  let interrupted = [];    // araya girilince kalan cümleler (devam et için)
  let fakeLevelT = 0;

  function ensureCtx() {
    if (ctx) return ctx;
    ctx = new (window.AudioContext || window.webkitAudioContext)();
    analyser = ctx.createAnalyser();
    analyser.fftSize = 512;
    master = ctx.createGain();
    master.gain.value = 1;
    analyser.connect(master);
    master.connect(ctx.destination);
    return ctx;
  }
  JV.unlockAudio = () => { ensureCtx(); if (ctx.state === "suspended") ctx.resume(); };

  function impulse(seconds, decay) {
    const rate = ctx.sampleRate, len = Math.floor(rate * seconds);
    const buf = ctx.createBuffer(2, len, rate);
    for (let c = 0; c < 2; c++) {
      const d = buf.getChannelData(c);
      for (let i = 0; i < len; i++) d[i] = (Math.random() * 2 - 1) * Math.pow(1 - i / len, decay);
    }
    return buf;
  }
  function shaper(k) {
    const n = 2048, curve = new Float32Array(n);
    for (let i = 0; i < n; i++) { const x = (i * 2) / n - 1; curve[i] = ((3 + k) * x * 20 * Math.PI / 180) / (Math.PI + k * Math.abs(x)); }
    const s = ctx.createWaveShaper(); s.curve = curve; s.oversample = "4x"; return s;
  }

  // ---- Film efekt ayarları (Ses laboratuvarından değiştirilebilir) ----
  // hpf: alçak kesim Hz · bass: kalınlık dB · presence: netlik dB · drive: distorsiyon · metal: metalik halka (0-1)
  // double: ikinci ses katmanı (0-1) · reverb: yankı (0-1) · room: oda büyüklüğü sn · speed: oynatma hızı · radio: hologram/telsiz filtresi (0-1)
  const FX = {
    jarvis: { hpf: 140, bass: 1, presence: 4, drive: 0, metal: 0, double: 0.12, reverb: 0.22, room: 1.4, speed: 1, radio: 0.1 },
    friday: { hpf: 110, bass: 0, presence: 3, drive: 0, metal: 0, double: 0, reverb: 0.12, room: 0.9, speed: 1, radio: 0 },
    ultron: { hpf: 50, bass: 8, presence: 2, drive: 6, metal: 0.35, double: 0.5, reverb: 0.38, room: 2.6, speed: 0.96, radio: 0 },
  };
  JV.FX_DEFAULTS = FX;
  JV.fxFor = (persona) => Object.assign({}, FX[persona] || FX.jarvis, ((JV.settings.voice_fx || {})[persona]) || {});

  // efekt zinciri; giriş düğümünü döndürür
  function chain(persona, fxOn, override) {
    const out = analyser;
    const input = ctx.createGain();
    if (!fxOn) { input.connect(out); return { input, rate: 1 }; }
    const f = Object.assign(JV.fxFor(persona), override || {});
    const dry = ctx.createGain(), wet = ctx.createGain(), rev = ctx.createConvolver(), cleanups = [];
    const hp = ctx.createBiquadFilter(); hp.type = "highpass"; hp.frequency.value = f.hpf;
    const low = ctx.createBiquadFilter(); low.type = "lowshelf"; low.frequency.value = 220; low.gain.value = f.bass;
    const pres = ctx.createBiquadFilter(); pres.type = "peaking"; pres.frequency.value = 3200; pres.gain.value = f.presence; pres.Q.value = 0.9;
    input.connect(hp); hp.connect(low); low.connect(pres);
    let node = pres;
    if (f.radio > 0) { // hologram/telsiz: bant geçiren + hafif sıkıştırma
      const bp = ctx.createBiquadFilter(); bp.type = "bandpass"; bp.frequency.value = 1800; bp.Q.value = 0.4 + f.radio * 1.2;
      const mixA = ctx.createGain(), mixB = ctx.createGain(), sum = ctx.createGain(); mixA.gain.value = 1 - f.radio; mixB.gain.value = f.radio * 1.6;
      node.connect(mixA); node.connect(bp); bp.connect(mixB); mixA.connect(sum); mixB.connect(sum); node = sum;
    }
    if (f.drive > 0) { const d = shaper(f.drive); node.connect(d); node = d; }
    if (f.metal > 0) {
      const ring = ctx.createGain(); ring.gain.value = 1 - f.metal * 0.5;
      const osc = ctx.createOscillator(); osc.frequency.value = 48;
      const depth = ctx.createGain(); depth.gain.value = f.metal; osc.connect(depth); depth.connect(ring.gain); osc.start();
      cleanups.push(() => osc.stop()); node.connect(ring); node = ring;
    }
    node.connect(dry);
    if (f.double > 0) { const dly = ctx.createDelay(); dly.delayTime.value = 0.018; const g = ctx.createGain(); g.gain.value = f.double * 0.9; low.connect(dly); dly.connect(g); g.connect(dry); }
    node.connect(rev); rev.buffer = impulse(Math.max(0.3, f.room), persona === "ultron" ? 2.2 : 3);
    dry.gain.value = 0.92; wet.gain.value = f.reverb;
    rev.connect(wet); dry.connect(out); wet.connect(out);
    return { input, rate: f.speed || 1, cleanup: () => cleanups.forEach((c) => c()) };
  }

  function mood(text) {
    const t = text.toLowerCase();
    if (/(maalesef|üzgünüm|ne yazık|kayıp|başarısız)/.test(t)) return "sad";
    if (/(dikkat|uyarı|tehlike|acil|kritik)/.test(t)) return "serious";
    if (/!/.test(text) || /(harika|müthiş|tebrik|süper|başardık)/.test(t)) return "excited";
    if (/\?\s*$/.test(text)) return "curious";
    return "";
  }

  async function fetchTTS(text, persona, myGen, lang, opts, useOriginal = false) {
    try {
      const o = opts || {};
      // Original clips are optional, exact-phrase matches only. The regular
      // Neural TTS path remains the fallback for every unrecorded sentence.
      if (useOriginal && !o.voice) {
        const clipLang = (lang && lang !== "auto") ? lang :
          (/[çğıöşüÇĞİÖŞÜ]/.test(text) ? "tr" : (JV.settings.voice_lang === "tr" ? "tr" : "en"));
        const clip = await JV.api("/api/original-voice?persona=" + encodeURIComponent(persona) +
          "&lang=" + encodeURIComponent(clipLang) + "&text=" + encodeURIComponent(text), { raw: true });
        if (clip.ok) {
          const bytes = await clip.arrayBuffer();
          if (myGen !== gen) return null;
          return await ensureCtx().decodeAudioData(bytes);
        }
      }
      if (!JV.state || !JV.state.tts) return null;
      const extra = (o.voice ? "&voice=" + encodeURIComponent(o.voice) : "") + (o.rate != null ? "&rate=" + o.rate : "") + (o.pitch != null ? "&pitch=" + o.pitch : "");
      const r = await JV.api(`/api/tts?persona=${persona}&mood=${mood(text)}${lang ? "&lang=" + lang : ""}${extra}&text=${encodeURIComponent(text)}`, { raw: true });
      if (!r.ok) return null;
      const buf = await r.arrayBuffer();
      if (myGen !== gen) return null;
      return await ensureCtx().decodeAudioData(buf);
    } catch (e) { return null; }
  }

  function browserSpeak(text, persona, forceLang) {
    return new Promise((resolve) => {
      if (!("speechSynthesis" in window)) return resolve();
      const p = (JV.state.personas || []).find((x) => x.id === persona) || {};
      const u = new SpeechSynthesisUtterance(text);
      const lang = forceLang || (/[çğıöşüÇĞİÖŞÜ]/.test(text) || JV.settings.voice_lang === "tr" ? "tr" : (JV.settings.voice_lang === "en" ? "en" : "tr"));
      if (forceLang) u.lang = forceLang;
      const voices = speechSynthesis.getVoices();
      const female = persona === "friday";
      const cand = voices.filter((v) => v.lang.toLowerCase().startsWith(lang));
      u.voice = cand.find((v) => female ? /female|emel|filiz|zira|jenny|aria/i.test(v.name) : /male|ahmet|tolga|david|guy|ryan/i.test(v.name)) || cand[0] || null;
      u.lang = lang === "tr" ? "tr-TR" : "en-GB";
      u.pitch = (p.voice && p.voice.browser_pitch) || 1;
      u.rate = (p.voice && p.voice.browser_rate) || 1;
      u.onend = u.onerror = () => { fakeLevelT = 0; resolve(); };
      fakeLevelT = 1;
      speechSynthesis.speak(u);
    });
  }

  function playBuffer(buffer, persona, fxOverride) {
    return new Promise((resolve) => {
      const c = chain(persona, JV.settings.effects !== false || !!fxOverride, fxOverride);
      const src = ctx.createBufferSource();
      src.buffer = buffer; src.playbackRate.value = c.rate;
      src.connect(c.input);
      src.onended = () => { c.cleanup && c.cleanup(); current = null; resolve(); };
      current = src; src.start();
    });
  }

  async function pump() {
    if (playing) return;
    playing = true;
    const myGen = gen;
    while (queue.length && myGen === gen) {
      const item = queue.shift();
      currentItem = item;
      setSpeaking(true);
      JV.onCaption && JV.onCaption(item.text);
      const buf = await item.promise;
      if (myGen !== gen) break;
      if (buf) await playBuffer(buf, item.persona, item.fx);
      else await browserSpeak(item.text, item.persona, item.lang);
    }
    playing = false;
    if (myGen === gen) { currentItem = null; interrupted = []; setSpeaking(false); JV.onSpeechEnd && JV.onSpeechEnd(); }
  }

  function setSpeaking(v) {
    JV.speaking = v;
    document.body.classList.toggle("speaking", v);
  }

  JV.say = function (text, persona, lang, force) {
    text = (text || "").replace(/[*_#`>]/g, "").replace(/https?:\/\/\S+/g, "bağlantı").trim();
    if (!text || !JV.settings.voice_enabled) return;
    if (JV.quiet && !force) return; // sessiz mod
    ensureCtx();
    const myGen = gen;
    queue.push({ text, persona, lang, promise: fetchTTS(text, persona, myGen, lang, null, true) });
    pump();
  };

  // Ses laboratuvarı önizlemesi: kaydetmeden belirli ses/hız/ton/efektle konuş
  JV.sayWith = function (text, persona, opts = {}) {
    ensureCtx(); if (ctx.state === "suspended") ctx.resume();
    JV.stopSpeaking(false);
    const myGen = gen;
    queue.push({ text, persona, lang: opts.lang, fx: opts.fx, promise: fetchTTS(text, persona, myGen, opts.lang, opts) });
    pump();
  };

  JV.stopSpeaking = function (keep = true) {
    if (keep && (currentItem || queue.length)) interrupted = [currentItem, ...queue].filter(Boolean).map((q) => ({ text: q.text, persona: q.persona }));
    else if (!keep) interrupted = [];
    currentItem = null;
    gen++;
    queue = [];
    try { current && current.stop(); } catch (e) {}
    current = null;
    if ("speechSynthesis" in window) speechSynthesis.cancel();
    playing = false; fakeLevelT = 0;
    setSpeaking(false);
  };

  JV.hasInterrupted = () => interrupted.length > 0;
  JV.resumeSpeaking = function () {
    const items = interrupted; interrupted = [];
    items.forEach((i) => JV.say(i.text, i.persona));
    return items.length;
  };

  // akan metni cümlelere bölen yardımcı
  JV.Sentencer = function (persona) {
    let buf = "";
    return {
      push(t) {
        buf += t;
        let m;
        while ((m = buf.match(/^([\s\S]{12,}?[.!?…:;](?=\s|$)|[\s\S]+?\n)/))) {
          const s = m[0]; buf = buf.slice(s.length);
          if (s.trim()) JV.say(s.trim(), persona);
        }
      },
      flush() { if (buf.trim()) JV.say(buf.trim(), persona); buf = ""; },
    };
  };

  // sinyal seviyesi
  const data = new Uint8Array(256);
  (function meter() {
    let lvl = 0;
    if (analyser && JV.speaking) {
      analyser.getByteTimeDomainData(data);
      let s = 0; for (let i = 0; i < data.length; i++) { const v = (data[i] - 128) / 128; s += v * v; }
      lvl = Math.min(1, Math.sqrt(s / data.length) * 4.5);
    }
    if (fakeLevelT) lvl = Math.max(lvl, 0.25 + 0.35 * Math.abs(Math.sin(performance.now() / 90)) * Math.random());
    JV.level += (lvl - JV.level) * 0.35;
    requestAnimationFrame(meter);
  })();

  // kısa sinyal sesi (uyandırma onayı)
  JV.beep = function (f = 880) {
    ensureCtx();
    const o = ctx.createOscillator(), g = ctx.createGain();
    o.frequency.value = f; g.gain.setValueAtTime(0.0001, ctx.currentTime);
    g.gain.exponentialRampToValueAtTime(0.15, ctx.currentTime + 0.02);
    g.gain.exponentialRampToValueAtTime(0.0001, ctx.currentTime + 0.18);
    o.connect(g); g.connect(ctx.destination); o.start(); o.stop(ctx.currentTime + 0.2);
  };
})();
