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

  // kişiliğe göre efekt zinciri; giriş düğümünü döndürür
  function chain(persona, fx) {
    const out = analyser;
    const input = ctx.createGain();
    if (!fx) { input.connect(out); return { input, rate: 1 }; }
    const dry = ctx.createGain(), wet = ctx.createGain(), rev = ctx.createConvolver();
    if (persona === "ultron") {
      const low = ctx.createBiquadFilter(); low.type = "lowshelf"; low.frequency.value = 220; low.gain.value = 7;
      const dist = shaper(6);
      const ring = ctx.createGain(); ring.gain.value = 0.65;
      const osc = ctx.createOscillator(); osc.frequency.value = 48;
      const depth = ctx.createGain(); depth.gain.value = 0.35; osc.connect(depth); depth.connect(ring.gain); osc.start();
      const dly = ctx.createDelay(); dly.delayTime.value = 0.018; const dlyG = ctx.createGain(); dlyG.gain.value = 0.45;
      input.connect(low); low.connect(dist); dist.connect(ring); ring.connect(dry);
      low.connect(dly); dly.connect(dlyG); dlyG.connect(dry);
      ring.connect(rev); rev.buffer = impulse(2.6, 2.2); wet.gain.value = 0.38; dry.gain.value = 0.9;
      rev.connect(wet); dry.connect(out); wet.connect(out);
      return { input, rate: 0.96, cleanup: () => osc.stop() };
    }
    const hp = ctx.createBiquadFilter(); hp.type = "highpass"; hp.frequency.value = persona === "jarvis" ? 140 : 100;
    const pres = ctx.createBiquadFilter(); pres.type = "peaking"; pres.frequency.value = persona === "jarvis" ? 3000 : 4200; pres.gain.value = persona === "jarvis" ? 3 : 2; pres.Q.value = 0.9;
    input.connect(hp); hp.connect(pres); pres.connect(dry); pres.connect(rev);
    rev.buffer = impulse(persona === "jarvis" ? 1.3 : 0.9, 3);
    dry.gain.value = 0.92; wet.gain.value = persona === "jarvis" ? 0.2 : 0.12;
    rev.connect(wet); dry.connect(out); wet.connect(out);
    return { input, rate: 1 };
  }

  function mood(text) {
    const t = text.toLowerCase();
    if (/(maalesef|üzgünüm|ne yazık|kayıp|başarısız)/.test(t)) return "sad";
    if (/(dikkat|uyarı|tehlike|acil|kritik)/.test(t)) return "serious";
    if (/!/.test(text) || /(harika|müthiş|tebrik|süper|başardık)/.test(t)) return "excited";
    if (/\?\s*$/.test(text)) return "curious";
    return "";
  }

  async function fetchTTS(text, persona, myGen, lang) {
    if (!JV.state || !JV.state.tts) return null;
    try {
      const r = await JV.api(`/api/tts?persona=${persona}&mood=${mood(text)}${lang ? "&lang=" + lang : ""}&text=${encodeURIComponent(text)}`, { raw: true });
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

  function playBuffer(buffer, persona) {
    return new Promise((resolve) => {
      const c = chain(persona, JV.settings.effects !== false);
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
      if (buf) await playBuffer(buf, item.persona);
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
    queue.push({ text, persona, lang, promise: fetchTTS(text, persona, myGen, lang) });
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
