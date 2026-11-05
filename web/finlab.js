/* FİNANS LABORATUVARI: portföy (canlı değer, kâr/zarar, dağılım halkası), strateji geri testi (özsermaye eğrisi), Monte Carlo (olasılık bantları), kredi. */
(function () {
  const JV = (window.JV = window.JV || {});
  const $ = (s, r = document) => r.querySelector(s);
  const esc = (t) => String(t == null ? "" : t).replace(/[&<>"]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" })[c]);
  const fmt = (n, d = 0) => (n == null || isNaN(n) ? "—" : Number(n).toLocaleString("tr-TR", { maximumFractionDigits: d }));
  const css = (v) => getComputedStyle(document.documentElement).getPropertyValue(v).trim() || "#38d6ff";
  let root, tab = "portfolio";

  function build() {
    if (root) return; root = document.createElement("div"); root.id = "finlab"; root.className = "hidden";
    root.innerHTML = `<div class="fl-card"><div class="s-head"><span>FİNANS LABORATUVARI</span><button class="mini" id="fl-x">KAPAT ✕</button></div>
      <div class="s-tabs fl-tabs">${[["portfolio", "PORTFÖY"], ["backtest", "GERİ TEST"], ["montecarlo", "MONTE CARLO"], ["loan", "KREDİ"]].map(([k, t]) => `<button data-t="${k}">${t}</button>`).join("")}</div>
      <div id="fl-form" class="cam-row fl-form"></div><div id="fl-out"></div><canvas id="fl-cv" width="900" height="300"></canvas>
      <div class="note">Bilgi amaçlıdır, yatırım tavsiyesi değildir. Geçmiş getiri geleceği garanti etmez.</div></div>`;
    document.body.append(root);
    $("#fl-x", root).onclick = () => root.classList.add("hidden");
    root.querySelectorAll("[data-t]").forEach((b) => (b.onclick = () => show(b.dataset.t)));
  }
  const FORMS = {
    portfolio: `<input id="f-sym" placeholder="Sembol (THYAO.IS, AAPL, altın, bitcoin)"><input id="f-qty" type="number" placeholder="Adet" style="max-width:90px"><input id="f-bp" type="number" placeholder="Alış (ops.)" style="max-width:110px"><button class="mini" id="f-go">EKLE</button><button class="mini" id="f-ref">YENİLE</button>`,
    backtest: `<input id="f-sym" placeholder="Sembol" value="XU100.IS"><select id="f-st"><option value="sma">SMA kesişimi</option><option value="rsi">RSI 30/70</option><option value="hold">Al-tut</option></select><input id="f-s" type="number" value="50" style="max-width:70px"><input id="f-l" type="number" value="200" style="max-width:70px"><select id="f-p"><option>1y</option><option>2y</option><option selected>5y</option><option>10y</option><option>max</option></select><button class="mini" id="f-go">TEST ET</button>`,
    montecarlo: `<label>Başlangıç<input id="f-i" type="number" value="100000"></label><label>Aylık<input id="f-m" type="number" value="5000"></label><label>Yıl<input id="f-y" type="number" value="20"></label><label>Getiri %<input id="f-r" type="number" value="10"></label><label>Oynaklık %<input id="f-v" type="number" value="18"></label><label>Enflasyon %<input id="f-inf" type="number" value="0"></label><label>Hedef<input id="f-g" type="number" value="0"></label><button class="mini" id="f-go">SİMÜLE ET</button>`,
    loan: `<label>Tutar<input id="f-pr" type="number" value="1000000"></label><label>Yıllık faiz %<input id="f-ar" type="number" value="40"></label><label>Ay<input id="f-mo" type="number" value="36"></label><button class="mini" id="f-go">HESAPLA</button>`,
  };
  const v = (id) => +($("#" + id, root) || {}).value || 0;
  async function run() {
    const out = $("#fl-out", root); out.textContent = "hesaplanıyor…";
    let r;
    try {
      if (tab === "portfolio") { const s = $("#f-sym", root).value.trim(); if (s && v("f-qty")) await JV.api("/api/finlab/add", { body: { symbol: s, quantity: v("f-qty"), buy_price: v("f-bp") } }); r = await JV.api("/api/finlab/portfolio"); }
      else if (tab === "backtest") r = await JV.api("/api/finlab/backtest", { body: { symbol: $("#f-sym", root).value, strategy: $("#f-st", root).value, short: v("f-s"), long: v("f-l"), period: $("#f-p", root).value } });
      else if (tab === "montecarlo") r = await JV.api("/api/finlab/montecarlo", { body: { initial: v("f-i"), monthly: v("f-m"), years: v("f-y"), annual_return: v("f-r"), volatility: v("f-v"), inflation: v("f-inf"), goal: v("f-g") } });
      else r = await JV.api("/api/finlab/loan", { body: { principal: v("f-pr"), annual_rate: v("f-ar"), months: v("f-mo") } });
    } catch (e) { r = { error: e.message }; }
    render(r);
  }
  function show(t, data) {
    build(); tab = t; root.classList.remove("hidden");
    root.querySelectorAll("[data-t]").forEach((b) => b.classList.toggle("active", b.dataset.t === t));
    $("#fl-form", root).innerHTML = FORMS[t]; $("#f-go", root).onclick = run; const rf = $("#f-ref", root); if (rf) rf.onclick = run;
    $("#fl-out", root).innerHTML = ""; clear();
    if (data) render(data); else if (t === "portfolio") run();
  }
  function clear() { const c = $("#fl-cv", root); c.getContext("2d").clearRect(0, 0, c.width, c.height); c.style.display = "none"; }
  function lines(series, labels, opts = {}) {
    const c = $("#fl-cv", root), g = c.getContext("2d"); c.style.display = "block";
    const W = c.width, H = c.height, P = 44; g.clearRect(0, 0, W, H);
    const all = series.flatMap((s) => s.data).filter((x) => x != null); const mn = opts.min ?? Math.min(...all), mx = Math.max(...all);
    const X = (i, n) => P + (i / Math.max(1, n - 1)) * (W - P - 10), Y = (y) => H - 24 - ((y - mn) / (mx - mn || 1)) * (H - 40);
    g.strokeStyle = "rgba(120,160,180,.25)"; g.fillStyle = "#7f9aab"; g.font = "11px monospace";
    for (let k = 0; k <= 4; k++) { const y = mn + (mx - mn) * k / 4; g.beginPath(); g.moveTo(P, Y(y)); g.lineTo(W - 10, Y(y)); g.stroke(); g.fillText(opts.fmt ? opts.fmt(y) : fmt(y, 2), 2, Y(y) + 4); }
    if (labels) { [0, Math.floor(labels.length / 2), labels.length - 1].forEach((i) => g.fillText(labels[i], Math.min(W - 80, X(i, labels.length) - 20), H - 6)); }
    if (opts.band) { const [lo, hi, col] = opts.band; g.fillStyle = col; g.beginPath(); lo.forEach((y, i) => (i ? g.lineTo(X(i, lo.length), Y(y)) : g.moveTo(X(i, lo.length), Y(y)))); for (let i = hi.length - 1; i >= 0; i--) g.lineTo(X(i, hi.length), Y(hi[i])); g.closePath(); g.fill(); }
    if (opts.band2) { const [lo, hi, col] = opts.band2; g.fillStyle = col; g.beginPath(); lo.forEach((y, i) => (i ? g.lineTo(X(i, lo.length), Y(y)) : g.moveTo(X(i, lo.length), Y(y)))); for (let i = hi.length - 1; i >= 0; i--) g.lineTo(X(i, hi.length), Y(hi[i])); g.closePath(); g.fill(); }
    series.forEach((s) => { g.strokeStyle = s.color; g.lineWidth = s.w || 2; g.beginPath(); s.data.forEach((y, i) => (i ? g.lineTo(X(i, s.data.length), Y(y)) : g.moveTo(X(i, s.data.length), Y(y)))); g.stroke(); });
    let lx = P + 6; series.forEach((s) => { g.fillStyle = s.color; g.fillRect(lx, 8, 12, 4); g.fillStyle = "#cfefff"; g.fillText(s.name, lx + 16, 13); lx += g.measureText(s.name).width + 40; });
  }
  function donut(items) {
    const c = $("#fl-cv", root), g = c.getContext("2d"); c.style.display = "block"; g.clearRect(0, 0, c.width, c.height);
    const cols = ["#38d6ff", "#22e39a", "#ffb020", "#b37dff", "#ff5c7a", "#5cc8ff", "#f15bb5", "#9be564"]; let a = -Math.PI / 2; const tot = items.reduce((s, x) => s + x.v, 0) || 1;
    items.forEach((it, i) => { const da = it.v / tot * Math.PI * 2; g.beginPath(); g.arc(150, 150, 120, a, a + da); g.arc(150, 150, 72, a + da, a, true); g.closePath(); g.fillStyle = cols[i % cols.length]; g.fill(); a += da;
      g.fillRect(320, 30 + i * 24, 14, 14); g.fillStyle = "#cfefff"; g.font = "13px sans-serif"; g.fillText(`${it.n}  %${fmt(it.v / tot * 100, 1)}`, 342, 42 + i * 24); });
  }
  function kv(o) { return `<div class="wp-grid fl-kv">${Object.entries(o).filter(([, x]) => typeof x !== "object").map(([k, x]) => `<i>${esc(k.replace(/_/g, " "))}</i><b>${typeof x === "number" ? fmt(x, 2) : esc(x)}</b>`).join("")}</div>`; }
  function render(r) {
    const out = $("#fl-out", root); clear();
    if (!r || r.error) { out.textContent = (r && r.error) || "Hata"; return; }
    if (r.mesaj) { out.textContent = r.mesaj; return; }
    if (tab === "portfolio") {
      out.innerHTML = `<table class="fl-t"><tr><th>Varlık</th><th>Adet</th><th>Maliyet</th><th>Fiyat</th><th>Günlük</th><th>Değer</th><th>K/Z</th><th>Pay</th><th></th></tr>${r.varlıklar.map((a) => `<tr><td>${esc(a.ad)} <small>${esc(a.sembol)}</small></td><td>${fmt(a.adet, 4)}</td><td>${fmt(a.maliyet, 2)}</td><td>${fmt(a.fiyat, 2)} ${esc(a.para)}</td><td class="${a["günlük_%"] >= 0 ? "up" : "dn"}">${fmt(a["günlük_%"], 2)}%</td><td>${fmt(a.değer, 2)}</td><td class="${a.kâr_zarar >= 0 ? "up" : "dn"}">${fmt(a.kâr_zarar, 2)} (${fmt(a["kâr_zarar_%"], 1)}%)</td><td>${fmt(a["pay_%"], 1)}%</td><td><button class="mini" data-rm="${esc(a.sembol)}">✕</button></td></tr>`).join("")}</table>
        <div class="fl-tot">Toplam: <b>${fmt(r.toplam_TL, 0)} TL</b> · K/Z: <b class="${r.kâr_zarar_TL >= 0 ? "up" : "dn"}">${fmt(r.kâr_zarar_TL, 0)} TL (${fmt(r["kâr_zarar_%"], 2)}%)</b></div>`;
      out.querySelectorAll("[data-rm]").forEach((b) => (b.onclick = async () => { await JV.api("/api/finlab/remove", { body: { symbol: b.dataset.rm } }); run(); }));
      donut(r.varlıklar.filter((a) => a.değer_TL > 0).map((a) => ({ n: a.ad, v: a.değer_TL })));
    } else if (tab === "backtest") {
      out.innerHTML = `<div class="fl-cols"><div><h4>${esc(r.strateji)}</h4>${kv(r.strateji_sonuç)}</div><div><h4>AL-TUT</h4>${kv(r.al_tut_sonuç)}</div></div><div class="note">${esc(r.sembol)} · ${esc(r.dönem)} · günlük kapanış, sinyal ertesi gün uygulanır, işlem başına %0,1 komisyon.</div>`;
      lines([{ name: "Strateji", data: r.seri.strateji, color: css("--c") }, { name: "Al-tut", data: r.seri.al_tut, color: "#ffb020" }], r.seri.tarih, { fmt: (y) => "×" + y.toFixed(2) });
    } else if (tab === "montecarlo") {
      out.innerHTML = kv({ yatırılan_toplam: r.yatırılan_toplam, medyan_son: r.medyan_son, kötü_senaryo_p10: r.kötü_senaryo_p10, iyi_senaryo_p90: r.iyi_senaryo_p90, ...(r.hedef ? { hedefe_ulaşma_olasılığı_yüzde: r["hedefe_ulaşma_olasılığı_%"] } : {}), varsayım: r.varsayım, simülasyon: r.simülasyon });
      const b = r.bantlar, yrs = b.p50.map((_, i) => i + 1 + ". yıl");
      lines([{ name: "Medyan", data: b.p50, color: css("--c"), w: 2.5 }, { name: "%10", data: b.p10, color: "#ff5c7a", w: 1 }, { name: "%90", data: b.p90, color: "#22e39a", w: 1 }], yrs,
        { min: 0, band: [b.p10, b.p90, "rgba(56,214,255,.10)"], band2: [b.p25, b.p75, "rgba(56,214,255,.18)"], fmt: (y) => (y >= 1e6 ? fmt(y / 1e6, 1) + " mn" : fmt(y / 1000, 0) + " bin") });
    } else {
      out.innerHTML = kv({ aylık_taksit: r.aylık_taksit, toplam_faiz: r.toplam_faiz, toplam_ödeme: r.toplam_ödeme, taksit_sayısı: r.taksit_sayısı }) +
        `<table class="fl-t"><tr><th>Yıl</th><th>Faiz</th><th>Anapara</th><th>Kalan</th></tr>${r.yıllık_özet.map((y) => `<tr><td>${y.yıl}</td><td>${fmt(y.ödenen_faiz)}</td><td>${fmt(y.ödenen_anapara)}</td><td>${fmt(y.kalan)}</td></tr>`).join("")}</table>`;
    }
  }
  const hasData = (r) => r && (r.varlıklar || r.seri || r.bantlar || r.yıllık_özet || r.error || r.mesaj);
  JV.finlab = { open: (r) => show(r && FORMS[r.tab] ? r.tab : "portfolio", hasData(r) ? r : null) };
  document.addEventListener("DOMContentLoaded", () => { const b = $("#t-finlab"); if (b) b.onclick = () => JV.finlab.open(); });
})();
