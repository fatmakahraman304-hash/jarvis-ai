/* MÜZİK STÜDYOSU: besteyi WebAudio sentezleyicileriyle çalar (piyano, e-piyano, çan, yaylılar, pad, bakır, saksafon, lead, gitar, baslar,
   davullar), piyano rulosu + oynatma çizgisi, WAV (OfflineAudioContext) ve MIDI indirme. */
(function () {
  const JV = (window.JV = window.JV || {});
  const $ = (s, r = document) => r.querySelector(s);
  const esc = (t) => String(t == null ? "" : t).replace(/[&<>"]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" })[c]);
  const hz = (m) => 440 * Math.pow(2, (m - 69) / 12);
  let root, song = null, ctx = null, startAt = 0, raf = 0;

  // ---------- sentez ----------
  let noiseBuf = null;
  function noise(c) {
    if (noiseBuf && noiseBuf.sampleRate === c.sampleRate) return noiseBuf;
    const b = c.createBuffer(1, c.sampleRate * 2, c.sampleRate), d = b.getChannelData(0);
    for (let i = 0; i < d.length; i++) d[i] = Math.random() * 2 - 1;
    return (noiseBuf = b);
  }
  function impulse(c, sec = 2.4) {
    const L = Math.floor(c.sampleRate * sec), b = c.createBuffer(2, L, c.sampleRate);
    for (let ch = 0; ch < 2; ch++) { const d = b.getChannelData(ch); for (let i = 0; i < L; i++) d[i] = (Math.random() * 2 - 1) * Math.pow(1 - i / L, 3); }
    return b;
  }
  function osc(c, type, f, t, det = 0) { const o = c.createOscillator(); o.type = type; o.frequency.value = f; o.detune.value = det; return o; }
  function env(c, g, t, a, peak, d, sus, rel, end) {
    g.gain.setValueAtTime(0.0001, t); g.gain.linearRampToValueAtTime(peak, t + a);
    g.gain.setTargetAtTime(peak * sus, t + a, d);
    g.gain.setTargetAtTime(0.0001, end, rel);
  }
  function voice(c, out, inst, t, dur, midi, vel) {
    const f = hz(midi), v = (vel / 127), end = t + dur, g = c.createGain(); g.connect(out);
    const play = (nodes, stop) => nodes.forEach((n) => { n.start(t); n.stop(stop); });
    const lp = (freq, q = 0.7) => { const b = c.createBiquadFilter(); b.type = "lowpass"; b.frequency.value = freq; b.Q.value = q; b.connect(g); return b; };
    switch (inst) {
      case "piano": { const a = osc(c, "triangle", f), b = osc(c, "sine", f * 2), bg = c.createGain(); bg.gain.value = 0.25; const fl = lp(Math.min(9000, f * 8));
        a.connect(fl); b.connect(bg).connect(fl); env(c, g, t, 0.004, 0.22 * v, Math.min(1.2, 0.3 + dur * 0.4), 0.15, 0.25, end); play([a, b], end + 1.5); break; }
      case "epiano": { const a = osc(c, "sine", f), b = osc(c, "sine", f * 2.0, 3), bg = c.createGain(); bg.gain.value = 0.18; const tr = c.createGain(); const lf = osc(c, "sine", 4.5), lg = c.createGain(); lg.gain.value = 0.25;
        lf.connect(lg).connect(tr.gain); tr.gain.value = 0.75; a.connect(tr); b.connect(bg).connect(tr); tr.connect(g); env(c, g, t, 0.006, 0.2 * v, 0.8, 0.3, 0.3, end); play([a, b, lf], end + 1.5); break; }
      case "bell": { const a = osc(c, "sine", f), b = osc(c, "sine", f * 2.76), bg = c.createGain(); bg.gain.setValueAtTime(0.35, t); bg.gain.exponentialRampToValueAtTime(0.001, t + 0.6);
        a.connect(g); b.connect(bg).connect(g); env(c, g, t, 0.003, 0.16 * v, 0.9, 0.05, 0.4, end); play([a, b], end + 2); break; }
      case "strings": case "pad": { const n = inst === "pad" ? 3 : 2, fl = lp(inst === "pad" ? 1400 : 2600), os = [];
        for (let k = 0; k < n; k++) { const o = osc(c, "sawtooth", f, (k - (n - 1) / 2) * 9); o.connect(fl); os.push(o); }
        const A = inst === "pad" ? 0.9 : 0.25; env(c, g, t, A, (inst === "pad" ? 0.07 : 0.09) * v, 1, 0.9, inst === "pad" ? 1.0 : 0.35, end); play(os, end + 3); break; }
      case "brass": { const o = osc(c, "sawtooth", f), b = c.createBiquadFilter(); b.type = "lowpass"; b.Q.value = 2; b.frequency.setValueAtTime(500, t); b.frequency.linearRampToValueAtTime(2800, t + 0.12); b.frequency.setTargetAtTime(1600, t + 0.12, 0.3);
        o.connect(b).connect(g); env(c, g, t, 0.05, 0.13 * v, 0.4, 0.8, 0.15, end); play([o], end + 1); break; }
      case "sax": case "lead": { const o = osc(c, inst === "sax" ? "sawtooth" : "square", f), vib = osc(c, "sine", 5.2), vg = c.createGain(); vg.gain.value = f * 0.006; vib.connect(vg).connect(o.frequency);
        const fl = lp(inst === "sax" ? 2200 : 3200, 1.2); o.connect(fl); env(c, g, t, 0.03, (inst === "sax" ? 0.11 : 0.07) * v, 0.3, 0.7, 0.08, end); play([o, vib], end + 1); break; }
      case "guitar": { const o = osc(c, "sawtooth", f), o2 = osc(c, "square", f, 8), ws = c.createWaveShaper(), curve = new Float32Array(256);
        for (let i = 0; i < 256; i++) { const x = i / 128 - 1; curve[i] = Math.tanh(x * 3); } ws.curve = curve; const fl = lp(2400); o.connect(ws); o2.connect(ws); ws.connect(fl);
        env(c, g, t, 0.005, 0.07 * v, 0.6, 0.4, 0.1, end); play([o, o2], end + 1); break; }
      default: { // baslar
        const o = osc(c, inst === "synthbass" ? "sawtooth" : "triangle", f), s = osc(c, "sine", f), fl = lp(inst === "synthbass" ? 700 : inst === "cello" ? 1600 : 900, inst === "synthbass" ? 4 : 0.8);
        o.connect(fl); s.connect(g); const A = inst === "cello" ? 0.12 : 0.008; env(c, g, t, A, 0.2 * v, 0.5, inst === "upright" ? 0.2 : 0.6, 0.1, end); play([o, s], end + 1);
      }
    }
  }
  function drum(c, out, kind, t, vel) {
    const v = vel / 127, g = c.createGain(); g.connect(out);
    const nz = (type, freq, q, dec, amp) => { const s = c.createBufferSource(); s.buffer = noise(c); const b = c.createBiquadFilter(); b.type = type; b.frequency.value = freq; b.Q.value = q; const gg = c.createGain();
      gg.gain.setValueAtTime(amp * v, t); gg.gain.exponentialRampToValueAtTime(0.0001, t + dec); s.connect(b).connect(gg).connect(g); s.start(t); s.stop(t + dec + 0.05); };
    if (kind === "kick") { const o = osc(c, "sine", 150); o.frequency.setValueAtTime(150, t); o.frequency.exponentialRampToValueAtTime(42, t + 0.12); const gg = c.createGain(); gg.gain.setValueAtTime(0.9 * v, t); gg.gain.exponentialRampToValueAtTime(0.0001, t + 0.45); o.connect(gg).connect(g); o.start(t); o.stop(t + 0.5); }
    else if (kind === "snare") { nz("bandpass", 1800, 0.8, 0.18, 0.5); const o = osc(c, "triangle", 185), gg = c.createGain(); gg.gain.setValueAtTime(0.3 * v, t); gg.gain.exponentialRampToValueAtTime(0.0001, t + 0.1); o.connect(gg).connect(g); o.start(t); o.stop(t + 0.12); }
    else if (kind === "clap") { [0, 0.012, 0.024].forEach((d) => { const s = c.createBufferSource(); s.buffer = noise(c); const b = c.createBiquadFilter(); b.type = "bandpass"; b.frequency.value = 1500; const gg = c.createGain(); gg.gain.setValueAtTime(0.45 * v, t + d); gg.gain.exponentialRampToValueAtTime(0.0001, t + d + 0.12); s.connect(b).connect(gg).connect(g); s.start(t + d); s.stop(t + d + 0.15); }); }
    else if (kind === "hat") nz("highpass", 7500, 0.7, 0.05, 0.22);
    else if (kind === "ohat") nz("highpass", 7000, 0.7, 0.28, 0.16);
    else if (kind === "ride") nz("bandpass", 5200, 1.5, 0.6, 0.12);
    else if (kind === "crash") nz("highpass", 4500, 0.5, 1.6, 0.22);
    else if (kind === "rim") { const o = osc(c, "square", 1700), gg = c.createGain(); gg.gain.setValueAtTime(0.12 * v, t); gg.gain.exponentialRampToValueAtTime(0.0001, t + 0.03); o.connect(gg).connect(g); o.start(t); o.stop(t + 0.04); }
    else if (kind === "tom") { const o = osc(c, "sine", 130); o.frequency.exponentialRampToValueAtTime(75, t + 0.25); const gg = c.createGain(); gg.gain.setValueAtTime(0.6 * v, t); gg.gain.exponentialRampToValueAtTime(0.0001, t + 0.45); o.connect(gg).connect(g); o.start(t); o.stop(t + 0.5); }
  }
  function schedule(c, s, t0) {
    const spb = 60 / s.bpm, master = c.createGain(); master.gain.value = 0.75;
    const comp = c.createDynamicsCompressor(); comp.threshold.value = -14; comp.ratio.value = 4;
    let tail = master;
    if (s.lofi) { const lp = c.createBiquadFilter(); lp.type = "lowpass"; lp.frequency.value = 3600; master.connect(lp); tail = lp;
      const cr = c.createBufferSource(); cr.buffer = noise(c); cr.loop = true; const hp = c.createBiquadFilter(); hp.type = "highpass"; hp.frequency.value = 2500; const cg = c.createGain(); cg.gain.value = 0.012; cr.connect(hp).connect(cg).connect(comp); cr.start(t0); cr.stop(t0 + s.bars * 4 * spb + 2); }
    const lim = c.createDynamicsCompressor(); lim.threshold.value = -4; lim.knee.value = 0; lim.ratio.value = 20; lim.attack.value = 0.002; lim.release.value = 0.12;
    const outG = c.createGain(); outG.gain.value = 0.8; // sınırlayıcı + pay: kırpılma olmasın
    tail.connect(comp); comp.connect(lim).connect(outG).connect(c.destination);
    const rev = c.createConvolver(); rev.buffer = impulse(c); const wet = c.createGain(); wet.gain.value = s.reverb || 0.2; master.connect(rev).connect(wet).connect(comp);
    s.tracks.forEach((tr) => tr.notes.forEach(([b, d, m, v]) => voice(c, master, tr.instrument, t0 + b * spb, Math.max(0.05, d * spb), m, v)));
    (s.drums || []).forEach(([b, k, v]) => drum(c, master, k, t0 + b * spb, v));
    return s.bars * 4 * spb;
  }

  // ---------- oynatma ve çizim ----------
  function stop() { cancelAnimationFrame(raf); if (ctx) { try { ctx.close(); } catch (e) {} ctx = null; } draw(-1); setBtn(false); }
  function play() {
    if (!song) return; stop();
    ctx = new (window.AudioContext || window.webkitAudioContext)(); startAt = ctx.currentTime + 0.15;
    const dur = schedule(ctx, song, startAt); setBtn(true);
    const tick = () => { if (!ctx) return; const p = (ctx.currentTime - startAt) / dur; draw(p); if (p < 1.02) raf = requestAnimationFrame(tick); else stop(); };
    tick();
  }
  function setBtn(on) { const b = $("#mu-play", root); if (b) b.textContent = on ? "■ DURDUR" : "▶ ÇAL"; }
  const COLS = ["#38d6ff", "#ffb020", "#22e39a"];
  function draw(p) {
    const cv = $("#mu-roll", root); if (!cv || !song) return; const g = cv.getContext("2d"), W = cv.width, H = cv.height; g.clearRect(0, 0, W, H);
    const beats = song.bars * 4, all = song.tracks.flatMap((t) => t.notes.map((n) => n[2])); const lo = Math.min(...all, 40) - 1, hi = Math.max(...all, 80) + 1;
    const dh = song.drums.length ? 40 : 0, rh = (H - dh - 6) / (hi - lo);
    g.strokeStyle = "rgba(120,160,180,.15)"; for (let b = 0; b <= song.bars; b++) { const x = b * 4 / beats * W; g.beginPath(); g.moveTo(x, 0); g.lineTo(x, H); g.stroke(); }
    song.tracks.forEach((tr, i) => { g.fillStyle = COLS[i % 3]; tr.notes.forEach(([b, d, m]) => g.fillRect(b / beats * W, (hi - m) * rh, Math.max(1.5, d / beats * W - 1), Math.max(2, rh - 0.5))); });
    if (dh) { const rows = { kick: 0, snare: 1, clap: 1, tom: 1, rim: 1, hat: 2, ohat: 2, ride: 2, crash: 3 }; g.fillStyle = "#ff5c7a"; song.drums.forEach(([b, k]) => g.fillRect(b / beats * W, H - dh + (rows[k] || 0) * 10, 2, 8)); }
    if (p >= 0) { g.fillStyle = "#fff"; g.fillRect(Math.min(W - 2, p * W), 0, 2, H); }
  }
  function wavBlob(buf) {
    const n = buf.length, ch = buf.numberOfChannels, sr = buf.sampleRate, out = new DataView(new ArrayBuffer(44 + n * ch * 2));
    const w = (o, s) => [...s].forEach((c, i) => out.setUint8(o + i, c.charCodeAt(0)));
    w(0, "RIFF"); out.setUint32(4, 36 + n * ch * 2, true); w(8, "WAVE"); w(12, "fmt "); out.setUint32(16, 16, true); out.setUint16(20, 1, true); out.setUint16(22, ch, true);
    out.setUint32(24, sr, true); out.setUint32(28, sr * ch * 2, true); out.setUint16(32, ch * 2, true); out.setUint16(34, 16, true); w(36, "data"); out.setUint32(40, n * ch * 2, true);
    const data = [...Array(ch)].map((_, k) => buf.getChannelData(k)); let o = 44;
    for (let i = 0; i < n; i++) for (let k = 0; k < ch; k++) { const s = Math.max(-1, Math.min(1, data[k][i])); out.setInt16(o, s < 0 ? s * 0x8000 : s * 0x7fff, true); o += 2; }
    return new Blob([out], { type: "audio/wav" });
  }
  async function exportWav() {
    if (!song) return; const b = $("#mu-wav", root); b.textContent = "HAZIRLANIYOR…";
    const dur = song.bars * 4 * 60 / song.bpm + 3, oc = new OfflineAudioContext(2, Math.ceil(44100 * dur), 44100);
    schedule(oc, song, 0.05); const buf = await oc.startRendering();
    const a = document.createElement("a"); a.href = URL.createObjectURL(wavBlob(buf)); a.download = (song.title || "jarvis").replace(/[^\wçğıöşü]+/gi, "_") + ".wav"; a.click();
    b.textContent = "⬇ WAV";
    return buf;
  }
  function build() {
    if (root) return; root = document.createElement("div"); root.id = "music"; root.className = "hidden";
    root.innerHTML = `<div class="mu-card"><div class="s-head"><span id="mu-title">MÜZİK STÜDYOSU</span><button class="mini" id="mu-x">KAPAT ✕</button></div>
      <div class="mu-info" id="mu-info"></div><canvas id="mu-roll" width="1000" height="260"></canvas>
      <div class="cam-row mu-row"><button class="btn-primary" id="mu-play">▶ ÇAL</button><button class="mini" id="mu-wav">⬇ WAV</button><a class="mini" id="mu-mid" download>⬇ MIDI</a>
        <select id="mu-style">${["lofi", "sinematik", "elektronik", "piyano", "ambient", "hiphop", "caz", "rock"].map((s) => `<option>${s}</option>`).join("")}</select>
        <select id="mu-mood"><option value="">ruh hali</option>${["neşeli", "hüzünlü", "karanlık", "sakin", "epik"].map((s) => `<option>${s}</option>`).join("")}</select>
        <input id="mu-bpm" type="number" placeholder="BPM" style="width:70px"><button class="mini" id="mu-new">🎲 YENİ BESTE</button><button class="mini" id="mu-drum">🥁 SADECE RİTİM</button></div>
      <div class="note">Mavi: akorlar · turuncu: bas · yeşil: melodi · kırmızı: davul. MIDI dosyasını FL Studio, Ableton, GarageBand ya da MuseScore'da açabilirsin.</div></div>`;
    document.body.append(root);
    $("#mu-x", root).onclick = () => { stop(); root.classList.add("hidden"); };
    $("#mu-play", root).onclick = () => (ctx ? stop() : play());
    $("#mu-wav", root).onclick = exportWav;
    const gen = async (parts) => { const r = await JV.api("/api/music", { body: { style: $("#mu-style", root).value, mood: $("#mu-mood", root).value, bpm: +$("#mu-bpm", root).value || 0, parts } }); if (r.song) { open(r); play(); } };
    $("#mu-new", root).onclick = () => gen("all"); $("#mu-drum", root).onclick = () => gen("drums");
  }
  function open(r) {
    build(); stop(); song = r.song; root.classList.remove("hidden");
    $("#mu-title", root).textContent = (song.title || "MÜZİK").toUpperCase();
    $("#mu-info", root).innerHTML = `Akorlar: <b>${esc((song.progression || []).join(" – "))}</b> · ${song.bars} ölçü · ${(song.bars * 4 * 60 / song.bpm).toFixed(1)} sn${song.swing > 0.5 ? " · swing" : ""}`;
    const m = $("#mu-mid", root); m.href = "/api/files/download?path=" + encodeURIComponent(r.midi || song.midi || "") + "&token=" + encodeURIComponent(JV.token || "");
    $("#mu-style", root).value = song.style; draw(-1);
  }
  JV.music = { open, play, stop, exportWav, _schedule: schedule, _wav: wavBlob };
  document.addEventListener("DOMContentLoaded", () => { const b = $("#t-music"); if (b) b.onclick = () => { build(); if (!song) $("#mu-new", root).click(); else root.classList.remove("hidden"); }; });
})();
