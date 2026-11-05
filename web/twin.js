/* DİJİTAL İKİZ (bilgisayar + ev) ve BİYOLOJİ (gerçek protein yapıları + hücre) dünyaları. */
(function () {
  const JV = window.JV; if (!JV || !JV.wutil) return;
  const U = JV.wutil, T = U.T, camera = U.camera, controls = U.controls;
  const esc = (t) => String(t == null ? "" : t).replace(/[&<>"]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" })[c]);
  const heat = (k) => new T.Color().setHSL(0.55 - 0.55 * Math.max(0, Math.min(1, k)), 0.9, 0.5); // mavi → kırmızı
  function lbl(text, scale = 1, color = "#cfefff") { const s = U.label(text, color, 44); s.scale.multiplyScalar(scale * 10); return s; }
  function capsule(r, len, seg = 10) { // r128'de CapsuleGeometry yok: döndürme yüzeyi ile
    const pts = [];
    for (let i = 0; i <= seg; i++) { const a = -Math.PI / 2 + (i / seg) * Math.PI / 2; pts.push(new T.Vector2(Math.cos(a) * r, Math.sin(a) * r - len / 2)); }
    for (let i = 0; i <= seg; i++) { const a = (i / seg) * Math.PI / 2; pts.push(new T.Vector2(Math.cos(a) * r, Math.sin(a) * r + len / 2)); }
    return new T.LatheGeometry(pts, 20);
  }
  function std(c, e = 0.2, o = 1) { return new T.MeshStandardMaterial({ color: c, emissive: c, emissiveIntensity: e, metalness: 0.4, roughness: 0.45, transparent: o < 1, opacity: o }); }

  // =====================================================================
  // DİJİTAL İKİZ
  // =====================================================================
  const tScene = new T.Scene();
  tScene.add(new T.AmbientLight(0x8899aa, 0.7)); const tl = new T.DirectionalLight(0xffffff, 0.9); tl.position.set(20, 30, 25); tScene.add(tl);
  tScene.add(new T.GridHelper(80, 40, 0x1d4a5e, 0x0c2230));
  let tRoot = null, tKind = "pc", tTimer = 0, tUpdate = null, tClick = null, tData = null;

  function tReset(kind) {
    if (tRoot) { tScene.remove(tRoot); U.disposeTree(tRoot); }
    tRoot = new T.Group(); tScene.add(tRoot); tKind = kind; tUpdate = null; tClick = null; U.caption("");
  }

  // ---------- bilgisayar ----------
  function buildPC() {
    tReset("pc"); camera.position.set(26, 20, 30); controls.target.set(0, 7, 0);
    const caseW = 20, caseH = 18, caseD = 10;
    const glass = new T.Mesh(new T.BoxGeometry(caseW, caseH, caseD), new T.MeshPhongMaterial({ color: 0x38d6ff, transparent: true, opacity: 0.06, depthWrite: false }));
    glass.position.y = caseH / 2; tRoot.add(glass);
    const edges = new T.LineSegments(new T.EdgesGeometry(glass.geometry), new T.LineBasicMaterial({ color: 0x38d6ff, transparent: true, opacity: 0.6 })); edges.position.copy(glass.position); tRoot.add(edges);
    const board = new T.Mesh(new T.BoxGeometry(16, 15, 0.3), std(0x0d3b2c, 0.15)); board.position.set(-1, 9, -caseD / 2 + 0.5); tRoot.add(board);
    // CPU soketi + çekirdek ızgarası
    const cpu = new T.Group(); cpu.position.set(-1, 12, -caseD / 2 + 1.2); tRoot.add(cpu);
    cpu.add(new T.Mesh(new T.BoxGeometry(4.2, 4.2, 0.4), std(0x777777, 0.1)));
    const cores = []; let coreN = 0;
    function makeCores(n) {
      cores.forEach((c) => cpu.remove(c)); cores.length = 0; coreN = n;
      const g = Math.ceil(Math.sqrt(n)), s = 3.6 / g;
      for (let i = 0; i < n; i++) { const m = new T.Mesh(new T.BoxGeometry(s * 0.8, s * 0.8, 0.3), std(0x2266ff, 0.6)); m.position.set(-1.8 + s / 2 + (i % g) * s, 1.8 - s / 2 - Math.floor(i / g) * s, 0.35); cpu.add(m); cores.push(m); }
    }
    const cpuL = lbl("CPU", 0.8); cpuL.position.set(-1, 15.2, -caseD / 2 + 1.5); tRoot.add(cpuL);
    // soğutucu fanı
    const fan = (r) => { const g = new T.Group(); for (let i = 0; i < 7; i++) { const b = new T.Mesh(new T.BoxGeometry(r * 0.9, 0.15, r * 0.35), std(0x99aabb, 0.1)); b.position.x = r * 0.45; const p = new T.Group(); p.rotation.y = (i / 7) * Math.PI * 2; b.rotation.x = 0.4; p.add(b); g.add(p); } g.add(new T.Mesh(new T.CylinderGeometry(r * 0.2, r * 0.2, 0.3, 16), std(0x222222))); const ring = new T.Mesh(new T.TorusGeometry(r, 0.12, 8, 32), std(0x38d6ff, 0.6)); ring.rotation.x = Math.PI / 2; g.add(ring); return g; };
    const cpuFan = fan(2); cpuFan.rotation.x = Math.PI / 2; cpuFan.position.set(-1, 12, -caseD / 2 + 3.2); tRoot.add(cpuFan);
    const caseFans = [fan(2.3), fan(2.3)]; caseFans[0].rotation.z = Math.PI / 2; caseFans[0].position.set(caseW / 2 - 0.3, 13, 0); caseFans[1].rotation.z = Math.PI / 2; caseFans[1].position.set(caseW / 2 - 0.3, 7, 0);
    caseFans.forEach((f) => tRoot.add(f));
    // RAM modülleri
    const rams = []; for (let i = 0; i < 4; i++) { const g = new T.Group(); g.position.set(3.3 + i * 0.75, 11, -caseD / 2 + 1.5); const shell = new T.Mesh(new T.BoxGeometry(0.35, 5, 1.6), std(0x333333, 0.05, 0.5)); g.add(shell); const fill = new T.Mesh(new T.BoxGeometry(0.36, 5, 1.62), std(0x22e39a, 0.7)); g.add(fill); rams.push(fill); tRoot.add(g); }
    const ramL = lbl("RAM", 0.7); ramL.position.set(4.4, 14.4, -caseD / 2 + 1.5); tRoot.add(ramL);
    // GPU
    const gpu = new T.Group(); gpu.position.set(-1, 6, -caseD / 2 + 3); tRoot.add(gpu);
    gpu.add(new T.Mesh(new T.BoxGeometry(12, 1.2, 4.5), std(0x1a1f26, 0.1)));
    const gFans = [fan(1.4), fan(1.4)]; gFans.forEach((f, i) => { f.position.set(-2.8 + i * 5.6, -0.7, 0); gpu.add(f); });
    const gpuBar = new T.Mesh(new T.BoxGeometry(12, 0.15, 0.15), std(0xff5c7a, 1)); gpuBar.position.set(0, 0.7, 2.3); gpu.add(gpuBar);
    const gpuL = lbl("GPU", 0.7); gpuL.position.set(-1, 7.6, -caseD / 2 + 5.4); tRoot.add(gpuL);
    // diskler
    const disks = new T.Group(); disks.position.set(-7.5, 1.6, 1.5); tRoot.add(disks);
    // güç kaynağı
    const psu = new T.Mesh(new T.BoxGeometry(6, 3, 6), std(0x222831, 0.05)); psu.position.set(5.5, 1.6, 0); tRoot.add(psu);
    const psuL = lbl("PSU", 0.6); psuL.position.set(5.5, 3.8, 0); tRoot.add(psuL);
    // ağ portu ve veri akışı
    const port = new T.Mesh(new T.BoxGeometry(0.6, 1, 1.4), std(0xffb020, 0.5)); port.position.set(-caseW / 2, 15, -2); tRoot.add(port);
    const flowN = 300, flowPos = new Float32Array(flowN * 3), flowSeed = Array.from({ length: flowN }, () => [Math.random(), Math.random() < 0.5 ? 1 : -1, (Math.random() - 0.5) * 1.2, (Math.random() - 0.5) * 1.2]);
    const flow = new T.Points(new T.BufferGeometry().setAttribute("position", new T.BufferAttribute(flowPos, 3)), new T.PointsMaterial({ color: 0xffd060, size: 0.28, transparent: true, opacity: 0.9, blending: T.AdditiveBlending, depthWrite: false }));
    tRoot.add(flow);
    let d = null, fanSpin = 0, gSpin = 0, cfSpin = 0, netIn = 0, netOut = 0, diskLeds = [];
    tUpdate = (dt) => {
      if (d) {
        fanSpin += dt * (2 + d.cpu / 8); cpuFan.rotation.y = fanSpin;
        cfSpin += dt * (3 + d.cpu / 15); caseFans.forEach((f) => (f.rotation.y = cfSpin));
        gSpin += dt * (d.gpu ? 1 + (d.gpu.kullanım || 0) / 6 : 0.4); gFans.forEach((f) => (f.rotation.y = gSpin));
        diskLeds.forEach((l) => (l.material.emissiveIntensity = Math.random() < Math.min(0.95, (d.disk_okuma_mbs + d.disk_yazma_mbs) / 20) ? 2 : 0.1));
      }
      // ağ parçacıkları: dışarıdan porta (indirme) ve porttan dışarı (yükleme), miktar hızla orantılı
      const inK = Math.min(1, netIn * 8), outK = Math.min(1, netOut * 8);
      for (let i = 0; i < flowN; i++) {
        const s = flowSeed[i]; s[0] += dt * 0.6; if (s[0] > 1) { s[0] -= 1; s[1] = Math.random() < inK / (inK + outK + 1e-6) ? 1 : -1; }
        const active = (s[1] > 0 ? inK : outK) > (i / flowN);
        const t = s[1] > 0 ? s[0] : 1 - s[0];
        flowPos.set(active ? [-caseW / 2 - 14 + t * 14, 15 + s[2], -2 + s[3]] : [0, -999, 0], i * 3);
      }
      flow.geometry.attributes.position.needsUpdate = true;
    };
    async function poll() {
      try { d = await JV.api("/api/twin/pc"); } catch (e) { return; }
      tData = d; if (d.error) { U.panel(`<div class="wp-title">BİLGİSAYAR İKİZİ</div><p class="note">${esc(d.error)}</p>`); return; }
      if (coreN !== d.çekirdekler.length) makeCores(d.çekirdekler.length);
      d.çekirdekler.forEach((v, i) => { const c = heat(v / 100); cores[i].material.color.copy(c); cores[i].material.emissive.copy(c); cores[i].scale.z = 1 + v / 25; });
      rams.forEach((r, i) => { const k = Math.max(0, Math.min(1, d.ram_yüzde / 100 * 4 - i)); r.scale.y = Math.max(0.001, k); r.position.y = -2.5 + 2.5 * k; r.material.color.copy(heat(d.ram_yüzde / 100)); });
      if (d.gpu) { gpuBar.scale.x = Math.max(0.02, (d.gpu.kullanım || 0) / 100); gpuBar.position.x = -6 + 6 * gpuBar.scale.x; }
      if (disks.children.length !== d.diskler.length * 3) {
        disks.clear(); diskLeds = [];
        d.diskler.forEach((k, i) => { const b = new T.Mesh(new T.BoxGeometry(3.5, 0.9, 5), std(0x30363f, 0.05)); b.position.y = i * 1.2; disks.add(b); const led = new T.Mesh(new T.BoxGeometry(0.2, 0.2, 0.2), std(0x22e39a, 0.1)); led.position.set(1.9, i * 1.2, 2.3); disks.add(led); diskLeds.push(led); const bar = new T.Mesh(new T.BoxGeometry(0.1, 0.5, 4.6), std(0xffb020, 0.7)); bar.position.set(-1.8, i * 1.2, 0); disks.add(bar); });
      }
      d.diskler.forEach((k, i) => { const bar = disks.children[i * 3 + 2]; if (bar) { bar.scale.z = Math.max(0.02, k.yüzde / 100); bar.material.color.copy(heat(k.yüzde / 100)); } });
      netIn = d.ağ_indirme_mbs; netOut = d.ağ_yükleme_mbs;
      const temps = Object.entries(d.sıcaklıklar || {}).slice(0, 4);
      U.panel(`<div class="wp-title">BİLGİSAYAR İKİZİ · CANLI</div><div class="wp-grid">
        <i>CPU</i><b>%${Math.round(d.cpu)} · ${d.çekirdekler.length} çekirdek${d.frekans_mhz ? " · " + d.frekans_mhz + " MHz" : ""}</b>
        <i>RAM</i><b>%${d.ram_yüzde} · ${d.ram_gb}/${d.ram_toplam_gb} GB</b>
        ${d.gpu ? `<i>GPU</i><b>${esc(d.gpu.ad)} · %${d.gpu.kullanım}${d.gpu.sıcaklık != null ? " · " + d.gpu.sıcaklık + "°C" : ""}</b>` : `<i>GPU</i><b>veri yok (NVIDIA değil ya da sürücü aracı yok)</b>`}
        <i>Disk G/Ç</i><b>↓${d.disk_okuma_mbs} ↑${d.disk_yazma_mbs} MB/s</b><i>Ağ</i><b>↓${d.ağ_indirme_mbs} ↑${d.ağ_yükleme_mbs} MB/s</b>
        ${d.diskler.map((k) => `<i>${esc(k.ad)}</i><b>%${k.yüzde} · ${k.boş_gb} GB boş</b>`).join("")}
        ${temps.length ? temps.map(([k, v]) => `<i>${esc(k)}</i><b>${v} °C</b>`).join("") : `<i>Sıcaklık</i><b>sensör erişimi yok</b>`}
        ${d.pil ? `<i>Pil</i><b>%${d.pil.yüzde} ${d.pil.şarjda ? "şarjda" : ""}</b>` : ""}</div>
        <div class="wp-title" style="font-size:11px;margin-top:8px">EN ÇOK RAM</div>${d.en_çok_ram.map((p) => `<div class="mc-li"><span>${esc(p.ad)}</span><em>${p.mb} MB</em></div>`).join("")}
        <p class="note">Çekirdek blokları yüke göre yükselir ve kızarır; fanlar yüke göre döner; sarı parçacıklar ağ trafiği.</p>`);
    }
    poll(); tTimer = setInterval(poll, 2000);
  }

  // ---------- ev ----------
  async function buildHome() {
    tReset("home"); camera.position.set(0, 40, 42); controls.target.set(0, 0, 0);
    let d; try { d = await JV.api("/api/twin/home"); } catch (e) { d = { bağlı: false, not: e.message }; }
    const demo = !d.bağlı;
    if (demo) d = { odalar: [{ ad: "Salon", cihazlar: [{ id: "light.salon", ad: "Salon ışığı", durum: "on" }, { id: "sensor.salon_t", ad: "Sıcaklık", durum: "22.5", birim: "°C" }, { id: "media_player.tv", ad: "TV", durum: "off" }] },
      { ad: "Mutfak", cihazlar: [{ id: "light.mutfak", ad: "Mutfak ışığı", durum: "off" }, { id: "binary_sensor.kapi", ad: "Arka kapı", durum: "off", cihaz_sınıfı: "door" }] },
      { ad: "Yatak odası", cihazlar: [{ id: "light.yatak", ad: "Abajur", durum: "off" }, { id: "climate.klima", ad: "Klima", durum: "cool" }] }, { ad: "Banyo", cihazlar: [{ id: "sensor.nem", ad: "Nem", durum: "61", birim: "%" }] }] };
    const rooms = d.odalar, cols = Math.ceil(Math.sqrt(rooms.length)), RW = 14, RD = 11, devMeshes = [];
    rooms.forEach((r, i) => {
      const x = (i % cols - (cols - 1) / 2) * (RW + 1), z = (Math.floor(i / cols) - (Math.ceil(rooms.length / cols) - 1) / 2) * (RD + 1);
      const floor = new T.Mesh(new T.BoxGeometry(RW, 0.3, RD), std(0x1b2a36, 0.05)); floor.position.set(x, 0, z); tRoot.add(floor);
      const walls = new T.LineSegments(new T.EdgesGeometry(new T.BoxGeometry(RW, 3, RD)), new T.LineBasicMaterial({ color: 0x38d6ff, transparent: true, opacity: 0.5 })); walls.position.set(x, 1.5, z); tRoot.add(walls);
      const l = lbl(r.ad, 1.1); l.position.set(x, 4.2, z - RD / 2 + 1); tRoot.add(l);
      r.cihazlar.slice(0, 12).forEach((c, k) => {
        const dx = x - RW / 2 + 2 + (k % 4) * 3.3, dz = z - RD / 2 + 3 + Math.floor(k / 4) * 3, dom = c.id.split(".")[0];
        const on = ["on", "open", "heat", "cool", "playing", "unlocked", "home"].includes(c.durum);
        let m;
        if (dom === "light") { m = new T.Mesh(new T.SphereGeometry(0.6, 16, 12), std(on ? 0xffd060 : 0x444444, on ? 1.5 : 0.05)); m.position.set(dx, 2.4, dz); if (on) { const pl = new T.PointLight(0xffd080, 0.8, 9); pl.position.copy(m.position); tRoot.add(pl); } }
        else if (dom === "binary_sensor") { m = new T.Mesh(new T.BoxGeometry(0.8, 1.6, 0.2), std(on ? 0xff3b4e : 0x22e39a, 0.8)); m.position.set(dx, 1, dz); }
        else if (dom === "sensor" || dom === "climate") { m = new T.Mesh(new T.CylinderGeometry(0.4, 0.4, 1, 12), std(0x38d6ff, 0.4)); m.position.set(dx, 0.7, dz); }
        else { m = new T.Mesh(new T.BoxGeometry(1, 1, 1), std(on ? 0x22e39a : 0x555555, on ? 0.7 : 0.05)); m.position.set(dx, 0.7, dz); }
        m.userData = c; tRoot.add(m); devMeshes.push(m);
        const val = dom === "sensor" ? `${c.durum}${c.birim || ""}` : dom === "binary_sensor" ? (on ? "AÇIK" : "kapalı") : c.durum;
        const vl = lbl(`${c.ad}: ${val}`, 0.75, on ? "#ffe9a8" : "#9fb7c8"); vl.position.set(dx, m.position.y + 1.4, dz); tRoot.add(vl);
      });
    });
    tClick = async (ray) => {
      const h = ray.intersectObjects(devMeshes)[0]; if (!h) return; const c = h.object.userData;
      if (demo) { U.caption(`${c.ad} (örnek) — gerçek kontrol için Home Assistant bağla`); return; }
      const r = await JV.api("/api/twin/toggle", { body: { id: c.id } }); U.caption(typeof r.sonuç === "string" ? r.sonuç : `${c.ad} değiştirildi`); setTimeout(buildHome, 900);
    };
    U.panel(`<div class="wp-title">EV İKİZİ${demo ? " · ÖRNEK" : " · CANLI"}</div><div class="wp-grid"><i>Oda</i><b>${rooms.length}</b><i>Cihaz</i><b>${rooms.reduce((s, r) => s + r.cihazlar.length, 0)}</b></div>
      <p class="note">${demo ? esc(d.not || "Home Assistant bağlı değil; bu bir örnek düzendir.") : "Bir cihaza tıkla: aç/kapat. Durum 10 sn'de bir yenilenir."}</p>`);
    if (!demo) tTimer = setTimeout(() => { if (JV.getView() === "twin" && tKind === "home") buildHome(); }, 10000);
  }

  JV.worlds.twin = {
    scene: tScene,
    enter() { controls.enablePan = true; controls.minDistance = 5; controls.maxDistance = 300; if (!tRoot) buildPC(); else if (tKind === "pc" && !tTimer) buildPC(); },
    exit() { clearInterval(tTimer); clearTimeout(tTimer); tTimer = 0; },
    update(dt) { if (tUpdate) tUpdate(dt); },
    click(ray) { if (tClick) tClick(ray); },
    cmd(r) { clearInterval(tTimer); clearTimeout(tTimer); tTimer = 0; (r.kind === "home" ? buildHome : buildPC)(); },
  };

  // =====================================================================
  // BİYOLOJİ: PROTEİN + HÜCRE
  // =====================================================================
  const bScene = new T.Scene();
  bScene.add(new T.AmbientLight(0x8899aa, 0.65)); const bl = new T.DirectionalLight(0xffffff, 0.95); bl.position.set(30, 40, 50); bScene.add(bl);
  const bl2 = new T.DirectionalLight(0x88aaff, 0.4); bl2.position.set(-30, -10, -40); bScene.add(bl2);
  let bRoot = null, bUpdate = null, bClick = null;
  function bReset() { if (bRoot) { bScene.remove(bRoot); U.disposeTree(bRoot); } bRoot = new T.Group(); bScene.add(bRoot); bUpdate = null; bClick = null; U.caption(""); }
  const CPK = { C: 0x909090, N: 0x3050f8, O: 0xff0d0d, S: 0xffff30, P: 0xff8000, H: 0xffffff, FE: 0xe06633, ZN: 0x7d80b0, MG: 0x8aff00, CA: 0x3dff00, CL: 0x1ff01f, NA: 0xab5cf2, K: 0x8f40d4, CU: 0xc88033, MN: 0x9c7ac7 };
  const CHAIN_COLS = [0x38d6ff, 0x22e39a, 0xffb020, 0xb37dff, 0xff7a59, 0x5cc8ff, 0xf15bb5, 0x9be564];

  async function protein(r) {
    bReset(); U.panel(`<div class="wp-title">PROTEİN</div><p class="note">RCSB PDB'den indiriliyor: ${esc(r.query)}…</p>`);
    let d; try { d = await JV.api("/api/twin/protein?q=" + encodeURIComponent(r.query || "1CRN")); } catch (e) { d = { error: e.message }; }
    if (d.error) { U.panel(`<div class="wp-title">PROTEİN</div><p class="note">${esc(d.error)}</p>`); return; }
    const A = d.atoms, c = new T.Vector3(); A.forEach((a) => c.add(new T.Vector3(a[0], a[1], a[2]))); c.divideScalar(A.length);
    let R = 0; A.forEach((a) => { R = Math.max(R, Math.hypot(a[0] - c.x, a[1] - c.y, a[2] - c.z)); });
    const ss = (ch, seq) => d.helices.some(([hc, a, b]) => hc === ch && seq >= a && seq <= b) ? "H" : d.sheets.some(([sc, a, b]) => sc === ch && seq >= a && seq <= b) ? "E" : "C";
    const style = r.style === "atoms" || A.length < 120 ? "atoms" : "cartoon";
    const chains = {};
    A.forEach((a) => { if (!a[8] && (a[6] === "CA" || a[6] === "P")) (chains[a[4]] = chains[a[4]] || []).push(a); });
    const chainIds = Object.keys(chains);
    if (style === "cartoon" && chainIds.length) {
      chainIds.forEach((ch, ci) => {
        const pts = chains[ch].sort((p, q) => p[5] - q[5]);
        // zincir kırıklarında ayrı parçalar
        let seg = [];
        const flush = () => {
          if (seg.length < 4) { seg = []; return; }
          const curve = new T.CatmullRomCurve3(seg.map((p) => new T.Vector3(p[0] - c.x, p[1] - c.y, p[2] - c.z)));
          const n = seg.length * 6, geo = new T.TubeGeometry(curve, n, 0.45, 8, false);
          const cols = [], base = new T.Color(CHAIN_COLS[ci % CHAIN_COLS.length]);
          const ring = geo.attributes.position.count / (n + 1);
          for (let k = 0; k <= n; k++) {
            const res = seg[Math.min(seg.length - 1, Math.round((k / n) * (seg.length - 1)))], s = ss(ch, res[5]);
            const col = s === "H" ? new T.Color(0xff4d6d) : s === "E" ? new T.Color(0xffd23f) : base;
            for (let j = 0; j < ring; j++) cols.push(col.r, col.g, col.b);
          }
          geo.setAttribute("color", new T.Float32BufferAttribute(cols, 3));
          const m = new T.Mesh(geo, new T.MeshStandardMaterial({ vertexColors: true, roughness: 0.4, metalness: 0.1 })); m.userData = { chain: ch }; bRoot.add(m); seg = [];
        };
        pts.forEach((p, k) => { if (k && (Math.hypot(p[0] - pts[k - 1][0], p[1] - pts[k - 1][1], p[2] - pts[k - 1][2]) > 8.5)) flush(); seg.push(p); });
        flush();
      });
    }
    // atomlar: tümü (atom stili) ya da yalnızca ligandlar (çizgi film stilinde)
    const show = style === "atoms" ? A.filter((a) => a[3] !== "H") : A.filter((a) => a[8] && !["HOH", "WAT"].includes(a[7]));
    if (show.length) {
      const geo = new T.SphereGeometry(1, 10, 8), mat = new T.MeshStandardMaterial({ roughness: 0.35, metalness: 0.1 });
      const inst = new T.InstancedMesh(geo, mat, show.length), m4 = new T.Matrix4(), col = new T.Color();
      show.forEach((a, i) => { const rr = style === "atoms" ? (a[3] === "C" ? 0.75 : 0.68) : 0.5; m4.makeScale(rr, rr, rr).setPosition(a[0] - c.x, a[1] - c.y, a[2] - c.z); inst.setMatrixAt(i, m4); inst.setColorAt(i, col.setHex(CPK[a[3]] || 0xff66cc)); });
      inst.instanceMatrix.needsUpdate = true; if (inst.instanceColor) inst.instanceColor.needsUpdate = true; bRoot.add(inst);
      bClick = (ray) => { const h = ray.intersectObject(inst)[0]; if (h) { const a = show[h.instanceId]; U.caption(`${a[7]} ${a[5]} · zincir ${a[4]} · atom ${a[6]} (${a[3]})`); } };
    }
    camera.position.set(0, R * 0.3, R * 2.6); controls.target.set(0, 0, 0);
    bUpdate = (dt) => { bRoot.rotation.y += dt * 0.12; };
    const I = d.info;
    U.panel(`<div class="wp-title">${esc(I.kod)} · ${esc(I.tanım || "Protein")}</div><div class="wp-grid">
      ${I.başlık ? `<i>Başlık</i><b>${esc(I.başlık)}</b>` : ""}${I.organizma ? `<i>Organizma</i><b>${esc(I.organizma)}</b>` : ""}
      ${I.yöntem ? `<i>Yöntem</i><b>${esc(I.yöntem)}</b>` : ""}${I.çözünürlük_Å ? `<i>Çözünürlük</i><b>${I.çözünürlük_Å} Å</b>` : ""}
      <i>Zincir</i><b>${I.zincir}</b><i>Kalıntı</i><b>${U.fmt(I.kalıntı)}</b><i>Atom</i><b>${U.fmt(I.atom)}</b>${I.ligandlar.length ? `<i>Ligand</i><b>${esc(I.ligandlar.join(", "))}</b>` : ""}</div>
      <p class="note">${style === "cartoon" ? "Kırmızı: α-sarmal · sarı: β-tabaka · zincir renkleri: diğer kısımlar · küreler: bağlı küçük moleküller (ligand)." : "Atom renkleri CPK: gri C, mavi N, kırmızı O, sarı S."} Gerçek deneysel koordinatlar (RCSB PDB).</p>`);
  }

  // ---------- hücre ----------
  const ORG = {
    çekirdek: "Kromozomlarda DNA'yı saklar; genlerin ne zaman okunacağını yönetir. Çift katlı zar ve nükleer porlarla çevrilidir.",
    çekirdekçik: "Ribozom RNA'sının (rRNA) üretildiği ve ribozom alt birimlerinin birleştirildiği bölge.",
    mitokondri: "Hücresel solunumla ATP üretir (enerji santrali). Kendi DNA'sı vardır; iç zarı kıvrımlıdır (krista).",
    "endoplazmik retikulum": "Granüllü ER ribozomlarıyla protein sentezler ve katlar; düz ER yağ (lipit) üretir ve zehir giderir.",
    golgi: "Proteinleri değiştirir, paketler ve kesecikler halinde hedeflerine gönderir (hücrenin postanesi).",
    lizozom: "Sindirim enzimleri taşır; yıpranmış organelleri ve yabancı maddeleri parçalar.",
    ribozom: "mRNA'daki şifreyi okuyarak amino asitlerden protein yapar.",
    sentrozom: "Hücre bölünmesinde iğ ipliklerini organize eden mikrotübül merkezi.",
    "hücre zarı": "Fosfolipit çift katmanı; madde giriş-çıkışını seçici olarak denetler.",
    kloroplast: "Fotosentez yapar: ışık enerjisiyle CO₂ ve sudan glikoz ve oksijen üretir. Klorofil içerir.",
    koful: "Bitkide büyük merkezi koful su depolar ve turgor basıncıyla hücreyi dik tutar.",
    "hücre duvarı": "Selülozdan sert dış katman; bitki hücresine şekil ve dayanıklılık verir.",
    nükleoid: "Bakterinin halkasal DNA'sının bulunduğu, zarla çevrili olmayan bölge.",
    plazmit: "Küçük halkasal DNA; antibiyotik direnci gibi genler taşıyabilir.",
    kamçı: "Bakteriyi döner motor gibi iterek hareket ettirir (flagellum).",
    pili: "Yüzeye tutunma ve DNA aktarımı (konjugasyon) için kıl benzeri uzantılar.",
    kapsül: "Bakteriyi kurumaya ve bağışıklık sistemine karşı koruyan dış tabaka.",
    kesecik: "Maddeleri hücre içinde taşıyan küçük zarlı kabarcıklar.",
  };
  function cell(kind) {
    bReset(); const clickable = [];
    const add = (mesh, name) => { mesh.userData.org = name; bRoot.add(mesh); clickable.push(mesh); return mesh; };
    const tr = (c, o) => new T.MeshPhongMaterial({ color: c, transparent: true, opacity: o, depthWrite: false, side: T.DoubleSide, shininess: 60 });
    const anim = [];
    if (kind === "bacteria") {
      const body = new T.Mesh(new T.CylinderGeometry(4, 4, 14, 32, 1, true), tr(0x7bd389, 0.25)); body.rotation.z = Math.PI / 2; add(body, "hücre zarı");
      [-7, 7].forEach((x) => { const cap = new T.Mesh(new T.SphereGeometry(4, 32, 16, 0, Math.PI * 2, 0, Math.PI / 2), tr(0x7bd389, 0.25)); cap.rotation.z = x > 0 ? -Math.PI / 2 : Math.PI / 2; cap.position.x = x; add(cap, "hücre zarı"); });
      const capM = new T.Mesh(capsule(4.6, 14), tr(0xc8f7c5, 0.08)); capM.rotation.z = Math.PI / 2; add(capM, "kapsül");
      const pts = []; for (let i = 0; i < 400; i++) { const t = i / 400 * Math.PI * 14; pts.push(new T.Vector3(Math.cos(t) * 2.2 * Math.sin(t * 0.13), Math.sin(t) * 1.6, Math.sin(t * 0.37) * 1.4)); }
      add(new T.Mesh(new T.TubeGeometry(new T.CatmullRomCurve3(pts), 600, 0.08, 6, false), std(0x5ab0ff, 0.6)), "nükleoid");
      for (let k = 0; k < 3; k++) { const p = new T.Mesh(new T.TorusGeometry(0.6, 0.08, 8, 24), std(0xff9f1c, 0.6)); p.position.set(-4 + k * 3.5, -2.2, 1.5); add(p, "plazmit"); }
      for (let k = 0; k < 120; k++) { const r = new T.Mesh(new T.SphereGeometry(0.13, 6, 4), std(0x9b5de5, 0.4)); r.position.set((Math.random() - 0.5) * 16, (Math.random() - 0.5) * 6, (Math.random() - 0.5) * 6); if (Math.abs(r.position.x) < 9) add(r, "ribozom"); }
      const fl = []; for (let i = 0; i < 80; i++) fl.push(new T.Vector3(-11 - i * 0.25, Math.sin(i * 0.35) * 1.2, Math.cos(i * 0.35) * 1.2));
      const flag = add(new T.Mesh(new T.TubeGeometry(new T.CatmullRomCurve3(fl), 160, 0.1, 6, false), std(0xeeeeee, 0.3)), "kamçı");
      anim.push((t) => (flag.rotation.x = t * 6));
      for (let k = 0; k < 40; k++) { const dir = new T.Vector3(Math.random() * 2 - 1, Math.random() * 2 - 1, Math.random() * 2 - 1).normalize(); const p = new T.Mesh(new T.CylinderGeometry(0.03, 0.03, 1.4, 4), std(0xdddddd, 0.2)); p.position.set(dir.x * 8, dir.y * 4.6, dir.z * 4.6); p.lookAt(p.position.clone().multiplyScalar(2)); p.rotateX(Math.PI / 2); add(p, "pili"); }
      camera.position.set(0, 8, 32);
    } else {
      const plant = kind === "plant";
      if (plant) { const wall = new T.Mesh(new T.BoxGeometry(30, 22, 22), tr(0x5f9e3a, 0.12)); add(wall, "hücre duvarı"); bRoot.add(new T.LineSegments(new T.EdgesGeometry(wall.geometry), new T.LineBasicMaterial({ color: 0x9be564 }))); }
      const mem = plant ? new T.Mesh(new T.BoxGeometry(29, 21, 21), tr(0x38d6ff, 0.07)) : new T.Mesh(new T.SphereGeometry(14, 64, 48), tr(0x38d6ff, 0.12));
      add(mem, "hücre zarı");
      const nuc = add(new T.Mesh(new T.SphereGeometry(4.2, 48, 32), tr(0x7b5cff, 0.55)), "çekirdek"); nuc.position.set(plant ? -6 : 0, 1, 0);
      const nl = add(new T.Mesh(new T.SphereGeometry(1.4, 24, 16), std(0x3a1d8f, 0.5)), "çekirdekçik"); nl.position.copy(nuc.position).add(new T.Vector3(0.9, 0.7, 0.8));
      // granüllü ER: çekirdeği saran kıvrımlı zarlar
      for (let k = 0; k < 5; k++) { const er = add(new T.Mesh(new T.TorusGeometry(5.6 + k * 0.9, 0.22, 8, 64, Math.PI * (1.1 + Math.random() * 0.5)), std(0x2ec4b6, 0.35)), "endoplazmik retikulum"); er.position.copy(nuc.position); er.rotation.set(Math.random() * 3, Math.random() * 3, 0); }
      // golgi: üst üste kavisli diskler
      const golgi = new T.Group(); golgi.position.set(plant ? 3 : 7, -4, 3); for (let k = 0; k < 6; k++) { const g = new T.Mesh(new T.TorusGeometry(2.4 - k * 0.15, 0.25, 6, 32, Math.PI), std(0xffb020, 0.4)); g.position.y = k * 0.55; g.rotation.x = Math.PI / 2; golgi.add(g); g.userData.org = "golgi"; clickable.push(g); } bRoot.add(golgi);
      // mitokondriler
      const mitos = [];
      for (let k = 0; k < (plant ? 6 : 10); k++) {
        const m = new T.Group(); const shell = new T.Mesh(capsule(0.9, 2.6), std(0xff5c7a, 0.35)); shell.userData.org = "mitokondri"; clickable.push(shell); m.add(shell);
        for (let j = 0; j < 5; j++) { const cr = new T.Mesh(new T.TorusGeometry(0.55, 0.05, 4, 16), std(0xffd1dc, 0.6)); cr.position.y = -1.1 + j * 0.55; cr.rotation.x = Math.PI / 2; m.add(cr); }
        const a = Math.random() * Math.PI * 2, rr = 7 + Math.random() * 4; m.position.set(Math.cos(a) * rr, (Math.random() - 0.5) * 9, Math.sin(a) * rr * (plant ? 0.7 : 1)); m.rotation.set(Math.random() * 3, Math.random() * 3, 0); bRoot.add(m); mitos.push(m);
      }
      anim.push((t) => mitos.forEach((m, i) => { m.rotation.y += 0.002; m.position.y += Math.sin(t + i) * 0.003; }));
      for (let k = 0; k < (plant ? 3 : 7); k++) { const l = add(new T.Mesh(new T.SphereGeometry(0.8, 16, 12), std(0x9be564, 0.4)), "lizozom"); l.position.set((Math.random() - 0.5) * 18, (Math.random() - 0.5) * 12, (Math.random() - 0.5) * 12); if (l.position.length() > 12) l.position.setLength(10); }
      const ves = []; for (let k = 0; k < 14; k++) { const v = add(new T.Mesh(new T.SphereGeometry(0.4, 10, 8), std(0xffe08a, 0.5)), "kesecik"); v.position.copy(golgi.position).add(new T.Vector3((Math.random() - 0.5) * 6, (Math.random() - 0.5) * 6, (Math.random() - 0.5) * 6)); ves.push([v, new T.Vector3(Math.random() - 0.5, Math.random() - 0.5, Math.random() - 0.5).multiplyScalar(0.03)]); }
      anim.push(() => ves.forEach(([v, s]) => { v.position.add(s); if (v.position.length() > 12) s.negate(); }));
      const ribo = new Float32Array(1500 * 3); for (let k = 0; k < 1500; k++) { const v = new T.Vector3(Math.random() - 0.5, Math.random() - 0.5, Math.random() - 0.5).normalize().multiplyScalar(5 + Math.random() * 7); ribo.set([v.x, v.y, v.z], k * 3); }
      const rp = new T.Points(new T.BufferGeometry().setAttribute("position", new T.BufferAttribute(ribo, 3)), new T.PointsMaterial({ color: 0xb37dff, size: 0.18 })); rp.userData.org = "ribozom"; bRoot.add(rp);
      if (!plant) { const cen = new T.Group(); for (let k = 0; k < 2; k++) { const c9 = new T.Mesh(new T.CylinderGeometry(0.35, 0.35, 1.4, 9), std(0xff9f1c, 0.5)); c9.rotation.z = k * Math.PI / 2; c9.userData.org = "sentrozom"; clickable.push(c9); cen.add(c9); } cen.position.set(-6, -6, 4); bRoot.add(cen); }
      if (plant) {
        const vac = add(new T.Mesh(new T.SphereGeometry(7, 40, 28), tr(0x6ec6ff, 0.25)), "koful"); vac.position.set(6, 1, 0); vac.scale.set(1, 1.1, 1.2);
        for (let k = 0; k < 9; k++) { const ch = new T.Group(); const sh = new T.Mesh(new T.SphereGeometry(1.2, 20, 14), std(0x2e9e44, 0.35)); sh.scale.set(1.6, 0.8, 1); sh.userData.org = "kloroplast"; clickable.push(sh); ch.add(sh); for (let j = 0; j < 4; j++) { const gr = new T.Mesh(new T.CylinderGeometry(0.35, 0.35, 0.5, 12), std(0x145a25, 0.3)); gr.position.set(-1.1 + j * 0.75, 0, 0); ch.add(gr); } ch.position.set(-12 + Math.random() * 24, (Math.random() < 0.5 ? -1 : 1) * (7 + Math.random() * 2), (Math.random() - 0.5) * 16); ch.rotation.y = Math.random() * 3; bRoot.add(ch); }
      }
      camera.position.set(0, 10, plant ? 52 : 44);
    }
    controls.target.set(0, 0, 0);
    let t = 0; bUpdate = (dt) => { t += dt; anim.forEach((f) => f(t)); };
    bClick = (ray) => { const h = ray.intersectObjects(clickable)[0]; if (!h) return; const n = h.object.userData.org; U.panel(`<div class="wp-title">${esc(n.toUpperCase())}</div><p>${esc(ORG[n] || "")}</p><p class="note">Başka bir organele tıkla.</p>`); };
    const title = { animal: "HAYVAN HÜCRESİ", plant: "BİTKİ HÜCRESİ", bacteria: "BAKTERİ (prokaryot)" }[kind];
    U.panel(`<div class="wp-title">${title}</div><p class="note">Bir organele tıkla: görevi. Ölçekler eğitim amaçlı basitleştirilmiştir (gerçek hayvan hücresi ~10–30 µm, bakteri ~1–5 µm).</p>`);
  }

  JV.worlds.bio = {
    scene: bScene,
    enter() { controls.enablePan = true; controls.minDistance = 2; controls.maxDistance = 900; if (!bRoot) cell("animal"); },
    exit() {},
    update(dt) { if (bUpdate) bUpdate(dt); },
    click(ray) { if (bClick) bClick(ray); },
    cmd(r) { if (r.kind === "protein") protein(r); else cell(r.cell || "animal"); },
  };
})();
