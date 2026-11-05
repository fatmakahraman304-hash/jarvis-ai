/* TELEFON EKRANLARI — iki parça:
   1) EKRAN CİHAZI: eski telefon. JARVIS adresini sonuna ?rol=ekran ekleyip aç (ya da Telefon Ekranları panelinden "Bu cihazı ekran yap").
      Bekleme ekranında reaktör çekirdeği + saat; JARVIS komut yolladığında: YouTube videosu tam ekran, büyük yazı, sesli konuşma,
      animasyon, GELEN ARAMA (JARVIS seni arar). Altta "📞 JARVIS'İ ARA" ile eller serbest görüşme.
   2) PANEL (bilgisayar): ⊞ Uygulamalar > 📱 Telefon Ekranları — bağlı telefonlar, hepsine/birine video, yazı, animasyon, çaldır, durdur. */
(function () {
  const JV = (window.JV = window.JV || {});
  const LS = (k, v) => { try { if (v === undefined) return localStorage.getItem(k); localStorage.setItem(k, v); } catch (e) { return null; } };
  const qs = new URLSearchParams(location.search);
  const isScreen = qs.get("rol") === "ekran" || qs.get("role") === "screen" || LS("jv_role") === "ekran";
  JV.isScreenRole = isScreen;
  const esc = (s) => String(s == null ? "" : s).replace(/[&<>"]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]));

  // ================= 1) EKRAN CİHAZI =================
  function device() {
    document.body.classList.add("scrrole"); JV.coreHidden = true;
    const id = LS("jv_scr_id") || ("ekr" + Math.random().toString(36).slice(2, 7)); LS("jv_scr_id", id); LS("jv_role", "ekran");
    const ui = document.createElement("div"); ui.id = "scrnode";
    ui.innerHTML = `<canvas id="sn-orb"></canvas>
      <div class="sn-top"><b id="sn-name"></b><span id="sn-st">○ BAĞLANIYOR</span></div>
      <div class="sn-clock"><b id="sn-time"></b><span id="sn-date"></span></div>
      <div class="sn-text hidden" id="sn-text"></div>
      <div class="sn-bot"><button class="btn-primary" id="sn-call">📞 JARVIS'İ ARA</button><button class="mini" id="sn-set">⚙</button></div>
      <div class="sn-start" id="sn-start"><div><b>J.A.R.V.I.S. · EKRAN</b><p>Bu telefon JARVIS'in ekranı olacak: video, yazı, animasyon ve arama buraya gelir.</p>
        <label>Ad <input id="sn-nm" placeholder="TELEFON-1"></label><button class="btn-primary" id="sn-go">BAŞLAT</button>
        <button class="mini" id="sn-exit">Normal JARVIS'e dön</button><p class="note">Telefonu şarjda tut; otomatik kilidi kapat. Ses ve tam ekran için bir kez BAŞLAT'a dokunman gerekiyor.</p></div></div>`;
    document.body.append(ui);
    const $ = (s) => ui.querySelector(s);
    $("#sn-nm").value = LS("jv_scr_name") || "TELEFON-1";
    $("#sn-name").textContent = $("#sn-nm").value;
    let wake = null, textT = 0, fails = 0;
    async function keepAwake() { try { wake = await navigator.wakeLock.request("screen"); } catch (e) {} }
    document.addEventListener("visibilitychange", () => { if (document.visibilityState === "visible") keepAwake(); });
    $("#sn-go").onclick = async () => {
      const nm = $("#sn-nm").value.trim() || "TELEFON-1"; LS("jv_scr_name", nm); $("#sn-name").textContent = nm;
      $("#sn-start").classList.add("hidden"); keepAwake();
      try { await document.documentElement.requestFullscreen(); } catch (e) {}
      try { const a = new (window.AudioContext || window.webkitAudioContext)(); await a.resume(); a.close(); } catch (e) {}
      poll();
    };
    $("#sn-exit").onclick = () => { LS("jv_role", ""); location.href = location.pathname; };
    $("#sn-set").onclick = () => { $("#sn-start").classList.remove("hidden"); };
    $("#sn-call").onclick = () => JV.call && JV.call.start();
    // bekleme ekranı çekirdeği
    const cv = $("#sn-orb");
    (function draw() {
      const d = Math.min(devicePixelRatio || 1, 2), w = innerWidth, h = innerHeight;
      if (cv.width !== Math.round(w * d)) { cv.width = w * d; cv.height = h * d; }
      const g = cv.getContext("2d"); g.setTransform(d, 0, 0, d, 0, 0); g.clearRect(0, 0, w, h);
      if (!document.body.classList.contains("stage-busy") && JV.core2d) {
        const hex = (getComputedStyle(document.documentElement).getPropertyValue("--c").trim() || "#38d6ff").slice(0, 7);
        JV.core2d.reactor(g, { t: performance.now() / 1000, lvl: JV.speaking ? JV.level || 0.3 : 0, cx: w / 2, cy: h * 0.46, R: Math.min(w, h) * 0.24, hex, name: $("#sn-name").textContent });
      }
      const t = new Date(); $("#sn-time").textContent = t.toLocaleTimeString("tr-TR", { hour: "2-digit", minute: "2-digit" });
      $("#sn-date").textContent = t.toLocaleDateString("tr-TR", { weekday: "long", day: "numeric", month: "long" }).toUpperCase();
      requestAnimationFrame(draw);
    })();
    function showText(t) { const e = $("#sn-text"); e.textContent = t; e.classList.remove("hidden"); clearTimeout(textT); textT = setTimeout(() => e.classList.add("hidden"), 15000); }
    function run(c) {
      if (c.type === "video" && JV.video) JV.video.open({ id: c.id, title: c.title, channel: c.channel });
      else if (c.type === "say" && JV.say) JV.say(c.text, (JV.settings && JV.settings.persona) || "jarvis", null, true);
      else if (c.type === "show") showText(c.text);
      else if (c.type === "anim" && JV.stage) JV.stage.anim({ preset: c.preset });
      else if (c.type === "ring" && JV.call) JV.call.incoming(c.text);
      else if (c.type === "stop") { if (JV.stage) JV.stage.clear(); if (JV.video) JV.video.close(); $("#sn-text").classList.add("hidden"); }
    }
    JV._screenRun = run;
    async function poll() {
      try {
        const st = JV.call && JV.call.active() ? "görüşmede" : (JV.stage && JV.stage.current()) || "";
        const r = await JV.api(`/api/screens/poll?id=${encodeURIComponent(id)}&name=${encodeURIComponent($("#sn-name").textContent)}&state=${encodeURIComponent(st)}`);
        if (r.error) { $("#sn-st").textContent = "✕ " + r.error; fails++; }
        else { fails = 0; $("#sn-st").textContent = "● BAĞLI"; (r.cmds || []).forEach(run); }
      } catch (e) { fails++; $("#sn-st").textContent = "○ BAĞLANTI YOK"; }
      setTimeout(poll, fails ? Math.min(10000, 1500 * fails) : 1500);
    }
  }

  // ================= 2) PANEL =================
  let pn;
  function panel() {
    if (!pn) {
      pn = document.createElement("div"); pn.id = "phonespanel"; pn.className = "hidden";
      pn.innerHTML = `<div class="ph-card"><div class="ph-top"><b>📱 TELEFON EKRANLARI</b><span id="ph-n"></span><button class="mini" id="ph-x">✕</button></div>
        <ul id="ph-list"></ul>
        <div class="ph-row"><select id="ph-t"><option value="hepsi">Hepsi</option></select><input id="ph-q" placeholder="video adı / yazı (her telefona farklı video: a | b | c)"></div>
        <div class="ph-row ph-acts"><button class="mini" data-a="video">▶ VİDEO</button><button class="mini" data-a="show">🅰 YAZI</button><button class="mini" data-a="say">🔊 KONUŞ</button><button class="mini" data-a="anim">✨ ANİMASYON</button><button class="mini" data-a="ring">📞 ÇALDIR</button><button class="mini" data-a="stop">■ DURDUR</button></div>
        <p class="note" id="ph-help">Telefonda JARVIS adresini sonuna <code>?rol=ekran</code> ekleyerek aç (bilgisayarda JARVIS <code>--lan</code> ile çalışmalı; adres ve anahtar Ayarlar &gt; PLATFORMLAR'da). Ya da: <button class="mini" id="ph-me">Bu cihazı ekran yap</button></p>
        <div class="note" id="ph-out"></div></div>`;
      document.body.append(pn);
      pn.querySelector("#ph-x").onclick = close;
      pn.querySelector("#ph-me").onclick = () => { LS("jv_role", "ekran"); location.href = location.pathname + "?rol=ekran"; };
      pn.querySelectorAll("[data-a]").forEach((b) => (b.onclick = async () => {
        const a = b.dataset.a, q = pn.querySelector("#ph-q").value.trim(), target = pn.querySelector("#ph-t").value;
        const body = { type: a, target };
        if (a === "video") { if (!q) return out("Video adı yaz."); body.query = q; }
        if (a === "show" || a === "say" || a === "ring") body.text = q || (a === "ring" ? "" : "Merhaba!");
        if (a === "anim") body.preset = q || "galaxy";
        out("Gönderiliyor…");
        try { const r = await JV.api("/api/screens/send", { body }); out(r.error ? "✕ " + r.error : "✓ " + (r.oynatılıyor ? r.oynatılıyor.map((x) => x.telefon + ": " + x.video).join(" · ") : (r.telefonlar || r.çalan || []).join(", ") || "tamam")); }
        catch (e) { out("✕ " + e.message); }
      }));
      addEventListener("keydown", (e) => { if (e.key === "Escape" && !pn.classList.contains("hidden")) close(); });
    }
    return pn;
  }
  const out = (t) => { if (pn) pn.querySelector("#ph-out").textContent = t; };
  let listT = 0;
  async function refresh() {
    try {
      const r = await JV.api("/api/screens/list"); const L = r.telefonlar || [];
      pn.querySelector("#ph-n").textContent = L.length ? L.length + " BAĞLI" : "BAĞLI YOK";
      pn.querySelector("#ph-list").innerHTML = L.map((x) => `<li><i>●</i><b>${esc(x.ad)}</b><span>${esc(x.durum)}</span><small>${esc(x.son)}</small></li>`).join("") || `<li class="none">Henüz telefon yok.</li>`;
      const sel = pn.querySelector("#ph-t"), cur = sel.value; sel.innerHTML = `<option value="hepsi">Hepsi</option>` + L.map((x) => `<option>${esc(x.ad)}</option>`).join(""); sel.value = [...sel.options].some((o) => o.value === cur) ? cur : "hepsi";
    } catch (e) {}
  }
  function open() { panel().classList.remove("hidden"); refresh(); clearInterval(listT); listT = setInterval(refresh, 3000); }
  function close() { if (pn) pn.classList.add("hidden"); clearInterval(listT); }
  JV.phones = { open, close, refresh };

  const go = () => { if (isScreen) device(); };
  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", go); else go();
})();
