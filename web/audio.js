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
          (JV.settings.voice_lang === "tr" || JV.settings.voice_lang === "en" ? JV.settings.voice_lang : "auto");
        const clip = await JV.api("/api/original-voice?persona=" + encodeURIComponent(persona) +
          "&lang=" + encodeURIComponent(clipLang) + "&text=" + encodeURIComponent(text), { raw: true });
        if (clip.ok) {
          const bytes = await clip.arrayBuffer();
          if (myGen !== gen) return null;
          return await ensureCtx().decodeAudioData(bytes);
        }
      }
      if (!JV.state || !JV.state.tts) return null;
      const r = await JV.api(`/api/tts?persona=${persona}&mood=${mood(text)}${lang ? "&lang=" + lang : ""}&text=${encodeURIComponent(text)}`, { raw: true });
      if (!r.ok) return null;
      const buf = await r.arrayBuffer();
      if (myGen !== gen) return null;
      return await ensureCtx().decodeAudioData(buf);
    } catch (e) { return null; }
  }

  // Mark LVI-style Gemini Live speech output. Keep one persistent session and
  // serialize sentences; Edge TTS remains the fallback and voice-lab preview.
  let liveSocket = null, liveConnect = null, liveReady = false, liveVoicePersona = "";
  let liveCurrent = null, liveSequence = 0, liveQueue = Promise.resolve();
  let liveFailureUntil = 0, liveWarned = false;

  function liveEnsureSocket(persona) {
    const wanted = ["jarvis", "friday", "ultron"].includes(persona) ? persona : "jarvis";
    if (liveSocket && liveVoicePersona !== wanted) {
      const previous = liveSocket;
      liveSocket = null; liveReady = false; liveConnect = null;
      try { previous.close(); } catch (_) {}
    }
    if (liveSocket && liveSocket.readyState === WebSocket.OPEN && liveReady) return Promise.resolve();
    if (liveConnect) return liveConnect;
    liveConnect = new Promise((resolve, reject) => {
      const scheme = location.protocol === "https:" ? "wss:" : "ws:";
      const url = new URL(scheme + "//" + location.host + "/api/live-voice");
      if (JV.token) url.searchParams.set("token", JV.token);
      url.searchParams.set("persona", wanted);
      liveVoicePersona = wanted;
      const ws = new WebSocket(url.toString());
      liveSocket = ws;
      let settled = false;
      const timer = setTimeout(() => {
        if (!settled) { settled = true; liveConnect = null; reject(new Error("Gemini Live bağlantı zaman aşımı")); try { ws.close(); } catch (_) {} }
      }, 12000);
      ws.onmessage = (event) => {
        let msg;
        try { msg = JSON.parse(event.data); } catch (_) { return; }
        if (msg.type === "ready") {
          liveReady = true;
          if (!settled) { settled = true; clearTimeout(timer); liveConnect = null; resolve(); }
        } else if (msg.type === "audio" && liveCurrent && msg.id === liveCurrent.id) {
          liveCurrent.chunks.push(msg.data);
          liveCurrent.rate = msg.sample_rate || 24000;
        } else if (msg.type === "done" && liveCurrent && msg.id === liveCurrent.id) {
          const job = liveCurrent; liveCurrent = null; clearTimeout(job.timer);
          if (!job.chunks.length) job.reject(new Error("Gemini Live ses verisi döndürmedi"));
          else job.resolve({ chunks: job.chunks, rate: job.rate || 24000 });
        } else if (msg.type === "error") {
          const err = new Error(msg.text || "Gemini Live ses hatası");
          if (liveCurrent) { const job = liveCurrent; liveCurrent = null; clearTimeout(job.timer); job.reject(err); }
          if (!settled) { settled = true; clearTimeout(timer); liveConnect = null; reject(err); }
        }
      };
      ws.onerror = () => {
        const err = new Error("Gemini Live WebSocket bağlantısı kurulamadı");
        if (!settled) { settled = true; clearTimeout(timer); liveConnect = null; reject(err); }
        if (liveCurrent) { const job = liveCurrent; liveCurrent = null; clearTimeout(job.timer); job.reject(err); }
      };
      ws.onclose = () => {
        if (liveSocket !== ws) return;
        liveReady = false; liveSocket = null; liveConnect = null; liveVoicePersona = "";
        if (!settled) { settled = true; clearTimeout(timer); reject(new Error("Gemini Live bağlantısı kapandı")); }
        if (liveCurrent) { const job = liveCurrent; liveCurrent = null; clearTimeout(job.timer); job.reject(new Error("Gemini Live bağlantısı kapandı")); }
      };
    });
    return liveConnect;
  }

  function livePcmBuffer(result) {
    const decoded = result.chunks.map((part) => {
      const raw = atob(part), chunk = new Uint8Array(raw.length);
      for (let i = 0; i < raw.length; i++) chunk[i] = raw.charCodeAt(i);
      return chunk;
    });
    const size = decoded.reduce((n, chunk) => n + chunk.length, 0);
    const bytes = new Uint8Array(size);
    let offset = 0;
    for (const chunk of decoded) { bytes.set(chunk, offset); offset += chunk.length; }
    const usable = bytes.byteLength - (bytes.byteLength % 2);
    if (!usable) throw new Error("Gemini Live boş PCM ses döndürdü");
    const pcm = new Int16Array(bytes.buffer, bytes.byteOffset, usable / 2);
    const buffer = ensureCtx().createBuffer(1, pcm.length, result.rate);
    const channel = buffer.getChannelData(0);
    for (let i = 0; i < pcm.length; i++) channel[i] = pcm[i] / 32768;
    return buffer;
  }

  function liveRequest(text, myGen, persona) {
    if (Date.now() < liveFailureUntil) return Promise.reject(new Error("Gemini Live kısa süreliğine beklemeye alındı"));
    return liveEnsureSocket(persona).then(() => {
      if (myGen !== gen) return null;
      const id = String(++liveSequence);
      return new Promise((resolve, reject) => {
        const timer = setTimeout(() => {
          if (liveCurrent && liveCurrent.id === id) liveCurrent = null;
          reject(new Error("Gemini Live yanıtı 25 saniyede tamamlanmadı"));
        }, 25000);
        liveCurrent = { id, chunks: [], rate: 24000, resolve, reject, timer };
        try { liveSocket.send(JSON.stringify({ id, text })); }
        catch (e) { clearTimeout(timer); liveCurrent = null; reject(e); }
      });
    }).then((result) => {
      if (!result || myGen !== gen) return null;
      return livePcmBuffer(result);
    }).catch((error) => {
      liveFailureUntil = Date.now() + 60000;
      if (liveSocket) { try { liveSocket.close(); } catch (_) {} }
      throw error;
    });
  }

  function liveSynthesize(text, myGen, persona) {
    const task = liveQueue.then(() => liveRequest(text, myGen, persona));
    liveQueue = task.catch(() => null);
    return task;
  }
  JV.resetLiveVoice = function () {
    const previous = liveSocket;
    liveSocket = null; liveConnect = null; liveReady = false; liveVoicePersona = "";
    try { previous && previous.close(); } catch (_) {}
  };
  addEventListener("pagehide", () => { try { liveSocket && liveSocket.close(); } catch (_) {} });

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
      let buf = item.promise ? await item.promise : null;
      if (myGen !== gen) break;
      if (!buf && item.live && JV.settings.live_voice !== false) {
        try { buf = await liveSynthesize(item.text, myGen, item.persona); }
        catch (e) {
          if (!liveWarned) {
            liveWarned = true;
            JV.toast && JV.toast("Gemini Live sesi kullanılamadı; Edge TTS ile devam ediyorum: " + e.message, 8000);
          }
        }
      }
      if (myGen !== gen) break;
      if (!buf && item.live) buf = await fetchTTS(item.text, item.persona, myGen, item.lang, null, true);
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
    queue.push({ text, persona, lang, live: true, promise: JV.settings.live_voice === false ? fetchTTS(text, persona, myGen, lang, null, true) : null });
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
