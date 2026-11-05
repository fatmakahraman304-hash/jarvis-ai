/* AR MASAÜSTÜ — kamera görüntüsünün üstünde elle yönetilen HUD.
   ✋ Avucunu aç ve 0,8 sn sabit tut → avucunun çevresinde DAİRESEL MENÜ (ortada saat). Bir öğeye işaret parmağınla dokun (0,5 sn bekle) ya da çimdikle seç.
   Alttaki DOCK: Saat · Sistem · Hava · Haberler · İşler · Müzik · Dünya · Kılavuz · Kapat — parmakla üstünde bekle ya da çimdikle.
   PANELLER: çimdikle tut → taşı · iki elle çimdikle → büyüt/küçült · ✕ ile kapat. Fareyle de sürüklenir. */
(function () {
  const JV = (window.JV = window.JV || {});
  const esc = (s) => String(s == null ? "" : s).replace(/[&<>"]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]));
  const ITEMS = [["clock", "🕒", "Saat"], ["system", "📊", "Sistem"], ["weather", "⛅", "Hava"], ["news", "📰", "Haberler"], ["tasks", "✅", "İşler"], ["music", "🎵", "Müzik"], ["globe", "🌍", "Dünya"], ["guide", "❔", "Kılavuz"]];
  let layer, dock, menu = null, on = false, panels = {}, z = 10, timers = {};
  const hov = {}; // el başına: {el, since}
  const grab = {}; // el başına: {panel, dx, dy}
  let twoHand = null;

  function build() {
    if (layer) return;
    const stage = document.getElementById("arstage");
    layer = document.createElement("div"); layer.id = "ardesk"; stage.append(layer);
    dock = document.createElement("div"); dock.className = "ad-dock";
    dock.innerHTML = ITEMS.map(([k, i, t]) => `<button data-air="${k}" class="ad-ico"><span>${i}</span><small>${t}</small></button>`).join("") + `<button data-air="close" class="ad-ico ad-x"><span>✕</span><small>Kapat</small></button>`;
    layer.append(dock);
    dock.addEventListener("click", (e) => { const b = e.target.closest("[data-air]"); if (b) act(b.dataset.air, b); });
  }
  function act(k, elx) {
    if (k === "close") return api.toggle(false);
    if (k === "globe") { JV.handfx && JV.handfx.stop(); JV.setView && JV.setView("globe"); setTimeout(() => JV.gesture && JV.gesture.start("nesne"), 400); JV.toast && JV.toast("🌍 Dünya: açık elle döndür, başparmak+işaretle yakınlaştır, hızlı savurunca görünüm değişir", 7000); return; }
    if (k.startsWith("p:")) { const [, pid, a] = k.split(":"); return panelAct(pid, a, elx); }
    openPanel(k);
  }

  // ---------------- paneller ----------------
  const TITLES = { clock: "SAAT", system: "SİSTEM", weather: "HAVA", news: "HABERLER", tasks: "İŞLER", music: "MÜZİK", guide: "KILAVUZ" };
  function openPanel(k) {
    if (!TITLES[k]) return;
    if (panels[k]) { panels[k].style.zIndex = ++z; flash(panels[k]); return; }
    const p = document.createElement("div"); p.className = "ad-panel"; p.dataset.panel = k;
    const n = Object.keys(panels).length, W = innerWidth;
    p.style.left = Math.min(W - 340, 80 + (n % 3) * 330) + "px"; p.style.top = (90 + Math.floor(n / 3) * 230 + (n % 2) * 20) + "px"; p.style.zIndex = ++z;
    p.innerHTML = `<div class="ad-ph"><b>${TITLES[k]}</b><button data-air="p:${k}:close" class="ad-pc">✕</button></div><div class="ad-pb"></div>`;
    layer.append(p); panels[k] = p;
    p.querySelector(".ad-pc").onclick = () => closePanel(k);
    mouseDrag(p);
    fill(k); clearInterval(timers[k]); timers[k] = setInterval(() => fill(k), { clock: 1000, system: 2000, weather: 600000, news: 600000, tasks: 30000, music: 0, guide: 0 }[k] || 1e9);
    flash(p); JV.fxSound && JV.fxSound("lift");
  }
  function closePanel(k) { const p = panels[k]; if (!p) return; clearInterval(timers[k]); p.classList.add("out"); setTimeout(() => p.remove(), 300); delete panels[k]; }
  function flash(p) { p.classList.remove("flash"); void p.offsetWidth; p.classList.add("flash"); }
  const ring = (v, lbl, col) => { const r = 26, c = 2 * Math.PI * r, k = Math.max(0, Math.min(100, v || 0)) / 100; return `<div class="ad-ring"><svg viewBox="0 0 64 64"><circle cx="32" cy="32" r="${r}" class="bg"/><circle cx="32" cy="32" r="${r}" class="fg" style="stroke:${col};stroke-dasharray:${c};stroke-dashoffset:${c * (1 - k)}"/></svg><b>${v == null ? "—" : Math.round(v) + "%"}</b><small>${lbl}</small></div>`; };
  async function fill(k) {
    const p = panels[k]; if (!p) return; const b = p.querySelector(".ad-pb");
    const get = (u) => (JV.api ? JV.api(u) : fetch(u).then((r) => r.json()));
    try {
      if (k === "clock") { const t = new Date(); b.innerHTML = `<div class="ad-clock">${t.toLocaleTimeString("tr-TR", { hour: "2-digit", minute: "2-digit" })}<small>:${String(t.getSeconds()).padStart(2, "0")}</small></div><div class="ad-date">${t.toLocaleDateString("tr-TR", { weekday: "long", day: "numeric", month: "long", year: "numeric" })}</div>`; }
      if (k === "system") { const s = await get("/api/hud/system"); const col = (v) => (v > 85 ? "#ff6b6b" : v > 60 ? "#ffcf5a" : "#00e5ff"); b.innerHTML = `<div class="ad-rings">${ring(s.cpu, "CPU", col(s.cpu))}${ring(s.ram, "RAM", col(s.ram))}${ring(s.gpu, "GPU", col(s.gpu))}${ring(s.disk, "DİSK", col(s.disk))}</div>`; }
      if (k === "weather") { const w = await get("/api/hud/weather"); if (w.error) throw new Error(w.error); b.innerHTML = `<div class="ad-wx">${JV.wxIcon ? JV.wxIcon(w.ikon, 58) : ""}<div><b>${w.derece}°</b><span>${esc(w.şehir)} · ${esc(w.durum)}</span><small>↑${w.yüksek}° ↓${w.düşük}° · 💧%${w.yağmur}</small></div></div><div class="ad-wxd">${(w.günler || []).slice(1, 6).map((d) => `<div><small>${d.gün}</small>${JV.wxIcon ? JV.wxIcon(d.ikon, 26) : ""}<b>${d.max}°</b></div>`).join("")}</div>`; }
      if (k === "news") { const n = await get("/api/hud/news"); b.innerHTML = `<ul class="ad-list">${(Array.isArray(n) ? n : []).slice(0, 5).map((x) => `<li>${esc(x.başlık)} <i>${esc(x.kaynak)}</i></li>`).join("") || "<li>haber yok</li>"}</ul>`; }
      if (k === "tasks") { const t = await get("/api/hud/tasks"); b.innerHTML = `<ul class="ad-list">${(Array.isArray(t) ? t : []).slice(0, 7).map((x) => `<li>${x.gecikti ? "⚠ " : "□ "}${esc(x.text)}${x.due ? ` <i>${esc(x.due)}</i>` : ""}</li>`).join("") || "<li>Yapılacak iş yok 🎉</li>"}</ul>`; }
      if (k === "music") b.innerHTML = `<div class="ad-music">${[["previous", "⏮"], ["play_pause", "⏯"], ["next", "⏭"], ["volume_down", "🔉"], ["volume_up", "🔊"], ["mute", "🔇"]].map(([a, i]) => `<button data-air="p:music:${a}">${i}</button>`).join("")}</div><small class="note">Windows medya tuşları (Spotify, YouTube…)</small>`;
      if (k === "guide") b.innerHTML = `<ul class="ad-list"><li>✋ sabit tut → dairesel menü</li><li>☝ öğede bekle / 🤏 çimdik → seç</li><li>🤏 panelde çimdik → taşı</li><li>🤏🤏 iki elle → büyüt</li><li>✋ ateş · ✋✋ mühür · ☝☝ şimşek</li><li>👍 komut · ✌ mikrofon · ✊ sus</li></ul>`;
    } catch (e) { b.innerHTML = `<p class="dim">${esc(e.message)}</p>`; }
  }
  function panelAct(pid, a) {
    if (a === "close") return closePanel(pid);
    if (pid === "music") { fetch("/api/gesture/media", { method: "POST", headers: { "Content-Type": "application/json", "x-token": JV.token || "" }, body: JSON.stringify({ action: a, steps: 2 }) }).catch(() => {}); JV.fxSound && JV.fxSound("found"); }
  }
  function mouseDrag(p) {
    const h = p.querySelector(".ad-ph"); let d = null;
    h.onpointerdown = (e) => { if (e.target.closest("button")) return; d = [e.clientX - p.offsetLeft, e.clientY - p.offsetTop]; p.style.zIndex = ++z; h.setPointerCapture(e.pointerId); };
    h.onpointermove = (e) => { if (d) { p.style.left = e.clientX - d[0] + "px"; p.style.top = e.clientY - d[1] + "px"; } };
    h.onpointerup = () => (d = null);
  }

  // ---------------- dairesel menü ----------------
  function openMenu(x, y) {
    closeMenu();
    menu = document.createElement("div"); menu.className = "ad-menu"; menu.style.left = x + "px"; menu.style.top = y + "px";
    const R = 105;
    menu.innerHTML = `<div class="ad-mc"><b>${new Date().toLocaleTimeString("tr-TR", { hour: "2-digit", minute: "2-digit" })}</b><small>${new Date().toLocaleDateString("tr-TR", { weekday: "short" })}</small></div>` +
      ITEMS.map(([k, i, t], n) => { const a = -Math.PI / 2 + (n / ITEMS.length) * Math.PI * 2; return `<button data-air="${k}" class="ad-mi" style="left:${Math.cos(a) * R}px;top:${Math.sin(a) * R}px" title="${t}"><span>${i}</span><small>${t}</small></button>`; }).join("");
    layer.append(menu); menu._t = performance.now(); menu._x = x; menu._y = y;
    menu.addEventListener("click", (e) => { const b = e.target.closest("[data-air]"); if (b) { act(b.dataset.air, b); closeMenu(); } });
    JV.fxSound && JV.fxSound("lift");
  }
  function closeMenu() { if (menu) { menu.remove(); menu = null; } }

  // ---------------- her kare (handfx çağırır) ----------------
  function frame(ctx, hands, M, now) {
    if (!on) return { busy: false };
    let busy = false;
    const seen = {};
    // iki elle büyütme: iki çimdik aynı paneldeyse
    const pin = hands.filter((h) => h.pinch);
    if (pin.length === 2) {
      const pa = panelAt(pin[0].pp.x, pin[0].pp.y), pb = panelAt(pin[1].pp.x, pin[1].pp.y);
      if (pa && pa === pb) {
        const d = Math.hypot(pin[0].pp.x - pin[1].pp.x, pin[0].pp.y - pin[1].pp.y);
        if (!twoHand || twoHand.p !== pa) twoHand = { p: pa, d0: d, s0: +(pa.dataset.scale || 1) };
        const s = Math.max(0.6, Math.min(2.2, twoHand.s0 * d / twoHand.d0)); pa.dataset.scale = s; pa.style.transform = `scale(${s})`;
        return { busy: true };
      }
    } else twoHand = null;
    for (const h of hands) {
      const id = h.handed; seen[id] = true;
      const tip = h.P[8], pt = h.pinch ? h.pp : tip;
      // tutulan paneli taşı
      const g = grab[id];
      if (g) {
        if (h.pinch) { g.panel.style.left = pt.x - g.dx + "px"; g.panel.style.top = pt.y - g.dy + "px"; busy = true; drawCursor(ctx, pt, "#ffcf5a", 1); continue; }
        delete grab[id];
      }
      const target = airAt(pt.x, pt.y);
      // çimdik başladı
      if (h.pinch && !h.st.deskPinch) {
        h.st.deskPinch = true;
        if (target) { fire(target); busy = true; continue; }
        const p = panelAt(pt.x, pt.y);
        if (p) { grab[id] = { panel: p, dx: pt.x - p.offsetLeft, dy: pt.y - p.offsetTop }; p.style.zIndex = ++z; busy = true; continue; }
      }
      if (!h.pinch) h.st.deskPinch = false;
      // parmakla üstünde bekle (dwell)
      if ((h.pointing || h.pinch) && target) {
        busy = true;
        const s = hov[id];
        if (!s || s.el !== target) hov[id] = { el: target, since: now };
        const k = (now - hov[id].since) / 550;
        drawCursor(ctx, tip, "#00e5ff", Math.min(1, k));
        target.classList.add("hover");
        if (k >= 1 && !hov[id].fired) { hov[id].fired = true; fire(target); }
      } else { if (hov[id]) hov[id].el.classList.remove("hover"); delete hov[id]; if ((h.pointing || h.pinch) && (panelAt(tip.x, tip.y) || (menu && near(tip)))) { busy = true; drawCursor(ctx, tip, "#00e5ff", 0); } }
      // avucu sabit tut → menü
      const still = Math.hypot(h.st.vel[0], h.st.vel[1]) < 3.5;
      if (h.pose === "open" && still && hands.length === 1) { h.st.menuSince = h.st.menuSince || now; if (now - h.st.menuSince > 800 && !menu && !panelAt(h.P[9].x, h.P[9].y)) { openMenu(h.P[9].x, h.P[9].y); } }
      else h.st.menuSince = 0;
      if (menu && h.pose === "open" && still) { menu.style.left = h.P[9].x + "px"; menu.style.top = h.P[9].y + "px"; menu._t = now; }
    }
    Object.keys(hov).forEach((k) => { if (!seen[k]) { hov[k].el.classList.remove("hover"); delete hov[k]; } });
    if (menu && now - menu._t > 4000) closeMenu();
    if (menu) busy = busy || hands.some((h) => h.pose === "open");
    return { busy, menu: !!menu };
  }
  function near(p) { return menu && Math.hypot(p.x - menu._x, p.y - menu._y) < 160; }
  function airAt(x, y) { const e = document.elementFromPoint(x, y); const a = e && e.closest && e.closest("#ardesk [data-air]"); return a || null; }
  function panelAt(x, y) { const e = document.elementFromPoint(x, y); return (e && e.closest && e.closest(".ad-panel")) || null; }
  function fire(t) { t.classList.add("press"); setTimeout(() => t.classList.remove("press"), 250); JV.fxSound && JV.fxSound("found"); act(t.dataset.air, t); if (t.closest(".ad-menu")) closeMenu(); }
  function drawCursor(ctx, p, col, k) {
    ctx.strokeStyle = col; ctx.lineWidth = 2; ctx.shadowColor = col; ctx.shadowBlur = 10;
    ctx.beginPath(); ctx.arc(p.x, p.y, 12, 0, 6.29); ctx.stroke();
    if (k > 0) { ctx.lineWidth = 4; ctx.beginPath(); ctx.arc(p.x, p.y, 18, -Math.PI / 2, -Math.PI / 2 + 6.283 * k); ctx.stroke(); }
    ctx.shadowBlur = 0; ctx.lineWidth = 1;
  }
  const api = {
    get on() { return on; },
    toggle(v, panel) {
      build(); on = v == null ? !on : !!v; layer.classList.toggle("on", on);
      if (!on) { closeMenu(); Object.keys(panels).forEach(closePanel); }
      else { JV.toast && JV.toast("🖥 AR masaüstü: avucunu açıp sabit tut → menü · alttaki dock · paneli çimdikle taşı", 6000); if (panel) openPanel(panel); }
    },
    openPanel, closePanel, openMenu, closeMenu, frame, _panels: () => Object.keys(panels), _menu: () => !!menu,
  };
  JV.ardesk = api;
})();
