/* JARVIS MASTER CONTROL: komuta merkezi (canlı sistem/ekip/görev/güvenlik/bağlantı/modül/makro panosu) + çalışma modlarının arayüze uygulanması. */
(function () {
  const JV = (window.JV = window.JV || {});
  const $ = (s, r = document) => r.querySelector(s);
  const esc = (t) => String(t == null ? "" : t).replace(/[&<>"]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" })[c]);
  const hm = (ts) => { if (!ts) return "—"; const d = new Date(ts * 1000); const today = new Date().toDateString() === d.toDateString(); return (today ? "" : d.toLocaleDateString("tr-TR", { day: "2-digit", month: "2-digit" }) + " ") + d.toLocaleTimeString("tr-TR", { hour: "2-digit", minute: "2-digit" }); };
  let root, timer, mode = "normal";

  // ---------- modlar ----------
  JV.applyMode = function (m, opts = {}) {
    mode = m || "normal";
    document.body.className = document.body.className.replace(/\bmode-\S+/g, "").trim();
    document.body.classList.add("mode-" + mode);
    JV.quiet = mode === "sessiz";
    if (!opts.silent) {
      if (mode === "mühendislik" && JV.setView) JV.setView("lab");
      if (mode === "komuta" || mode === "acil") open();
      JV.toast && JV.toast("Çalışma modu: " + mode.toUpperCase());
    }
    if (root) root.querySelectorAll("[data-mode]").forEach((b) => b.classList.toggle("on", b.dataset.mode === mode));
    const t = $("#t-command"); if (t) t.classList.toggle("on", mode !== "normal");
  };

  async function post(body) { return JV.api("/api/command", { body }); }

  function build() {
    if (root) return;
    root = document.createElement("div"); root.id = "command"; root.className = "hidden";
    root.innerHTML = `<div class="mc">
      <header class="mc-head"><div><div class="mc-title">J.A.R.V.I.S. · MASTER CONTROL</div><div class="mc-sub" id="mc-sub">—</div></div>
        <div class="mc-modes" id="mc-modes"></div><button class="mini" id="mc-close">KAPAT ✕</button></header>
      <div class="mc-grid">
        <section class="mc-box mc-sys"><h4>SİSTEM</h4><div id="mc-sys"></div></section>
        <section class="mc-box"><h4>GÜVENLİK</h4><div id="mc-sec"></div></section>
        <section class="mc-box"><h4>BUGÜN</h4><div id="mc-today"></div></section>
        <section class="mc-box mc-wide"><h4>YAPAY ZEKÂ EKİBİ · CANLI</h4><div id="mc-team"></div></section>
        <section class="mc-box"><h4>ZAMANLANMIŞ</h4><div id="mc-sched"></div></section>
        <section class="mc-box"><h4>BAĞLANTILAR · MODELLER</h4><div id="mc-conn"></div></section>
        <section class="mc-box mc-wide"><h4>BİLGİSAYARLARIM <small id="mc-q"></small></h4><div id="mc-nodes"></div>
          <div class="mc-form"><input id="mc-nurl" placeholder="IP (ör. 192.168.1.20)"><input id="mc-ntok" placeholder="o bilgisayarın erişim anahtarı"><button class="mini" id="mc-nadd">BAĞLA</button><button class="mini" id="mc-ndisc">AĞI TARA</button></div></section>
        <section class="mc-box mc-wide"><h4>MODÜLLER <small>(tıkla: aç/kapat)</small></h4><div id="mc-mods" class="mc-chips"></div></section>
        <section class="mc-box"><h4>MAKROLAR</h4><div id="mc-macros"></div>
          <div class="mc-form"><input id="mc-mname" placeholder="ad (ör. film modu)"><input id="mc-msteps" placeholder="adımlar ; ile (ör. mod:sessiz; YouTube'da lofi aç)"><button class="mini" id="mc-msave">KAYDET</button></div></section>
        <section class="mc-box mc-wide"><h4>KURULUM DURUMU</h4><div id="mc-setup"></div></section>
        <section class="mc-box"><h4>SON İŞLEMLER</h4><div id="mc-acts"></div></section>
        <section class="mc-box"><h4>BİLDİRİMLER</h4><div id="mc-notes"></div></section>
      </div></div>`;
    document.body.append(root);
    $("#mc-close", root).onclick = close;
    $("#mc-msave", root).onclick = async () => {
      const n = $("#mc-mname", root).value.trim(), st = $("#mc-msteps", root).value.trim(); if (!n || !st) return;
      await post({ action: "macro_save", name: n, steps: st }); $("#mc-mname", root).value = $("#mc-msteps", root).value = ""; refresh();
    };
    $("#mc-nadd", root).onclick = async () => { const r = await JV.api("/api/node/add", { body: { url: $("#mc-nurl", root).value, token: $("#mc-ntok", root).value } }); JV.toast && JV.toast(typeof r.sonuç === "string" ? r.sonuç : "Bağlandı: " + (r.sonuç && r.sonuç.bağlandı)); refresh(); };
    $("#mc-ndisc", root).onclick = async (e) => { e.target.textContent = "TARANIYOR…"; const r = await JV.api("/api/node/discover"); e.target.textContent = "AĞI TARA";
      const f = r.sonuç; JV.toast && JV.toast(Array.isArray(f) ? f.map((x) => `${x.ad} ${x.adres}${x.bağlı ? " (bağlı)" : ""}`).join(" · ") : f, 15000); if (Array.isArray(f) && f[0] && !f[0].bağlı) $("#mc-nurl", root).value = f[0].adres; };
    root.addEventListener("click", async (e) => {
      const b = e.target.closest("button"); if (!b) return;
      if (b.dataset.mode) { const r = await post({ action: "mode", mode: b.dataset.mode }); if (r.sonuç && r.sonuç.mode) JV.applyMode(r.sonuç.mode, { silent: r.sonuç.mode === "komuta" }); refresh(); }
      else if (b.dataset.mod) { await post({ action: "module", module: b.dataset.mod, on: b.dataset.on !== "1" }); refresh(); }
      else if (b.dataset.run) { b.disabled = true; b.textContent = "…"; const r = await post({ action: "macro", name: b.dataset.run, persona: JV.persona ? JV.persona() : "" }); JV.toast && JV.toast("Makro bitti: " + ((r.sonuç && r.sonuç.adımlar) ? r.sonuç.adımlar.length + " adım" : JSON.stringify(r.sonuç || r.error))); refresh(); }
      else if (b.dataset.del) { await post({ action: "macro_delete", name: b.dataset.del }); refresh(); }
      else if (b.id === "mc-estop") { const t = $("#t-estop"); if (b.dataset.on === "1" && !document.body.classList.contains("estop")) document.body.classList.add("estop"); t && t.click(); setTimeout(refresh, 600); }
    });
  }

  const bar = (label, v, unit = "%") => `<div class="mc-bar"><span>${label}</span><i><b style="width:${Math.min(100, +v || 0)}%" class="${v > 85 ? "hot" : v > 65 ? "warm" : ""}"></b></i><em>${v == null ? "—" : v + unit}</em></div>`;
  const ok = (v) => `<span class="mc-dot ${v ? "ok" : "no"}"></span>`;
  const ST = { bekliyor: "wait", "çalışıyor": "run", bitti: "done", "yeniden yapılıyor": "redo" };

  function render(d) {
    $("#mc-sub", root).textContent = `${new Date().toLocaleString("tr-TR")} · MOD: ${d.mod.toUpperCase()}`;
    $("#mc-modes", root).innerHTML = d.modlar.map((m) => `<button class="mc-mode ${m.etkin ? "on" : ""} m-${m.mod}" data-mode="${m.mod}" title="${esc(m.açıklama)}">${esc(m.ad.toUpperCase())}</button>`).join("");
    const s = d.sistem || {};
    $("#mc-sys", root).innerHTML = bar("CPU", s.cpu_yüzde) + bar("RAM", s.ram_yüzde) + bar("DİSK", s.disk_yüzde) +
      `<div class="mc-kv"><span>Pil</span><b>${esc(s.pil || "—")}</b><span>Açık kalma</span><b>${esc(s.açık_kalma || "—")}</b><span>Ağ ↑/↓</span><b>${s.ağ_gönderilen_mb ?? "—"} / ${s.ağ_alınan_mb ?? "—"} MB</b></div>`;
    const g = d.güvenlik;
    $("#mc-sec", root).innerHTML = `<button id="mc-estop" data-on="${g.acil_durdurma ? 1 : 0}" class="mc-estop ${g.acil_durdurma ? "on" : ""}">${g.acil_durdurma ? "ACİL DURDURMA ETKİN · SIFIRLA" : "■ ACİL DURDUR"}</button>
      <div class="mc-kv"><span>İnternet</span><b>${ok(g.çevrimiçi)}${g.çevrimiçi ? "bağlı" : "YOK"}</b><span>Güvenli mod</span><b>${g.güvenli_mod ? "açık" : "kapalı"}</b><span>Misafir modu</span><b>${g.misafir_modu ? "açık" : "kapalı"}</b></div>`;
    const t = d.bugün;
    $("#mc-today", root).innerHTML = `<div class="mc-big"><b>${t.işlem}</b><span>işlem</span></div><div class="mc-big"><b>${t.işlem ? Math.round(100 * t.başarılı / t.işlem) : 100}%</b><span>başarı</span></div><div class="mc-big"><b>${t.mesaj}</b><span>mesaj</span></div>`;
    $("#mc-team", root).innerHTML = (d.ekip || []).length ? d.ekip.map((r) => {
      const n = r.ajanlar.length, done = r.ajanlar.filter((a) => a.durum === "bitti").length;
      return `<div class="mc-run"><div class="mc-run-h"><b>#${r.no}</b> ${esc(r.hedef)} <em>${r.bitti ? "TAMAMLANDI" : done + "/" + n}</em></div><i class="mc-prog"><b style="width:${n ? 100 * done / n : 0}%"></b></i>
        ${r.ajanlar.map((a) => `<div class="mc-agent ${ST[a.durum] || ""}"><span>${esc(a.rol)}</span><small>${esc(a.görev)}</small><em>${esc(a.durum)}</em></div>`).join("")}</div>`;
    }).join("") : `<div class="note">Şu an çalışan ekip yok. "Ekip kur: …" de, burada canlı izle.</div>` +
      ((d.ekip_geçmiş || []).slice(0, 3).map((h) => `<div class="mc-li"><span>#${h.no} ${esc(h.hedef)}</span><em>${esc(h.durum)}</em></div>`).join(""));
    const sched = [...(d.alarmlar || []).map((a) => ["⏰", hm(a.saat), a.etiket]), ...(d.hatırlatmalar || []).map((a) => ["🔔", hm(a.saat), a.metin]),
      ...(d.görevler || []).map((a) => ["⚙", hm(a.sonraki), a.görev]), ...(d.yapılacaklar || []).map((a) => ["☐", a.öncelik || "", a.metin])];
    $("#mc-sched", root).innerHTML = sched.length ? sched.slice(0, 10).map(([i, w, x]) => `<div class="mc-li"><span>${i} ${esc(x)}</span><em>${esc(w)}</em></div>`).join("") : '<div class="note">Planlanmış bir şey yok.</div>';
    $("#mc-conn", root).innerHTML = `<div class="mc-chips">${Object.entries(d.bağlantılar).map(([k, v]) => `<span class="mc-chip ${v ? "ok" : ""}">${ok(v)}${esc(k)}${typeof v === "number" ? " " + v : ""}</span>`).join("")}</div>
      <div class="mc-chips">${d.modeller.map((m) => `<span class="mc-chip ${m.hazır ? "ok" : ""}">${ok(m.hazır)}${esc(m.ad)}</span>`).join("")}</div>`;
    $("#mc-mods", root).innerHTML = d.modüller.map((m) => `<button class="mc-chip ${m.açık ? "ok" : "off"}" data-mod="${m.modül}" data-on="${m.açık ? 1 : 0}" title="${esc(m.açıklama)}">${ok(m.açık)}${esc(m.modül)} <small>${m.araç}</small></button>`).join("");
    $("#mc-macros", root).innerHTML = d.makrolar.length ? d.makrolar.map((m) => `<div class="mc-li"><span><b>${esc(m.ad)}</b> <small>${esc(m.adımlar.join(" → "))}</small></span><span><button class="mini" data-run="${esc(m.ad)}">▶</button><button class="mini" data-del="${esc(m.ad)}">✕</button></span></div>`).join("") : '<div class="note">Makro yok. Örnek: ad "çalışma modu", adımlar "mod:sessiz; Spotify\'da odak müziği aç; bekle:2; söyle:Odak modu hazır".</div>';
    $("#mc-acts", root).innerHTML = d.işlemler.map((a) => `<div class="mc-li ${a.ok ? "" : "bad"}"><span>${a.ok ? "✓" : "✗"} ${esc(a.araç)} <small>${esc(a.sonuç)}</small></span><em>${hm(a.zaman)}</em></div>`).join("") || '<div class="note">Henüz işlem yok.</div>';
    $("#mc-notes", root).innerHTML = d.bildirimler.map((n) => `<div class="mc-li"><span>${esc(n.metin)}</span><em>${hm(n.zaman)}</em></div>`).join("") || '<div class="note">Bildirim yok.</div>';
    const k = d.kurulum;
    if (k) $("#mc-setup", root).innerHTML = k.bileşenler.filter((x) => !x.durum).map((x) => `<div class="mc-li ${x.zorunlu ? "bad" : ""}"><span>${ok(false)}<b>${esc(x.bileşen)}</b> <small>${esc(x.açar)}</small></span><em>${esc(x.çözüm)}</em></div>`).join("") +
      `<div class="note">${k.bileşenler.filter((x) => x.durum).length}/${k.bileşenler.length} bileşen hazır${k.hazır ? " · zorunlu olanların hepsi tamam ✓" : " · ZORUNLU EKSİK VAR"}</div>`;
    $("#mc-q", root).textContent = d.kuyruk ? `· kuyrukta ${d.kuyruk} iş` : "";
    $("#mc-nodes", root).innerHTML = (d.bilgisayarlar || []).length ? d.bilgisayarlar.map((n) => `<div class="mc-li"><span>${ok(n.çevrimiçi)}<b>${esc(n.ad)}</b> <small>${esc(n.adres)}</small></span><em>${n.çevrimiçi ? `CPU %${Math.round(n.durum.cpu_yüzde || 0)} · RAM %${Math.round(n.durum.ram_yüzde || 0)} · disk %${Math.round(n.durum.disk_yüzde || 0)}${n.durum.pil ? " · " + esc(n.durum.pil) : ""}` : "çevrimdışı"}</em></div>`).join("") : '<div class="note">Başka bilgisayar bağlı değil. O bilgisayarda JARVIS\'i "python run.py --lan" ile aç; ekranda yazan anahtarı buraya gir.</div>';
    if (d.mod !== mode) JV.applyMode(d.mod, { silent: true });
  }

  async function refresh() {
    if (!root || root.classList.contains("hidden")) return;
    try { render(await JV.api("/api/command")); } catch (e) { $("#mc-sub", root).textContent = "Bağlantı hatası: " + e.message; }
  }
  function open() { build(); root.classList.remove("hidden"); refresh(); clearInterval(timer); timer = setInterval(refresh, 3000); }
  function close() { if (root) root.classList.add("hidden"); clearInterval(timer); }
  JV.command = { open, close, refresh, isOpen: () => !!root && !root.classList.contains("hidden") };

  document.addEventListener("keydown", (e) => { if (e.ctrlKey && e.shiftKey && e.key.toLowerCase() === "k") { e.preventDefault(); JV.command.isOpen() ? close() : open(); } });
  document.addEventListener("DOMContentLoaded", () => {
    const b = $("#t-command"); if (b) b.onclick = () => (JV.command.isOpen() ? close() : open());
    setTimeout(async () => { try { const s = await JV.api("/api/settings"); JV.applyMode(s.work_mode || "normal", { silent: true }); } catch (e) {} }, 1200);
  });
})();
