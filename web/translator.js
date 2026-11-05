/* Canlı tercüman: iki yönlü sesli çeviri (dil otomatik tanınır), bilgisayar sesini (görüntülü görüşme, video) yakalayıp çevirme,
   yazılı çeviri, büyük çift dilli altyazılar. Ses → /api/translate/audio (Whisper dil tanıma + model çevirisi) → seslendirme. */
(function () {
  const JV = (window.JV = window.JV || {});
  const $ = (s) => document.querySelector(s);
  const LANGS = { tr: "Türkçe", en: "İngilizce", de: "Almanca", fr: "Fransızca", es: "İspanyolca", it: "İtalyanca", ru: "Rusça", ar: "Arapça", zh: "Çince",
    ja: "Japonca", ko: "Korece", pt: "Portekizce", nl: "Felemenkçe", el: "Yunanca", fa: "Farsça", hi: "Hintçe", uk: "Ukraynaca", pl: "Lehçe", az: "Azerice",
    sv: "İsveççe", ro: "Romence", bg: "Bulgarca" };
  const SPEECH = { tr: "tr-TR", en: "en-US", de: "de-DE", fr: "fr-FR", es: "es-ES", it: "it-IT", ru: "ru-RU", ar: "ar-SA", zh: "zh-CN", ja: "ja-JP", ko: "ko-KR",
    pt: "pt-BR", nl: "nl-NL", el: "el-GR", fa: "fa-IR", hi: "hi-IN", uk: "uk-UA", pl: "pl-PL", az: "az-AZ", sv: "sv-SE", ro: "ro-RO", bg: "bg-BG" };
  let mic = null, sys = null, root = null;

  function build() {
    if (root) return root;
    root = document.createElement("div");
    root.id = "translator"; root.className = "hidden";
    const opts = Object.entries(LANGS).map(([k, v]) => `<option value="${k}">${v}</option>`).join("");
    root.innerHTML = `<div class="tr-card">
      <div class="s-head"><span>CANLI TERCÜMAN</span><button class="mini" id="tr-close">KAPAT ✕</button></div>
      <div class="tr-langs"><select id="tr-a">${opts}</select><button class="mini" id="tr-swap">⇄</button><select id="tr-b">${opts}</select></div>
      <div class="tr-big"><div id="tr-src" class="tr-src">Konuşmak için bir düğmeye bas. Dil otomatik tanınır.</div><div id="tr-dst" class="tr-dst"></div></div>
      <div class="cam-row tr-btns">
        <button class="btn-primary" id="tr-talk">🎤 KONUŞ (OTOMATİK)</button>
        <button class="mini" id="tr-cont">SÜREKLİ: KAPALI</button>
        <button class="mini" id="tr-sys">🖥 BİLGİSAYAR SESİNİ ÇEVİR</button>
        <button class="mini on" id="tr-voice">SESLENDİR: AÇIK</button>
      </div>
      <div class="cam-row"><input id="tr-text" placeholder="Yazıyla çevir (Enter)…"><button class="mini" id="tr-go">ÇEVİR</button></div>
      <div id="tr-log" class="tr-log"></div>
      <div class="note">İki kişi sırayla konuşur; JARVIS konuşulan dili tanır, öbür dile çevirip o dilin sesiyle okur. Görüntülü görüşmede “bilgisayar sesini çevir” → paylaşılan pencere/sekme için “sesi paylaş” işaretli olmalı. Groq anahtarı gerekir.</div>
    </div>`;
    document.body.append(root);
    $("#tr-a").value = "tr"; $("#tr-b").value = "en";
    $("#tr-close").onclick = close;
    $("#tr-swap").onclick = () => { const a = $("#tr-a").value; $("#tr-a").value = $("#tr-b").value; $("#tr-b").value = a; };
    $("#tr-talk").onclick = () => (mic ? mic.stop(true) : startMic());
    $("#tr-cont").onclick = (e) => { cont = !cont; e.target.textContent = "SÜREKLİ: " + (cont ? "AÇIK" : "KAPALI"); e.target.classList.toggle("on", cont); if (cont && !mic) startMic(); };
    $("#tr-voice").onclick = (e) => { speak = !speak; e.target.textContent = "SESLENDİR: " + (speak ? "AÇIK" : "KAPALI"); e.target.classList.toggle("on", speak); };
    $("#tr-sys").onclick = () => (sys ? stopSys() : startSys());
    $("#tr-go").onclick = textTranslate;
    $("#tr-text").addEventListener("keydown", (e) => { if (e.key === "Enter") textTranslate(); });
    return root;
  }
  let cont = false, speak = true;

  function show(src, srcLang, dst, dstLang, who) {
    $("#tr-src").textContent = src; $("#tr-dst").textContent = dst;
    $("#tr-src").dir = ["ar", "fa"].includes(srcLang) ? "rtl" : "ltr"; $("#tr-dst").dir = ["ar", "fa"].includes(dstLang) ? "rtl" : "ltr";
    const row = document.createElement("div"); row.className = "tr-row";
    row.innerHTML = `<b>${who || ""}${LANGS[srcLang] || srcLang || ""} → ${LANGS[dstLang] || dstLang}</b><div></div><div class="tr-d"></div>`;
    row.children[1].textContent = src; row.children[2].textContent = dst;
    $("#tr-log").prepend(row);
    while ($("#tr-log").children.length > 40) $("#tr-log").lastChild.remove();
  }

  async function postAudio(blob, target, other) {
    const r = await fetch(`/api/translate/audio?target=${target}&other=${other}`, { method: "POST", headers: { "x-token": JV.token || "", "Content-Type": blob.type || "audio/webm" }, body: blob });
    return r.json();
  }

  // Mikrofon: konuşma başlayınca kaydeder, ~1.2 sn sessizlikte keser (ses etkinliği algılama)
  async function startMic() {
    let stream;
    try { stream = await navigator.mediaDevices.getUserMedia({ audio: { echoCancellation: true, noiseSuppression: true } }); }
    catch (e) { JV.toast && JV.toast("Mikrofon izni yok."); return; }
    if (JV.speaking) JV.stopSpeaking(false);
    const ctx = new (window.AudioContext || window.webkitAudioContext)();
    const an = ctx.createAnalyser(); an.fftSize = 1024; ctx.createMediaStreamSource(stream).connect(an);
    const rec = new MediaRecorder(stream); const chunks = []; rec.ondataavailable = (e) => e.data.size && chunks.push(e.data);
    const buf = new Uint8Array(an.fftSize); let heard = false, quiet = 0, t0 = performance.now(), cancelled = false, iv;
    const btn = $("#tr-talk"); btn.classList.add("on"); btn.textContent = "● DİNLİYORUM… (bitir)";
    const finish = (manual) => { if (rec.state !== "inactive") rec.stop(); clearInterval(iv); stream.getTracks().forEach((t) => t.stop()); ctx.close(); };
    mic = { stop: (manual) => { if (manual && !heard) cancelled = true; if (manual) { cont = false; $("#tr-cont").textContent = "SÜREKLİ: KAPALI"; $("#tr-cont").classList.remove("on"); } finish(manual); } };
    iv = setInterval(() => {
      an.getByteTimeDomainData(buf); let s = 0; for (const v of buf) s += (v - 128) * (v - 128);
      const rms = Math.sqrt(s / buf.length);
      if (rms > 6) { heard = true; quiet = 0; } else if (heard) quiet += 50;
      if ((heard && quiet > 1200) || performance.now() - t0 > 30000) finish(false);
      if (!heard && performance.now() - t0 > 12000) { cancelled = true; finish(false); }
    }, 50);
    rec.onstop = async () => {
      mic = null; btn.classList.remove("on"); btn.textContent = "🎤 KONUŞ (OTOMATİK)";
      if (cancelled || !chunks.length) { if (cont && !cancelled) startMic(); return; }
      $("#tr-src").textContent = "çevriliyor…";
      try {
        const a = $("#tr-a").value, b = $("#tr-b").value;
        const r = await postAudio(new Blob(chunks, { type: rec.mimeType || "audio/webm" }), b, a);
        if (r.error) { $("#tr-src").textContent = r.error; return; }
        if (r.metin) {
          show(r.metin, r.dil, r.çeviri, r.hedef);
          if (speak && r.çeviri) await sayWait(r.çeviri, r.hedef);
        }
      } catch (e) { $("#tr-src").textContent = "Çeviri hatası: " + e.message; }
      if (cont && root && !root.classList.contains("hidden")) startMic();
    };
    rec.start(250);
  }

  function sayWait(text, lang) {
    return new Promise((res) => {
      const prev = JV.onSpeechEnd; let done = false;
      const end = () => { if (done) return; done = true; JV.onSpeechEnd = prev; res(); };
      JV.onSpeechEnd = () => { prev && prev(); end(); };
      JV.say(text, JV.persona ? JV.persona() : "jarvis", lang);
      setTimeout(() => { if (!JV.speaking) end(); }, 1500);
      setTimeout(end, 30000);
    });
  }

  // Bilgisayar sesi (görüntülü görüşme / video): ekran paylaşımı sesinden 6 sn'lik parçalar → A diline çeviri altyazısı
  async function startSys() {
    let st;
    try { st = await navigator.mediaDevices.getDisplayMedia({ video: true, audio: true }); }
    catch (e) { JV.toast && JV.toast("Ekran/ses paylaşımı reddedildi."); return; }
    const at = st.getAudioTracks();
    if (!at.length) { st.getTracks().forEach((t) => t.stop()); JV.toast && JV.toast("Ses paylaşılmadı: paylaşırken 'sesi de paylaş' kutusunu işaretle."); return; }
    const astream = new MediaStream(at); let stopped = false;
    const btn = $("#tr-sys"); btn.classList.add("on"); btn.textContent = "■ BİLGİSAYAR SESİ ÇEVRİLİYOR";
    sys = { stop() { stopped = true; st.getTracks().forEach((t) => t.stop()); } };
    at[0].onended = stopSys;
    const cycle = () => {
      if (stopped) return;
      const rec = new MediaRecorder(astream); const ch = [];
      rec.ondataavailable = (e) => e.data.size && ch.push(e.data);
      rec.onstop = async () => {
        cycle();
        const blob = new Blob(ch, { type: rec.mimeType || "audio/webm" });
        if (blob.size < 4000) return;
        try {
          const a = $("#tr-a").value;
          const r = await postAudio(blob, a, a);
          if (r.metin && r.metin.trim().length > 1 && r.dil !== a) {
            show(r.metin, r.dil, r.çeviri, r.hedef, "🖥 ");
            if (speak) JV.say(r.çeviri, JV.persona ? JV.persona() : "jarvis", a);
          }
        } catch (e) {}
      };
      rec.start(); setTimeout(() => rec.state !== "inactive" && rec.stop(), 6000);
    };
    cycle();
  }
  function stopSys() { if (sys) sys.stop(); sys = null; const b = $("#tr-sys"); if (b) { b.classList.remove("on"); b.textContent = "🖥 BİLGİSAYAR SESİNİ ÇEVİR"; } }

  async function textTranslate() {
    const t = $("#tr-text").value.trim(); if (!t) return;
    const b = $("#tr-b").value; $("#tr-dst").textContent = "çevriliyor…";
    const r = await JV.api("/api/translate", { body: { text: t, target: b } });
    if (r.error) { $("#tr-dst").textContent = r.error; return; }
    show(t, "", r.çeviri, b); $("#tr-text").value = "";
    if (speak) JV.say(r.çeviri, JV.persona ? JV.persona() : "jarvis", b);
  }

  function open(r) {
    build(); root.classList.remove("hidden");
    if (r && r.a && LANGS[r.a]) $("#tr-a").value = r.a;
    if (r && r.b && LANGS[r.b]) $("#tr-b").value = r.b;
  }
  function close() { if (mic) mic.stop(true); stopSys(); root && root.classList.add("hidden"); }
  JV.translator = { open, close, LANGS, SPEECH, isOpen: () => !!root && !root.classList.contains("hidden") };

  document.addEventListener("DOMContentLoaded", () => {
    const b = $("#t-translate"); if (b) b.onclick = () => (JV.translator.isOpen() ? close() : open());
    const c = $("#cam-trans");
    if (c) c.onclick = async () => {
      const v = $("#cam-video"); if (!v || !v.videoWidth) return;
      const cv = document.createElement("canvas"); const w = Math.min(1600, v.videoWidth);
      cv.width = w; cv.height = Math.round(v.videoHeight * w / v.videoWidth); cv.getContext("2d").drawImage(v, 0, 0, cv.width, cv.height);
      const to = (root && $("#tr-a").value) || "tr";
      $("#cam-info").textContent = "Yazılar okunuyor ve çevriliyor…";
      const q = `Görüntüdeki TÜM yazıları (tabela, menü, etiket, belge) oku. Her biri için önce orijinal metni, sonra "→" ile ${LANGS[to]} çevirisini yaz. Yazı yoksa "Yazı görmüyorum" de.`;
      try {
        const r = await JV.api("/api/vision", { body: { image: cv.toDataURL("image/jpeg", 0.9), question: q, persona: JV.persona ? JV.persona() : "jarvis", session: "main" } });
        const t = r.text || r.error || "Okunamadı.";
        $("#cam-info").textContent = t; JV.say(t.split("\n").map((l) => l.split("→").pop()).join(". "), JV.persona ? JV.persona() : "jarvis", to);
      } catch (e) { $("#cam-info").textContent = "Hata: " + e.message; }
    };
  });
})();
