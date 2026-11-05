/* Daha doğru konuşma tanıma: sesi kaydeder (konuşma bitince ~1,2 sn sessizlikte kendiliğinden durur) ve sunucuda Whisper ile
   yazıya çevirir (Groq, ücretsiz). Tarayıcının kendi tanımasından çok daha isabetli; özel isimleri ve Türkçeyi iyi anlar. */
(function () {
  const JV = (window.JV = window.JV || {});
  let active = null;
  JV.stt = {
    available() {
      const eng = (JV.settings && JV.settings.stt_engine) || "auto";
      if (eng === "browser") return false;
      const groq = (JV.state && JV.state.providers || []).find((p) => p.id === "groq");
      return eng === "whisper" || !!(groq && groq.configured);
    },
    busy: () => !!active,
    stop() { if (active) active.stop(true); },
    async record({ onStart, onText, onError, maxMs = 30000, silenceMs = 1200, waitMs = 8000 } = {}) {
      if (active) { active.stop(true); return; }
      let stream;
      try { stream = await navigator.mediaDevices.getUserMedia({ audio: { echoCancellation: true, noiseSuppression: true, autoGainControl: true } }); }
      catch (e) { onError && onError("Mikrofon izni yok."); return; }
      const ctx = new (window.AudioContext || window.webkitAudioContext)();
      const an = ctx.createAnalyser(); an.fftSize = 1024; ctx.createMediaStreamSource(stream).connect(an);
      const rec = new MediaRecorder(stream), chunks = [];
      rec.ondataavailable = (e) => e.data.size && chunks.push(e.data);
      const buf = new Uint8Array(an.fftSize); let heard = false, quiet = 0, t0 = performance.now(), noise = 0, n = 0, iv;
      const finish = () => { clearInterval(iv); if (rec.state !== "inactive") rec.stop(); stream.getTracks().forEach((t) => t.stop()); ctx.close().catch(() => {}); };
      active = { stop: (manual) => { if (manual && !heard) active.cancel = true; finish(); } };
      iv = setInterval(() => {
        an.getByteTimeDomainData(buf); let s = 0; for (const v of buf) s += (v - 128) * (v - 128);
        const rms = Math.sqrt(s / buf.length);
        if (n < 6) { noise = (noise * n + rms) / (n + 1); n++; return; } // ilk 0,3 sn: ortam gürültüsü
        const thr = Math.max(5, noise * 2.2);
        if (rms > thr) { heard = true; quiet = 0; } else if (heard) quiet += 50;
        const el = performance.now() - t0;
        if ((heard && quiet > silenceMs) || el > maxMs) finish();
        if (!heard && el > waitMs) { active.cancel = true; finish(); }
      }, 50);
      rec.onstop = async () => {
        const me = active; active = null;
        if (me && me.cancel) { onText && onText(""); return; }
        const blob = new Blob(chunks, { type: rec.mimeType || "audio/webm" });
        try {
          const r = await fetch("/api/transcribe?lang=" + ((JV.settings.stt_lang || "tr").slice(0, 2)), { method: "POST", headers: { "x-token": JV.token || "", "Content-Type": blob.type }, body: blob });
          const j = await r.json();
          if (j.error) onError && onError(j.error); else onText && onText((j.text || "").trim());
        } catch (e) { onError && onError(e.message); }
      };
      rec.start(250); onStart && onStart();
    },
  };
})();
