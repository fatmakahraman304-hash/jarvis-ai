/* BİLGİ MERKEZİ: kütüphane paneli (yükle, ara, kaynaklı sor, grafik), quiz ekranı (aralıklı tekrar kartları), 3D bilgi grafiği dünyası. */
(function () {
  const JV = (window.JV = window.JV || {});
  const $ = (s, r = document) => r.querySelector(s);
  const esc = (t) => String(t == null ? "" : t).replace(/[&<>"]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" })[c]);
  let lib, quiz;

  // ---------- kütüphane paneli ----------
  function buildLib() {
    if (lib) return; lib = document.createElement("div"); lib.id = "library"; lib.className = "hidden";
    lib.innerHTML = `<div class="kb-card"><div class="s-head"><span>BİLGİ MERKEZİ</span><span><button class="mini" id="kb-review">🧠 TEKRAR</button> <button class="mini" id="kb-close">KAPAT ✕</button></span></div>
      <div class="kb-drop" id="kb-drop">Belgeleri buraya sürükle ya da <label class="mini">SEÇ<input type="file" id="kb-file" multiple accept=".pdf,.docx,.txt,.md,.html,.htm,.epub,.pptx" hidden></label> · ya da link: <input id="kb-url" placeholder="https://…"><button class="mini" id="kb-addurl">EKLE</button></div>
      <div class="cam-row"><input id="kb-q" placeholder="Kütüphaneye sor (kaynak göstererek cevaplar) ya da ara…"><button class="btn-primary" id="kb-ask">SOR</button><button class="mini" id="kb-search">ARA</button><button class="mini" id="kb-graph">🕸 GRAFİK</button></div>
      <div id="kb-answer" class="kb-answer"></div>
      <div class="kb-cols"><div><h4>BELGELER</h4><div id="kb-docs"></div></div><div><h4>ÖĞRENME</h4><div id="kb-stats"></div></div></div></div>`;
    document.body.append(lib);
    $("#kb-close", lib).onclick = () => lib.classList.add("hidden");
    $("#kb-file", lib).onchange = (e) => upload([...e.target.files]);
    const drop = $("#kb-drop", lib);
    drop.addEventListener("dragover", (e) => { e.preventDefault(); drop.classList.add("over"); });
    drop.addEventListener("dragleave", () => drop.classList.remove("over"));
    drop.addEventListener("drop", (e) => { e.preventDefault(); drop.classList.remove("over"); upload([...e.dataTransfer.files]); });
    $("#kb-addurl", lib).onclick = async () => { const u = $("#kb-url", lib).value.trim(); if (!u) return; say("Ekleniyor…"); const r = await JV.api("/api/knowledge/add", { body: { path: u } }); say(fmt(r.sonuç || r.error)); $("#kb-url", lib).value = ""; refresh(); };
    $("#kb-ask", lib).onclick = ask; $("#kb-q", lib).addEventListener("keydown", (e) => { if (e.key === "Enter") ask(); });
    $("#kb-search", lib).onclick = async () => { const q = $("#kb-q", lib).value.trim(); if (!q) return; const r = await JV.api("/api/knowledge/search", { body: { query: q } }); const h = r.sonuç;
      $("#kb-answer", lib).innerHTML = Array.isArray(h) ? h.map((x) => `<div class="kb-hit"><b>${esc(x.belge)}</b> <em>s.${x.sayfa} · ${x.puan}</em><div>${esc(x.metin)}</div></div>`).join("") : esc(h); };
    $("#kb-graph", lib).onclick = async () => { const q = $("#kb-q", lib).value.trim(); say("Grafik çıkarılıyor…"); const r = await JV.api("/api/knowledge/graph", { body: { topic: q } }); if (r.ui) { lib.classList.add("hidden"); JV.uiCommand("knowledge_graph", {}, JSON.stringify(r)); } else say(r.error || "Grafik yok."); };
    $("#kb-review", lib).onclick = async () => { const r = await JV.api("/api/knowledge/review", { body: {} }); if (r.ui) openQuiz(r); else say(r.note || r.error); };
    lib.addEventListener("click", async (e) => {
      const b = e.target.closest("button[data-doc]"); if (!b) return;
      const act = b.dataset.act, doc = b.dataset.doc;
      if (act === "del") { await JV.api("/api/knowledge/remove", { body: { doc } }); refresh(); }
      else if (act === "graph") { say("Grafik çıkarılıyor…"); const r = await JV.api("/api/knowledge/graph", { body: { doc } }); if (r.ui) { lib.classList.add("hidden"); JV.uiCommand("knowledge_graph", {}, JSON.stringify(r)); } }
      else if (act === "quiz" || act === "sum" || act === "book") {
        lib.classList.add("hidden");
        const txt = { quiz: `"${b.dataset.title}" belgesinden 5 soruluk quiz hazırla (doc=${doc})`, sum: `"${b.dataset.title}" belgesini özetle (doc=${doc})`, book: `"${b.dataset.title}" belgesini sesli kitap yap (doc=${doc})` }[act];
        JV.sendCommand ? JV.sendCommand(txt) : null;
      }
    });
  }
  const fmt = (r) => (typeof r === "string" ? r : r && r.başlık ? `Eklendi: ${r.başlık} (${r.sayfa} sayfa, ${r.parça} parça)` : r && r.eklenen != null ? `${r.eklenen} belge eklendi, ${r.atlanan} atlandı` : JSON.stringify(r));
  const say = (t) => { $("#kb-answer", lib).textContent = t; };
  async function upload(files) {
    for (const f of files) {
      say(`Yükleniyor: ${f.name}…`);
      const r = await fetch(`/api/files/upload?quiet=1&path=${encodeURIComponent("belgeler/JARVIS Kütüphane")}&name=${encodeURIComponent(f.name)}`, { method: "POST", headers: { "x-token": JV.token || "" }, body: f }).then((x) => x.json());
      if (!r.path) { say("Yüklenemedi: " + (r.error || "")); continue; }
      const a = await JV.api("/api/knowledge/add", { body: { path: r.path } }); say(fmt(a.sonuç || a.error));
    }
    refresh();
  }
  async function ask() {
    const q = $("#kb-q", lib).value.trim(); if (!q) return; say("Kaynaklar okunuyor…");
    const r = await JV.api("/api/knowledge/ask", { body: { question: q } }); const a = r.sonuç;
    if (a && a.cevap) { $("#kb-answer", lib).innerHTML = `<div class="kb-ans">${esc(a.cevap).replace(/\n/g, "<br>")}</div><div class="kb-src">${a.kaynaklar.map((k) => `[${k.no}] ${esc(k.belge)} s.${k.sayfa}`).join(" · ")}</div>`; JV.say && JV.say(a.cevap, JV.persona ? JV.persona() : "jarvis"); }
    else say(typeof a === "string" ? a : r.error || "Cevap yok.");
  }
  async function refresh() {
    const docs = await JV.api("/api/knowledge/list");
    $("#kb-docs", lib).innerHTML = docs.length ? docs.map((d) => `<div class="mc-li"><span><b>${esc(d.başlık)}</b> <small>${esc(d.tür)} · ${d.sayfa} s · ${d.parça} parça</small></span><span>
      <button class="mini" data-doc="${d.no}" data-title="${esc(d.başlık)}" data-act="sum" title="Özetle">Ö</button><button class="mini" data-doc="${d.no}" data-title="${esc(d.başlık)}" data-act="quiz" title="Quiz">?</button><button class="mini" data-doc="${d.no}" data-act="graph" title="Grafik">🕸</button><button class="mini" data-doc="${d.no}" data-title="${esc(d.başlık)}" data-act="book" title="Sesli kitap">🎧</button><button class="mini" data-doc="${d.no}" data-act="del" title="Kaldır">✕</button></span></div>`).join("") : '<div class="note">Kütüphane boş. PDF, Word, EPUB… sürükle bırak.</div>';
    const st = await JV.api("/api/knowledge/stats");
    $("#kb-stats", lib).innerHTML = st.length ? st.map((s) => `<div class="mc-li"><span>${esc(s.konu)} <small>${s.kart} kart · %${s["başarı_%"]} · kutu ${s.ustalık_kutusu}</small></span><em>${s.tekrar_bekleyen ? s.tekrar_bekleyen + " tekrar" : "✓"}</em></div>`).join("") : '<div class="note">Henüz quiz yok. "Bana fotosentez hakkında quiz yap" de.</div>';
  }
  function openLib() { buildLib(); lib.classList.remove("hidden"); refresh(); }

  // ---------- quiz ----------
  function openQuiz(r) {
    if (!quiz) { quiz = document.createElement("div"); quiz.id = "quiz"; document.body.append(quiz); }
    const qs = r.questions || []; let i = 0, score = 0;
    quiz.className = "";
    const show = () => {
      if (i >= qs.length) {
        quiz.innerHTML = `<div class="qz-card"><div class="s-head"><span>${esc(r.title).toUpperCase()}</span><button class="mini" id="qz-x">KAPAT ✕</button></div><div class="qz-score">${score} / ${qs.length}</div><div class="note">Yanlışlar yarın, doğrular kutularına göre 1–16 gün sonra tekrar sorulacak (aralıklı tekrar).</div></div>`;
        $("#qz-x", quiz).onclick = () => quiz.classList.add("hidden");
        JV.say && JV.say(`${qs.length} sorudan ${score} doğru.`, JV.persona ? JV.persona() : "jarvis"); return;
      }
      const q = qs[i];
      quiz.innerHTML = `<div class="qz-card"><div class="s-head"><span>${esc(r.title).toUpperCase()} · ${i + 1}/${qs.length}</span><button class="mini" id="qz-x">KAPAT ✕</button></div>
        <div class="qz-q">${esc(q.q)}</div><div class="qz-opts">${q.options.map((o, k) => `<button data-k="${k}">${"ABCD"[k] || k + 1}) ${esc(o)}</button>`).join("")}</div><div class="qz-exp" id="qz-exp"></div></div>`;
      $("#qz-x", quiz).onclick = () => quiz.classList.add("hidden");
      quiz.querySelectorAll("[data-k]").forEach((b) => (b.onclick = async () => {
        const k = +b.dataset.k; quiz.querySelectorAll("[data-k]").forEach((x) => (x.disabled = true));
        let res = { doğru: k === q.answer, doğru_şık: q.answer, açıklama: q.explain };
        if (q.id) { try { res = await JV.api("/api/knowledge/answer", { body: { card: q.id, chosen: k } }); } catch (e) {} }
        if (res.doğru) score++;
        quiz.querySelector(`[data-k="${res.doğru_şık}"]`).classList.add("ok"); if (!res.doğru) b.classList.add("bad");
        $("#qz-exp", quiz).innerHTML = `${res.doğru ? "✓ Doğru" : "✗ Yanlış"} — ${esc(res.açıklama || "")} <button class="mini" id="qz-next">${i + 1 < qs.length ? "SONRAKİ ›" : "SONUÇ"}</button>`;
        $("#qz-next", quiz).onclick = () => { i++; show(); };
      }));
    };
    show();
  }

  // ---------- 3D bilgi grafiği dünyası ----------
  const U = JV.wutil;
  if (U) {
    const T = U.T, scene = new T.Scene(); let root = null, nodes = [], edgesObj = null, data = null, meshes = [];
    scene.add(new T.AmbientLight(0x8899aa, 0.8)); const L = new T.PointLight(0xffffff, 1.2, 0); L.position.set(30, 40, 50); scene.add(L);
    const TYPE_COL = { "kişi": 0xffb020, "yer": 0x22e39a, "kavram": 0x38d6ff, "olay": 0xff5c7a, "nesne": 0xb37dff };
    function layout(ns, es) { // 3D Fruchterman–Reingold
      const n = ns.length, k = 12, P = ns.map(() => new T.Vector3((Math.random() - 0.5) * 40, (Math.random() - 0.5) * 40, (Math.random() - 0.5) * 40));
      const idx = Object.fromEntries(ns.map((x, i) => [x.id, i]));
      const E = es.map((e) => [idx[e.a], idx[e.b]]).filter(([a, b]) => a != null && b != null && a !== b);
      for (let it = 0; it < 300; it++) {
        const D = P.map(() => new T.Vector3()), temp = 6 * (1 - it / 300) + 0.2;
        for (let a = 0; a < n; a++) for (let b = a + 1; b < n; b++) { const d = P[a].clone().sub(P[b]); const l = Math.max(0.1, d.length()); if (l > 3 * k) continue; d.multiplyScalar((k * k) / (l * l)); D[a].add(d); D[b].sub(d); }
        for (const [a, b] of E) { const d = P[a].clone().sub(P[b]); const l = Math.max(0.1, d.length()); d.multiplyScalar(l / k); D[a].sub(d); D[b].add(d); }
        for (let a = 0; a < n; a++) { D[a].sub(P[a].clone().multiplyScalar(0.12)); const l = D[a].length(); if (l > 0) P[a].addScaledVector(D[a], Math.min(l, temp) / l); }
      }
      const c = P.reduce((a, v) => a.add(v), new T.Vector3()).divideScalar(Math.max(1, n)); P.forEach((v) => v.sub(c)); // ortala
      return { P, E };
    }
    function show(r) {
      if (root) { scene.remove(root); U.disposeTree(root); } root = new T.Group(); scene.add(root); data = r; meshes = [];
      const { P, E } = layout(r.nodes, r.edges); nodes = r.nodes;
      const R = Math.max(10, P.map((v) => v.length()).sort((x, y) => x - y)[Math.floor(P.length * 0.9)] || 10), ls = Math.max(1, R / 22);
      const deg = r.nodes.map((_, i) => E.filter(([a, b]) => a === i || b === i).length);
      r.nodes.forEach((nd, i) => {
        const col = TYPE_COL[nd.type] || new T.Color().setHSL((i * 0.137) % 1, 0.65, 0.6).getHex();
        const m = new T.Mesh(new T.SphereGeometry((0.6 + Math.sqrt(deg[i] + 1) * 0.35) * ls, 20, 14), new T.MeshPhongMaterial({ color: col, emissive: col, emissiveIntensity: 0.35 }));
        m.position.copy(P[i]); m.userData = { i }; root.add(m); meshes.push(m);
        const lb = U.label(nd.id, "#e8f6ff", 44); lb.scale.multiplyScalar(18 * ls); lb.position.copy(P[i]).add(new T.Vector3(0, (1.6 + Math.sqrt(deg[i] + 1) * 0.3) * ls, 0)); root.add(lb);
      });
      const pos = []; E.forEach(([a, b]) => pos.push(P[a].x, P[a].y, P[a].z, P[b].x, P[b].y, P[b].z));
      edgesObj = new T.LineSegments(new T.BufferGeometry().setAttribute("position", new T.Float32BufferAttribute(pos, 3)), new T.LineBasicMaterial({ color: 0x5fb8d8, transparent: true, opacity: 0.45 }));
      root.add(edgesObj);
      U.camera.position.set(0, R * 0.25, R * 2.4); U.controls.target.set(0, 0, 0);
      U.panel(`<div class="wp-title">${esc(r.title)}</div><div class="wp-grid"><i>Kavram</i><b>${r.nodes.length}</b><i>Bağlantı</i><b>${E.length}</b><i>Yöntem</i><b>${esc(r.yöntem || "")}</b></div><p class="note">Bir kavrama tıkla: bağlantıları ve açıklaması.</p>`);
    }
    JV.worlds.graph = {
      scene,
      enter() { U.controls.enablePan = true; U.controls.minDistance = 5; U.controls.maxDistance = 400; if (!root) show({ title: "Bilgi grafiği", nodes: [{ id: "JARVIS" }], edges: [] }); },
      exit() {},
      update(dt) { if (root) root.rotation.y += dt * 0.03; },
      click(ray) {
        const h = ray.intersectObjects(meshes)[0]; if (!h) return;
        const i = h.object.userData.i, nd = nodes[i];
        meshes.forEach((m) => (m.material.emissiveIntensity = 0.15));
        const nb = data.edges.filter((e) => e.a === nd.id || e.b === nd.id);
        const ids = new Set(nb.flatMap((e) => [e.a, e.b])); meshes.forEach((m, k) => { if (ids.has(nodes[k].id)) m.material.emissiveIntensity = 0.9; });
        U.panel(`<div class="wp-title">${esc(nd.id)}</div><div class="wp-grid">${nd.type ? `<i>Tür</i><b>${esc(nd.type)}</b>` : ""}<i>Bağlantı</i><b>${nb.length}</b></div>${nd.info ? `<p>${esc(nd.info)}</p>` : ""}<div>${nb.map((e) => `<div class="mc-li"><span>${esc(e.a === nd.id ? e.b : e.a)}</span><em>${esc(e.rel || "")}</em></div>`).join("")}</div>`);
      },
      cmd: show,
    };
  }

  JV.knowledge = { open: openLib, quiz: openQuiz };
  document.addEventListener("DOMContentLoaded", () => { const b = $("#t-library"); if (b) b.onclick = openLib; });
})();
