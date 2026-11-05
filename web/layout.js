/* KOMUTA MERKEZİ DÜZENİ (geniş ekran ≥ 1000 px)
   Üst: ince bar (marka · kişilik + dünyalar · durum hapı · saat/tarih/hava)
   Sol sütun: SİSTEM · AĞ · DURUM · İŞLEMLER · GÖREVLER · MODELLER (köşeli kutular)
   Orta: köşeli çerçeveli sahne (çekirdek/dünyalar), altyazı ve onaylar sahnenin içinde
   Sağ sütun: İLETİŞİM (diyalog) + KOMUT kutusu (öneri çipleri, yazı/mikrofon, hızlı düğmeler)
   Alt: durum şeridi (motor, ses, mikrofon, sürüm, kısayollar)
   Var olan tüm öğeler kimlikleri korunarak taşınır; bütün özellikler aynen çalışır. Dar ekranda eski (dikey) düzen kalır. */
(function () {
  const JV = (window.JV = window.JV || {});
  const $ = (s, r = document) => r.querySelector(s);
  const WIDE = 1000;
  const mk = (tag, cls, html) => { const e = document.createElement(tag); if (cls) e.className = cls; if (html != null) e.innerHTML = html; return e; };
  function section(title, meta = "") {
    const s = mk("section", "cc-box"); s.append(mk("div", "cc-h", `<span>${title}</span><i>${meta}</i>`)); return s;
  }
  function build() {
    if (JV.isCamRole || innerWidth < WIDE || document.body.classList.contains("cc")) return;
    document.body.classList.add("cc");
    // ---------- üst bar ----------
    const top = $("#top"); const mid = mk("div", "cc-mid");
    const per = $("#personas"), views = $("#views"), status = $("#status-line");
    if (per) mid.append(per); if (views) mid.append(views);
    top.insertBefore(mid, $(".top-right", top));
    if (status) { status.classList.add("cc-pill"); top.insertBefore(status, $(".top-right", top)); }
    // ---------- sol sütun ----------
    const left = $("#left");
    if (left) {
      const kids = [...left.children]; left.innerHTML = "";
      const take = (sel) => kids.find((k) => k.matches && k.matches(sel));
      const sys = section("SİSTEM", "CANLI"); [take(".gauges")].filter(Boolean).forEach((n) => sys.append(n)); left.append(sys);
      const net = section("AĞ", '<b id="cc-net-v">—</b>'); net.append(mk("canvas", "cc-spark", "")); net.querySelector("canvas").id = "cc-net"; left.append(net);
      const st = section("DURUM", ""); const kv = take("#sysinfo"); if (kv) st.append(kv); left.append(st);
      const pr = section("İŞLEMLER", "RAM"); const pl = take("#procs"); if (pl) pr.append(pl); left.append(pr);
      const tk = section("GÖREVLER", '<b id="cc-task-n"></b>'); tk.append(mk("ul", "cc-tasks", "")); tk.querySelector("ul").id = "cc-tasks"; left.append(tk);
      const md = section("MODELLER", ""); const pm = take("#prov-mini"); if (pm) md.append(pm); left.append(md);
    }
    // ---------- sağ sütun ----------
    const right = $("#right");
    if (right) {
      const t = $(".panel-title", right); if (t) { t.classList.add("cc-h"); t.firstChild && (t.firstChild.textContent = "İLETİŞİM"); }
      const cmd = mk("section", "cc-cmd"); cmd.append(mk("div", "cc-h", "<span>KOMUT</span><i>Ctrl+K · palet</i>"));
      const chips = $("#chips"), ask = $("#ask"), row = $("#bottom .ctrl-row");
      if (chips) cmd.append(chips); if (ask) cmd.append(ask); if (row) { row.classList.add("cc-keys"); cmd.append(row); }
      right.append(cmd);
    }
    const bottom = $("#bottom"); if (bottom) bottom.classList.add("cc-empty");
    // ---------- orta sahne çerçevesi ----------
    const fr = mk("div", "", `<i class="c1"></i><i class="c2"></i><i class="c3"></i><i class="c4"></i><div class="cc-st-l"><b id="cc-view">ÇEKİRDEK</b><span id="cc-sub">// BEKLEMEDE</span></div><div class="cc-st-r"><span class="cc-rec">●</span> CANLI · <span id="cc-fps"></span></div>`);
    fr.id = "cc-stage"; document.body.append(fr);
    ["#live-caption", "#confirms"].forEach((s) => { const e = $(s); if (e) e.classList.add("cc-in-stage"); });
    // ---------- alt durum şeridi ----------
    const foot = mk("footer", "", `<span>MOTOR <b id="cc-f-model">—</b></span><span>SES <b id="cc-f-voice">—</b></span><span>MİKROFON <b id="cc-f-mic">HAZIR</b></span><span>KİŞİLİK <b id="cc-f-per">—</b></span><span class="sp"></span><span>⌘K KOMUT PALETİ</span><span>␣ KONUŞ</span><span>ESC SUSTUR</span><span id="cc-f-ver"></span>`);
    foot.id = "cc-foot"; document.body.append(foot);
    live();
    dispatchEvent(new Event("resize")); // çekirdek merkezini sahneye göre yeniden hesapla
  }

  // ---------- canlı veriler ----------
  let netHist = [], lastNet = null;
  async function pollNet() {
    try {
      const s = await JV.api("/api/system"); const n = s.ağ_mb; if (!n) return;
      const tot = n.gönderilen + n.alınan, now = Date.now();
      if (lastNet) { const mbps = Math.max(0, (tot - lastNet.v) / ((now - lastNet.t) / 1000)); netHist.push(mbps); netHist = netHist.slice(-60); $("#cc-net-v").textContent = mbps < 1 ? Math.round(mbps * 1000) + " KB/s" : mbps.toFixed(1) + " MB/s"; drawSpark(); }
      lastNet = { v: tot, t: now };
    } catch (e) {}
  }
  function drawSpark() {
    const c = $("#cc-net"); if (!c) return; const w = (c.width = c.clientWidth * 2), h = (c.height = 70), g = c.getContext("2d");
    const mx = Math.max(0.05, ...netHist); g.clearRect(0, 0, w, h);
    const col = getComputedStyle(document.body).getPropertyValue("--c").trim() || "#38d6ff";
    g.strokeStyle = "rgba(255,255,255,.06)"; for (let y = 0; y < h; y += 14) { g.beginPath(); g.moveTo(0, y); g.lineTo(w, y); g.stroke(); }
    g.beginPath(); netHist.forEach((v, i) => { const x = (i / 59) * w, y = h - 4 - (v / mx) * (h - 10); i ? g.lineTo(x, y) : g.moveTo(x, y); });
    g.strokeStyle = col; g.lineWidth = 2; g.stroke();
    g.lineTo(((netHist.length - 1) / 59) * w, h); g.lineTo(0, h); g.closePath(); g.globalAlpha = 0.15; g.fillStyle = col; g.fill(); g.globalAlpha = 1;
  }
  async function pollTasks() {
    try {
      const t = await JV.api("/api/hud/tasks"); const ul = $("#cc-tasks"); if (!ul) return;
      const list = Array.isArray(t) ? t : [];
      $("#cc-task-n").textContent = list.length ? list.length + " AÇIK" : "";
      ul.innerHTML = list.slice(0, 5).map((x) => `<li class="${x.gecikti ? "late" : ""}"><i>${x.gecikti ? "!" : "▸"}</i>${String(x.text).replace(/</g, "&lt;")}${x.due ? `<small>${x.due}</small>` : ""}</li>`).join("") || `<li class="none">Açık iş yok — "yapılacaklara ekle: …"</li>`;
    } catch (e) {}
  }
  function live() {
    pollNet(); setInterval(pollNet, 3000); pollTasks(); setInterval(pollTasks, 30000);
    const sync = () => {
      if (document.body.classList.contains("stage-busy")) return syncFoot();
      const st = $("#status-text"); $("#cc-sub").textContent = "// " + (st ? st.textContent : "");
      const v = document.querySelector("#views button.on"); $("#cc-view").textContent = v ? v.textContent.replace(/^[^\p{L}]+/u, "").trim() : "ÇEKİRDEK";
    };
    const syncFoot = () => {
      const mb = $("#model-badge"); $("#cc-f-model").textContent = mb ? mb.textContent.replace(/^MODEL:\s*/, "").split("·").pop().trim() || "—" : "—";
      const pn = $("#p-name"); $("#cc-f-per").textContent = pn ? pn.textContent : "—";
      const vb = $("#t-voice"); $("#cc-f-voice").textContent = vb && vb.classList.contains("on") ? "AÇIK" : "KAPALI";
      $("#cc-f-mic").textContent = document.body.classList.contains("listening") ? "DİNLİYOR" : JV.speaking ? "KONUŞUYOR" : "HAZIR";
      $("#cc-f-ver").textContent = JV.state && JV.state.version ? "v" + JV.state.version : "";
    };
    const all = () => { sync(); syncFoot(); };
    all(); setInterval(all, 700);
    let fr = 0, t0 = performance.now(); (function f() { fr++; const n = performance.now(); if (n - t0 > 1000) { const e = $("#cc-fps"); if (e) e.textContent = fr + " FPS"; fr = 0; t0 = n; } requestAnimationFrame(f); })();
  }
  // geniş ↔ dar arasında geçilirse sayfayı yeniden kur (öğeler taşındığı için)
  let wasWide = innerWidth >= WIDE, rt = 0;
  addEventListener("resize", () => { clearTimeout(rt); rt = setTimeout(() => { const w = innerWidth >= WIDE; if (w !== wasWide && !JV.isCamRole) location.reload(); }, 600); });
  // shell.js çipleri oluşturduktan sonra çalışsın
  const go = () => setTimeout(build, 0);
  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", go); else go();
  JV.layout = { build, wide: () => document.body.classList.contains("cc") };
})();
