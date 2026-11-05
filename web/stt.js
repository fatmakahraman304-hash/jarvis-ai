/* Daha doğru konuşma tanıma: sesi kaydeder (konuşma bitince ~1,2 sn sessizlikte kendiliğinden durur) ve sunucuda
   yazıya çevirir (Groq Whisper; o yoksa Gemini). Ses 16 kHz WAV olarak gönderilir: her iki servis de sorunsuz okur.
   Ortam gürültüsüne kendini ayarlar; seçili mikrofonu kullanır (Ayarlar > SES). */
(function () {
  const JV = (window.JV = window.JV || {});
  let active = null;

  function wav(chunks, inRate, outRate = 16000) {
    let len = 0; for (const c of chunks) len += c.length;
    const all = new Float32Array(len); let o = 0; for (const c of chunks) { all.set(c, o); o += c.length; }
    const ratio = inRate / outRate, n = Math.floor(all.length / ratio), pcm = new Int16Array(n);
    let peak = 0; for (let i = 0; i < all.length; i++) peak = Math.max(peak, Math.abs(all[i]));
    const gain = peak > 0.0005 && peak < 0.3 ? Math.min(8, 0.6 / peak) : 1; // kısık mikrofonu yükselt
    for (let i = 0; i < n; i++) { // basit ortalamalı örnek azaltma
      let s = 0, a = Math.floor(i * ratio), b = Math.min(all.length, Math.floor((i + 1) * ratio)); for (let j = a; j < b; j++) s += all[j];
      const v = Math.max(-1, Math.min(1, (s / Math.max(1, b - a)) * gain)); pcm[i] = v < 0 ? v * 0x8000 : v * 0x7fff;
    }
    const buf = new ArrayBuffer(44 + pcm.length * 2), d = new DataView(buf), w = (p, s) => [...s].forEach((ch, i) => d.setUint8(p + i, ch.charCodeAt(0)));
    w(0, "RIFF"); d.setUint32(4, 36 + pcm.length * 2, true); w(8, "WAVE"); w(12, "fmt "); d.setUint32(16, 16, true); d.setUint16(20, 1, true);
    d.setUint16(22, 1, true); d.setUint32(24, outRate, true); d.setUint32(28, outRate * 2, true); d.setUint16(32, 2, true); d.setUint16(34, 16, true);
    w(36, "data"); d.setUint32(40, pcm.length * 2, true); new Int16Array(buf, 44).set(pcm);
    return { blob: new Blob([buf], { type: "audio/wav" }), peak };
  }

  JV.wav = wav;
  JV.stt = {
    available() {
      const eng = (JV.settings && JV.settings.stt_engine) || "auto";
      if (eng === "browser") return false;
      const ok = (id) => (JV.state && JV.state.providers || []).some((p) => p.id === id && p.configured && !p.key_error);
      return eng === "whisper" || (JV.state && JV.state.stt_ready) || ok("groq") || ok("gemini");
    },
    busy: () => !!active,
    stop() { if (active) active.stop(true); },
    async devices() {
      try { const d = await navigator.mediaDevices.enumerateDevices(); return d.filter((x) => x.kind === "audioinput"); } catch (e) { return []; }
    },
    async record({ onStart, onText, onError, onLevel, maxMs = 30000, silenceMs = 1300, waitMs = 10000, transcribe = true } = {}) {
      if (active) { active.stop(true); return; }
      let stream;
      const mic = JV.settings && JV.settings.mic_id;
      const base = { echoCancellation: true, noiseSuppression: true, autoGainControl: true };
      try { stream = await navigator.mediaDevices.getUserMedia({ audio: mic ? { ...base, deviceId: { exact: mic } } : base }); }
      catch (e) {
        try { stream = await navigator.mediaDevices.getUserMedia({ audio: base }); } // seçili mikrofon çıkarılmışsa varsayılan
        catch (e2) { onError && onError("Mikrofon açılamadı (izin verilmedi ya da mikrofon yok)."); return; }
      }
      const ctx = new (window.AudioContext || window.webkitAudioContext)();
      if (ctx.state === "suspended") await ctx.resume().catch(() => {});
      const src = ctx.createMediaStreamSource(stream);
      const proc = ctx.createScriptProcessor(4096, 1, 1), pcm = [];
      const sink = ctx.createGain(); sink.gain.value = 0; // hoparlöre ses verme
      src.connect(proc); proc.connect(sink); sink.connect(ctx.destination);
      let heard = false, quiet = 0, t0 = performance.now(), noise = 0.004, maxLvl = 0, speechMs = 0, done = false;
      const finish = (cancel) => {
        if (done) return; done = true;
        proc.disconnect(); src.disconnect(); stream.getTracks().forEach((t) => t.stop());
        const me = active; active = null; ctx.close().catch(() => {});
        if (cancel || (me && me.cancel)) {
          onText && onText("", { reason: heard ? "iptal" : "sessiz", level: maxLvl });
          return;
        }
        const { blob, peak } = wav(pcm, ctx.sampleRate);
        if (!transcribe) { onText && onText("", { reason: "test", level: maxLvl, peak, blob }); return; }
        fetch("/api/transcribe?lang=" + ((JV.settings.stt_lang || "tr").slice(0, 2)), { method: "POST", headers: { "x-token": JV.token || "", "Content-Type": "audio/wav" }, body: blob })
          .then((r) => r.json())
          .then((j) => { if (j.error) onError && onError(j.error); else onText && onText((j.text || "").trim(), { reason: j.text ? "ok" : "anlaşılmadı", level: maxLvl, engine: j.engine }); })
          .catch((e) => onError && onError(e.message));
      };
      active = { stop: (manual) => { if (manual && !heard) active.cancel = true; finish(); } };
      proc.onaudioprocess = (e) => {
        if (done) return;
        const x = e.inputBuffer.getChannelData(0); pcm.push(new Float32Array(x));
        let s = 0; for (let i = 0; i < x.length; i++) s += x[i] * x[i];
        const rms = Math.sqrt(s / x.length), dt = (x.length / ctx.sampleRate) * 1000;
        maxLvl = Math.max(maxLvl, rms);
        // gürültü tabanı: yalnızca sessiz anlarda yavaşça güncellenir (konuşma tabanı yükseltmez)
        const thr = Math.min(0.06, Math.max(0.008, noise * 2.5));
        if (rms < thr) noise = noise * 0.95 + rms * 0.05;
        onLevel && onLevel(Math.min(1, rms / 0.15), rms > thr);
        if (rms > thr) { speechMs += dt; if (speechMs > 120) heard = true; quiet = 0; } else if (heard) quiet += dt;
        const el = performance.now() - t0;
        if ((heard && quiet > silenceMs) || el > maxMs) finish();
        else if (!heard && el > waitMs) finish(true);
      };
      onStart && onStart();
    },
  };
})();
