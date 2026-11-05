/* BÜYÜK HAVA PANELİ — "hava durumunu göster": anlık derece + durum, yüksek/düşük, yağmur, UV, gün doğumu/batımı,
   24 saatlik sıcaklık eğrisi (yağmur çubuklarıyla) ve 7 günlük kartlar. Veri: Open-Meteo (ücretsiz). */
(function () {
  const JV = (window.JV = window.JV || {});
  const esc = (s) => String(s == null ? "" : s).replace(/[&<>"]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]));
  // basit, özgün SVG simgeler
  const ICON = {
    sun: `<circle cx="32" cy="32" r="12" fill="#ffd34d"/>${[...Array(8)].map((_, i) => { const a = i * Math.PI / 4; return `<line x1="${32 + Math.cos(a) * 18}" y1="${32 + Math.sin(a) * 18}" x2="${32 + Math.cos(a) * 25}" y2="${32 + Math.sin(a) * 25}" stroke="#ffd34d" stroke-width="3" stroke-linecap="round"/>`; }).join("")}`,
    cloud: `<path d="M18 46h28a10 10 0 0 0 0-20 14 14 0 0 0-27-3A10 10 0 0 0 18 46z" fill="#e8f4ff"/>`,
    partly: `<circle cx="24" cy="24" r="10" fill="#ffd34d"/><path d="M22 50h26a9 9 0 0 0 0-18 13 13 0 0 0-25-3A9 9 0 0 0 22 50z" fill="#e8f4ff"/>`,
    rain: `<path d="M18 38h28a10 10 0 0 0 0-20 14 14 0 0 0-27-3A10 10 0 0 0 18 38z" fill="#cfe6ff"/>${[22, 32, 42].map((x) => `<line x1="${x}" y1="44" x2="${x - 4}" y2="56" stroke="#5ab8ff" stroke-width="3" stroke-linecap="round"/>`).join("")}`,
    drizzle: `<path d="M18 38h28a10 10 0 0 0 0-20 14 14 0 0 0-27-3A10 10 0 0 0 18 38z" fill="#cfe6ff"/>${[24, 34, 44].map((x) => `<circle cx="${x}" cy="48" r="2" fill="#5ab8ff"/>`).join("")}`,
    snow: `<path d="M18 38h28a10 10 0 0 0 0-20 14 14 0 0 0-27-3A10 10 0 0 0 18 38z" fill="#eef6ff"/>${[22, 32, 42].map((x) => `<text x="${x - 4}" y="56" font-size="12" fill="#fff">✻</text>`).join("")}`,
    storm: `<path d="M18 36h28a10 10 0 0 0 0-20 14 14 0 0 0-27-3A10 10 0 0 0 18 36z" fill="#9fb3c8"/><path d="M33 38l-8 12h7l-4 10 12-15h-7l4-7z" fill="#ffd34d"/>`,
    fog: `${[24, 32, 40].map((y, i) => `<line x1="${12 + i * 3}" y1="${y}" x2="${52 - i * 3}" y2="${y}" stroke="#cfe0ee" stroke-width="4" stroke-linecap="round"/>`).join("")}`,
  };
  const svg = (k, s = 64) => `<svg viewBox="0 0 64 64" width="${s}" height="${s}">${ICON[k] || ICON.cloud}</svg>`;
  JV.wxIcon = svg;
  let el;
  function build() {
    if (el) return;
    el = document.createElement("div"); el.id = "wxpanel"; el.className = "hidden";
    document.body.append(el);
    addEventListener("keydown", (e) => { if (e.key === "Escape" && !el.classList.contains("hidden")) close(); });
  }
  function curve(h) {
    if (!h || !h.length) return "";
    const W = 900, H = 120, pad = 20, ts = h.map((x) => x.derece), lo = Math.min(...ts) - 2, hi = Math.max(...ts) + 2;
    const X = (i) => pad + (i / (h.length - 1)) * (W - pad * 2), Y = (t) => H - 18 - ((t - lo) / (hi - lo || 1)) * (H - 46);
    const path = h.map((x, i) => `${i ? "L" : "M"}${X(i).toFixed(1)},${Y(x.derece).toFixed(1)}`).join(" ");
    const bars = h.map((x, i) => `<rect x="${X(i) - 6}" y="${H - 4 - x.yağmur * 0.3}" width="12" height="${x.yağmur * 0.3}" fill="rgba(90,184,255,.55)"/>`).join("");
    const labels = h.map((x, i) => (i % 3 ? "" : `<text x="${X(i)}" y="${Y(x.derece) - 9}" text-anchor="middle" class="wx-ct">${x.derece}°</text><text x="${X(i)}" y="${H + 12}" text-anchor="middle" class="wx-ch">${x.saat}</text>`)).join("");
    return `<svg class="wx-curve" viewBox="0 0 ${W} ${H + 16}" preserveAspectRatio="none"><defs><linearGradient id="wxg" x1="0" x2="0" y1="0" y2="1"><stop offset="0" stop-color="rgba(0,229,255,.35)"/><stop offset="1" stop-color="rgba(0,229,255,0)"/></linearGradient></defs>
      ${bars}<path d="${path} L${X(h.length - 1)},${H} L${X(0)},${H} Z" fill="url(#wxg)"/><path d="${path}" fill="none" stroke="#00e5ff" stroke-width="2.5"/>${labels}</svg>`;
  }
  function render(w) {
    const t = new Date();
    el.innerHTML = `<div class="wx-card"><div class="wx-head"><div><h2>HAVA · ${esc((w.şehir || "").toUpperCase())}</h2>
        <div class="wx-sub">${esc([w.şehir, w.bölge, w.ülke].filter(Boolean).join(", "))} · yerel ${esc(t.toLocaleDateString("tr-TR", { weekday: "short", day: "numeric", month: "short" }))} ${esc(t.toLocaleTimeString("tr-TR"))} · ${esc(w.kaynak || "")}</div></div>
        <span class="wx-live">● CANLI</span><button class="mini" id="wx-x">✕</button></div>
      <div class="wx-main"><div class="wx-now">${svg(w.ikon, 120)}<div><div class="wx-t">${w.derece}°</div><div class="wx-d">${esc((w.durum || "").toUpperCase())}</div><div class="wx-f">hissedilen ${w.hissedilen}° · nem %${w.nem} · rüzgar ${w.rüzgar} km/s</div></div></div>
        <div class="wx-grid">${[["YÜKSEK", w.yüksek + "°"], ["DÜŞÜK", w.düşük + "°"], ["YAĞMUR", "%" + w.yağmur], ["UV", w.uv], ["GÜN DOĞUMU", w.doğuş], ["GÜN BATIMI", w.batış]].map(([k, v]) => `<div><span>${k}</span><b>${esc(v)}</b></div>`).join("")}</div></div>
      ${curve(w.saatlik)}
      <div class="wx-days">${(w.günler || []).map((d, i) => `<div class="wx-day${i === 0 ? " on" : ""}"><span>${esc(d.gün)}</span>${svg(d.ikon, 44)}<small>${d.yağmur ? "💧" + d.yağmur + "%" : ""}</small><div class="wx-rng"><i style="width:${Math.max(8, Math.min(100, (d.max - d.min) * 8))}%"></i></div><b>${d.min}° / ${d.max}°</b></div>`).join("")}</div></div>`;
    el.querySelector("#wx-x").onclick = close;
  }
  async function open(r = {}) {
    build(); el.classList.remove("hidden");
    let w = r.data;
    if (!w) { el.innerHTML = `<div class="wx-card"><p class="h3-load">hava durumu alınıyor…</p></div>`; try { w = await JV.api("/api/hud/weather?city=" + encodeURIComponent(r.city || "")); } catch (e) { w = { error: e.message }; } }
    if (!w || w.error) { el.innerHTML = `<div class="wx-card"><p>Hava durumu alınamadı: ${esc(w && w.error)}</p><button class="mini" id="wx-x">✕</button></div>`; el.querySelector("#wx-x").onclick = close; return; }
    render(w);
  }
  function close() { if (el) el.classList.add("hidden"); }
  JV.weather = { open, close };
})();
