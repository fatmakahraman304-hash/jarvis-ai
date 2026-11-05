/* Arayüz beyni: sohbet akışı, konuşma tanıma, uyandırma kelimesi, paneller, ayarlar. */
(function () {
  const JV = (window.JV = window.JV || {});
  const $ = (s) => document.querySelector(s);
  const el = (tag, cls, txt) => { const e = document.createElement(tag); if (cls) e.className = cls; if (txt != null) e.textContent = txt; return e; };

  // ---------- erişim anahtarı (telefon) ----------
  const qs = new URLSearchParams(location.search);
  if (qs.get("token")) { try { localStorage.setItem("jv_token", qs.get("token")); } catch (e) {} history.replaceState(null, "", location.pathname); }
  let token = ""; try { token = localStorage.getItem("jv_token") || ""; } catch (e) {}
  JV.token = token;
  const isPhone = /Android|iPhone|iPad|Mobile/i.test(navigator.userAgent);

  JV.api = async function (url, opt = {}) {
    const headers = Object.assign({ "x-token": token }, opt.body ? { "Content-Type": "application/json" } : {});
    const r = await fetch(url, { method: opt.method || (opt.body ? "POST" : "GET"), headers, body: opt.body ? JSON.stringify(opt.body) : undefined, signal: opt.signal });
    if (opt.raw) return r;
    if (r.status === 401) { toast("Erişim anahtarı gerekli: bilgisayardaki adresi ?token=… ile aç."); throw new Error("401"); }
    return r.json();
  };

  JV.state = { personas: [], providers: [], tts: false };
  JV.settings = { voice_enabled: true, effects: true, persona: "jarvis", visual: "sphere" };
  let persona = "jarvis";
  let busy = false;
  let abortCtl = null;

  // ---------- yardımcılar ----------
  function setStatus(s, text) {
    document.body.classList.remove("listening", "thinking");
    if (s) document.body.classList.add(s);
    $("#status-text").textContent = text || (s === "listening" ? "DİNLİYOR" : s === "thinking" ? "İŞLENİYOR" : "BEKLEMEDE");
  }
  JV.toast = (t, ms) => toast(t, ms);
  JV.sendCommand = (t) => send(t);
  JV.currentPersona = () => persona;
  JV.persona = () => persona;
  JV.openPanel = (name, open = true) => {
    const n = (name || "").toLowerCase();
    if (/sistem|system/.test(n)) document.body.classList.toggle("hide-left", !open);
    else if (/ayar|settings/.test(n)) open ? openSettings() : $("#settings").classList.add("hidden");
    else if (/kamera|camera/.test(n)) open ? $("#t-camera").click() : $("#cam-close").click();
    else if (/el|gesture|hareket/.test(n)) open ? JV.gesture.start() : JV.gesture.stop();
    else if (/klavye|keyboard/.test(n)) { JV.gesture.start("klavye"); }
    else if (/görev|task/.test(n)) { openSettings(); setTimeout(() => document.querySelector('.s-tabs button[data-tab=tasks]').click(), 300); }
    else if (/dosya|files/.test(n)) { openSettings(); setTimeout(() => document.querySelector('.s-tabs button[data-tab=files]') && document.querySelector('.s-tabs button[data-tab=files]').click(), 300); }
  };
  function toast(t, ms = 5000) { const d = el("div", "toast", t); $("#toasts").append(d); setTimeout(() => d.remove(), ms); }
  function P(id) { return JV.state.personas.find((p) => p.id === id) || { id, name: id.toUpperCase(), color: "#38d6ff", color2: "#0a6cff", full: "" }; }
  function scrollLog() { const l = $("#log"); l.scrollTop = l.scrollHeight; }
  function addMsg(role, text, pid, who) {
    const m = el("div", "msg " + role);
    if (role === "ai") { m.style.setProperty("--mc", P(pid).color); m.append(el("div", "who", P(pid).name)); }
    if (role === "user") m.append(el("div", "who", who ? who.toUpperCase() : "SEN"));
    const body = el("div", "body", text); m.append(body);
    $("#log").append(m); scrollLog();
    return body;
  }
  let capTimer = null;
  JV.onCaption = (t) => { $("#live-caption").textContent = t; clearTimeout(capTimer); };
  JV.onSpeechEnd = () => { capTimer = setTimeout(() => ($("#live-caption").textContent = ""), 2500); if (!busy) setStatus(recognizing ? "listening" : null); };

  // ---------- kişilik ----------
  function applyPersona(id, speak) {
    persona = id; const p = P(id);
    document.documentElement.style.setProperty("--c", p.color);
    document.documentElement.style.setProperty("--c2", p.color2);
    $("#p-name").textContent = p.name; $("#p-full").textContent = p.full;
    document.title = p.name;
    document.querySelectorAll("#personas button").forEach((b) => b.classList.toggle("active", b.dataset.id === id));
    JV.setColor(p.color);
    if (speak) { JV.stopSpeaking(); addMsg("ai", p.greeting, id); JV.say(p.greeting, id); }
  }
  function renderPersonas() {
    const nav = $("#personas"); nav.innerHTML = "";
    JV.state.personas.forEach((p) => {
      const b = el("button", "", p.id.toUpperCase()); b.dataset.id = p.id; b.style.setProperty("--pc", p.color);
      b.onclick = () => { if (p.id === persona) return; applyPersona(p.id, true); saveSettings({ persona: p.id }); };
      nav.append(b);
    });
  }

  async function saveSettings(patch) { JV.settings = await JV.api("/api/settings", { body: patch }); return JV.settings; }
  JV.saveSettings = saveSettings;

  // ---------- sohbet ----------
  async function send(text, opts = {}) {
    text = (text || "").trim();
    if (!text) return;
    if (busy && abortCtl) abortCtl.abort();
    JV.stopSpeaking(false);
    busy = true; setStatus("thinking");
    if (!opts.hidden) addMsg("user", text, null, opts.speaker);
    const body = addMsg("ai", "", persona);
    const sent = JV.Sentencer(persona);
    abortCtl = new AbortController();
    const url = opts.confirm ? "/api/confirm" : "/api/chat";
    const payload = opts.confirm ? opts.confirm : { text, persona, session: opts.guest ? "guest" : "main", source: isPhone ? "phone" : "web", speaker: opts.speaker || "", guest: !!opts.guest };
    try {
      const r = await JV.api(url, { body: payload, raw: true, signal: abortCtl.signal });
      if (r.status === 401) { body.textContent = "Erişim anahtarı gerekli."; return; }
      const reader = r.body.getReader(); const dec = new TextDecoder(); let buf = "";
      while (true) {
        const { value, done } = await reader.read(); if (done) break;
        buf += dec.decode(value, { stream: true });
        let i;
        while ((i = buf.indexOf("\n\n")) >= 0) {
          const line = buf.slice(0, i); buf = buf.slice(i + 2);
          if (!line.startsWith("data:")) continue;
          handleEvent(JSON.parse(line.slice(5)), body, sent);
        }
      }
    } catch (e) {
      if (e.name !== "AbortError") { body.parentElement.classList.add("err"); body.textContent = "Bağlantı hatası: " + e.message; }
    } finally {
      sent.flush(); busy = false;
      if (!JV.speaking) setStatus(recognizing ? "listening" : null);
      if (!body.textContent) body.parentElement.remove();
    }
  }

  function handleEvent(ev, body, sent) {
    switch (ev.type) {
      case "provider": $("#model-badge").textContent = `MODEL: ${ev.label} · ${ev.model}`; setStatus("thinking", "DÜŞÜNÜYOR · " + ev.model); break;
      case "token": body.textContent += ev.text; sent.push(ev.text); scrollLog(); break;
      case "tool":
        if (ev.status === "running") {
          const t = el("div", "msg tool", `⚙ ${ev.name} …`); body.parentElement.before(t); scrollLog();
          const nice = { web_search: "İNTERNETTE ARIYOR", news_search: "HABERLERE BAKIYOR", read_webpage: "SAYFAYI OKUYOR", weather: "HAVA DURUMUNA BAKIYOR" }[ev.name];
          setStatus("thinking", nice || ("ÇALIŞIYOR: " + ev.name));
        }
        if (ev.status === "done" && ev.result && ev.result.startsWith("{") && ev.result.includes('"ui"') && JV.uiCommand) { try { JV.uiCommand(ev.name, ev.args, ev.result); } catch (e) { console.warn(e); } }
        break;
      case "confirm": showConfirm(ev); break;
      case "error": body.parentElement.classList.add("err"); if (!body.textContent) { body.textContent = ev.text; JV.say(ev.text, persona); } break;
      case "done": break;
    }
  }

  function showConfirm(ev) {
    if (document.querySelector(`.confirm[data-id="${ev.id}"]`)) return;
    const c = el("div", "confirm"); c.dataset.id = ev.id;
    c.append(el("div", "t", "⚠ KRİTİK İŞLEM — ONAY GEREKİYOR"), el("code", "", ev.text));
    const ok = el("button", "btn-danger", "ONAYLA"), no = el("button", "mini", "REDDET");
    ok.onclick = () => { c.remove(); send("onay", { hidden: true, confirm: { id: ev.id, approve: true } }); };
    no.onclick = () => { c.remove(); send("ret", { hidden: true, confirm: { id: ev.id, approve: false } }); };
    c.append(ok, no); $("#confirms").append(c);
  }

  $("#ask").addEventListener("submit", (e) => { e.preventDefault(); const q = $("#q"); send(q.value); q.value = ""; });
  $("#clear-btn").onclick = async () => { await JV.api("/api/history?session=main", { method: "DELETE" }); $("#log").innerHTML = ""; };

  // ---------- konuşma tanıma ----------
  const SR = window.SpeechRecognition || window.webkitSpeechRecognition;
  let rec = null, recognizing = false, wakeMode = false, awaitingCmd = 0, oneShot = false;
  const WAKE = {
    jarvis: ["jarvis", "carvis", "cervis", "jarvıs", "çarvis", "jarviz", "jervis", "jarvis'", "javis"],
    friday: ["friday", "fraydey", "fraydi", "frayday", "fırayday", "fridey"],
    ultron: ["ultron", "altron", "ültron", "ultran", "oltron"],
  };
  const STOP = ["dur", "sus", "yeter", "stop", "kes"];
  async function guardedSend(text) {
    const low = text.toLowerCase().trim();
    if (/acil (dur|durdur|stop)/.test(low)) { estop(); return; }
    if (JV.hasInterrupted() && /^(devam|devam et|kaldığın yerden|sürdür|continue)/.test(low)) { JV.resumeSpeaking(); return; }
    const cards = [...document.querySelectorAll(".confirm")];
    const useId = JV.settings.voice_id || JV.settings.voice_lock;
    const who = useId ? await JV.voiceId.identify(3.5) : null;
    if (cards.length && /(onayla|onaylıyorum|onay ver|reddet|iptal et)/.test(low)) {
      if (useId && !(who && who.owner)) { toast("Kritik işlemi sesle onaylamak için sahibinin sesi gerekli."); JV.say("Bu onayı sadece sahibim verebilir.", persona); return; }
      const card = cards[cards.length - 1];
      (/(reddet|iptal)/.test(low) ? card.querySelector(".mini") : card.querySelector(".btn-danger")).click();
      return;
    }
    const noProfiles = !!(who && who.no_profiles); // henüz kimse tanıtılmadıysa herkes "sahip" sayılır
    if (noProfiles && !JV._vidHint) { JV._vidHint = true; toast("Ses tanıma açık ama kayıtlı ses yok: Ayarlar > SES > SESİMİ TANIT ile sesini tanıt.", 9000); }
    if (JV.settings.voice_lock && who && !who.known && !noProfiles) { toast("Ses tanınmadı, komut yok sayıldı."); JV.say("Sesinizi tanımadım.", persona); return; }
    const guest = !!(who && !who.known && !noProfiles && JV.settings.voice_id); // tanınmayan ses → misafir modu
    if (guest) toast("Tanınmayan ses: misafir modunda cevap veriliyor.");
    send(text, { speaker: who && who.known ? who.name : guest ? "Misafir" : "", guest });
  }
  function findWake(text) {
    const t = text.toLowerCase();
    for (const [pid, words] of Object.entries(WAKE)) for (const w of words) {
      const i = t.indexOf(w);
      if (i >= 0) return { pid, rest: text.slice(i + w.length).replace(/^[\s,.!?:'’]+/, "").trim() };
    }
    return null;
  }

  function startRec(single) {
    if (!SR) { if (single) recordFallback(); else toast("Sürekli dinleme için Edge veya Chrome gerekli; mikrofon düğmesi bu tarayıcıda kayıt moduyla çalışır."); return; }
    oneShot = !!single;
    if (JV.settings.voice_id || JV.settings.voice_lock) JV.voiceId.start();
    if (rec) { try { rec.abort(); } catch (e) {} }
    rec = new SR();
    rec.lang = (JV.settings.stt_lang) || "tr-TR";
    rec.continuous = !single; rec.interimResults = true;
    rec.onstart = () => { recognizing = true; if (!busy && !JV.speaking) setStatus("listening"); };
    rec.onerror = (e) => { if (e.error === "not-allowed") { toast("Mikrofon izni verilmedi."); wakeMode = false; updateToggles(); } };
    rec.onend = () => { recognizing = false; if (!busy && !JV.speaking) setStatus(null); if (wakeMode && !oneShot) setTimeout(() => startRec(false), 250); };
    rec.onresult = (e) => {
      let interim = "", final = "";
      for (let i = e.resultIndex; i < e.results.length; i++) { const r = e.results[i]; (r.isFinal ? (final += r[0].transcript) : (interim += r[0].transcript)); }
      const heard = (final || interim).trim();
      if (!heard) return;
      // konuşurken araya girme: uyandırma kelimesi veya "dur"
      if (JV.speaking && (findWake(heard) || STOP.some((s) => heard.toLowerCase().split(/\s+/).includes(s)))) JV.stopSpeaking();
      if (oneShot) { $("#q").value = heard; if (final) { $("#q").value = ""; guardedSend(final); } return; }
      if (!final) return;
      const w = findWake(final);
      if (w) {
        if (w.pid !== persona) { applyPersona(w.pid, false); saveSettings({ persona: w.pid }); }
        if (w.rest.length > 2) guardedSend(w.rest);
        else if (JV.stt && JV.stt.available()) { JV.beep(); whisperOnce(); }
        else { JV.beep(); awaitingCmd = Date.now() + 8000; setStatus("listening", "SİZİ DİNLİYORUM"); }
      } else if (awaitingCmd > Date.now() || ([...document.querySelectorAll(".confirm")].length && /(onayla|reddet)/i.test(final))) { awaitingCmd = 0; guardedSend(final); }
    };
    try { rec.start(); } catch (e) {}
  }
  function stopRec() { wakeMode = false; if (rec) { try { rec.abort(); } catch (e) {} } recognizing = false; setStatus(null); }

  // Web Speech yoksa (Firefox, bazı telefonlar): sesi kaydet → sunucuda Whisper ile yazıya çevir
  let mediaRec = null, chunks = [];
  async function recordFallback() {
    if (mediaRec && mediaRec.state === "recording") { mediaRec.stop(); return; }
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      mediaRec = new MediaRecorder(stream); chunks = [];
      mediaRec.ondataavailable = (e) => chunks.push(e.data);
      mediaRec.onstop = async () => {
        stream.getTracks().forEach((t) => t.stop());
        setStatus("thinking", "YAZIYA ÇEVRİLİYOR");
        const blob = new Blob(chunks, { type: mediaRec.mimeType || "audio/webm" });
        const r = await fetch("/api/transcribe?lang=" + ((JV.settings.stt_lang || "tr").slice(0, 2)), { method: "POST", headers: { "x-token": token, "Content-Type": blob.type }, body: blob });
        const j = await r.json(); setStatus(null);
        if (j.text) send(j.text); else toast(j.error || "Anlaşılamadı");
      };
      mediaRec.start(); setStatus("listening", "KAYDEDİYOR — bitirmek için tekrar bas");
      setTimeout(() => mediaRec && mediaRec.state === "recording" && mediaRec.stop(), 30000);
    } catch (e) { toast("Mikrofon açılamadı: " + e.message); }
  }
  // Whisper ile tek komut dinle (Groq anahtarı varsa varsayılan: çok daha doğru tanıma)
  function whisperOnce() {
    if (JV.settings.voice_id || JV.settings.voice_lock) JV.voiceId.start();
    let lastBar = 0;
    JV.stt.record({
      onStart: () => setStatus("listening", "DİNLİYORUM — bitince kendiliğinden gönderilir"),
      onLevel: (v, voice) => {
        const now = performance.now(); if (now - lastBar < 120) return; lastBar = now;
        const k = Math.round(v * 10); setStatus("listening", "DİNLİYORUM " + "▮".repeat(k) + "▯".repeat(10 - k) + (voice ? "  🎙 ses var" : ""));
      },
      onText: (t, info = {}) => {
        setStatus(null);
        if (t) { guardedSend(t); return; }
        if (info.reason === "sessiz") toast(info.level < 0.004 ? "Mikrofondan hiç ses gelmiyor. Ayarlar > SES > Mikrofon'dan doğru mikrofonu seç ya da Windows'ta mikrofon sesini aç." : "Konuşma duyulmadı. Biraz daha yüksek/yakından konuş; Ayarlar > SES > MİKROFON TESTİ ile deneyebilirsin.", 9000);
        else if (info.reason === "anlaşılmadı") toast("Ses geldi ama ne dediğin anlaşılamadı, tekrar söyler misin?", 6000);
      },
      onError: (e) => { setStatus(null); toast("Konuşma tanınamadı: " + e, 9000); },
    });
  }
  JV.whisperOnce = whisperOnce;
  $("#mic").onclick = () => {
    JV.unlockAudio();
    if (JV.speaking) JV.stopSpeaking();
    if (JV.stt && JV.stt.available()) { if (JV.stt.busy()) JV.stt.stop(); else whisperOnce(); return; }
    if (!SR) { recordFallback(); return; }
    if (recognizing && oneShot) { try { rec.stop(); } catch (e) {} return; }
    startRec(true);
  };
  addEventListener("keydown", (e) => {
    if (e.target.tagName === "INPUT" || e.target.tagName === "SELECT") return;
    if (e.code === "Space") { e.preventDefault(); $("#mic").click(); }
    if (e.code === "Escape") JV.stopSpeaking();
  });

  // ---------- düğmeler ----------
  function updateToggles() {
    $("#t-visual").textContent = JV.settings.visual === "face" ? "☺ YÜZ" : "◉ KÜRE";
    $("#t-visual").classList.add("on");
    $("#t-voice").classList.toggle("on", !!JV.settings.voice_enabled);
    $("#t-wake").classList.toggle("on", wakeMode);
  }
  $("#t-visual").onclick = async () => { const v = JV.settings.visual === "face" ? "sphere" : "face"; JV.settings.visual = v; JV.setVisual(v); updateToggles(); saveSettings({ visual: v }); };
  $("#t-voice").onclick = async () => { JV.settings.voice_enabled = !JV.settings.voice_enabled; if (!JV.settings.voice_enabled) JV.stopSpeaking(); updateToggles(); saveSettings({ voice_enabled: JV.settings.voice_enabled }); };
  $("#t-wake").onclick = () => {
    JV.unlockAudio();
    if (wakeMode) { stopRec(); saveSettings({ wake_word: false }); }
    else { wakeMode = true; startRec(false); toast('Uyandırma açık: "JARVIS …", "FRIDAY …" veya "ULTRON …" de.'); saveSettings({ wake_word: true }); }
    updateToggles();
  };

  // ---------- sistem paneli ----------
  function gauge(k, v) {
    const g = document.querySelector(`.gauge[data-k=${k}]`); if (!g || v == null) return;
    g.querySelector("b").textContent = Math.round(v) + "%";
    g.querySelector(".g-fg").style.strokeDashoffset = 264 - (264 * Math.min(100, v)) / 100;
    g.querySelector(".g-fg").style.stroke = v > 85 ? "#ff4d4d" : "";
  }
  async function pollSystem() {
    try {
      const s = await JV.api("/api/system");
      gauge("cpu", s["cpu_yüzde"]); gauge("ram", s["ram_yüzde"]); gauge("disk", s["disk_yüzde"]);
      const kv = $("#sysinfo"); kv.innerHTML = "";
      [["OS", s["işletim_sistemi"]], ["RAM", (s["ram_gb"] || "") + " GB"], ["PİL", s["pil"] || "—"], ["UPTIME", s["açık_kalma"]]].forEach(([k, v]) => { kv.append(el("i", "", k), el("span", "", v || "—")); });
    } catch (e) {}
  }
  async function pollProcs() {
    try {
      const ps = await JV.api("/api/processes");
      const ul = $("#procs"); ul.innerHTML = "";
      (Array.isArray(ps) ? ps : []).slice(0, 7).forEach((p) => { const li = el("li"); li.append(el("span", "", p.ad), el("span", "", p.ram_mb + " MB")); ul.append(li); });
    } catch (e) {}
  }
  let lastNote = 0;
  async function pollNotes() {
    try {
      const ns = await JV.api("/api/notifications?since=" + lastNote);
      let needPending = false;
      ns.forEach((n) => {
        lastNote = Math.max(lastNote, n.id);
        if (n.kind === "mode") { if (JV.applyMode && document.body.classList.contains("mode-" + n.text) === false) JV.applyMode(n.text); return; }
        toast((n.kind === "reminder" ? "⏰ " : n.kind === "error" ? "⚠ " : "🔔 ") + n.text, 12000);
        addMsg("ai", n.text, persona);
        if (n.kind === "confirm") needPending = true;
        else if (n.kind === "alarm") ringAlarm(n.text);
        else if (!JV.quiet || ["error", "security", "confirm"].includes(n.kind)) JV.say(n.text.replace(/\(Onay kodu \w+\)/, ""), persona, undefined, true);
      });
      if (needPending) { const st = await JV.api("/api/state"); (st.pending || []).forEach((p) => showConfirm({ id: p.id, text: `${p.name}(${JSON.stringify(p.args)})` })); JV.say("Bir görev onayınızı bekliyor.", persona); }
    } catch (e) {}
  }
  setInterval(() => ($("#clock").textContent = new Date().toLocaleTimeString("tr-TR", { hour: "2-digit", minute: "2-digit" })), 1000);

  function renderProvMini() {
    const ul = $("#prov-mini"); ul.innerHTML = "";
    const g = JV.state.google || {};
    const gl = el("li"); gl.append(el("span", "", "Gmail + Takvim"), el("span", g.connected ? "on" : "off", g.connected ? "● BAĞLI" : "○ yok")); ul.append(gl);
    JV.state.providers.filter((p) => (p.id !== "custom" || p.configured) && !p.disabled).forEach((p) => {
      const li = el("li"); li.append(el("span", "", p.label.split(" (")[0]), el("span", p.key_error ? "bad" : p.configured ? "on" : "off", p.key_error ? "✗ ANAHTAR" : p.configured ? "● AKTİF" : "○ yok")); ul.append(li);
    });
  }

  // ---------- ayarlar ----------
  const KEY_LINKS = {
    gemini: "https://aistudio.google.com/apikey", groq: "https://console.groq.com/keys",
    openrouter: "https://openrouter.ai/keys", xai: "https://console.x.ai", mistral: "https://console.mistral.ai/api-keys",
    cerebras: "https://cloud.cerebras.ai", ollama: "https://ollama.com/download",
  };
  $("#t-settings").onclick = openSettings;
  $("#s-close").onclick = () => $("#settings").classList.add("hidden");
  $("#settings").addEventListener("click", (e) => { if (e.target.id === "settings") $("#settings").classList.add("hidden"); });
  document.querySelectorAll(".s-tabs button").forEach((b) => b.onclick = () => {
    document.querySelectorAll(".s-tabs button").forEach((x) => x.classList.toggle("active", x === b));
    document.querySelectorAll(".s-card section").forEach((s) => (s.hidden = s.dataset.tab !== b.dataset.tab));
    if (b.dataset.tab === "memory") loadMemory();
    if (b.dataset.tab === "links") loadLinks();
    if (b.dataset.tab === "tasks") loadTasks();
    if (b.dataset.tab === "vault") loadVault();
    if (b.dataset.tab === "files") loadFiles("");
  });

  async function openSettings() {
    $("#settings").classList.remove("hidden");
    await refreshState();
    // sağlayıcılar
    const pl = $("#prov-list"); pl.innerHTML = "";
    const og = el("label", "row only-g");
    const ogc = el("input"); ogc.type = "checkbox"; ogc.checked = JV.settings.only_gemini !== false;
    og.append(el("span", "", "Sadece Gemini kullan (tek beyin; diğer anahtarlar saklanır ama kullanılmaz)"), ogc);
    ogc.onchange = async () => { await saveSettings({ only_gemini: ogc.checked }); toast(ogc.checked ? "Artık yalnızca Gemini kullanılıyor." : "Tüm bağlı modeller yedek olarak kullanılacak."); openSettings(); };
    pl.append(og);
    JV.state.providers.filter((p) => !p.disabled).forEach((p) => {
      const row = el("div", "prov");
      const name = el("div"); name.append(el("b", "", p.label), el("div", "st " + (p.key_error ? "bad" : p.configured ? "on" : "off"), p.key_error ? "✗ ANAHTAR GEÇERSİZ" : p.configured ? "● BAĞLI" : "○ bağlı değil"));
      if (p.key_error) name.append(el("div", "key-err", p.key_error));
      let inp;
      if (p.id === "ollama") { inp = el("div", "note", "Anahtar gerekmez — Ollama'yı kur, `ollama pull qwen2.5` çalıştır."); }
      else if (p.id === "custom") { inp = el("input"); inp.placeholder = "CUSTOM_BASE_URL (örn. http://localhost:1234/v1)"; inp.dataset.env = "CUSTOM_BASE_URL"; }
      else { inp = el("input"); inp.type = "password"; inp.placeholder = p.configured ? "•••••• (değiştirmek için yapıştır)" : p.key_env; inp.dataset.env = p.key_env; }
      const right = el("div");
      if (KEY_LINKS[p.id]) { const a = el("a", "", p.id === "ollama" ? "indir ↗" : "ücretsiz anahtar al ↗"); a.href = KEY_LINKS[p.id]; a.target = "_blank"; right.append(a); }
      row.append(name, inp, right); pl.append(row);
      if (p.configured) {  // bu sağlayıcının beyni: otomatik (en yeni) ya da elle seçilen model
        const ms = el("select", "model-pick"); ms.title = "Bu sağlayıcıda kullanılacak model";
        name.append(ms);
        JV.api(`/api/models/${p.id}`).then((r) => {
          if (!r.models || !r.models.length) { ms.remove(); return; }
          const a = el("option", "", `otomatik · ${r.auto}`); a.value = ""; ms.append(a);
          const kd = r.kota_doldu || {};
          r.models.forEach((m) => { const o = el("option", "", m + (kd[m] ? ` · kota doldu (${kd[m]}'de yenilenir)` : "")); o.value = m; ms.append(o); });
          ms.value = r.pinned || "";
          const dl = document.getElementById("ml-" + p.id) || document.body.appendChild(Object.assign(document.createElement("datalist"), { id: "ml-" + p.id }));
          dl.innerHTML = r.models.map((m) => `<option value="${m}">`).join("");
        }).catch(() => ms.remove());
        ms.onchange = async () => {
          const k = `${p.id.toUpperCase()}_MODEL`;
          const r = await JV.api("/api/keys", { body: { [k]: ms.value } });
          toast(r.ok ? `${p.label.split(" (")[0]} beyni: ${ms.value || "otomatik (en yeni)"}` : (r.error || "Kaydedilemedi"));
        };
      }
    });
    const save = el("button", "btn-primary", "ANAHTARLARI KAYDET");
    save.onclick = async () => {
      const keys = {}; pl.querySelectorAll("input[data-env]").forEach((i) => { if (i.value.trim()) keys[i.dataset.env] = i.value.trim(); });
      const r = await JV.api("/api/keys", { body: keys });
      if (r.ok && r.checks) {
        const bad = Object.entries(r.checks).filter(([, v]) => v !== "ok");
        toast(bad.length ? "⚠ " + bad.map(([, v]) => v).join(" · ") : "Kaydedildi ve denendi: anahtar(lar) ÇALIŞIYOR ✓", bad.length ? 15000 : 4000);
      } else toast(r.ok ? "Kaydedildi. Modeller hazır." : (r.error || "Kaydedilemedi"));
      openSettings();
    };
    pl.append(save);
    // kişilik → model
    const pm = $("#persona-models"); pm.innerHTML = "";
    const confd = JV.state.providers.filter((p) => p.configured && !p.disabled);
    JV.state.personas.forEach((per) => {
      const conf = JV.settings.personas[per.id] || { providers: [], model: "" };
      const row = el("div", "pm"); row.style.color = per.color;
      const sel = el("select");
      (confd.length ? confd : JV.state.providers).forEach((p) => { const o = el("option", "", p.label); o.value = p.id; sel.append(o); });
      sel.value = (conf.providers || []).find((x) => confd.some((c) => c.id === x)) || (confd[0] || {}).id || "";
      const mod = el("input"); mod.placeholder = "model (boş = otomatik en iyisi)"; mod.value = conf.model || "";
      mod.setAttribute("list", "ml-" + sel.value); sel.addEventListener("change", () => mod.setAttribute("list", "ml-" + sel.value));
      const commit = () => {
        const order = [sel.value, ...(conf.providers || []).filter((x) => x !== sel.value)];
        saveSettings({ personas: { [per.id]: { providers: order, model: mod.value.trim() } } });
      };
      sel.onchange = () => { mod.value = ""; commit(); };
      mod.onchange = commit;
      row.append(el("span", "", per.id.toUpperCase()), sel, mod); pm.append(row);
    });
    // ses
    $("#v-lang").value = JV.settings.voice_lang || "auto";
    $("#v-fx").checked = JV.settings.effects !== false;
    $("#v-stt").value = JV.settings.stt_lang || "tr-TR";
    $("#v-engine").value = JV.settings.stt_engine || "auto";
    $("#sl-idle").value = JV.settings.sleep_idle_min || 0; $("#sl-thr").value = JV.settings.clap_threshold || 0.35; $("#ar-cmd").value = JV.settings.ar_thumb_command || ""; $("#ar-name").value = JV.settings.user_name || "";
    if (JV.loadMics) JV.loadMics();
    JV.api("/api/autostart").then((r) => { $("#o-autostart").checked = !!r.açık; }).catch(() => {});
    $("#b-on").checked = !!(JV.settings.briefing || {}).on; $("#b-time").value = (JV.settings.briefing || {}).time || "08:00";
    if (JV.voiceLab) JV.voiceLab.render($("#voice-sliders"));
    loadVoiceIds();
    $("#tts-note").textContent = JV.state.tts ? "Film tarzı sinir ağı sesleri aktif (Microsoft Neural, ücretsiz)." : "edge-tts kurulu değil: tarayıcının kendi sesi kullanılıyor. Kurulum için: pip install edge-tts";
    // platformlar
    const host = location.hostname;
    $("#platform-info").innerHTML = "";
    const pi = $("#platform-info");
    const p1 = el("p"); p1.innerHTML = `<b>Bilgisayar:</b> bu pencere. <code>start.bat</code> JARVIS'i ayrı bir uygulama penceresi olarak açar.`;
    const p2 = el("p"); p2.innerHTML = `<b>Telefon (aynı Wi-Fi):</b> <code>start-lan.bat</code> ile başlat; komut penceresinde yazan <code>http://…/?token=…</code> adresini telefonda aç, "Ana ekrana ekle" de — uygulama gibi çalışır.`;
    const p3 = el("p"); p3.innerHTML = `<b>Telegram (her yerden):</b> ${JV.state.telegram ? "<span style='color:#3cff8a'>bağlı ✓</span>" : "bağlı değil"}. @BotFather'dan bot oluştur, <code>.env</code> dosyasına <code>TELEGRAM_BOT_TOKEN</code> ve kendi kimliğin için <code>TELEGRAM_ALLOWED_IDS</code> yaz, yeniden başlat.`;
    pi.append(p1, p2, p3);
  }
  $("#v-lang").onchange = (e) => saveSettings({ voice_lang: e.target.value });
  $("#v-engine").onchange = (e) => saveSettings({ stt_engine: e.target.value });
  $("#sl-idle").onchange = (e) => saveSettings({ sleep_idle_min: Math.max(0, +e.target.value || 0) });
  $("#sl-thr").onchange = (e) => saveSettings({ clap_threshold: +e.target.value });
  $("#ar-cmd").onchange = (e) => saveSettings({ ar_thumb_command: e.target.value.trim() });
  $("#ar-name").onchange = (e) => saveSettings({ user_name: e.target.value.trim() });
  $("#o-camrole").onclick = () => JV.cams && JV.cams.makeThisCamera();
  $("#o-camview").onclick = () => { $("#settings").classList.add("hidden"); JV.cams && JV.cams.open(); };
  document.getElementById("t-cams").onclick = () => JV.cams && JV.cams.open();
  $("#sl-now").onclick = () => { $("#settings").classList.add("hidden"); JV.sleep && JV.sleep.enter(); };
  // mikrofon seçimi + test
  async function loadMics() {
    const sel = $("#v-mic"); if (!sel || !JV.stt) return;
    let devs = await JV.stt.devices();
    if (devs.length && !devs.some((d) => d.label)) { // adlar için bir kez izin iste
      try { (await navigator.mediaDevices.getUserMedia({ audio: true })).getTracks().forEach((t) => t.stop()); devs = await JV.stt.devices(); } catch (e) {}
    }
    sel.innerHTML = '<option value="">Windows varsayılanı</option>' + devs.filter((d) => d.deviceId && d.deviceId !== "default" && d.deviceId !== "communications")
      .map((d, i) => `<option value="${d.deviceId}">${(d.label || "Mikrofon " + (i + 1)).replace(/</g, "")}</option>`).join("");
    sel.value = JV.settings.mic_id || "";
  }
  JV.loadMics = loadMics;
  $("#v-mic").onchange = (e) => saveSettings({ mic_id: e.target.value });
  $("#v-mictest").onclick = () => {
    const out = $("#v-micout"), bar = $("#v-miclvl");
    out.textContent = "Konuş… (örn. 'merhaba JARVIS')";
    JV.stt.record({
      waitMs: 6000, maxMs: 8000,
      onLevel: (v, voice) => { bar.style.width = Math.round(v * 100) + "%"; bar.style.background = voice ? "#3cff8a" : "var(--c)"; },
      onText: (t, info = {}) => {
        bar.style.width = "0";
        const lvl = Math.round((info.level || 0) * 1000);
        if (t) out.innerHTML = `✓ Duyulan: <b>"${t.replace(/</g, "")}"</b> (seviye ${lvl}${info.engine ? ", " + info.engine : ""})`;
        else if (info.reason === "sessiz") out.textContent = lvl < 4 ? `✗ Mikrofondan ses gelmiyor (seviye ${lvl}). Başka mikrofon seç ya da Windows Ses ayarlarında mikrofonu aç/yükselt.` : `✗ Ses çok kısık (seviye ${lvl}). Daha yakından konuş ya da mikrofon seviyesini yükselt.`;
        else out.textContent = `Ses geldi (seviye ${lvl}) ama kelime anlaşılamadı. Tekrar dene.`;
      },
      onError: (e) => { bar.style.width = "0"; out.textContent = "✗ " + e; },
    });
  };
  $("#b-on").onchange = (e) => { saveSettings({ briefing: { on: e.target.checked, time: $("#b-time").value || "08:00" } }); toast(e.target.checked ? `Her gün ${$("#b-time").value} brifingi açık.` : "Sabah brifingi kapalı."); };
  $("#o-autostart").onchange = async (e) => { const r = await JV.api("/api/autostart", { body: { on: e.target.checked } }); e.target.checked = !!r.açık; toast(typeof r.sonuç === "string" ? r.sonuç : r.açık ? "JARVIS artık Windows ile birlikte açılacak." : "Otomatik başlatma kapatıldı."); };
  $("#b-time").onchange = (e) => saveSettings({ briefing: { time: e.target.value } });
  $("#b-now").onclick = () => { $("#settings").classList.add("hidden"); send("Sabah brifingimi ver (morning_briefing aracını kullan)."); };
  $("#v-fx").onchange = (e) => saveSettings({ effects: e.target.checked });
  $("#v-stt").onchange = (e) => saveSettings({ stt_lang: e.target.value });

  async function loadMemory() {
    const m = await JV.api("/api/memory");
    const ul = $("#facts"); ul.innerHTML = "";
    if (!m.facts.length) ul.append(el("li", "", "Henüz kayıt yok. Sohbette \"bunu hatırla\" diyebilirsin."));
    m.facts.forEach((f) => { const li = el("li"); const d = el("button", "mini", "SİL"); d.onclick = async () => { await JV.api("/api/memory/" + f.id, { method: "DELETE" }); loadMemory(); }; li.append(el("span", "", f.fact), d); ul.append(li); });
    const rl = $("#reminders"); rl.innerHTML = "";
    m.reminders.forEach((r) => rl.append(el("li", "", `${new Date(r.due * 1000).toLocaleString("tr-TR")} — ${r.text}`)));
    if (!m.reminders.length) rl.append(el("li", "", "—"));
    const al = $("#actions"); al.innerHTML = "";
    m.actions.forEach((a) => al.append(el("li", "", `${new Date(a.ts * 1000).toLocaleTimeString("tr-TR")} ${a.ok ? "✓" : "✗"} ${a.tool} ${a.args}`)));
  }
  $("#fact-form").addEventListener("submit", async (e) => { e.preventDefault(); const v = $("#fact-in").value.trim(); if (!v) return; await JV.api("/api/memory", { body: { fact: v } }); $("#fact-in").value = ""; loadMemory(); });


  // ---------- kamera ----------
  let camStream = null, facing = "user";
  async function openCam() {
    try {
      camStream = await navigator.mediaDevices.getUserMedia({ video: { facingMode: facing, width: 1280 }, audio: false });
      $("#cam-video").srcObject = camStream; $("#camera").classList.remove("hidden");
    } catch (e) { toast("Kamera açılamadı: " + e.message); }
  }
  function closeCam() { if (camStream) camStream.getTracks().forEach((t) => t.stop()); camStream = null; $("#camera").classList.add("hidden"); }
  $("#t-camera").onclick = () => { JV.unlockAudio(); openCam(); };
  $("#cam-close").onclick = closeCam;
  $("#cam-flip").onclick = () => { facing = facing === "user" ? "environment" : "user"; closeCam(); openCam(); };
  $("#cam-look").onclick = async () => {
    const v = $("#cam-video"); if (!v.videoWidth) return;
    const c = document.createElement("canvas"); const w = Math.min(1280, v.videoWidth);
    c.width = w; c.height = Math.round(v.videoHeight * w / v.videoWidth);
    c.getContext("2d").drawImage(v, 0, 0, c.width, c.height);
    const q = $("#cam-q").value.trim();
    setStatus("thinking", "GÖRÜNTÜ ANALİZİ");
    addMsg("user", "📷 " + (q || "Ne görüyorsun?"));
    try {
      const r = await JV.api("/api/vision", { body: { image: c.toDataURL("image/jpeg", 0.85), question: q, persona, session: "main" } });
      const t = r.text || r.error || "Görüntü analiz edilemedi.";
      addMsg("ai", t, persona); JV.say(t, persona);
    } finally { setStatus(null); }
  };
  $("#cam-q").addEventListener("keydown", (e) => { if (e.key === "Enter") $("#cam-look").click(); });
  // ---------- kahve falı (eğlence): kameradaki fincandan tek kare ----------
  JV.fortune = async () => {
    if (!camStream) await openCam();
    if (!camStream) return;
    toast("☕ Fincanı kameraya göster… 3 sn sonra bakıyorum", 3500);
    await new Promise((r) => setTimeout(r, 3000));
    const v = $("#cam-video"); if (!v.videoWidth) return;
    const c = document.createElement("canvas"); const w = Math.min(1280, v.videoWidth);
    c.width = w; c.height = Math.round(v.videoHeight * w / v.videoWidth); c.getContext("2d").drawImage(v, 0, 0, c.width, c.height);
    setStatus("thinking", "FAL BAKILIYOR ☕");
    try {
      const q = "Bu bir Türk kahvesi fincanı/tabağı görüntüsü olmalı. Telvede GERÇEKTEN görünen şekillere (yol, kuş, kalp, dağ, balık gibi) bakarak "
        + "eğlenceli, esprili ve iyimser, 4-5 cümlelik bir kahve falı yorumla; gördüğün şekilleri adlandır. Bunun bilim olmadığını bir kez kısaca, şakayla belirt. "
        + "Fincan ya da telve görünmüyorsa uydurma: fincanı kameraya göstermesini iste.";
      const r = await JV.api("/api/vision", { body: { image: c.toDataURL("image/jpeg", 0.85), question: q, persona, session: "main" } });
      const t = r.text || r.error || "Fala bakılamadı.";
      addMsg("user", "☕ Falıma bak"); addMsg("ai", t, persona); JV.say(t, persona);
    } finally { setStatus(null); }
  };

  // ---------- Google kurulum sihirbazı (adım adım) ----------
  let gwStep = 0;
  function googleWizard(g) {
    const local = location.hostname === "127.0.0.1" || location.hostname === "localhost";
    const steps = [
      { t: "Proje oluştur", h: `<a href="https://console.cloud.google.com/projectcreate" target="_blank">Google Cloud'da yeni proje</a> sayfasını aç. Proje adı: <b>JARVIS</b> → <b>Oluştur</b>. Üstteki proje seçicide JARVIS'in seçili olduğundan emin ol.` },
      { t: "API'leri aç", h: `Sırayla iki sayfayı aç ve ikisinde de <b>Etkinleştir</b>'e bas:<br>① <a href="https://console.cloud.google.com/apis/library/gmail.googleapis.com" target="_blank">Gmail API</a><br>② <a href="https://console.cloud.google.com/apis/library/calendar-json.googleapis.com" target="_blank">Google Calendar API</a>` },
      { t: "İzin ekranı", h: `<a href="https://console.cloud.google.com/auth/overview" target="_blank">Google Auth Platform</a> → <b>Başlayın</b>. Uygulama adı <b>JARVIS</b>, destek e-postası kendi adresin, kitle <b>Harici (External)</b>, iletişim e-postası yine senin → Oluştur.<br>Sonra <a href="https://console.cloud.google.com/auth/audience" target="_blank">Kitle</a> sayfasında <b>Test kullanıcıları → Kullanıcı ekle</b>: kendi Gmail adresin.<br><span class="note">İpucu: aynı sayfada <b>Uygulamayı yayınla</b> dersen bağlantı 7 günde bir kopmaz.</span>` },
      { t: "Anahtarları yapıştır", form: true, h: `<a href="https://console.cloud.google.com/auth/clients" target="_blank">İstemciler</a> → <b>İstemci oluştur</b> → uygulama türü <b>Masaüstü uygulaması</b> → ad JARVIS → Oluştur. Açılan pencereden iki değeri kopyala:` },
      { t: "Bağlan", h: `Son adım: <b>GOOGLE'A BAĞLAN</b>'a bas, açılan sayfada hesabını seç. <i>"Google bu uygulamayı doğrulamadı"</i> uyarısında <b>Devam</b> de (uygulama senin; veriler yalnızca bu bilgisayarda kalır), tüm izin kutularını işaretle.` },
    ];
    if (g.configured && gwStep < 3) gwStep = 4;
    const w = el("div", "gwiz");
    w.append(el("div", "gstate", "○ bağlı değil" + (g.configured ? " · anahtarlar kayıtlı" : "")));
    const dots = el("div", "gw-dots");
    steps.forEach((st, i) => { const x = el("span", i === gwStep ? "on" : i < gwStep ? "done" : "", `${i + 1}. ${st.t}`); x.onclick = () => { gwStep = i; loadLinks(); }; dots.append(x); });
    w.append(dots);
    const st = steps[gwStep], body = el("div", "gw-body"); body.innerHTML = st.h; w.append(body);
    const msg = el("div", "gtest");
    if (st.form) {
      const r1 = el("div", "prov"), i1 = el("input"); i1.placeholder = "123456789-xxxx.apps.googleusercontent.com"; r1.append(el("b", "", "Client ID"), i1, el("span"));
      const r2 = el("div", "prov"), i2 = el("input"); i2.type = "password"; i2.placeholder = "GOCSPX-…"; r2.append(el("b", "", "Client Secret"), i2, el("span"));
      const check = async () => {
        if (!i1.value && !i2.value) { msg.textContent = ""; return []; }
        const r = await JV.api("/api/google/check/format", { body: { id: i1.value, secret: i2.value } });
        msg.innerHTML = r.sorunlar.length ? "⚠ " + r.sorunlar.join("<br>⚠ ") : "✓ biçim doğru";
        msg.className = "gtest " + (r.sorunlar.length ? "bad" : "ok");
        return r.sorunlar;
      };
      i1.oninput = i2.oninput = () => { clearTimeout(check._t); check._t = setTimeout(check, 350); };
      const sv = el("button", "btn-primary", "KAYDET VE DOĞRULA");
      sv.onclick = async () => {
        const p = await check(); if (p.length) return;
        await JV.api("/api/keys", { body: { GOOGLE_CLIENT_ID: i1.value.trim(), GOOGLE_CLIENT_SECRET: i2.value.trim() } });
        msg.textContent = "Google'a soruluyor…"; msg.className = "gtest";
        const v = await JV.api("/api/google/check/verify");
        msg.textContent = (v.ok ? "✓ " : "✗ ") + v.mesaj; msg.className = "gtest " + (v.ok ? "ok" : "bad");
        if (v.ok) { gwStep = 4; setTimeout(loadLinks, 1200); }
      };
      body.append(r1, r2, sv);
    }
    if (gwStep === 4) {
      const cn = el("button", "btn-primary", "GOOGLE'A BAĞLAN");
      cn.disabled = !g.configured || !local; cn.style.opacity = cn.disabled ? 0.4 : 1;
      cn.onclick = async () => {
        const r = await JV.api("/api/google/connect");
        if (!r.url) { msg.textContent = r.error || "Bağlanamadı"; msg.className = "gtest bad"; return; }
        window.open(r.url, "_blank"); msg.textContent = "Tarayıcıda izin ver; bitince bu pencere kendiliğinden güncellenecek…"; msg.className = "gtest";
        const iv = setInterval(async () => { await refreshState(); if (JV.state.google.connected) { clearInterval(iv); gwStep = 0; loadLinks(); JV.say("Google hesabınız bağlandı.", persona); } }, 3000);
        setTimeout(() => clearInterval(iv), 300000);
      };
      const vf = el("button", "mini", "ANAHTARLARI DOĞRULA"); vf.style.marginLeft = "8px";
      vf.onclick = async () => { msg.textContent = "Google'a soruluyor…"; const v = await JV.api("/api/google/check/verify"); msg.textContent = (v.ok ? "✓ " : "✗ ") + v.mesaj; msg.className = "gtest " + (v.ok ? "ok" : "bad"); };
      body.append(cn, vf);
      if (!g.configured) body.append(el("p", "note", "Önce 4. adımda anahtarları kaydet."));
    }
    w.append(msg);
    const nav = el("div", "gw-nav");
    const back = el("button", "mini", "◀ GERİ"); back.disabled = gwStep === 0; back.onclick = () => { gwStep--; loadLinks(); };
    const next = el("button", "mini", "İLERİ ▶"); next.disabled = gwStep === steps.length - 1; next.onclick = () => { gwStep++; loadLinks(); };
    nav.append(back, el("span", "note", `adım ${gwStep + 1} / ${steps.length}`), next); w.append(nav);
    if (!local) w.append(el("p", "note", "Not: Google bağlantısını bilgisayardaki JARVIS penceresinden yapmalısın."));
    return w;
  }

  // ---------- bağlantılar (Google, Home Assistant) ----------
  async function loadLinks() {
    await refreshState();
    const g = JV.state.google || {}, box = $("#google-box"); box.innerHTML = "";
    const d = el("div", "gbox");
    if (g.connected) {
      d.append(el("div", "gstate on", "● BAĞLI: " + (g.email || "Google hesabı")));
      d.append(el("p", "note", "Artık şunları diyebilirsin: \"okunmamış maillerimi özetle\", \"Ahmet'e yarınki toplantı için mail yaz\", \"bu maili arşivle\", \"bugünkü programım ne\", \"cuma 14:00'e dişçi randevusu ekle\"."));
      const out = el("div", "gtest");
      const t = el("button", "mini", "BAĞLANTIYI DENE");
      t.onclick = async () => {
        out.textContent = "deneniyor…";
        const r = await JV.api("/api/google/check/test");
        out.innerHTML = r.mesaj ? r.mesaj : `Gmail: <b>${r.gmail}</b><br>Takvim: <b>${r.takvim}</b>`;
        out.className = "gtest " + (r.ok ? "ok" : "bad");
      };
      const b = el("button", "mini", "BAĞLANTIYI KES"); b.style.marginLeft = "8px";
      b.onclick = async () => { await JV.api("/api/google/disconnect", { method: "POST" }); loadLinks(); };
      d.append(t, b, out);
    } else {
      d.append(googleWizard(g));
    }
    box.append(d);
    const s = JV.settings;
    $("#o-guest").checked = !!s.guest_mode; $("#o-rcam").checked = !!s.allow_remote_camera; $("#o-rscr").checked = s.allow_remote_screen !== false; $("#o-rcmd").checked = !!s.allow_remote_commands; $("#o-rport").value = s.robot_port || ""; $("#o-rurl").value = s.robot_url || "";
    $("#o-auto").checked = !!s.auto_control; $("#o-mail").checked = s.email_watch !== false; $("#o-meet").checked = s.meeting_alerts !== false; $("#o-city").value = s.city || "";
  }
  $("#links-save").onclick = async () => {
    const k = {}; document.querySelectorAll('section[data-tab=links] .prov input[data-env]').forEach((i) => i.value.trim() && (k[i.dataset.env] = i.value.trim()));
    const r = await JV.api("/api/keys", { body: k }); toast(r.ok ? "Kaydedildi." : (r.error || "Kaydedilemedi"));
  };
  $("#o-auto").onchange = (e) => { saveSettings({ auto_control: e.target.checked }); if (e.target.checked) toast("Dikkat: JARVIS artık ekranda onaysız tıklayıp yazabilir."); };
  $("#o-mail").onchange = (e) => saveSettings({ email_watch: e.target.checked });
  $("#o-meet").onchange = (e) => saveSettings({ meeting_alerts: e.target.checked });
  $("#o-city").onchange = (e) => saveSettings({ city: e.target.value.trim() });

  async function loadTasks() {
    const r = await JV.api("/api/tasks");
    const tl = $("#task-list"); tl.innerHTML = "";
    if (!Array.isArray(r.tasks)) tl.append(el("li", "", "Henüz görev yok."));
    else r.tasks.forEach((t) => { const li = el("li"); const left = el("div"); left.append(el("div", "", `#${t.id} ${t.prompt}`), el("small", "", `${t.kind}${t.at ? " " + t.at : ""} · sonraki ${t.sonraki} · son ${t.son}${t.enabled ? "" : " · DURDURULDU"}`)); li.append(left); tl.append(li); });
    const dl = $("#todo-list"); dl.innerHTML = "";
    if (!Array.isArray(r.todos)) dl.append(el("li", "", "Yapılacak iş yok."));
    else r.todos.forEach((t) => { const li = el("li", t.done ? "done" : t.gecikti ? "late" : ""); li.append(el("span", "", `#${t.id} ${t.text}`), el("small", "", t.due || "")); dl.append(li); });
  }


  // ---------- ses kimliği ayarları ----------
  async function loadVoiceIds() {
    $("#vid-on").checked = !!JV.settings.voice_id; $("#vid-lock").checked = !!JV.settings.voice_lock;
    const p = await JV.api("/api/voice/profiles"); const ul = $("#vid-list"); ul.innerHTML = "";
    const names = Object.keys(p || {});
    if (!names.length) ul.append(el("li", "", "Henüz tanıtılmış ses yok."));
    names.forEach((n) => { const li = el("li"); const d = el("button", "mini", "SİL");
      d.onclick = async () => { await JV.api("/api/voice/delete?name=" + encodeURIComponent(n), { method: "POST", body: {} }); loadVoiceIds(); };
      li.append(el("span", "", `${n}${p[n].sahip ? " (sahibi)" : ""} — ${p[n].örnek} örnek`), d); ul.append(li); });
    if (!$("#vid-name").value && names.length) $("#vid-name").value = names[0];
  }
  $("#vid-on").onchange = (e) => { JV.settings.voice_id = e.target.checked; saveSettings({ voice_id: e.target.checked }); if (e.target.checked) JV.voiceId.start(); };
  $("#vid-lock").onchange = (e) => { JV.settings.voice_lock = e.target.checked; saveSettings({ voice_lock: e.target.checked }); if (e.target.checked) JV.voiceId.start(); };
  const SENTENCES = ["Merhaba JARVIS, bugün hava nasıl olacak ve takvimimde neler var?",
    "Lütfen müziği biraz kıs, sonra bana okunmamış e-postalarımı özetle.",
    "Yarın sabah dokuzda toplantı var, bana bir saat önce hatırlat."];
  $("#vid-enroll").onclick = async () => {
    const name = $("#vid-name").value.trim() || "Sahip"; const owner = $("#vid-owner").checked;
    const btn = $("#vid-enroll"); btn.disabled = true;
    try {
      for (let i = 0; i < SENTENCES.length; i++) {
        $("#vid-prompt").innerHTML = `<b>${i + 1}/3</b> — 5 saniye boyunca normal sesinle oku:<br><i>"${SENTENCES[i]}"</i>`;
        JV.beep(660); await new Promise((r) => setTimeout(r, 400));
        const r = await JV.voiceId.recordAndEnroll(name, 5, i === 0 ? owner : undefined);
        if (r.error) { $("#vid-prompt").textContent = "Hata: " + r.error + " — tekrar dene."; return; }
      }
      $("#vid-prompt").textContent = "Tamam! Artık seni sesinden tanıyorum. Daha iyi tanıma için başka bir zaman bir kez daha tanıtabilirsin.";
      JV.settings.voice_id = true; saveSettings({ voice_id: true }); JV.say(`Memnun oldum ${name}. Sesinizi kaydettim.`, persona);
      loadVoiceIds();
    } catch (e) { $("#vid-prompt").textContent = "Hata: " + e.message; }
    finally { btn.disabled = false; }
  };


  // ---------- şifre kasası ----------
  async function loadVault() {
    const ul = $("#vault-list"); ul.innerHTML = "";
    const r = await JV.api("/api/vault/list");
    if (r.error) { ul.append(el("li", "", r.error)); return; }
    if (!r.length) ul.append(el("li", "", "Kasa boş."));
    r.forEach((e) => {
      const li = el("li"); const left = el("div"); left.append(el("div", "", e.ad), el("small", "", [e.kullanıcı, e.site].filter(Boolean).join(" · ")));
      const right = el("div"); const show = el("button", "mini", "GÖSTER"), del = el("button", "mini", "SİL");
      show.onclick = async () => { const x = await JV.api("/api/vault/reveal", { body: { name: e.ad } }); show.textContent = x.secret || x.error; setTimeout(() => (show.textContent = "GÖSTER"), 8000); };
      del.onclick = async () => { if (confirm(e.ad + " silinsin mi?")) { await JV.api("/api/vault/delete", { body: { name: e.ad } }); loadVault(); } };
      right.append(show, document.createTextNode(" "), del); li.append(left, right); ul.append(li);
    });
  }
  $("#vf-save").onclick = async () => {
    const b = { name: $("#vf-name").value.trim(), user: $("#vf-user").value.trim(), secret: $("#vf-secret").value, url: $("#vf-url").value.trim() };
    const r = await JV.api("/api/vault/save", { body: b });
    if (r.ok) { ["#vf-name", "#vf-user", "#vf-secret", "#vf-url"].forEach((s) => ($(s).value = "")); toast("Kasaya eklendi."); loadVault(); } else toast(r.error || "Eklenemedi");
  };

  // ---------- görünüm modları ----------
  document.querySelectorAll("#views [data-view]").forEach((b) => (b.onclick = () => JV.setView && JV.setView(b.dataset.view)));
  [["system", "☀ Güneş sistemi"], ["satellites", "🛰 Uydular"], ["sky", "✦ Yıldız haritası"], ["moon", "☾ Ay"], ["mars", "♂ Mars"], ["blackhole", "◉ Kara delik"], ["galaxy", "🌀 Galaksi oluştur"], ["universe", "🕸 Evren"]].forEach(([v, t]) => {
    const b = el("button", "tog", t); b.onclick = () => JV.uiCommand("space_show", {}, JSON.stringify({ ui: "space", view: v })); $("#space-menu").append(b);
  });


  // ---------- acil durdurma ----------
  async function estop() {
    JV.stopSpeaking(false);
    if (JV.gesture && JV.gesture.isRunning()) JV.gesture.stop();
    const r = await JV.api("/api/estop", { body: {} });
    document.body.classList.add("estop"); $("#t-estop").classList.add("on");
    addMsg("ai", r.text, persona); JV.say("Acil durdurma uygulandı.", persona, undefined, true);
  }
  $("#t-estop").onclick = async () => {
    if (document.body.classList.contains("estop")) {
      const r = await JV.api("/api/estop", { body: { reset: true } });
      document.body.classList.remove("estop"); $("#t-estop").classList.remove("on"); toast(r.text);
    } else estop();
  };
  addEventListener("keydown", (e) => { if (e.ctrlKey && e.shiftKey && e.code === "KeyX") estop(); });

  // ---------- alarm ----------
  let alarmTimer = null;
  function ringAlarm(text) {
    $("#alarm-text").textContent = text.replace("⏰ ALARM: ", "");
    $("#alarm").classList.remove("hidden");
    clearInterval(alarmTimer);
    let i = 0; alarmTimer = setInterval(() => { JV.beep(i++ % 2 ? 880 : 1175); if (i > 240) stopAlarm(); }, 450);
  }
  function stopAlarm() { clearInterval(alarmTimer); $("#alarm").classList.add("hidden"); }
  $("#alarm-off").onclick = stopAlarm;
  $("#alarm-snooze").onclick = async () => { stopAlarm(); const t = new Date(Date.now() + 5 * 60000); await JV.api("/api/chat", { body: { text: `${t.getHours()}:${String(t.getMinutes()).padStart(2, "0")} için '${$("#alarm-text").textContent}' alarmı kur`, persona }, raw: true }); toast("5 dakika ertelendi."); };

  // ---------- dosyalar (telefondan da) ----------
  let fbCur = "";
  async function loadFiles(path) {
    const r = await JV.api("/api/files/list?path=" + encodeURIComponent(path || ""));
    const ul = $("#fb-list"); ul.innerHTML = "";
    if (r.error) { ul.append(el("li", "", r.error)); return; }
    fbCur = r.yol; $("#fb-path").textContent = r.yol;
    const sh = $("#fb-short"); sh.innerHTML = "";
    Object.entries(r.kısayollar || {}).forEach(([k, v]) => { const b = el("button", "mini", k.toUpperCase()); b.onclick = () => loadFiles(v); sh.append(b); });
    $("#fb-up").onclick = () => r.üst && loadFiles(r.üst);
    r.öğeler.forEach((f) => {
      const li = el("li"); li.append(el("span", "", (f.klasör ? "📁 " : "📄 ") + f.ad), el("small", "", f.klasör ? "" : `${f.kb} KB · ${f.tarih}`));
      li.onclick = () => { if (f.klasör) loadFiles(f.yol); else window.open(`/api/files/download?path=${encodeURIComponent(f.yol)}&token=${encodeURIComponent(token)}`, "_blank"); };
      ul.append(li);
    });
  }
  $("#fb-file").onchange = async (e) => {
    const f = e.target.files[0]; if (!f) return;
    const r = await fetch(`/api/files/upload?path=${encodeURIComponent(fbCur)}&name=${encodeURIComponent(f.name)}`, { method: "POST", headers: { "x-token": token }, body: f });
    const j = await r.json(); toast(j.path ? "Yüklendi: " + j.path : j.error || "Yüklenemedi"); loadFiles(fbCur);
  };
  $("#o-guest").onchange = (e) => { JV.settings.guest_mode = e.target.checked; saveSettings({ guest_mode: e.target.checked }); toast(e.target.checked ? "Misafir modu açık." : "Misafir modu kapalı."); };
  $("#o-rcam").onchange = (e) => saveSettings({ allow_remote_camera: e.target.checked });
  $("#o-rscr").onchange = (e) => saveSettings({ allow_remote_screen: e.target.checked });
  $("#o-rcmd").onchange = (e) => saveSettings({ allow_remote_commands: e.target.checked });
  $("#o-rsave").onclick = async () => { await saveSettings({ robot_port: $("#o-rport").value.trim(), robot_url: $("#o-rurl").value.trim() }); toast("Robot ayarı kaydedildi."); };

  // ---------- başlangıç ----------
  async function refreshState() {
    const s = await JV.api("/api/state");
    JV.state = s; JV.settings = s.settings;
    renderProvMini();
    return s;
  }

  async function loadHistory() {
    try {
      const h = await JV.api("/api/history?session=main&limit=30");
      h.forEach((m) => addMsg(m.role === "user" ? "user" : "ai", m.content, m.persona || persona));
    } catch (e) {}
  }

  async function boot() {
    const lines = ["INITIALIZING NEURAL CORE...", "LOADING PERSONALITY MATRIX: JARVIS / FRIDAY / ULTRON", "MOUNTING MEMORY BANKS...", "LINKING MODEL NETWORK...", "AUDIO SUBSYSTEM ONLINE", "HUD ONLINE"];
    const log = $("#boot-log");
    for (const l of lines) { log.textContent += "> " + l + "\n"; await new Promise((r) => setTimeout(r, 160)); }
    try {
      await refreshState();
      const on = JV.state.providers.filter((p) => p.configured).map((p) => p.label);
      log.textContent += "> MODELLER: " + (on.length ? on.join(", ") : "YOK — Ayarlar'dan ücretsiz anahtar ekle") + "\n";
      log.textContent += "> SES: " + (JV.state.tts ? "NEURAL" : "TARAYICI") + "\n> HAZIR.";
    } catch (e) { log.textContent += "> SUNUCUYA ULAŞILAMADI: " + e.message; }
    renderPersonas();
    applyPersona(JV.settings.persona || "jarvis", false);
    JV.setVisual(JV.settings.visual || "sphere");
    lastNote = JV.state.last_notification || 0;
    updateToggles();
    loadHistory();
    pollSystem(); pollProcs();
    setInterval(pollSystem, 2500); setInterval(pollProcs, 12000); setInterval(pollNotes, 5000);
    (JV.state.pending || []).forEach((p) => showConfirm({ id: p.id, text: `${p.name}(${JSON.stringify(p.args)})` }));
  }

  $("#boot-btn").onclick = () => {
    JV.unlockAudio();
    $("#boot").classList.add("gone");
    const p = P(persona);
    if (p.greeting) { addMsg("ai", p.greeting, persona); JV.say(p.greeting, persona); }
    if (!JV.state.providers.some((x) => x.configured)) setTimeout(openSettings, 1200);
    if (JV.settings.wake_word) { wakeMode = true; startRec(false); updateToggles(); }
  };
  if ("speechSynthesis" in window) speechSynthesis.getVoices();
  boot();
})();
