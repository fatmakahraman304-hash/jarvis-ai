/* Ses kimliği: mikrofonun son birkaç saniyesini 16 kHz halka tamponda tutar,
   komut bitince o parçayı sunucuya gönderip kimin konuştuğunu öğrenir. */
(function () {
  const JV = (window.JV = window.JV || {});
  const RATE = 16000, SECONDS = 10;
  const ring = new Float32Array(RATE * SECONDS);
  let pos = 0, filled = 0, ctx = null, stream = null, running = false;

  async function start() {
    if (running) return true;
    try {
      stream = await navigator.mediaDevices.getUserMedia({ audio: { echoCancellation: true, noiseSuppression: true } });
      ctx = new (window.AudioContext || window.webkitAudioContext)();
      const src = ctx.createMediaStreamSource(stream);
      const proc = ctx.createScriptProcessor(4096, 1, 1);
      const ratio = ctx.sampleRate / RATE;
      proc.onaudioprocess = (e) => {
        const d = e.inputBuffer.getChannelData(0);
        for (let i = 0; i < d.length / ratio; i++) {
          ring[pos] = d[Math.floor(i * ratio)];
          pos = (pos + 1) % ring.length; filled = Math.min(ring.length, filled + 1);
        }
      };
      const mute = ctx.createGain(); mute.gain.value = 0;
      src.connect(proc); proc.connect(mute); mute.connect(ctx.destination);
      running = true;
      return true;
    } catch (e) { console.warn("ses kimliği mikrofonu açılamadı", e); return false; }
  }

  function last(seconds) {
    const n = Math.min(filled, Math.floor(seconds * RATE));
    const out = new Float32Array(n);
    for (let i = 0; i < n; i++) out[i] = ring[(pos - n + i + ring.length) % ring.length];
    return out;
  }

  function wav(samples) {
    const buf = new ArrayBuffer(44 + samples.length * 2), v = new DataView(buf);
    const w = (o, s) => { for (let i = 0; i < s.length; i++) v.setUint8(o + i, s.charCodeAt(i)); };
    w(0, "RIFF"); v.setUint32(4, 36 + samples.length * 2, true); w(8, "WAVE"); w(12, "fmt ");
    v.setUint32(16, 16, true); v.setUint16(20, 1, true); v.setUint16(22, 1, true); v.setUint32(24, RATE, true);
    v.setUint32(28, RATE * 2, true); v.setUint16(32, 2, true); v.setUint16(34, 16, true); w(36, "data");
    v.setUint32(40, samples.length * 2, true);
    for (let i = 0; i < samples.length; i++) v.setInt16(44 + i * 2, Math.max(-1, Math.min(1, samples[i])) * 0x7fff, true);
    return new Blob([buf], { type: "audio/wav" });
  }

  async function post(path, blob) {
    const r = await fetch(path, { method: "POST", headers: { "x-token": JV.token || "" }, body: blob });
    return r.json();
  }

  JV.voiceId = {
    start,
    isRunning: () => running,
    async identify(seconds = 3.5) {
      if (!running) return null;
      try { return await post("/api/voice/identify", wav(last(seconds))); } catch (e) { return null; }
    },
    async recordAndEnroll(name, seconds, owner) {
      if (!(await start())) throw new Error("Mikrofon açılamadı");
      filled = 0;
      await new Promise((r) => setTimeout(r, seconds * 1000));
      return post(`/api/voice/enroll?name=${encodeURIComponent(name)}${owner === undefined ? "" : "&owner=" + (owner ? 1 : 0)}`, wav(last(seconds)));
    },
  };
})();
