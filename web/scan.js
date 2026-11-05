/* TARAMA SAHNESİ — "odayı tara", "kumandayı bul", "bu belgeyi tara", "QR oku", "bu ne renk".
   ODA: kare dondurulur, tarama çizgisi geçer, nesneler kutulanır; bir nesneye TIKLA → kırpılıp HOLOGRAM olarak öne gelir
        (döner kaide, katmanlı derinlik, sürükleyerek çevir, tekerlekle yakınlaş) + bilgi kartı (ne, marka, boyut, ipucu, nerede satılır, yerini hatırla, soru sor).
   BUL: kamerada canlı arama (yerel MediaPipe; tanımadığı nesnede birkaç saniyede bir Gemini'ye sorar), bulunca işaretler ve söyler.
   BELGE: yazıyı çıkar / özetle / çevir / soruyu çöz → kopyala, kaydet, oku.  QR: QR/barkod okur (link, Wi-Fi).  RENK: tıkla → renk adı + kodu.
   Kaynak: bu cihazın kamerası ya da bağlı telefon kamerası (📹). */
(function () {
  const JV = (window.JV = window.JV || {});
  const $ = (s, r = document) => r.querySelector(s);
  const esc = (s) => String(s == null ? "" : s).replace(/[&<>"]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]));
  const say = (t) => JV.say && JV.say(t, JV.currentPersona && JV.currentPersona());
  const TR2EN = { kumanda: "remote", telefon: "cell phone", "cep telefonu": "cell phone", şişe: "bottle", fincan: "cup", bardak: "cup", kupa: "cup", kitap: "book", makas: "scissors",
    sandalye: "chair", kanepe: "couch", koltuk: "couch", saksı: "potted plant", bitki: "potted plant", çiçek: "potted plant", televizyon: "tv", tv: "tv", laptop: "laptop", "dizüstü": "laptop", bilgisayar: "laptop",
    fare: "mouse", klavye: "keyboard", saat: "clock", çanta: "handbag", sırt: "backpack", şemsiye: "umbrella", top: "sports ball", kedi: "cat", köpek: "dog", vazo: "vase", kase: "bowl", çatal: "fork",
    bıçak: "knife", kaşık: "spoon", masa: "dining table", yatak: "bed", bavul: "suitcase", "diş fırçası": "toothbrush", ayıcık: "teddy bear", oyuncak: "teddy bear", insan: "person", kişi: "person" };
  const EN2TR = Object.fromEntries(Object.entries(TR2EN).reverse().map(([a, b]) => [b, a]));
  let st, cv, ctx, vid, img, stream = null, src = "local", mode = "room", raf = 0, snap = null, items = [], hover = -1, scanT = 0, busy = false, findT = { thing: "", cls: "", last: 0, found: null, tries: 0, said: false };
  let holo = null;
  let actx = null;
  function fx(kind) { // kısa sentez sesler
    try {
      actx = actx || new (window.AudioContext || window.webkitAudioContext)(); const t = actx.currentTime, o = actx.createOscillator(), g = actx.createGain(); o.connect(g); g.connect(actx.destination);
      const [f0, f1, d, ty] = { scan: [300, 1200, 1.2, "sawtooth"], lift: [500, 1400, 0.35, "sine"], found: [880, 1760, 0.25, "triangle"] }[kind] || [600, 600, 0.1, "sine"];
      o.type = ty; o.frequency.setValueAtTime(f0, t); o.frequency.exponentialRampToValueAtTime(f1, t + d); g.gain.setValueAtTime(0.06, t); g.gain.exponentialRampToValueAtTime(0.0001, t + d + 0.05); o.start(t); o.stop(t + d + 0.1);
    } catch (e) {}
  }
  JV.fxSound = JV.fxSound || fx;

  function build() {
    if (st) return;
    st = document.createElement("div"); st.id = "scanstage"; st.className = "hidden";
    st.innerHTML = `<video id="sc-v" muted playsinline autoplay></video><canvas id="sc-c"></canvas>
      <div class="sc-top"><b>TARAMA</b>
        <span class="sc-tabs">${[["room", "🏠 ODA"], ["find", "🔍 BUL"], ["doc", "📄 BELGE"], ["qr", "▦ QR"], ["color", "🎨 RENK"], ["plant", "🌱 BİTKİ"]].map(([m, t]) => `<button class="mini" data-m="${m}">${t}</button>`).join("")}</span>
        <select id="sc-src"><option value="local">Bu cihazın kamerası</option></select>
        <input id="sc-loc" placeholder="oda adı (salon…)"><button class="mini" id="sc-go">⟳ TARA</button><button class="mini" id="sc-x">✕</button></div>
      <div id="sc-side" class="hidden"></div><div id="sc-msg"></div>`;
    document.body.append(st);
    cv = $("#sc-c", st); ctx = cv.getContext("2d"); vid = $("#sc-v", st);
    st.querySelectorAll(".sc-tabs button").forEach((b) => (b.onclick = () => setMode(b.dataset.m)));
    $("#sc-x", st).onclick = close; $("#sc-go", st).onclick = () => (mode === "room" ? scanRoom() : mode === "doc" ? null : null);
    $("#sc-src", st).onchange = (e) => useSource(e.target.value);
    cv.addEventListener("mousemove", (e) => { if (mode === "room" && snap) { hover = hitTest(e.clientX, e.clientY); cv.style.cursor = hover >= 0 ? "pointer" : "default"; } });
    cv.addEventListener("click", (e) => onClick(e.clientX, e.clientY));
    addEventListener("resize", size);
    addEventListener("keydown", (e) => { if (!st.classList.contains("hidden") && e.key === "Escape") { if (holo) closeHolo(); else close(); } });
  }
  function size() { if (!cv) return; cv.width = innerWidth; cv.height = innerHeight; }
  function msg(t, ms = 2500) { const m = $("#sc-msg", st); m.textContent = t; m.classList.add("on"); clearTimeout(m._t); if (ms) m._t = setTimeout(() => m.classList.remove("on"), ms); }

  // ---------------- kaynak (kamera / telefon) ----------------
  async function useSource(s) {
    src = s; stopStream();
    if (s === "local") {
      try { stream = await navigator.mediaDevices.getUserMedia({ video: { facingMode: { ideal: "environment" }, width: { ideal: 1920 }, height: { ideal: 1080 } }, audio: false }); vid.srcObject = stream; await vid.play().catch(() => {}); }
      catch (e) { msg("Kamera açılamadı: " + e.message, 6000); }
    } else {
      img = img || new Image(); img.crossOrigin = "anonymous";
      const load = () => { if (src !== s || st.classList.contains("hidden")) return; img.src = `/api/cams/${encodeURIComponent(s)}.jpg?viewer=scan&token=${encodeURIComponent(JV.token || "")}&t=${Date.now()}`; setTimeout(load, 700); };
      load();
    }
  }
  function stopStream() { if (stream) stream.getTracks().forEach((t) => t.stop()); stream = null; }
  function source() { return src === "local" ? vid : img; }
  const srcW = () => (src === "local" ? vid.videoWidth : img && img.naturalWidth) || 0, srcH = () => (src === "local" ? vid.videoHeight : img && img.naturalHeight) || 0;
  function fit() { const w = srcW() || 16, h = srcH() || 9, s = Math.min(cv.width / w, cv.height / h), dw = w * s, dh = h * s; return { x: (cv.width - dw) / 2, y: (cv.height - dh) / 2, w: dw, h: dh }; }
  function grab(max = 1600) {
    const w = srcW(), h = srcH(); if (!w) return null;
    const k = Math.min(1, max / Math.max(w, h)), c = document.createElement("canvas"); c.width = Math.round(w * k); c.height = Math.round(h * k);
    c.getContext("2d").drawImage(source(), 0, 0, c.width, c.height); return c;
  }
  const blob = (c, type = "image/jpeg", q = 0.88) => new Promise((r) => c.toBlob(r, type, q));
  async function post(path, body, type = "image/jpeg") {
    const r = await fetch(path, { method: "POST", headers: { "x-token": JV.token || "", "Content-Type": type }, body });
    return r.json();
  }

  // ---------------- açma / kapama / mod ----------------
  async function open(m = "room", opt = {}) {
    build(); size(); st.classList.remove("hidden"); document.body.classList.add("scan-on");
    const sel = $("#sc-src", st); sel.innerHTML = `<option value="local">Bu cihazın kamerası</option>` + ((JV.cams && JV.cams.list()) || []).filter((c) => c.online).map((c) => `<option value="${esc(c.id)}">📹 ${esc(c.name)} · ${esc(c.loc)}</option>`).join("");
    if (opt.location) $("#sc-loc", st).value = opt.location;
    if (!stream && src === "local") await useSource("local");
    setMode(m, opt);
    cancelAnimationFrame(raf); loop();
  }
  function close() { st.classList.add("hidden"); document.body.classList.remove("scan-on"); stopStream(); cancelAnimationFrame(raf); closeHolo(); snap = null; items = []; $("#sc-side", st).classList.add("hidden"); }
  function setMode(m, opt = {}) {
    mode = m; snap = null; items = []; hover = -1; $("#sc-side", st).classList.add("hidden");
    st.querySelectorAll(".sc-tabs button").forEach((b) => b.classList.toggle("on", b.dataset.m === m));
    $("#sc-go", st).style.display = m === "room" ? "" : "none";
    if (m === "room") setTimeout(() => scanRoom(), 1200);
    if (m === "find") { findT = { thing: opt.thing || "", cls: "", last: 0, found: null, tries: 0, said: false }; findT.cls = clsFor(findT.thing); JV.mp && JV.mp.load("object").catch(() => {}); if (!findT.thing) { const sd = $("#sc-side", st); sd.classList.remove("hidden"); sd.innerHTML = `<h4>🔍 NE ARAYALIM?</h4><form id="fd-f"><input id="fd-t" placeholder="kumanda, gözlük, anahtar…"><button class="mini">BUL</button></form>`; $("#fd-f", sd).onsubmit = (e) => { e.preventDefault(); const t = $("#fd-t", sd).value.trim(); if (t) { sd.classList.add("hidden"); setMode("find", { thing: t }); } }; return; }
      if (opt.memory && opt.memory.son_görüldüğü) msg(`Hafıza: ${findT.thing} en son ${opt.memory.son_görüldüğü} (${opt.memory.ne_zaman}). Şimdi kamerada arıyorum…`, 7000); else msg(`"${findT.thing}" aranıyor… kamerayı odada gezdir.`, 5000); }
    if (m === "doc") docPanel(opt.doc || "text");
    if (m === "qr") { msg("QR kodu ya da barkodu kameraya göster", 4000); loadQR(); }
    if (m === "color") msg("Görüntüde bir yere tıkla: rengini söyleyeyim", 4000);
    if (m === "plant") plantPanel();
  }
  function clsFor(t) { const k = (t || "").toLowerCase(); for (const [tr, en] of Object.entries(TR2EN)) if (k.includes(tr)) return en; return ""; }

  // ---------------- çizim döngüsü ----------------
  function loop() {
    raf = requestAnimationFrame(loop);
    const now = performance.now(), f = fit();
    ctx.clearRect(0, 0, cv.width, cv.height);
    if (snap) { ctx.drawImage(snap, f.x, f.y, f.w, f.h); ctx.fillStyle = "rgba(0,10,20,0.35)"; ctx.fillRect(f.x, f.y, f.w, f.h); }
    else if (srcW()) ctx.drawImage(source(), f.x, f.y, f.w, f.h);
    if (mode === "room") drawRoom(now, f);
    if (mode === "find") findStep(now, f);
    if (mode === "qr") qrStep(now, f);
    if (mode === "doc") { ctx.strokeStyle = "rgba(0,229,255,0.7)"; ctx.setLineDash([10, 8]); ctx.strokeRect(f.x + f.w * 0.12, f.y + f.h * 0.08, f.w * 0.76, f.h * 0.84); ctx.setLineDash([]); }
  }
  const toScr = (b, f) => ({ x: f.x + b[0] * f.w, y: f.y + b[1] * f.h, w: (b[2] - b[0]) * f.w, h: (b[3] - b[1]) * f.h });
  function brackets(r, col, L = 14, lw = 2) {
    ctx.strokeStyle = col; ctx.lineWidth = lw; ctx.shadowColor = col; ctx.shadowBlur = 10;
    [[r.x, r.y, 1, 1], [r.x + r.w, r.y, -1, 1], [r.x, r.y + r.h, 1, -1], [r.x + r.w, r.y + r.h, -1, -1]].forEach(([x, y, sx, sy]) => { ctx.beginPath(); ctx.moveTo(x, y + sy * L); ctx.lineTo(x, y); ctx.lineTo(x + sx * L, y); ctx.stroke(); });
    ctx.shadowBlur = 0; ctx.lineWidth = 1;
  }
  function drawRoom(now, f) {
    if (busy) { // tarama animasyonu: ızgara + süpürme
      ctx.strokeStyle = "rgba(0,229,255,0.08)"; for (let x = f.x; x < f.x + f.w; x += 40) { ctx.beginPath(); ctx.moveTo(x, f.y); ctx.lineTo(x, f.y + f.h); ctx.stroke(); }
      for (let y = f.y; y < f.y + f.h; y += 40) { ctx.beginPath(); ctx.moveTo(f.x, y); ctx.lineTo(f.x + f.w, y); ctx.stroke(); }
      const y = f.y + ((now - scanT) / 1600 % 1) * f.h, g = ctx.createLinearGradient(0, y - 60, 0, y);
      g.addColorStop(0, "rgba(0,229,255,0)"); g.addColorStop(1, "rgba(0,229,255,0.45)"); ctx.fillStyle = g; ctx.fillRect(f.x, y - 60, f.w, 60);
      ctx.fillStyle = "#9ff"; ctx.font = "16px Share Tech Mono, monospace"; ctx.fillText("ODA TARANIYOR · NESNELER ANALİZ EDİLİYOR…", f.x + 20, f.y + f.h - 24);
    }
    items.forEach((it, i) => {
      const age = now - (it.shown || 0); if (age < 0) return;
      const r = toScr(it.box, f), on = i === hover, k = Math.min(1, age / 300);
      brackets(r, on ? "rgba(255,200,80,1)" : `rgba(80,230,255,${0.5 + 0.4 * k})`, on ? 18 : 12, on ? 3 : 2);
      if (on) { ctx.fillStyle = "rgba(255,200,80,0.08)"; ctx.fillRect(r.x, r.y, r.w, r.h); }
      if (it.notlar && it.notlar.length) { // nesneye bırakılmış yapışkan not: sallanan sarı hologram etiket
        const nx = r.x + r.w + 8, ny = r.y + 6 + Math.sin(now / 500 + i) * 3, txt = it.notlar.map((n) => "📌 " + n.t).join("  ");
        ctx.font = "13px Rajdhani, sans-serif"; const nw = Math.min(260, ctx.measureText(txt).width + 16);
        ctx.fillStyle = "rgba(255,215,90,0.88)"; ctx.shadowColor = "#fc4"; ctx.shadowBlur = 14; ctx.fillRect(nx, ny, nw, 26); ctx.shadowBlur = 0;
        ctx.fillStyle = "#2a1d00"; ctx.fillText(txt.slice(0, 40), nx + 8, ny + 17);
      }
      const label = it.ad.toUpperCase(); ctx.font = "12px Share Tech Mono, monospace"; const tw = ctx.measureText(label).width;
      ctx.fillStyle = "rgba(0,12,20,0.8)"; ctx.fillRect(r.x, r.y - 20, tw + 12, 18); ctx.fillStyle = on ? "#ffd28a" : "#9ff"; ctx.fillText(label, r.x + 6, r.y - 7);
    });
    if (items.length && !busy && !holo) { ctx.fillStyle = "rgba(160,255,255,0.8)"; ctx.font = "13px Share Tech Mono, monospace"; ctx.fillText(`${items.length} NESNE · bir nesneye tıkla → hologram`, f.x + 20, f.y + f.h - 24); }
  }
  function hitTest(x, y) {
    const f = fit(); let best = -1, area = 1e9;
    items.forEach((it, i) => { const r = toScr(it.box, f); if (x >= r.x && x <= r.x + r.w && y >= r.y && y <= r.y + r.h && r.w * r.h < area) { area = r.w * r.h; best = i; } });
    return best;
  }
  function onClick(x, y) {
    if (mode === "room") { const i = hitTest(x, y); if (i >= 0) openHolo(items[i]); }
    if (mode === "color") pickColor(x, y);
  }

  // ---------------- ODA TARAMASI ----------------
  async function scanRoom() {
    if (busy) return; const c = grab(1600); if (!c) { msg("Kamera görüntüsü yok."); return; }
    snap = c; items = []; busy = true; scanT = performance.now(); closeHolo();
    JV.fxSound && JV.fxSound("scan");
    let res = null;
    try { res = await post(`/api/scene/room?location=${encodeURIComponent($("#sc-loc", st).value || "")}`, await blob(c)); } catch (e) { res = { error: e.message }; }
    let list = (res && res.nesneler) || [];
    if (!list.length) list = await localDetect(c); // Gemini yoksa/olmazsa yerel model
    busy = false;
    const t0 = performance.now();
    items = list.map((it, i) => ({ ...it, shown: t0 + i * 90 }));
    if (!items.length) { msg(res && res.error ? "Tarama yapılamadı: " + res.error : "Belirgin nesne bulunamadı.", 6000); return; }
    const noted = items.filter((x) => x.notlar && x.notlar.length);
    if (noted.length) setTimeout(() => say(`Not hatırlatması: ${noted.map((x) => x.ad + " üzerinde: " + x.notlar.map((n) => n.t).join(", ")).join(". ")}`), 4500);
    const t = `${items.length} nesne buldum: ${items.slice(0, 6).map((x) => x.ad).join(", ")}${items.length > 6 ? " ve diğerleri" : ""}. Birine tıklarsanız yakından gösteririm.`;
    msg(t, 6000); say(t);
  }
  async function localDetect(c) {
    try {
      const det = await JV.mp.load("object"); const r = det.detectForVideo(c, performance.now());
      const W = c.width, H = c.height, out = (r.detections || []).map((d) => { const b = d.boundingBox, n = (d.categories[0] || {}).categoryName || "?"; return { ad: EN2TR[n] || n, tür: "diğer", box: [b.originX / W, b.originY / H, (b.originX + b.width) / W, (b.originY + b.height) / H], not: "" }; });
      if (out.length) post("/api/scene/remember", JSON.stringify({ items: out, location: $("#sc-loc", st).value || "" }), "application/json").catch(() => {});
      return out;
    } catch (e) { return []; }
  }

  // ---------------- HOLOGRAM ----------------
  function holoCanvas(srcC, box) { // kırp + hologram rengi (siyan, tarama çizgisi, kenar parlaması)
    const pad = 0.08, W = srcC.width, H = srcC.height;
    const x0 = Math.max(0, (box[0] - pad * (box[2] - box[0])) * W), y0 = Math.max(0, (box[1] - pad * (box[3] - box[1])) * H);
    const x1 = Math.min(W, (box[2] + pad * (box[2] - box[0])) * W), y1 = Math.min(H, (box[3] + pad * (box[3] - box[1])) * H);
    const w = Math.max(8, x1 - x0), h = Math.max(8, y1 - y0), k = Math.min(3, 420 / Math.max(w, h));
    const raw = document.createElement("canvas"); raw.width = w * k; raw.height = h * k; raw.getContext("2d").drawImage(srcC, x0, y0, w, h, 0, 0, raw.width, raw.height);
    const hc = document.createElement("canvas"); hc.width = raw.width; hc.height = raw.height; const g = hc.getContext("2d");
    const d = raw.getContext("2d").getImageData(0, 0, raw.width, raw.height), o = g.createImageData(raw.width, raw.height), cx = raw.width / 2, cy = raw.height / 2, R = Math.hypot(cx, cy);
    for (let i = 0; i < d.data.length; i += 4) {
      const p = i / 4, x = p % raw.width, y = (p / raw.width) | 0, l = (d.data[i] * 0.3 + d.data[i + 1] * 0.59 + d.data[i + 2] * 0.11) / 255;
      const edge = 1 - Math.min(1, Math.hypot(x - cx, y - cy) / R) ** 2.2, scan = (y % 4 < 2) ? 1 : 0.72;
      o.data[i] = 40 * l + d.data[i] * 0.15; o.data[i + 1] = 200 * l + 40; o.data[i + 2] = 255 * Math.min(1, l * 1.1 + 0.15); o.data[i + 3] = 255 * Math.min(1, edge * 1.4) * scan * (0.55 + 0.45 * l);
    }
    g.putImageData(o, 0, 0);
    return { holo: hc.toDataURL("image/png"), raw: raw };
  }
  async function openHolo(it) {
    closeHolo();
    const { holo: url, raw } = holoCanvas(snap, it.box);
    holo = document.createElement("div"); holo.id = "holo3d";
    holo.innerHTML = `<div class="h3-scene"><div class="h3-obj">${[0, 1, 2, 3].map((i) => `<img src="${url}" style="transform:translateZ(${i * -14}px);opacity:${1 - i * 0.22}">`).join("")}</div>
        <div class="h3-base"><i></i><i></i><i></i></div><div class="h3-beam"></div></div>
      <div class="h3-card"><h3>${esc(it.ad.toUpperCase())}</h3><div class="h3-sub">${esc(it.tür || "")}${it.not ? " · " + esc(it.not) : ""}</div>
        ${(it.notlar || []).map((n) => `<div class="h3-note">📌 ${esc(n.t)}</div>`).join("")}
        <div id="h3-info" class="h3-load">analiz ediliyor…</div>
        <div class="h3-btns"><button class="mini" id="h3-say">🗣 ANLAT</button><button class="mini" id="h3-buy">🛒 NEREDE SATILIR</button><button class="mini" id="h3-mem">📍 YERİNİ HATIRLA</button><button class="mini" id="h3-x">✕ BIRAK</button></div>
        <form id="h3-ask"><input placeholder="Bu nesneye dair sor… (örn. nasıl temizlenir?)"><button class="mini">SOR</button></form></div>`;
    document.body.append(holo);
    requestAnimationFrame(() => holo.classList.add("on"));
    JV.fxSound && JV.fxSound("lift");
    let ry = -25, rx = 8, z = 1, drag = null, auto = true;
    const obj = $(".h3-obj", holo), apply = () => (obj.style.transform = `rotateX(${rx}deg) rotateY(${ry}deg) scale(${z})`);
    const spin = () => { if (!holo) return; if (auto && !drag) { ry += 0.35; apply(); } requestAnimationFrame(spin); }; spin();
    const sc = $(".h3-scene", holo);
    sc.onpointerdown = (e) => { drag = [e.clientX, e.clientY, ry, rx]; auto = false; sc.setPointerCapture(e.pointerId); };
    sc.onpointermove = (e) => { if (!drag) return; ry = drag[2] + (e.clientX - drag[0]) * 0.5; rx = Math.max(-40, Math.min(40, drag[3] - (e.clientY - drag[1]) * 0.3)); apply(); };
    sc.onpointerup = () => { drag = null; setTimeout(() => (auto = true), 2500); };
    sc.onwheel = (e) => { e.preventDefault(); z = Math.max(0.5, Math.min(2.5, z - e.deltaY * 0.001)); apply(); };
    $("#h3-x", holo).onclick = closeHolo;
    let info = {};
    const rawBlob = await blob(raw, "image/jpeg", 0.9);
    try { info = await post(`/api/scene/object?name=${encodeURIComponent(it.ad)}`, rawBlob); } catch (e) { info = { error: e.message }; }
    if (!holo) return;
    const box = $("#h3-info", holo); box.classList.remove("h3-load");
    box.innerHTML = info.error ? `<p class="dim">${esc(info.error)}</p>` : `<p>${esc(info.ne || "")}</p>${info.marka_model ? `<p><b>Marka/model:</b> ${esc(info.marka_model)}</p>` : ""}${info.tahmini_boyut ? `<p><b>Boyut:</b> ${esc(info.tahmini_boyut)}</p>` : ""}${info.ipucu ? `<p><b>İpucu:</b> ${esc(info.ipucu)}</p>` : ""}`;
    $("#h3-say", holo).onclick = () => say(`${info.ad || it.ad}. ${info.ne || ""} ${info.ipucu || ""}`);
    $("#h3-buy", holo).onclick = () => { closeHolo(); close(); JV.sendCommand && JV.sendCommand(`"${info.arama || info.marka_model || it.ad}" için güncel fiyatları ve nereden alınabileceğini kısaca ara`); };
    $("#h3-mem", holo).onclick = async () => { const loc = $("#sc-loc", st).value || "bu oda"; await post("/api/scene/remember", JSON.stringify({ items: [it], location: loc }), "application/json"); msg(`📍 ${it.ad}: ${loc} — hatırlıyorum.`); };
    $("#h3-ask", holo).onsubmit = async (e) => {
      e.preventDefault(); const q = e.target.querySelector("input"); if (!q.value.trim()) return; const qq = q.value.trim(); q.value = "…";
      const r = await post(`/api/scene/object?name=${encodeURIComponent(it.ad)}&question=${encodeURIComponent(qq)}`, rawBlob).catch((er) => ({ cevap: er.message }));
      q.value = ""; const p = document.createElement("p"); p.innerHTML = `<b>${esc(qq)}</b><br>${esc(r.cevap || r.error || "")}`; box.append(p); say(r.cevap || "");
    };
  }
  function closeHolo() { if (!holo) return; const h = holo; holo = null; h.classList.remove("on"); h.classList.add("off"); setTimeout(() => h.remove(), 500); }

  // ---------------- BUL (canlı) ----------------
  async function findStep(now, f) {
    if (!findT.thing) return;
    const t = findT;
    if (t.found && now - t.found.t < 2500) {
      const r = toScr(t.found.box, f), pulse = 1 + Math.sin(now / 120) * 0.06;
      brackets({ x: r.x - (pulse - 1) * r.w, y: r.y - (pulse - 1) * r.h, w: r.w * pulse, h: r.h * pulse }, "rgba(60,255,138,1)", 22, 3);
      ctx.fillStyle = "#3cff8a"; ctx.font = "16px Share Tech Mono, monospace"; ctx.fillText(`✓ ${t.thing.toUpperCase()} BULUNDU`, r.x, r.y - 10);
    } else {
      ctx.fillStyle = "rgba(160,255,255,0.85)"; ctx.font = "14px Share Tech Mono, monospace"; ctx.fillText(`ARANIYOR: ${t.thing.toUpperCase()} · kamerayı yavaşça gezdir`, f.x + 20, f.y + f.h - 24);
    }
    if (now - t.last < (t.cls ? 220 : 4500) || !srcW()) return;
    t.last = now;
    if (t.cls) { // yerel ve hızlı (COCO nesneleri)
      try {
        const det = await JV.mp.load("object"), r = det.detectForVideo(source(), now), W = srcW(), H = srcH();
        const d = (r.detections || []).find((x) => (x.categories[0] || {}).categoryName === t.cls);
        if (d) { const b = d.boundingBox; hit([b.originX / W, b.originY / H, (b.originX + b.width) / W, (b.originY + b.height) / H]); }
      } catch (e) {}
    } else if (t.tries < 12) { // tanımadığı nesne: birkaç saniyede bir Gemini'ye sor
      t.tries++; const c = grab(1024); if (!c) return;
      try {
        const r = await post(`/api/scene/object?name=&question=${encodeURIComponent(`Bu görüntüde "${t.thing}" var mı? Varsa SADECE JSON: {"var": true, "box": [x0,y0,x1,y1]} (0-1000). Yoksa {"var": false}.`)}`, await blob(c));
        const m = /\{.*\}/s.exec(r.cevap || ""); const j = m ? JSON.parse(m[0]) : {};
        if (j.var && Array.isArray(j.box)) hit(j.box.map((v) => v / 1000));
      } catch (e) {}
    }
  }
  function hit(box) {
    const now = performance.now(); findT.found = { box, t: now };
    if (!findT.said) { findT.said = true; JV.fxSound && JV.fxSound("found"); const cx = (box[0] + box[2]) / 2; say(`Buldum! ${findT.thing} görüntünün ${cx < 0.33 ? "solunda" : cx > 0.66 ? "sağında" : "ortasında"}.`); post("/api/scene/remember", JSON.stringify({ items: [{ ad: findT.thing, box, not: "" }], location: $("#sc-loc", st).value || "" }), "application/json").catch(() => {}); }
  }

  // ---------------- BELGE ----------------
  function docPanel(def) {
    const s = $("#sc-side", st); s.classList.remove("hidden");
    s.innerHTML = `<h4>📄 BELGE TARAYICI</h4><p class="note">Belgeyi çerçeveye yerleştir, net ve ışıklı olsun.</p>
      <div class="sc-btns">${[["text", "YAZIYI ÇIKAR"], ["summary", "ÖZETLE"], ["translate", "ÇEVİR"], ["math", "SORUYU ÇÖZ"]].map(([m, t]) => `<button class="mini${m === def ? " on" : ""}" data-d="${m}">${t}</button>`).join("")}</div>
      <select id="sc-lang"><option value="tr">→ Türkçe</option><option value="İngilizce">→ İngilizce</option><option value="Almanca">→ Almanca</option><option value="Arapça">→ Arapça</option><option value="Rusça">→ Rusça</option></select>
      <pre id="sc-out"></pre><div class="sc-btns"><button class="mini" id="sc-copy">📋 KOPYALA</button><button class="mini" id="sc-save">💾 KAYDET</button><button class="mini" id="sc-read">🔊 OKU</button></div>`;
    s.querySelectorAll("[data-d]").forEach((b) => (b.onclick = () => runDoc(b.dataset.d)));
    $("#sc-copy", s).onclick = () => { navigator.clipboard && navigator.clipboard.writeText($("#sc-out", s).textContent); msg("Kopyalandı"); };
    $("#sc-save", s).onclick = async () => { const r = await post("/api/scene/save", JSON.stringify({ text: $("#sc-out", s).textContent }), "application/json"); msg(r.dosya ? "Kaydedildi: " + r.dosya : r.error || "Kaydedilemedi", 6000); };
    $("#sc-read", s).onclick = () => say($("#sc-out", s).textContent.slice(0, 1500));
    if (def && def !== "text") setTimeout(() => runDoc(def), 1800);
  }
  async function runDoc(m) {
    const c = grab(2200), out = $("#sc-out", st); if (!c) return;
    snap = c; out.textContent = "okunuyor…";
    try { const r = await post(`/api/scene/doc?mode=${m}&lang=${encodeURIComponent($("#sc-lang", st).value)}`, await blob(c, "image/jpeg", 0.92)); out.textContent = r.metin || r.error || ""; if (m !== "text") say((r.metin || "").slice(0, 800)); }
    catch (e) { out.textContent = "Hata: " + e.message; }
    setTimeout(() => (snap = null), 1500);
  }

  // ---------------- BİTKİ DOKTORU ----------------
  function plantPanel() {
    const s = $("#sc-side", st); s.classList.remove("hidden");
    s.innerHTML = `<h4>🌱 BİTKİ DOKTORU</h4><p class="note">Bitkiyi (yapraklarıyla) kameraya göster.</p><button class="btn-primary" id="pl-go">ANALİZ ET</button><div id="pl-out"></div>`;
    $("#pl-go", s).onclick = runPlant; setTimeout(runPlant, 1800);
  }
  async function runPlant() {
    const c = grab(1400), out = $("#pl-out", st); if (!c) return; snap = c; out.innerHTML = "<p class='h3-load'>inceleniyor…</p>";
    let r = {}; try { r = await post("/api/life/plant", await blob(c)); } catch (e) { r = { hata: e.message }; }
    setTimeout(() => (snap = null), 1500);
    if (!r.bitki) { out.innerHTML = `<p>${esc(r.hata || r.error || "Görüntüde bitki göremedim.")}</p>`; return; }
    const hc = { iyi: "#3cff8a", dikkat: "#ffcf5a", sorunlu: "#ff6b6b" }[r.sağlık] || "#9fe";
    out.innerHTML = `<h3>${esc(r.bitki)}${r.emin ? "" : " <small>(emin değilim)</small>"}</h3><p>Sağlık: <b style="color:${hc}">${esc((r.sağlık || "").toUpperCase())}</b></p>
      ${(r.sorunlar || []).length ? `<p><b>Görülen:</b> ${esc(r.sorunlar.join(", "))}</p><p><b>Olası neden:</b> ${esc(r.neden || "")}</p>` : ""}
      ${(r.yapılacaklar || []).length ? `<ul>${r.yapılacaklar.map((x) => `<li>${esc(x)}</li>`).join("")}</ul>` : ""}
      <p>💧 ${r.sulama_gün ? r.sulama_gün + " günde bir" : "-"} · ☀ ${esc(r.ışık || "-")}</p><p class="note">${esc(r.ipucu || "")}</p>
      <button class="mini" id="pl-rem">💧 ${r.sulama_gün || 7} günde bir hatırlat</button>`;
    $("#pl-rem", out).onclick = async () => { const x = await post("/api/life/plant_reminder", JSON.stringify({ name: (r.bitki || "bitki").split("(")[0].trim(), every: r.sulama_gün || 7 }), "application/json"); msg(x.r || "Kaydedildi", 5000); say(x.r || ""); };
    say(`${r.bitki}. Sağlık durumu ${r.sağlık || "belirsiz"}. ${(r.yapılacaklar || [])[0] || ""}`);
  }

  // ---------------- QR ----------------
  let jsQR = null, qrLast = 0, qrSeen = "";
  function loadQR() { if (jsQR || window.BarcodeDetector) return; const s = document.createElement("script"); s.src = "https://cdn.jsdelivr.net/npm/jsqr@1.4.0/dist/jsQR.js"; s.onload = () => (jsQR = window.jsQR); document.head.append(s); }
  async function qrStep(now, f) {
    if (now - qrLast < 250 || !srcW()) return; qrLast = now;
    let text = "";
    try {
      if (window.BarcodeDetector) { const r = await new BarcodeDetector().detect(source()); if (r[0]) text = r[0].rawValue; }
      else if (jsQR || window.jsQR) { const c = grab(800), g = c.getContext("2d").getImageData(0, 0, c.width, c.height), r = (jsQR || window.jsQR)(g.data, c.width, c.height); if (r) text = r.data; }
    } catch (e) {}
    if (!text || text === qrSeen) return; qrSeen = text; JV.fxSound && JV.fxSound("found");
    const s = $("#sc-side", st); s.classList.remove("hidden");
    let html = `<h4>▦ OKUNDU</h4><pre>${esc(text)}</pre>`;
    const wifi = /^WIFI:(.*)/i.exec(text);
    if (wifi) { const g = (k) => ((new RegExp(k + ":([^;]*)")).exec(text) || [])[1] || ""; html += `<p>📶 Wi-Fi: <b>${esc(g("S"))}</b><br>Şifre: <b>${esc(g("P"))}</b> (${esc(g("T"))})</p>`; }
    if (/^https?:\/\//i.test(text)) html += `<p class="note">⚠ Bilinmeyen QR linklerine dikkat: adresi kontrol et.</p><a class="mini" href="${esc(text)}" target="_blank" rel="noopener">AÇ ↗</a>`;
    html += ` <button class="mini" id="qr-copy">📋 KOPYALA</button>`;
    s.innerHTML = html; $("#qr-copy", s).onclick = () => navigator.clipboard && navigator.clipboard.writeText(text);
    say(wifi ? "Wi-Fi QR kodu okundu." : /^https?:/.test(text) ? "Bir web adresi okundu." : "Kod okundu.");
  }

  // ---------------- RENK ----------------
  const NAMES = [["siyah", [20, 20, 20]], ["beyaz", [245, 245, 245]], ["gri", [128, 128, 128]], ["kırmızı", [210, 40, 40]], ["bordo", [128, 20, 40]], ["turuncu", [240, 140, 30]], ["sarı", [240, 220, 40]],
    ["yeşil", [40, 170, 60]], ["koyu yeşil", [20, 90, 40]], ["turkuaz", [40, 200, 200]], ["mavi", [40, 90, 210]], ["lacivert", [20, 30, 90]], ["mor", [120, 50, 170]], ["pembe", [240, 130, 180]], ["kahverengi", [120, 75, 40]], ["bej", [220, 200, 160]]];
  function pickColor(x, y) {
    const f = fit(); if (!srcW()) return;
    const sx = (x - f.x) / f.w * srcW(), sy = (y - f.y) / f.h * srcH(); if (sx < 0 || sy < 0 || sx > srcW() || sy > srcH()) return;
    const c = document.createElement("canvas"); c.width = c.height = 7; c.getContext("2d").drawImage(source(), sx - 3, sy - 3, 7, 7, 0, 0, 7, 7);
    const d = c.getContext("2d").getImageData(0, 0, 7, 7).data; let r = 0, g = 0, b = 0; for (let i = 0; i < d.length; i += 4) { r += d[i]; g += d[i + 1]; b += d[i + 2]; } const n = d.length / 4; r = Math.round(r / n); g = Math.round(g / n); b = Math.round(b / n);
    const hex = "#" + [r, g, b].map((v) => v.toString(16).padStart(2, "0")).join("").toUpperCase();
    const name = NAMES.reduce((a, c2) => { const dd = (c2[1][0] - r) ** 2 + (c2[1][1] - g) ** 2 + (c2[1][2] - b) ** 2; return dd < a[1] ? [c2[0], dd] : a; }, ["", 1e9])[0];
    const s = $("#sc-side", st); s.classList.remove("hidden");
    s.innerHTML = `<h4>🎨 RENK</h4><div class="sc-sw" style="background:${hex}"></div><p><b>${name}</b> · ${hex} · rgb(${r}, ${g}, ${b})</p><button class="mini" id="cp-copy">📋 ${hex}</button>`;
    $("#cp-copy", s).onclick = () => navigator.clipboard && navigator.clipboard.writeText(hex); say(`Bu renk ${name}, kodu ${hex.split("").join(" ")}.`.replace(/# /, "diyez "));
  }

  function cmd(r) { open(r.mode || "room", { location: r.location, thing: r.thing, memory: r.hafıza, doc: r.doc }); }
  JV.scan = { open, close, cmd, get active() { return st && !st.classList.contains("hidden"); }, _state: () => ({ mode, items: items.length, holo: !!holo, busy, found: !!findT.found }), _openHolo: (i) => items[i] && openHolo(items[i]), _setSnap: (c) => (snap = c), _scan: scanRoom };
})();
