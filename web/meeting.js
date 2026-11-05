/* TOPLANTI ASİSTANI — "toplantıyı kaydet": mikrofon ~15 sn'lik parçalar halinde yazıya dökülür (canlı altyazı),
   bitince özet, konular, kararlar, yapılacaklar çıkarılır; Belgeler/JARVIS toplantıları'na .md kaydedilir, yapılacaklar listeye eklenir.
   Sessiz parçalar gönderilmez. Kayıt sesi saklanmaz; yalnızca yazı tutulur. */
(function () {
  const JV = (window.JV = window.JV || {});
  const $ = (s, r = document) => r.querySelector(s);
  const esc = (s) => String(s == null ? "" : s).replace(/[&<>"]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]));
  let el, stream, ctx, proc, buf = [], rate = 48000, t0 = 0, iv = 0, flushIv = 0, paused = false, lines = [], pending = 0, title = "", peak = 0;
  function build() {
    if (el) return;
    el = document.createElement("div"); el.id = "meetpanel"; el.className = "hidden";
    el.innerHTML = `<div class="mt-top"><b>🎙 TOPLANTI</b><span id="mt-rec">● KAYIT</span><span id="mt-time">00:00</span><input id="mt-title" placeholder="Toplantı adı">
      <button class="mini" id="mt-pause">⏸</button><button class="btn-primary" id="mt-stop">■ BİTİR VE ÖZETLE</button><button class="mini" id="mt-x">✕</button></div>
      <div id="mt-live"></div><div id="mt-sum" class="hidden"></div>`;
    document.body.append(el);
    $("#mt-pause", el).onclick = () => { paused = !paused; $("#mt-pause", el).textContent = paused ? "▶" : "⏸"; $("#mt-rec", el).textContent = paused ? "⏸ DURAKLADI" : "● KAYIT"; };
    $("#mt-stop", el).onclick = finish;
    $("#mt-x", el).onclick = () => { stopRec(); el.classList.add("hidden"); };
  }
  async function start(t = "") {
    build(); el.classList.remove("hidden"); $("#mt-sum", el).classList.add("hidden"); $("#mt-live", el).innerHTML = ""; lines = []; title = t; $("#mt-title", el).value = t;
    try { stream = await navigator.mediaDevices.getUserMedia({ audio: { echoCancellation: true, noiseSuppression: true, autoGainControl: true, ...(JV.settings && JV.settings.mic_id ? { deviceId: JV.settings.mic_id } : {}) } }); }
    catch (e) { $("#mt-live", el).textContent = "Mikrofon açılamadı: " + e.message; return; }
    ctx = new (window.AudioContext || window.webkitAudioContext)(); rate = ctx.sampleRate;
    const src = ctx.createMediaStreamSource(stream); proc = ctx.createScriptProcessor(4096, 1, 1); const g = ctx.createGain(); g.gain.value = 0;
    src.connect(proc); proc.connect(g); g.connect(ctx.destination);
    proc.onaudioprocess = (e) => { if (paused) return; const x = e.inputBuffer.getChannelData(0); buf.push(new Float32Array(x)); for (let i = 0; i < x.length; i += 64) peak = Math.max(peak, Math.abs(x[i])); };
    t0 = Date.now(); paused = false;
    iv = setInterval(() => { const s = Math.floor((Date.now() - t0) / 1000); $("#mt-time", el).textContent = `${String(Math.floor(s / 60)).padStart(2, "0")}:${String(s % 60).padStart(2, "0")}${pending ? " · yazıya dökülüyor…" : ""}`; }, 1000);
    flushIv = setInterval(flush, 15000);
    JV.toast && JV.toast("🎙 Toplantı kaydı başladı. Bitince ■ BİTİR'e bas.", 5000);
  }
  async function flush() {
    if (!buf.length) return;
    const chunks = buf; buf = []; const pk = peak; peak = 0;
    if (pk < 0.02) return; // sessiz parça: gönderme
    const { blob } = JV.wav(chunks, rate);
    pending++;
    try {
      const r = await (await fetch("/api/life/meeting_chunk", { method: "POST", headers: { "x-token": JV.token || "", "Content-Type": "audio/wav" }, body: blob })).json();
      if (r.text) { const t = new Date(t0 + (lines.length ? 0 : 0)); lines.push(r.text); const p = document.createElement("p"); p.innerHTML = `<i>${new Date().toLocaleTimeString("tr-TR", { hour: "2-digit", minute: "2-digit" })}</i> ${esc(r.text)}`; $("#mt-live", el).append(p); p.scrollIntoView({ block: "end" }); }
      else if (r.error) { const p = document.createElement("p"); p.className = "dim"; p.textContent = "⚠ " + r.error; $("#mt-live", el).append(p); }
    } catch (e) {}
    pending--;
  }
  function stopRec() { clearInterval(iv); clearInterval(flushIv); if (proc) proc.disconnect(); if (stream) stream.getTracks().forEach((t) => t.stop()); if (ctx) ctx.close().catch(() => {}); stream = null; ctx = null; proc = null; }
  async function finish() {
    await flush(); stopRec();
    for (let i = 0; i < 40 && pending; i++) await new Promise((r) => setTimeout(r, 500));
    const s = $("#mt-sum", el); s.classList.remove("hidden"); s.innerHTML = "<p class='h3-load'>özet çıkarılıyor…</p>";
    const tr = lines.join("\n");
    if (tr.length < 20) { s.innerHTML = "<p>Yazıya dökülecek konuşma olmadı.</p>"; return; }
    try {
      const r = await (await fetch("/api/life/meeting_finish", { method: "POST", headers: { "x-token": JV.token || "", "Content-Type": "application/json" }, body: JSON.stringify({ transcript: tr, title: $("#mt-title", el).value.trim() }) })).json();
      if (r.error) { s.innerHTML = `<p>${esc(r.error)}</p>`; return; }
      const li = (a) => (a || []).map((x) => `<li>${esc(typeof x === "string" ? x : x.iş + (x.kim ? " — " + x.kim : "") + (x.tarih ? " (" + x.tarih + ")" : ""))}</li>`).join("");
      s.innerHTML = `<h3>${esc(r.başlık)}</h3><p>${esc(r.özet)}</p>${r.kararlar && r.kararlar.length ? `<h5>KARARLAR</h5><ul>${li(r.kararlar)}</ul>` : ""}${r.yapılacaklar && r.yapılacaklar.length ? `<h5>YAPILACAKLAR (${r.eklenen_iş} iş listene eklendi)</h5><ul>${li(r.yapılacaklar)}</ul>` : ""}${r.açık_sorular && r.açık_sorular.length ? `<h5>AÇIK SORULAR</h5><ul>${li(r.açık_sorular)}</ul>` : ""}<p class="note">Kaydedildi: ${esc(r.dosya)}</p>`;
      JV.say && JV.say(`Toplantı özeti hazır. ${r.özet || ""}`.slice(0, 600), JV.currentPersona && JV.currentPersona());
    } catch (e) { s.innerHTML = `<p>Hata: ${esc(e.message)}</p>`; }
  }
  JV.meeting = { start, finish, cmd: (r) => (r.action === "stop" ? finish() : start(r.title || "")), _lines: () => lines, get active() { return !!stream; } };
})();
