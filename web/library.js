/* 📚 KİTAPLIK — panel + holografik kitap + AR'de raftan kitap çekme.
   Panel: kitaplar, durum (okunacak/okunuyor/bitti), sayfa, notlar, alıntılar, özet, kapak; "📷 Raf fotoğrafından ekle", "Kameradan tara".
   AR (EL > ✨ EFEKT): ☝ işaret ucunu sırta getir → kitap seçilir (etiket) · 🤏 çimdik → kitap raftan kopar, holografik açılır ·
   ✋ açık avucu sola/sağa savur → sayfa · 👍 basılı tut → özeti okur · ✊ basılı tut → kitap kapanır, rafına döner.
   Kitaplığı tarama: AR'de K tuşu / ⚙ > Kitaplığı tara / sesle "kitaplığımı tara". */
(function () {
  const JV = (window.JV = window.JV || {});
  const $ = (s, r = document) => r.querySelector(s);
  const esc = (s) => String(s == null ? "" : s).replace(/[&<>"]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]));
  const api = (p, o) => (JV.api ? JV.api(p, o) : fetch(p).then((r) => r.json()));
  let data = { books: [], shelf: {} }, panel, book, cur = null, page = 0, sel = { id: "", since: 0, cand: "" }, scanning = false;

  async function load() { try { data = await api("/api/library"); } catch (e) {} return data; }
  const boxed = () => data.books.filter((b) => b.box);
  const named = () => data.books.filter((b) => b.title);

  // ---------------- panel ----------------
  function buildPanel() {
    if (panel) return;
    panel = document.createElement("div"); panel.id = "libpanel"; panel.className = "hidden modal-card";
    panel.innerHTML = `<div class="lp-top"><b>📚 KİTAPLIĞIM</b><span id="lp-count"></span>
        <label class="mini lp-up">📷 Raf fotoğrafından ekle<input type="file" id="lp-photo" accept="image/*" multiple hidden></label>
        <button class="mini" id="lp-scan">🎥 Kameradan tara</button><button class="mini" id="lp-x">✕</button></div>
      <form id="lp-add"><input id="lp-t" placeholder="Kitap adı"><input id="lp-a" placeholder="Yazar"><button class="mini">EKLE</button></form>
      <div class="lp-filter"><button class="mini on" data-f="">Hepsi</button><button class="mini" data-f="okunuyor">Okunuyor</button><button class="mini" data-f="okunacak">Okunacak</button><button class="mini" data-f="bitti">Bitti</button><button class="mini" data-f="?">Adsız (raf)</button></div>
      <div id="lp-list"></div><div id="lp-edit" class="hidden"></div>`;
    document.body.append(panel);
    $("#lp-x", panel).onclick = () => panel.classList.add("hidden");
    $("#lp-scan", panel).onclick = () => { panel.classList.add("hidden"); scan(); };
    $("#lp-add", panel).onsubmit = async (e) => {
      e.preventDefault(); const t = $("#lp-t", panel).value.trim(); if (!t) return;
      await api("/api/library/book", { body: { title: t, author: $("#lp-a", panel).value.trim() } }); $("#lp-t", panel).value = $("#lp-a", panel).value = "";
      await load(); renderList(); JV.toast && JV.toast("Eklendi; JARVIS sayfalarını birazdan dolduracak.");
    };
    $("#lp-photo", panel).onchange = async (e) => {
      const files = [...e.target.files]; if (!files.length) return;
      JV.toast && JV.toast(`📷 ${files.length} fotoğraf okunuyor… (fotoğraf başına ~20 sn)`, 8000);
      let total = [];
      for (const f of files) { try { const jpg = await shrink(f); const r = await fetch("/api/library/photo", { method: "POST", headers: { "x-token": JV.token || "", "Content-Type": "image/jpeg" }, body: jpg }); const j = await r.json(); total = total.concat(j.eklenen || []); } catch (er) {} }
      await load(); renderList(); JV.toast && JV.toast(total.length ? `Eklenen kitaplar: ${total.join(", ")}` : "Yeni kitap okunamadı (yakından ve net çek).", 9000);
      e.target.value = "";
    };
    panel.querySelectorAll(".lp-filter button").forEach((b) => (b.onclick = () => { panel.querySelectorAll(".lp-filter button").forEach((x) => x.classList.toggle("on", x === b)); filter = b.dataset.f; renderList(); }));
  }
  let filter = "";
  async function shrink(file, max = 2000) {
    const img = await createImageBitmap(file); const k = Math.min(1, max / Math.max(img.width, img.height));
    const c = document.createElement("canvas"); c.width = img.width * k; c.height = img.height * k; c.getContext("2d").drawImage(img, 0, 0, c.width, c.height);
    return new Promise((r) => c.toBlob(r, "image/jpeg", 0.88));
  }
  const ST = { okunacak: "📕 okunacak", okunuyor: "📖 okunuyor", bitti: "✅ bitti" };
  function renderList() {
    const l = $("#lp-list", panel); l.innerHTML = "";
    const list = data.books.filter((b) => (filter === "?" ? !b.title : filter ? b.status === filter && b.title : true));
    $("#lp-count", panel).textContent = `${named().length} kitap${boxed().length ? ` · rafta ${boxed().length} sırt` : ""}`;
    if (!list.length) l.innerHTML = `<p class="note">Henüz kitap yok. Yukarıdan ekle, raf fotoğrafı yükle ya da kameradan tara.</p>`;
    list.forEach((b) => {
      const r = document.createElement("div"); r.className = "lp-row";
      r.innerHTML = `${b.cover ? `<img src="${esc(b.cover)}" alt="">` : `<div class="lp-nocov">${esc((b.title || "?").slice(0, 2))}</div>`}
        <div class="lp-meta"><b>${esc(b.title || "(adsız sırt)")}</b><span>${esc(b.author || "")}</span><span class="lp-st">${ST[b.status] || ""}${b.page ? ` · s.${b.page}` : ""}${(b.notes || []).length ? ` · ${b.notes.length} not` : ""}${b.box ? " · rafta" : ""}</span></div>`;
      r.onclick = () => edit(b); l.append(r);
    });
  }
  function edit(b) {
    const e = $("#lp-edit", panel); e.classList.remove("hidden");
    e.innerHTML = `<div class="lp-e-top"><b>${esc(b.title || "Adsız sırt")}</b><button class="mini" id="le-x">✕</button></div>
      <label>Ad <input id="le-t" value="${esc(b.title)}" list="lp-titles"></label><datalist id="lp-titles">${named().map((x) => `<option value="${esc(x.title)}">`).join("")}</datalist>
      <label>Yazar <input id="le-a" value="${esc(b.author)}"></label>
      <label>Durum <select id="le-s">${Object.keys(ST).map((k) => `<option value="${k}"${b.status === k ? " selected" : ""}>${ST[k]}</option>`).join("")}</select></label>
      <label>Sayfa <input id="le-p" type="number" value="${b.page || 0}" style="width:90px"></label>
      <label>Özet <textarea id="le-sum" rows="3">${esc(b.summary)}</textarea></label>
      <label>Notlar (her satır bir not) <textarea id="le-n" rows="3">${esc((b.notes || []).map((n) => n.t).join("\n"))}</textarea></label>
      <label>Alıntılar (her satır bir alıntı) <textarea id="le-q" rows="2">${esc((b.quotes || []).map((n) => n.t).join("\n"))}</textarea></label>
      <div class="lp-e-btns"><button class="btn-primary" id="le-save">KAYDET</button><button class="mini" id="le-fill">✨ JARVIS doldursun / yeniden yaz</button><button class="mini" id="le-open">📖 AÇ</button><button class="mini btn-danger" id="le-del">SİL</button></div>`;
    $("#le-x", e).onclick = () => e.classList.add("hidden");
    const lines = (id, old) => $(id, e).value.split("\n").map((t) => t.trim()).filter(Boolean).map((t) => (old || []).find((o) => o.t === t) || { t, d: new Date().toISOString().slice(0, 10) });
    $("#le-save", e).onclick = async () => {
      const t = $("#le-t", e).value.trim(), other = named().find((x) => x.title === t && x.id !== b.id && !x.box);
      if (other && b.box) { await api("/api/library/book", { body: { id: other.id, box: b.box } }); await api("/api/library/delete", { body: { id: b.id } }); } // kayıtlı kitabı bu raf kutusuna yerleştir (notlar korunur)
      else await api("/api/library/book", { body: { id: b.id, title: t, author: $("#le-a", e).value.trim(), status: $("#le-s", e).value, page: +$("#le-p", e).value || 0, summary: $("#le-sum", e).value.trim(), notes: lines("#le-n", b.notes), quotes: lines("#le-q", b.quotes) } });
      await load(); renderList(); e.classList.add("hidden");
    };
    $("#le-fill", e).onclick = async () => { $("#le-fill", e).textContent = "yazılıyor…"; await api("/api/library/fill", { body: { title: $("#le-t", e).value.trim() || b.title, force: true } }); await load(); renderList(); edit(data.books.find((x) => x.id === b.id) || b); };
    $("#le-open", e).onclick = () => { panel.classList.add("hidden"); openBook(b.id, null); };
    $("#le-del", e).onclick = async () => { await api("/api/library/delete", { body: { id: b.id } }); await load(); renderList(); e.classList.add("hidden"); };
  }
  async function openPanel() { buildPanel(); await load(); renderList(); panel.classList.remove("hidden"); }

  // ---------------- holografik kitap ----------------
  function buildBook() {
    if (book) return;
    book = document.createElement("div"); book.id = "holobook"; book.className = "hidden";
    book.innerHTML = `<div class="hb-fly"><img id="hb-spine" alt=""></div><div class="hb-pages"><div class="hb-p hb-l"></div><div class="hb-p hb-r"></div></div>
      <div class="hb-nav"><button class="mini" id="hb-prev">◀</button><span id="hb-pn"></span><button class="mini" id="hb-next">▶</button><button class="mini" id="hb-read">🔊 OKU</button><button class="mini" id="hb-x">✕ RAFA KOY</button></div>`;
    document.body.append(book);
    $("#hb-prev", book).onclick = () => flip(-1); $("#hb-next", book).onclick = () => flip(1);
    $("#hb-x", book).onclick = () => closeBook(); $("#hb-read", book).onclick = () => readSummary();
  }
  function spreads(b) {
    const nb = b.notebook && b.notebook.bilinen ? b.notebook : null;
    const li = (a) => (a || []).map((x) => `<li>${esc(x)}</li>`).join("");
    const notes = (b.notes || []).map((n) => `<li>${esc(n.t)} <i>${esc(n.d || "")}</i></li>`).join("") || "<li class='dim'>Henüz not yok. \"not al: …\" de.</li>";
    const quotes = (b.quotes || []).map((n) => `<li>“${esc(n.t)}”</li>`).join("") || "<li class='dim'>Alıntı yok. \"alıntı ekle: …\" de.</li>";
    const unknown = b.title ? (b.notebook && b.notebook.bilinen === false ? "<p class='dim'>JARVIS bu kitabı tanımıyor; sayfa uydurulmadı. Özeti kendin yazabilirsin.</p>" : (!b.notebook ? "<p class='dim'>Sayfalar dolduruluyor…</p>" : "")) : "<p class='dim'>Bu sırtın adı okunamadı. \"Bu kitabın adı …\" de ya da aşağıya yaz.</p><input id='hb-name' placeholder='Kitabın adı'>";
    return [
      [`<h3>${esc(b.title || "ADSIZ KİTAP")}</h3><h4>${esc(b.author || "")}</h4>${b.cover ? `<img class="hb-cover" src="${esc(b.cover)}" alt="">` : ""}`,
       `<h5>KÜNYE</h5><p>Durum: <b>${ST[b.status] || "-"}</b>${b.page ? ` · Sayfa ${b.page}` : ""}</p><h5>ÖZET</h5><p>${esc(b.summary || (nb && nb.ozet) || "")}</p>${unknown}`],
      [`<h5>ANA FİKİRLER</h5><ul>${li(nb && nb.ana_fikirler) || "<li class='dim'>—</li>"}</ul>`,
       `<h5>YAZAR</h5><p>${esc(nb && nb.yazar_hakkinda || "—")}</p><h5>TEMALAR</h5><p>${esc((nb && (nb.temalar || []).join(" · ")) || "—")}</p>`],
      [`<h5>NEDEN OKUMALI</h5><p>${esc(nb && nb.neden_okumali || "—")}</p><h5>KİME UYGUN</h5><p>${esc(nb && nb.kime_uygun || "—")}</p>`,
       `<h5>RAFINDAN BENZER</h5><ul>${li(nb && nb.benzer) || "<li class='dim'>—</li>"}</ul>`],
      [`<h5>NOTLARIN</h5><ul>${notes}</ul>`, `<h5>ALINTILARIN</h5><ul>${quotes}</ul>`],
    ];
  }
  function render() {
    if (!cur) return;
    const b = data.books.find((x) => x.id === cur.id) || cur, sp = spreads(b);
    page = Math.max(0, Math.min(sp.length - 1, page));
    $(".hb-l", book).innerHTML = sp[page][0]; $(".hb-r", book).innerHTML = sp[page][1];
    $("#hb-pn", book).textContent = `${page + 1} / ${sp.length}`;
    const n = $("#hb-name", book); if (n) n.onkeydown = (e) => { if (e.key === "Enter" && n.value.trim()) nameOpen(n.value.trim()); };
  }
  async function openBook(id, crop) {
    buildBook(); await load();
    cur = data.books.find((b) => b.id === id); if (!cur) return;
    page = 0; book.classList.remove("hidden", "closing"); book.classList.add("flying");
    const sp = $("#hb-spine", book); sp.src = crop || cur.cover || ""; sp.style.display = sp.src ? "" : "none";
    setTimeout(() => { book.classList.remove("flying"); book.classList.add("open"); }, 900);
    render();
    if (cur.title && !cur.notebook) { api("/api/library/fill", { body: { title: cur.title } }).then(async () => { await load(); render(); }).catch(() => {}); }
    JV.sound && JV.sound("open");
  }
  function closeBook() {
    if (!cur) return; book.classList.add("closing"); book.classList.remove("open");
    const id = cur.id; cur = null; setTimeout(() => { book.classList.add("hidden"); book.classList.remove("closing"); }, 700);
    glow = { id, until: performance.now() + 1500 };
  }
  let glow = { id: "", until: 0 }, lastFlip = 0;
  function flip(d) { const now = performance.now(); if (!cur || now - lastFlip < 450) return; lastFlip = now; page += d; render(); }
  function readSummary() { if (!cur) return; const b = data.books.find((x) => x.id === cur.id) || cur; const nb = b.notebook || {}; const t = b.summary || nb.ozet; JV.say && JV.say(t ? `${b.title}. ${t}` : "Bu kitabın özeti henüz yok.", JV.currentPersona && JV.currentPersona()); }
  async function nameOpen(title) {
    if (!cur) return "Açık kitap yok.";
    const other = named().find((x) => x.title.toLowerCase() === title.toLowerCase() && x.id !== cur.id && !x.box);
    if (other && cur.box) { await api("/api/library/book", { body: { id: other.id, box: cur.box } }); await api("/api/library/delete", { body: { id: cur.id } }); cur = other; }
    else await api("/api/library/book", { body: { id: cur.id, title } });
    await load(); cur = data.books.find((x) => x.id === cur.id) || cur; render();
    JV.say && JV.say("Tamamdır, ekliyorum.", JV.currentPersona && JV.currentPersona());
    api("/api/library/fill", { body: { title } }).then(async () => { await load(); render(); }).catch(() => {});
  }

  // ---------------- raf taraması (kameradan) ----------------
  async function scan() {
    if (scanning) return;
    if (!(JV.handfx && JV.handfx.active)) { JV.gesture && JV.gesture.start("efekt"); await new Promise((r) => setTimeout(r, 2500)); }
    const v = JV.handfx && JV.handfx.video && JV.handfx.video();
    if (!v || !v.videoWidth) { JV.toast && JV.toast("Kamera açılamadı; raf fotoğrafından ekleyebilirsin (KİTAPLIK paneli)."); return; }
    scanning = true; scanT = performance.now();
    const c = document.createElement("canvas"); c.width = v.videoWidth; c.height = v.videoHeight; c.getContext("2d").drawImage(v, 0, 0);
    const blob = await new Promise((r) => c.toBlob(r, "image/jpeg", 0.92));
    JV.toast && JV.toast("📚 Raf taranıyor… (20-30 sn)", 6000);
    try {
      const r = await fetch(`/api/library/scan?w=${c.width}&h=${c.height}`, { method: "POST", headers: { "x-token": JV.token || "", "Content-Type": "image/jpeg" }, body: blob });
      const j = await r.json(); await load();
      const t = j.error ? "Tarama yapılamadı: " + j.error : `${j.özet}. ${j.tanınan < 5 ? "Bir kez daha tararsan rafa odaklanıp daha fazlasını okurum." : ""}`;
      JV.toast && JV.toast(t, 9000); JV.say && JV.say(t, JV.currentPersona && JV.currentPersona());
    } catch (e) { JV.toast && JV.toast("Tarama hatası: " + e.message); }
    scanning = false; revealT = performance.now();
  }
  let scanT = 0, revealT = 0;

  // ---------------- AR kancası (handfx her karede çağırır) ----------------
  // hands: [{lm, P(ekran), pose, pinch, pointing, sc, st}] · M: landmark→ekran · ctx: tuval
  function arFrame(ctx, hands, M, now) {
    const bx = boxed();
    const scrBox = (b) => { const a = M({ x: b[0], y: b[1] }), c = M({ x: b[2], y: b[3] }); return { x: Math.min(a.x, c.x), y: Math.min(a.y, c.y), w: Math.abs(c.x - a.x), h: Math.abs(c.y - a.y) }; };
    if (scanning) { // tarama çizgisi
      const W = ctx.canvas.width, H = ctx.canvas.height, x = ((now - scanT) / 1800 % 1) * W;
      const g = ctx.createLinearGradient(x - 80, 0, x, 0); g.addColorStop(0, "rgba(255,180,60,0)"); g.addColorStop(1, "rgba(255,180,60,0.55)");
      ctx.fillStyle = g; ctx.fillRect(x - 80, 0, 80, H); ctx.fillStyle = "#ffcf8a"; ctx.font = "14px Share Tech Mono, monospace"; ctx.fillText("KİTAPLIK TARANIYOR…", 20, H - 30);
    }
    if (!bx.length) return { busy: !!cur };
    if (revealT && now - revealT < 2500) bx.forEach((b, i) => { if (now - revealT > i * 25) { const s = scrBox(b.box); ctx.strokeStyle = b.title ? "rgba(80,230,255,0.8)" : "rgba(255,180,60,0.6)"; ctx.setLineDash(b.title ? [] : [4, 4]); ctx.strokeRect(s.x, s.y, s.w, s.h); ctx.setLineDash([]); } });
    if (glow.until > now) { const b = bx.find((x) => x.id === glow.id); if (b) { const s = scrBox(b.box); ctx.shadowColor = "#4df"; ctx.shadowBlur = 20; ctx.strokeStyle = "rgba(120,240,255,0.95)"; ctx.lineWidth = 3; ctx.strokeRect(s.x, s.y, s.w, s.h); ctx.shadowBlur = 0; ctx.lineWidth = 1; } }
    const reg = data.shelf && data.shelf.region;
    let inShelf = false;
    if (cur) { // kitap açıkken: savurma = sayfa, ✊ = kapat, 👍 = oku
      hands.forEach((h) => {
        const vx = h.st.vel ? h.st.vel[0] : 0;
        if (h.pose === "open" && Math.abs(vx) > 22) flip(vx < 0 ? 1 : -1);
        if (h.pose === "open" && h.st.prevSc && h.sc > h.st.prevSc * 1.25 && now - (h.st.pushT || 0) > 900) { h.st.pushT = now; closeBook(); }
        h.st.prevSc = h.sc;
      });
      return { busy: true, holds: { fist: [900, "RAFA KOY", closeBook], thumbs_up: [1000, "ÖZETİ OKU", readSummary] } };
    }
    const pointer = hands.find((h) => h.pointing || h.pinch);
    if (pointer && reg) {
      const tip = pointer.lm[8];
      inShelf = tip.x > reg[0] - 0.05 && tip.x < reg[2] + 0.05 && tip.y > reg[1] - 0.05 && tip.y < reg[3] + 0.05;
      if (inShelf) {
        const ps = M(tip); // nişangâh
        ctx.strokeStyle = "rgba(255,210,140,0.9)"; ctx.beginPath(); ctx.arc(ps.x, ps.y, 9, 0, 6.3); ctx.moveTo(ps.x - 14, ps.y); ctx.lineTo(ps.x + 14, ps.y); ctx.moveTo(ps.x, ps.y - 14); ctx.lineTo(ps.x, ps.y + 14); ctx.stroke();
        let best = null, bd = 1e9; // ucun hizasındaki en yakın sırt (tam üstünde olmak gerekmez)
        bx.forEach((b) => { const cx = (b.box[0] + b.box[2]) / 2, dy = tip.y < b.box[1] ? b.box[1] - tip.y : tip.y > b.box[3] ? tip.y - b.box[3] : 0, d = Math.abs(tip.x - cx) + dy * 1.5; if (d < bd) { bd = d; best = b; } });
        const curSel = bx.find((b) => b.id === sel.id);
        const curD = curSel ? Math.abs(tip.x - (curSel.box[0] + curSel.box[2]) / 2) : 1e9;
        if (best && best.id !== sel.id && bd < curD * 0.7) { if (sel.cand !== best.id) { sel.cand = best.id; sel.candT = now; } else if (now - sel.candT > 150) { sel.id = best.id; sel.since = now; } }
        const s = bx.find((b) => b.id === sel.id);
        if (s) {
          const r = scrBox(s.box);
          ctx.strokeStyle = "rgba(255,180,60,0.95)"; ctx.shadowColor = "#fa4"; ctx.shadowBlur = 14; ctx.lineWidth = 2.5; ctx.strokeRect(r.x - 2, r.y - 2, r.w + 4, r.h + 4); ctx.shadowBlur = 0; ctx.lineWidth = 1;
          const label = ((s.title || "ADI OKUNAMADI") + (s.author ? " · " + s.author.split(" ").slice(-1)[0] : "")).toUpperCase();
          ctx.font = "13px Share Tech Mono, monospace"; const tw = ctx.measureText(label).width;
          ctx.fillStyle = "rgba(10,10,10,0.75)"; ctx.fillRect(r.x + r.w / 2 - tw / 2 - 6, r.y - 26, tw + 12, 20);
          ctx.fillStyle = "#ffcf8a"; ctx.textAlign = "center"; ctx.fillText(label, r.x + r.w / 2, r.y - 11); ctx.textAlign = "left";
          if (pointer.pinch && !pointer.st.bookPinch) { // çimdikle tut → çek
            pointer.st.bookPinch = { id: s.id, sc: pointer.sc, x: tip.x, t: now };
          }
        }
      }
      const bp = pointer.st.bookPinch;
      if (bp && pointer.pinch) { // tutarken kendine çek: el raftan uzaklaşır ya da kameraya yaklaşır → kopar
        const pulled = pointer.sc > bp.sc * 1.2 || !inShelf || now - bp.t > 1200;
        if (pulled) { pointer.st.bookPinch = null; const b = bx.find((x) => x.id === bp.id); if (b) openBook(b.id, crop(b.box)); }
      } else if (!pointer.pinch) pointer.st.bookPinch = null;
    }
    return { busy: false, inShelf };
  }
  function crop(box) {
    const v = JV.handfx && JV.handfx.video && JV.handfx.video(); if (!v || !v.videoWidth) return null;
    const x = box[0] * v.videoWidth, y = box[1] * v.videoHeight, w = (box[2] - box[0]) * v.videoWidth, h = (box[3] - box[1]) * v.videoHeight;
    if (w < 4 || h < 4) return null;
    const c = document.createElement("canvas"); c.width = w; c.height = h; c.getContext("2d").drawImage(v, x, y, w, h, 0, 0, w, h);
    return c.toDataURL("image/jpeg", 0.85);
  }

  // ---------------- komutlar ----------------
  function cmd(r) {
    if (r.action === "scan") return scan();
    if (r.action === "name_open") return nameOpen(r.title || "");
    if (r.action === "open_panel") return openPanel();
  }
  JV.library = { openPanel, openBook, closeBook, scan, cmd, arFrame, load, get open() { return !!cur; }, _data: () => data, flip };
  document.addEventListener("DOMContentLoaded", () => { load(); const b = document.getElementById("t-books"); if (b) b.onclick = openPanel; });
  setTimeout(load, 1500);
})();
