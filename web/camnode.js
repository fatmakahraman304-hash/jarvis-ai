/* JARVIS'İN GÖZÜ — iki parça:
   1) KAMERA CİHAZI: eski telefon/tablet. Adres sonuna ?rol=kamera (ya da Ayarlar > PLATFORMLAR > "Bu cihazı kamera yap").
      Saniyede ~1 kare gönderir (izleyen yoksa daha seyrek), hareketi TELEFONDA algılar, ekranı açık tutar, karanlık ve sade arayüz.
   2) İZLEYİCİ: bilgisayar/tablette sol altta "● CAM · MUTFAK" düğmesi; tıklayınca canlı küçük pencere, tıklayınca tam ekran.
   Gizlilik: kareler diske yazılmaz; sunucu yalnızca son kareyi bellekte tutar. Kamera ekranında "CANLI · N izleyici" yazar. */
(function () {
  const JV = (window.JV = window.JV || {});
  const LS = (k, v) => { try { if (v === undefined) return localStorage.getItem(k); localStorage.setItem(k, v); } catch (e) { return null; } };
  const qs = new URLSearchParams(location.search);
  const isCamRole = qs.get("rol") === "kamera" || qs.get("role") === "camera" || LS("jv_role") === "kamera";
  const tok = () => JV.token || qs.get("token") || LS("jv_token") || "";

  // ================= 1) KAMERA CİHAZI =================
  function camDevice() {
    document.body.classList.add("camrole");
    const id = LS("jv_cam_id") || ("cam" + Math.random().toString(36).slice(2, 7)); LS("jv_cam_id", id);
    const ui = document.createElement("div"); ui.id = "camnode";
    ui.innerHTML = `<div class="cn-top"><b>J.A.R.V.I.S. · GÖZ</b><span id="cn-live">○ KAPALI</span></div>
      <video id="cn-v" muted playsinline autoplay></video>
      <div class="cn-form">
        <label>Ad <input id="cn-name" placeholder="CAM-01"></label>
        <label>Konum <input id="cn-loc" placeholder="MUTFAK"></label>
        <label>Kamera <select id="cn-face"><option value="environment">Arka</option><option value="user">Ön</option></select></label>
        <label>Hareket hassasiyeti <input type="range" id="cn-sens" min="2" max="30" value="10"></label>
        <label class="cn-row"><input type="checkbox" id="cn-motion" checked> Hareket algıla</label>
        <button id="cn-start" class="btn-primary">KAMERAYI BAŞLAT</button>
        <button id="cn-exit" class="mini">Normal JARVIS'e dön</button>
        <p class="note" id="cn-note">Telefonu şarjda tut. Ekran kapanırsa kamera durur (Ayarlar > Ekran > Otomatik kilit: Asla). Banyo/yatak odası gibi özel alanlara kurma; evdekilere kamerayı söyle.</p>
      </div>`;
    document.body.append(ui);
    const $ = (s) => ui.querySelector(s), v = $("#cn-v");
    $("#cn-name").value = LS("jv_cam_name") || "CAM-01"; $("#cn-loc").value = LS("jv_cam_loc") || ""; $("#cn-face").value = LS("jv_cam_face") || "environment";
    $("#cn-sens").value = LS("jv_cam_sens") || 10;
    ["name", "loc", "face", "sens"].forEach((k) => ($("#cn-" + k).onchange = (e) => { LS("jv_cam_" + k, e.target.value); if (k === "face" && stream) { stop(); start(); } }));
    $("#cn-exit").onclick = () => { LS("jv_role", ""); location.href = location.pathname; };
    let stream = null, timer = 0, wake = null, prev = null, hd = false, viewers = 0, fails = 0;
    const c = document.createElement("canvas"), cx = c.getContext("2d"), m = document.createElement("canvas"), mx = m.getContext("2d", { willReadFrequently: true });
    m.width = 32; m.height = 24;
    async function start() {
      try {
        stream = await navigator.mediaDevices.getUserMedia({ video: { facingMode: $("#cn-face").value, width: { ideal: 1280 }, height: { ideal: 720 } }, audio: false });
      } catch (e) { $("#cn-note").textContent = "Kamera açılamadı: " + e.message + " (kamera yalnızca https:// adreste çalışır — bilgisayarda start-vr.bat)"; return; }
      v.srcObject = stream; LS("jv_role", "kamera"); $("#cn-start").textContent = "DURDUR";
      try { wake = await navigator.wakeLock.request("screen"); } catch (e) { $("#cn-note").textContent = "Ekran açık tutulamıyor: telefonda otomatik kilidi kapat."; }
      tick();
    }
    function stop() { clearTimeout(timer); if (stream) stream.getTracks().forEach((t) => t.stop()); stream = null; if (wake) wake.release().catch(() => {}); wake = null; $("#cn-start").textContent = "KAMERAYI BAŞLAT"; $("#cn-live").textContent = "○ KAPALI"; }
    $("#cn-start").onclick = () => (stream ? stop() : start());
    document.addEventListener("visibilitychange", async () => { if (stream && document.visibilityState === "visible" && !wake) { try { wake = await navigator.wakeLock.request("screen"); } catch (e) {} } });
    function motion() {
      if (!$("#cn-motion").checked) return false;
      mx.drawImage(v, 0, 0, 32, 24); const d = mx.getImageData(0, 0, 32, 24).data, g = new Uint8Array(768);
      for (let i = 0; i < 768; i++) g[i] = (d[i * 4] * 3 + d[i * 4 + 1] * 6 + d[i * 4 + 2]) / 10;
      let changed = 0;
      if (prev) { let mean = 0; for (let i = 0; i < 768; i++) mean += g[i] - prev[i]; mean /= 768; // genel ışık değişimini çıkar
        for (let i = 0; i < 768; i++) if (Math.abs(g[i] - prev[i] - mean) > 22) changed++; }
      prev = g;
      return changed > (+$("#cn-sens").value) * 3; // hassasiyet: değişen küçük piksel sayısı
    }
    async function tick() {
      if (!stream) return;
      if (v.videoWidth) {
        const mv = motion();
        const w = hd ? Math.min(1280, v.videoWidth) : 640; c.width = w; c.height = Math.round(v.videoHeight * w / v.videoWidth);
        cx.drawImage(v, 0, 0, c.width, c.height);
        const blob = await new Promise((r) => c.toBlob(r, "image/jpeg", hd ? 0.85 : 0.6));
        const q = new URLSearchParams({ id, name: $("#cn-name").value || "CAM", loc: $("#cn-loc").value || "", motion: mv ? "1" : "0", w: c.width, h: c.height });
        try {
          const r = await fetch("/api/cams?" + q, { method: "POST", headers: { "x-token": tok(), "Content-Type": "image/jpeg" }, body: blob });
          const j = await r.json(); hd = !!j.hd; viewers = j.viewers || 0; fails = 0;
          $("#cn-live").textContent = `● CANLI · ${viewers} izleyici${j.security ? " · 🛡 GÜVENLİK" : ""}${mv ? " · HAREKET" : ""}`;
        } catch (e) { fails++; $("#cn-live").textContent = "⚠ JARVIS'e ulaşılamıyor"; }
      }
      timer = setTimeout(tick, hd || viewers ? 700 : fails ? 4000 : 1600); // izleyen yoksa seyrek (ısınma/pil)
    }
    if (LS("jv_role") === "kamera" && LS("jv_cam_auto") !== "0") setTimeout(start, 600);
  }

  // ================= 2) İZLEYİCİ (bilgisayar/tablet) =================
  const viewer = "v" + Math.random().toString(36).slice(2, 8);
  let badge, panel, cams = [], sel = "", refresh = 0;
  function buildViewer() {
    badge = document.createElement("div"); badge.id = "cam-badges"; document.body.append(badge);
    panel = document.createElement("div"); panel.id = "campanel"; panel.className = "hidden";
    panel.innerHTML = `<div class="cp-top"><span id="cp-tabs"></span><span id="cp-info"></span><button class="mini" id="cp-sec">🛡 GÜVENLİK</button><button class="mini" id="cp-ask">👁 JARVIS BAKSIN</button><button class="mini" id="cp-x">✕</button></div><img id="cp-img" alt="">`;
    document.body.append(panel);
    panel.querySelector("#cp-x").onclick = () => close();
    panel.querySelector("#cp-img").onclick = () => panel.classList.toggle("full");
    panel.querySelector("#cp-ask").onclick = () => { const c = cams.find((x) => x.id === sel); JV.sendCommand && JV.sendCommand(`${c && c.loc ? c.loc + " kamerasına" : "Kameraya"} bak, ne görüyorsun?`); };
    panel.querySelector("#cp-sec").onclick = async () => { const r = await (await fetch("/api/cams", { headers: { "x-token": tok() } })).json(); JV.sendCommand && JV.sendCommand(r.security ? "Güvenlik modunu kapat" : "Güvenlik modunu aç"); };
    poll(); setInterval(poll, 5000);
  }
  async function poll() {
    try {
      const r = await (await fetch("/api/cams", { headers: { "x-token": tok() } })).json();
      cams = r.cams || [];
      badge.innerHTML = "";
      cams.forEach((c) => { const b = document.createElement("button"); b.className = "cam-badge" + (c.online ? "" : " off") + (c.motion ? " mot" : ""); b.textContent = `${c.online ? "●" : "○"} ${c.name}${c.loc ? " · " + c.loc.toUpperCase() : ""}`; b.onclick = () => open(c.id); badge.append(b); });
      panel.querySelector("#cp-sec").classList.toggle("on", !!r.security);
      if (!panel.classList.contains("hidden")) renderTabs();
    } catch (e) {}
  }
  function renderTabs() {
    const t = panel.querySelector("#cp-tabs"); t.innerHTML = "";
    cams.forEach((c) => { const b = document.createElement("button"); b.className = "mini" + (c.id === sel ? " on" : ""); b.textContent = c.name; b.onclick = () => open(c.id); t.append(b); });
    const c = cams.find((x) => x.id === sel);
    panel.querySelector("#cp-info").textContent = c ? `${c.loc || ""} · ${c.online ? "CANLI" : "ÇEVRİMDIŞI"}${c.motion ? " · HAREKET" : ""}` : "";
  }
  function open(id) {
    sel = id || (cams[0] && cams[0].id) || ""; if (!sel) { JV.toast && JV.toast("Bağlı kamera yok. Telefonda JARVIS'i açıp Ayarlar > PLATFORMLAR > 'Bu cihazı kamera yap'.", 8000); return; }
    panel.classList.remove("hidden"); renderTabs(); clearInterval(refresh);
    const img = panel.querySelector("#cp-img");
    const load = () => { img.src = `/api/cams/${encodeURIComponent(sel)}.jpg?viewer=${viewer}&token=${encodeURIComponent(tok())}&t=${Date.now()}`; };
    load(); refresh = setInterval(load, 1000);
  }
  function close() { panel.classList.add("hidden"); panel.classList.remove("full"); clearInterval(refresh); }
  JV.cams = { open, close, list: () => cams, makeThisCamera: () => { LS("jv_role", "kamera"); location.href = location.pathname + "?rol=kamera"; } };

  addEventListener("DOMContentLoaded", () => (isCamRole ? camDevice() : buildViewer()));
  if (document.readyState !== "loading") (isCamRole ? camDevice() : buildViewer());
  JV.isCamRole = isCamRole;
})();
