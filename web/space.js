/* UZAY MERKEZİ: canlı güneş sistemi (gerçek konumlar, zaman kontrolü), uydular (canlı yörünge), yıldız haritası ve yerel gökyüzü,
   Ay ve Mars yüzeyi, gezegen inceleme, kara delik (ışık bükülmesi), kendi galaksini oluştur, kozmik ağ. */
(function () {
  const JV = window.JV; if (!JV || !JV.wutil) return;
  const U = JV.wutil, T = U.T, DEG = U.DEG, camera = U.camera, controls = U.controls;
  const scene = new T.Scene();
  const tex = new T.TextureLoader(), PT = "/static/vendor/textures/planets/";
  let root = null, update = null, view = "", clickFn = null;
  let simTime = Date.now(), speed = 1, lastReal = performance.now(); // simülasyon saati (ms) ve hız (×gerçek)

  // ---------- gök mekaniği (sunucudakiyle aynı JPL elemanları) ----------
  const EL = {
    "Merkür": [[0.38709927, 0.20563593, 7.00497902, 252.25032350, 77.45779628, 48.33076593], [0.00000037, 0.00001906, -0.00594749, 149472.67411175, 0.16047689, -0.12534081], "mercurymap.jpg", 0.38, 0xb1aca3],
    "Venüs": [[0.72333566, 0.00677672, 3.39467605, 181.97909950, 131.60246718, 76.67984255], [0.00000390, -0.00004107, -0.00078890, 58517.81538729, 0.00268329, -0.27769418], "venusmap.jpg", 0.95, 0xe3c27a],
    "Dünya": [[1.00000261, 0.01671123, -0.00001531, 100.46457166, 102.93768193, 0], [0.00000562, -0.00004392, -0.01294668, 35999.37244981, 0.32327364, 0], null, 1, 0x3b7bd6],
    "Mars": [[1.52371034, 0.09339410, 1.84969142, -4.55343205, -23.94362959, 49.55953891], [0.00001847, 0.00007882, -0.00813131, 19140.30268499, 0.44441088, -0.29257343], "marsmap1k.jpg", 0.53, 0xc1440e],
    "Jüpiter": [[5.20288700, 0.04838624, 1.30439695, 34.39644051, 14.72847983, 100.47390909], [-0.00011607, -0.00013253, -0.00183714, 3034.74612775, 0.21252668, 0.20469106], "jupitermap.jpg", 2.6, 0xd8b48a],
    "Satürn": [[9.53667594, 0.05386179, 2.48599187, 49.95424423, 92.59887831, 113.66242448], [-0.00125060, -0.00050991, 0.00193609, 1222.49362201, -0.41897216, -0.28867794], "saturnmap.jpg", 2.2, 0xe8d39c],
    "Uranüs": [[19.18916464, 0.04725744, 0.77263783, 313.23810451, 170.95427630, 74.01692503], [-0.00196176, -0.00004397, -0.00242939, 428.48202785, 0.40805281, 0.04240589], "uranusmap.jpg", 1.5, 0x9fe3ef],
    "Neptün": [[30.06992276, 0.00859048, 1.77004347, -55.12002969, 44.96476227, 131.78422574], [0.00026291, 0.00005105, 0.00035372, 218.45945325, -0.32241464, -0.00508664], "neptunemap.jpg", 1.45, 0x4062d8],
  };
  const jd = (ms) => ms / 86400000 + 2440587.5;
  function helio(n, J) {
    const [e0, r] = EL[n], Tc = (J - 2451545) / 36525, el = e0.map((v, i) => v + r[i] * Tc);
    let [a, e, I, L, wb, Om] = el; I *= DEG; Om *= DEG; wb *= DEG;
    const M = ((L * DEG - wb) % (2 * Math.PI) + 3 * Math.PI) % (2 * Math.PI) - Math.PI, w = wb - Om;
    let E = M + e * Math.sin(M); for (let k = 0; k < 10; k++) E -= (E - e * Math.sin(E) - M) / (1 - e * Math.cos(E));
    const xp = a * (Math.cos(E) - e), yp = a * Math.sqrt(1 - e * e) * Math.sin(E);
    const cw = Math.cos(w), sw = Math.sin(w), cO = Math.cos(Om), sO = Math.sin(Om), cI = Math.cos(I), sI = Math.sin(I);
    return [(cw * cO - sw * sO * cI) * xp + (-sw * cO - cw * sO * cI) * yp, (cw * sO + sw * cO * cI) * xp + (-sw * sO + cw * cO * cI) * yp, sw * sI * xp + cw * sI * yp];
  }
  // görsel ölçek: uzaklık sıkıştırılır (√), yoksa dış gezegenler görünmez
  const vis = (x, y, z) => { const r = Math.hypot(x, y, z), k = r > 0 ? 14 * Math.sqrt(r) / r : 0; return new T.Vector3(x * k, z * k, -y * k); };
  const gmst = (J) => (280.46061837 + 360.98564736629 * (J - 2451545)) % 360;

  function reset() {
    if (root) { scene.remove(root); U.disposeTree(root); }
    root = new T.Group(); scene.add(root); update = null; clickFn = null; U.panel(null); U.caption("");
    controls.target.set(0, 0, 0); controls.enablePan = true; controls.minDistance = 0.02; controls.maxDistance = 3000;
    document.getElementById("space-time").classList.add("hidden");
  }
  function starfield(n = 8000, r = 900) {
    const p = []; for (let i = 0; i < n; i++) { const v = new T.Vector3().setFromSphericalCoords(r, Math.acos(2 * Math.random() - 1), Math.random() * Math.PI * 2); p.push(v.x, v.y, v.z); }
    return new T.Points(new T.BufferGeometry().setAttribute("position", new T.Float32BufferAttribute(p, 3)), new T.PointsMaterial({ size: 1.2, color: 0x9fb8c8, sizeAttenuation: false }));
  }
  function label(t, size = 1.2, col = "#cfefff") { const l = U.label(t, col, 44); l.scale.set(size * l.userData.aspect, size, 1); return l; }
  const fmtDate = (ms) => new Date(ms).toLocaleString("tr-TR", { dateStyle: "medium", timeStyle: "short" });

  // ---------- zaman kontrol çubuğu ----------
  function timebar() {
    const bar = document.getElementById("space-time"); bar.classList.remove("hidden");
    const speeds = [["-1 yıl/sn", -31557600], ["-1 ay/sn", -2629800], ["⏸", 0], ["gerçek", 1], ["1 saat/sn", 3600], ["1 gün/sn", 86400], ["1 ay/sn", 2629800], ["1 yıl/sn", 31557600]];
    bar.innerHTML = `<span id="st-date"></span>`;
    speeds.forEach(([t, v]) => { const b = document.createElement("button"); b.className = "mini" + (v === speed ? " on" : ""); b.textContent = t; b.onclick = () => { speed = v; bar.querySelectorAll(".mini").forEach((x) => x.classList.remove("on")); b.classList.add("on"); }; bar.append(b); });
    const now = document.createElement("button"); now.className = "mini"; now.textContent = "ŞİMDİ"; now.onclick = () => { simTime = Date.now(); speed = 1; timebar(); }; bar.append(now);
  }

  // ================= CANLI GÜNEŞ SİSTEMİ =================
  async function system(p = {}) {
    reset(); camera.position.set(0, 26, 36); root.add(starfield());
    const sun = new T.Mesh(new T.SphereGeometry(2.4, 48, 32), new T.MeshBasicMaterial({ map: tex.load(PT + "sunmap.jpg") })); root.add(sun);
    root.add(new T.PointLight(0xfff2dd, 2.0, 0, 0)); root.add(new T.AmbientLight(0x404050, 0.5));
    const glow = new T.Sprite(new T.SpriteMaterial({ map: radial("#ffcc66"), blending: T.AdditiveBlending, transparent: true, depthWrite: false })); glow.scale.set(14, 14, 1); root.add(glow);
    const bodies = {};
    Object.entries(EL).forEach(([n, d]) => {
      const r = 0.25 + d[3] * 0.22;
      const mat = n === "Dünya" ? new T.MeshPhongMaterial({ map: tex.load("/static/vendor/textures/earth_atmos_2048.jpg") }) : new T.MeshPhongMaterial({ map: tex.load(PT + d[2]), shininess: 5 });
      const m = new T.Mesh(new T.SphereGeometry(r, 40, 28), mat); m.userData.name = n; root.add(m); bodies[n] = m;
      if (n === "Satürn") { const ring = new T.Mesh(new T.RingGeometry(r * 1.3, r * 2.3, 64), new T.MeshBasicMaterial({ map: tex.load(PT + "saturnringcolor.jpg"), side: T.DoubleSide, transparent: true, opacity: 0.8 })); ring.rotation.x = -Math.PI / 2 + 0.47; m.add(ring); }
      const l = label(n, 0.7); l.position.y = r + 0.8; m.add(l);
      // yörünge çizgisi (bir tam tur)
      const per = 360 / d[1][3] * 36525, pts = [], J0 = jd(Date.now());
      for (let k = 0; k <= 180; k++) pts.push(vis(...helio(n, J0 + per * k / 180)));
      root.add(new T.Line(new T.BufferGeometry().setFromPoints(pts), new T.LineBasicMaterial({ color: 0x38d6ff, transparent: true, opacity: 0.22 })));
    });
    const moon = new T.Mesh(new T.SphereGeometry(0.12, 20, 14), new T.MeshPhongMaterial({ map: tex.load(PT + "moonmap1k.jpg") })); bodies["Dünya"].add(moon);
    // uzay araçları (NASA JPL Horizons)
    const craftG = new T.Group(); root.add(craftG);
    JV.api("/api/space/craft").then((list) => {
      if (!Array.isArray(list)) return;
      list.forEach((c) => {
        const v = vis(c.x, c.y, c.z), s = new T.Mesh(new T.OctahedronGeometry(0.22), new T.MeshBasicMaterial({ color: 0xffd34d }));
        s.position.copy(v); s.userData = { craft: c }; craftG.add(s);
        const l = label(c.ad, 0.55, "#ffe58a"); l.position.copy(v).add(new T.Vector3(0, 0.6, 0)); craftG.add(l);
      });
    }).catch(() => {});
    timebar();
    update = () => {
      const J = jd(simTime);
      Object.entries(bodies).forEach(([n, m]) => { m.position.copy(vis(...helio(n, J))); m.rotation.y += 0.01; });
      const dm = (J - 2451545) * 13.176396 * DEG; moon.position.set(Math.cos(dm) * 0.55, 0, -Math.sin(dm) * 0.55);
      document.getElementById("st-date").textContent = fmtDate(simTime);
    };
    clickFn = (ray) => {
      const h = ray.intersectObjects([...Object.values(bodies), ...craftG.children])[0]; if (!h) return;
      const o = h.object.userData;
      if (o.craft) return U.panel(`<div class="wp-title">${o.craft.ad}</div><div class="wp-grid"><i>Güneş'e</i><b>${o.craft.güneşe_au} AU</b><i>Dünya'ya</i><b>${o.craft.dünyaya_au} AU</b><i>Işık süresi</i><b>${o.craft.ışık_süresi_saat} saat</b><i>Kaynak</i><b>NASA JPL Horizons</b></div>`);
      const J = jd(simTime), [x, y, z] = helio(o.name, J), [ex, ey, ez] = helio("Dünya", J), dE = Math.hypot(x - ex, y - ey, z - ez);
      U.panel(`<div class="wp-title">${o.name}</div><div class="wp-grid"><i>Tarih</i><b>${fmtDate(simTime)}</b><i>Güneş'e</i><b>${Math.hypot(x, y, z).toFixed(3)} AU</b>${o.name !== "Dünya" ? `<i>Dünya'ya</i><b>${U.fmt(dE * 149.6, 1)} milyon km</b><i>Işık süresi</i><b>${(dE * 149597870.7 / 299792.458 / 60).toFixed(1)} dk</b>` : ""}</div><div class="wp-row"><button class="mini" id="sp-go">YAKINDAN İNCELE</button></div>`);
      document.getElementById("sp-go").onclick = () => planet({ name: o.name });
    };
    U.panel(`<div class="wp-title">Canlı güneş sistemi</div><div class="wp-grid"><i>Konumlar</i><b>gerçek (JPL Kepler elemanları)</b><i>Uzaklık ölçeği</i><b>sıkıştırılmış (√)</b><i>Uzay araçları</i><b>NASA JPL Horizons</b></div><p class="note">Aşağıdaki çubukla zamanı hızlandır, geri sar. Bir gezegene tıkla.</p>`);
  }
  function radial(color) {
    const c = document.createElement("canvas"); c.width = c.height = 128; const g = c.getContext("2d");
    const gr = g.createRadialGradient(64, 64, 0, 64, 64, 64); gr.addColorStop(0, color); gr.addColorStop(0.3, color + "88"); gr.addColorStop(1, "#0000");
    g.fillStyle = gr; g.fillRect(0, 0, 128, 128); return new T.CanvasTexture(c);
  }

  // ================= GEZEGEN / AY / MARS YAKIN İNCELEME =================
  const PFILES = { "Merkür": ["mercurymap.jpg", null], "Venüs": ["venusmap.jpg", null], "Mars": ["marsmap1k.jpg", "marsbump1k.jpg"], "Jüpiter": ["jupitermap.jpg", null], "Satürn": ["saturnmap.jpg", null], "Uranüs": ["uranusmap.jpg", null], "Neptün": ["neptunemap.jpg", null], "Ay": ["moonmap1k.jpg", "moonbump1k.jpg"], "Plüton": ["plutomap1k.jpg", null] };
  const FACTS = {
    "Ay": [["Çap", "3.474 km"], ["Dünya'ya uzaklık", "~384.400 km"], ["Yüzey çekimi", "1,62 m/s²"], ["Gün", "29,5 Dünya günü"], ["Not", "Hep aynı yüzü Dünya'ya döner"]],
    "Mars": [["Çap", "6.779 km"], ["Yüzey çekimi", "3,72 m/s²"], ["Gün", "24 sa 37 dk"], ["En yüksek dağ", "Olympus Mons ~21,9 km"], ["Kanyon", "Valles Marineris ~4.000 km"]],
    "Jüpiter": [["Çap", "139.820 km"], ["Uydu", "95"], ["Büyük Kırmızı Leke", "Dünya'dan büyük fırtına"]], "Satürn": [["Çap", "116.460 km"], ["Yoğunluk", "sudan az (0,69 g/cm³)"], ["Uydu", "146"]],
    "Venüs": [["Yüzey sıcaklığı", "~465 °C"], ["Atmosfer", "%96 CO₂"]], "Merkür": [["Gündüz/gece", "+430 °C / −180 °C"]], "Uranüs": [["Eksen eğikliği", "~98°, yan yatmış"]], "Neptün": [["Rüzgar", "~2.100 km/sa'e kadar"]], "Plüton": [["Durum", "cüce gezegen (2006)"]],
  };
  function planet(p = {}) {
    reset(); camera.position.set(0, 0.6, 3.2); controls.minDistance = 1.03; controls.maxDistance = 20;
    const n = p.name || "Mars", [map, bump] = PFILES[n] || PFILES.Mars;
    root.add(starfield(4000, 300));
    const mat = new T.MeshPhongMaterial({ map: tex.load(PT + map), shininess: 4 });
    if (bump) { mat.bumpMap = tex.load(PT + bump); mat.bumpScale = n === "Ay" ? 0.04 : 0.06; }
    const sph = new T.Mesh(new T.SphereGeometry(1, 128, 96), mat); root.add(sph);
    if (n === "Satürn") { const ring = new T.Mesh(new T.RingGeometry(1.25, 2.3, 96), new T.MeshBasicMaterial({ map: tex.load(PT + "saturnringcolor.jpg"), side: T.DoubleSide, transparent: true, opacity: 0.85 })); ring.rotation.x = -Math.PI / 2 + 0.47; root.add(ring); }
    if (n === "Mars") { const atm = new T.Mesh(new T.SphereGeometry(1.025, 64, 48), new T.MeshBasicMaterial({ color: 0xff9a60, transparent: true, opacity: 0.12, side: T.BackSide })); root.add(atm); }
    const sun = new T.DirectionalLight(0xffffff, 1.4); sun.position.set(5, 2, 4); root.add(sun); root.add(new T.AmbientLight(0x303038, 0.6));
    update = (dt) => { sph.rotation.y += dt * 0.03; };
    U.panel(`<div class="wp-title">${n}</div><div class="wp-grid">${(FACTS[n] || []).map(([a, b]) => `<i>${a}</i><b>${b}</b>`).join("")}</div><p class="note">Yüzeye yaklaşmak için yakınlaştır (fare tekerleği veya başparmak+işaret parmağını aç). ${bump ? "Kabartma haritası ile kraterler/dağlar gölgelenir." : ""}</p>`);
  }

  // ================= UYDULAR (CANLI) =================
  async function satellites(p = {}) {
    reset(); camera.position.set(0, 1.5, 4.2); controls.minDistance = 1.1; controls.maxDistance = 30;
    root.add(starfield(4000, 300));
    const earth = new T.Mesh(new T.SphereGeometry(1, 96, 64), new T.MeshPhongMaterial({ map: tex.load("/static/vendor/textures/earth_atmos_2048.jpg"), specularMap: tex.load("/static/vendor/textures/earth_specular_2048.jpg"), shininess: 15 }));
    const earthRot = new T.Group(); earthRot.add(earth); root.add(earthRot);
    root.add(new T.AmbientLight(0x505868, 0.8)); const sl = new T.DirectionalLight(0xffffff, 1); sl.position.set(5, 2, 3); root.add(sl);
    const group = p.group || "stations";
    U.caption("Uydu yörünge verisi CelesTrak'tan alınıyor…");
    const els = await JV.api("/api/space/sats?group=" + encodeURIComponent(group));
    U.caption("");
    if (!Array.isArray(els)) { U.panel(`<div class="wp-title">Uydular</div><p class="note">Veri alınamadı: ${els.error || ""}</p>`); return; }
    const MU = 398600.4418, RE = 6378.137, J2 = 1.08262668e-3;
    const prep = els.slice(0, 4000).map((e) => { const n = e.n * 2 * Math.PI / 86400, a = Math.cbrt(MU / (n * n)); return { ...e, nr: n, a, ep: Date.parse(e.epoch + "Z") }; });
    const focus = (p.focus || "").toLowerCase();
    function eci(s, ms) {
      const dts = (ms - s.ep) / 1000, e = s.e, i = s.i * DEG, pp = s.a * (1 - e * e), k = 1.5 * s.nr * J2 * (RE / pp) ** 2;
      const raan = s.raan * DEG - k * Math.cos(i) * dts, argp = s.argp * DEG + 0.5 * k * (5 * Math.cos(i) ** 2 - 1) * dts;
      const M = ((s.M * DEG + s.nr * dts) % (2 * Math.PI) + 2 * Math.PI) % (2 * Math.PI);
      let E = M + e * Math.sin(M); for (let q = 0; q < 8; q++) E -= (E - e * Math.sin(E) - M) / (1 - e * Math.cos(E));
      const nu = 2 * Math.atan2(Math.sqrt(1 + e) * Math.sin(E / 2), Math.sqrt(1 - e) * Math.cos(E / 2)), r = s.a * (1 - e * Math.cos(E)), u = argp + nu;
      return [r * (Math.cos(raan) * Math.cos(u) - Math.sin(raan) * Math.sin(u) * Math.cos(i)), r * (Math.sin(raan) * Math.cos(u) + Math.cos(raan) * Math.sin(u) * Math.cos(i)), r * Math.sin(u) * Math.sin(i), r];
    }
    // ECI → sahne (y yukarı = kuzey kutbu); Dünya dokusu gmst kadar döndürülür
    const toV = (x, y, z) => new T.Vector3(x, z, -y).divideScalar(RE);
    const pos = new Float32Array(prep.length * 3), col = new Float32Array(prep.length * 3);
    prep.forEach((s, k) => { const c = new T.Color(s.ad.toLowerCase().includes(focus) && focus ? 0xff4d6d : s.n > 11 ? 0x38d6ff : s.n > 1.5 ? 0x5dff9a : 0xffd34d); col.set([c.r, c.g, c.b], k * 3); });
    const geo = new T.BufferGeometry().setAttribute("position", new T.BufferAttribute(pos, 3)).setAttribute("color", new T.BufferAttribute(col, 3));
    root.add(new T.Points(geo, new T.PointsMaterial({ size: prep.length > 500 ? 0.015 : 0.035, vertexColors: true })));
    let fsat = focus ? prep.find((s) => s.ad.toLowerCase() === focus) || prep.find((s) => s.ad.toLowerCase().includes(focus)) : null;
    if (!fsat && group === "stations") fsat = prep.find((s) => s.ad.startsWith("ISS"));
    let orbitLine = null, flabel = null;
    if (fsat) {
      const pts = [], per = 2 * Math.PI / fsat.nr * 1000;
      for (let k = 0; k <= 200; k++) { const [x, y, z] = eci(fsat, Date.now() + per * k / 200); pts.push(toV(x, y, z)); }
      orbitLine = new T.Line(new T.BufferGeometry().setFromPoints(pts), new T.LineBasicMaterial({ color: 0xff4d6d })); root.add(orbitLine);
      flabel = label(fsat.ad, 0.08, "#ffb0bf"); root.add(flabel);
    }
    timebar(); speed = speed === 0 ? 1 : speed;
    update = () => {
      const t = simTime;
      earthRot.rotation.y = gmst(jd(t)) * DEG + Math.PI;
      prep.forEach((s, k) => { const [x, y, z] = eci(s, t); const v = toV(x, y, z); pos[k * 3] = v.x; pos[k * 3 + 1] = v.y; pos[k * 3 + 2] = v.z; });
      geo.attributes.position.needsUpdate = true;
      if (fsat) {
        const [x, y, z, r] = eci(fsat, t); const v = toV(x, y, z); flabel.position.copy(v).multiplyScalar(1.04);
        const th = gmst(jd(t)) * DEG, xe = x * Math.cos(th) + y * Math.sin(th), ye = -x * Math.sin(th) + y * Math.cos(th);
        const lat = Math.atan2(z, Math.hypot(xe, ye)) / DEG, lon = ((Math.atan2(ye, xe) / DEG + 540) % 360) - 180;
        U.caption(`${fsat.ad}: ${lat.toFixed(2)}°, ${lon.toFixed(2)}° · ${Math.round(r - RE)} km · ${Math.round(Math.sqrt(MU * (2 / r - 1 / fsat.a)) * 3600).toLocaleString("tr-TR")} km/sa`);
      }
      document.getElementById("st-date").textContent = fmtDate(t);
    };
    U.panel(`<div class="wp-title">Uydular: ${group}</div><div class="wp-grid"><i>Sayı</i><b>${prep.length}</b><i>Kaynak</i><b>CelesTrak (NORAD)</b><i>Yöntem</i><b>J2 düzeltmeli Kepler</b><i>Renk</i><b>mavi alçak · yeşil orta · sarı yer-eşzamanlı</b></div>
      <div class="wp-row">${["stations", "visual", "gps", "weather", "science", "geo", "starlink"].map((g) => `<button class="mini" data-g="${g}">${g}</button>`).join("")}</div>`);
    document.querySelectorAll("#world-panel [data-g]").forEach((b) => (b.onclick = () => satellites({ group: b.dataset.g })));
  }

  // ================= YILDIZ HARİTASI / YEREL GÖKYÜZÜ =================
  let starData = null, constData = null;
  const bvColor = (bv) => { const t = Math.max(-0.4, Math.min(2, bv)); return new T.Color().setHSL(t < 0.4 ? 0.6 - t * 0.1 : 0.12 - (t - 0.4) * 0.05, t < 0 ? 0.7 : 0.6, 0.75); };
  const radecV = (ra, dec, r = 100) => { const a = ra * DEG, d = dec * DEG; return new T.Vector3(r * Math.cos(d) * Math.cos(a), r * Math.sin(d), -r * Math.cos(d) * Math.sin(a)); };
  async function sky(p = {}) {
    reset(); controls.minDistance = 0.01; controls.maxDistance = 0.02; camera.position.set(0, 0, 0.015); controls.target.set(0, 0, 0); controls.rotateSpeed = -0.35;
    starData = starData || (await (await fetch("/static/data/stars.json")).json());
    constData = constData || (await (await fetch("/static/data/constellations.json")).json());
    const sphere = new T.Group(); root.add(sphere);
    const pos = [], col = [], sizes = [];
    starData.forEach(([ra, dec, mag, bv]) => { const v = radecV(ra, dec); pos.push(v.x, v.y, v.z); const c = bvColor(bv); col.push(c.r, c.g, c.b); sizes.push(Math.max(1.2, 7 - mag * 1.05)); });
    const g = new T.BufferGeometry().setAttribute("position", new T.Float32BufferAttribute(pos, 3)).setAttribute("color", new T.Float32BufferAttribute(col, 3)).setAttribute("size", new T.Float32BufferAttribute(sizes, 1));
    sphere.add(new T.Points(g, new T.ShaderMaterial({ vertexColors: true, transparent: true, depthWrite: false,
      vertexShader: "attribute float size; varying vec3 vC; void main(){ vC=color; gl_PointSize=size; gl_Position=projectionMatrix*modelViewMatrix*vec4(position,1.0);} ",
      fragmentShader: "varying vec3 vC; void main(){ float d=length(gl_PointCoord-0.5); if(d>0.5) discard; gl_FragColor=vec4(vC, smoothstep(0.5,0.0,d)); }" })));
    const lp = [];
    constData.forEach((c) => c.l.forEach((seg) => { for (let i = 0; i < seg.length - 1; i++) { const a = radecV(seg[i][0], seg[i][1], 99.5), b = radecV(seg[i + 1][0], seg[i + 1][1], 99.5); lp.push(a.x, a.y, a.z, b.x, b.y, b.z); } }));
    sphere.add(new T.LineSegments(new T.BufferGeometry().setAttribute("position", new T.Float32BufferAttribute(lp, 3)), new T.LineBasicMaterial({ color: 0x38d6ff, transparent: true, opacity: 0.35 })));
    constData.forEach((c) => { const l = label(c.n, 2.2, "#7fdcff"); l.position.copy(radecV(c.lbl[0], c.lbl[1], 96)); sphere.add(l); });
    starData.filter((s) => s[4] && s[2] < 1.6).forEach((s) => { const l = label(s[4], 1.6, "#fff4cf"); l.position.copy(radecV(s[0], s[1], 95)).add(new T.Vector3(0, 1.2, 0)); sphere.add(l); });
    // gezegenler ve Ay (gerçek konum)
    const J = jd(Date.now()), [ex, ey, ez] = helio("Dünya", J), eps = 23.43928 * DEG;
    const eq = (x, y, z) => [x, y * Math.cos(eps) - z * Math.sin(eps), y * Math.sin(eps) + z * Math.cos(eps)];
    const bodies = Object.keys(EL).filter((n) => n !== "Dünya").map((n) => { const [x, y, z] = helio(n, J); return [n, ...eq(x - ex, y - ey, z - ez)]; });
    bodies.push(["Güneş", ...eq(-ex, -ey, -ez)]);
    bodies.forEach(([n, x, y, z]) => { const ra = Math.atan2(y, x) / DEG, dec = Math.atan2(z, Math.hypot(x, y)) / DEG; const v = radecV(ra, dec, 97); const m = new T.Mesh(new T.SphereGeometry(n === "Güneş" ? 1.4 : 0.55, 16, 12), new T.MeshBasicMaterial({ color: n === "Güneş" ? 0xffd34d : 0xffa060 })); m.position.copy(v); sphere.add(m); const l = label(n, 1.8, "#ffcf9a"); l.position.copy(v).add(new T.Vector3(0, 2, 0)); sphere.add(l); });
    // yerel ufuk
    if (p.lat != null) {
      const lst = (gmst(J) + p.lon) * DEG, lat = p.lat * DEG;
      sphere.rotation.set(0, 0, 0);
      const q = new T.Quaternion().setFromAxisAngle(new T.Vector3(0, 1, 0), lst).premultiply(new T.Quaternion().setFromAxisAngle(new T.Vector3(1, 0, 0), -(Math.PI / 2 - lat)));
      sphere.quaternion.copy(q);
      const ground = new T.Mesh(new T.SphereGeometry(98, 64, 32, 0, Math.PI * 2, Math.PI / 2, Math.PI / 2), new T.MeshBasicMaterial({ color: 0x0a1a12, side: T.BackSide, transparent: true, opacity: 0.92 }));
      root.add(ground);
      [["K", 0], ["D", 90], ["G", 180], ["B", 270]].forEach(([t, az]) => { const l = label(t, 4, "#5dff9a"); l.position.set(Math.sin(az * DEG) * 90, 2, -Math.cos(az * DEG) * 90); root.add(l); });
      camera.position.set(0, 0, 0.015); controls.target.set(0, 0, -0.0001);
      U.panel(`<div class="wp-title">${(p.yer || "").split(",")[0]} gökyüzü</div><div class="wp-grid"><i>Zaman (UTC)</i><b>${p.zaman_utc || ""}</b><i>Gökyüzü</i><b>${p.gökyüzü || ""}</b><i>Ay</i><b>${p.ay ? p.ay.evre + " · %" + p.ay["aydınlık_%"] : ""}</b></div>${(p.görünenler || []).map((v) => `<div class="st on">${v.gök_cismi}: ${v.yön}, ${v.yükseklik}° yukarıda</div>`).join("")}<p class="note">Etrafına bakmak için sürükle. Yeşil: ufuk ve yönler.</p>`);
    } else U.panel(`<div class="wp-title">Yıldız haritası</div><div class="wp-grid"><i>Yıldız</i><b>${U.fmt(starData.length)} (kadir ≤ 6)</b><i>Takımyıldız</i><b>${constData.length}</b><i>Gezegenler</i><b>bugünkü gerçek konum</b></div><p class="note">"İstanbul'dan bu gece gökyüzü" dersen ufkuyla birlikte gösteririm.</p>`);
  }

  // ================= KARA DELİK (ışık bükülmesi, ışın izleme) =================
  function blackhole(p = {}) {
    reset(); controls.minDistance = 4; controls.maxDistance = 60; camera.position.set(0, 3, 22);
    const mat = new T.ShaderMaterial({
      side: T.BackSide, uniforms: { uTime: { value: 0 }, uSpin: { value: p.spin ?? 1.0 } },
      vertexShader: "varying vec3 vW; void main(){ vec4 w = modelMatrix*vec4(position,1.0); vW=w.xyz; gl_Position=projectionMatrix*viewMatrix*w; }",
      fragmentShader: `
        uniform float uTime; uniform float uSpin; varying vec3 vW;
        float hash(vec3 p){ p=fract(p*0.3183099+.1); p*=17.0; return fract(p.x*p.y*p.z*(p.x+p.y+p.z)); }
        vec3 stars(vec3 d){ vec3 q = floor(d*180.0); float h = hash(q); float s = step(0.9975, h); return vec3(s)*(0.6+0.4*hash(q+1.0)) + vec3(0.02,0.03,0.06)*(0.5+0.5*d.y); }
        void main(){
          vec3 ro = cameraPosition; vec3 rd = normalize(vW - cameraPosition);
          vec3 p = ro; vec3 v = rd; float h2 = dot(cross(p,v), cross(p,v));
          vec3 col = vec3(0.0); float alpha = 1.0;
          for(int i=0;i<400;i++){
            float r = length(p);
            if(r < 1.0){ alpha = 0.0; break; }            // olay ufku (rs = 1)
            if(r > 80.0) break;
            float dt = clamp(0.06*r, 0.02, 1.2);
            vec3 pPrev = p;
            vec3 acc = -1.5 * h2 * p / pow(r, 5.0);       // Schwarzschild ışık yörüngesi
            v += acc*dt; p += v*dt;
            if(pPrev.y*p.y < 0.0){                         // ince birikim diski y=0 düzleminde
              vec3 hp = mix(pPrev, p, pPrev.y/(pPrev.y-p.y)); float rr = length(hp.xz);
              if(rr > 3.0 && rr < 12.0){
                float temp = pow(3.0/rr, 0.75);
                vec3 vel = normalize(vec3(-hp.z, 0.0, hp.x)) * sqrt(0.5/rr) * uSpin;
                float dop = 1.0 / (1.0 - dot(vel, normalize(v)) * 1.6);      // Doppler parlaması
                float ring = 0.88 + 0.12*sin(rr*4.0 - uTime*1.5 + atan(hp.z,hp.x)*2.0);
                vec3 c = mix(vec3(1.0,0.35,0.08), vec3(1.0,0.92,0.75), temp) * temp * 1.15 * pow(clamp(dop,0.2,3.0), 3.0) * ring;
                c = c / (1.0 + c);  // ton eşleme
                col += c * alpha * 0.85; alpha *= 0.25;
              }
            }
          }
          col += stars(normalize(v)) * alpha;
          gl_FragColor = vec4(col, 1.0);
        }` });
    const sky = new T.Mesh(new T.SphereGeometry(500, 64, 32), mat); root.add(sky);
    update = (dt, t) => { mat.uniforms.uTime.value = t; };
    U.panel(`<div class="wp-title">Kara delik</div><div class="wp-grid"><i>Model</i><b>Schwarzschild (dönmeyen)</b><i>Olay ufku</i><b>r = 1 rₛ</b><i>Foton küresi</i><b>1,5 rₛ</b><i>Disk</i><b>3–12 rₛ, Doppler parlaması</b></div><p class="note">Her piksel için ışık ışını kütle çekimiyle bükülerek izlenir; diskin arka tarafı deliğin üstünde ve altında görünür (Interstellar'daki görüntünün aynı fiziği). Etrafında dönmek için sürükle.</p>`);
  }

  // ================= KENDİ GALAKSİN =================
  function galaxy(p = {}) {
    reset(); camera.position.set(0, 35, 50);
    const n = Math.min(200000, p.stars || 80000), arms = p.arms || 3, spin = p.spin ?? 1.1, size = p.size || 30, rnd = p.randomness ?? 0.35, bulge = p.bulge ?? 0.18;
    const ci = new T.Color(p.inner || "#ffc98a"), co = new T.Color(p.outer || "#4f8fff"), pos = new Float32Array(n * 3), col = new Float32Array(n * 3);
    for (let i = 0; i < n; i++) {
      const isBulge = Math.random() < bulge, r = isBulge ? Math.pow(Math.random(), 2) * size * 0.18 : Math.pow(Math.random(), 1.3) * size;
      const br = ((i % arms) / arms) * Math.PI * 2, sp = r / size * spin * Math.PI * 2;
      const j = () => Math.pow(Math.random(), 3) * (Math.random() < 0.5 ? 1 : -1) * rnd * (r + 1);
      const ang = isBulge ? Math.random() * Math.PI * 2 : br + sp;
      pos.set([Math.cos(ang) * r + j(), j() * (isBulge ? 1.2 : 0.25), Math.sin(ang) * r + j()], i * 3);
      const c = ci.clone().lerp(co, Math.min(1, r / size)); col.set([c.r, c.g, c.b], i * 3);
    }
    const g = new T.Points(new T.BufferGeometry().setAttribute("position", new T.BufferAttribute(pos, 3)).setAttribute("color", new T.BufferAttribute(col, 3)), new T.PointsMaterial({ size: 0.08, vertexColors: true, blending: T.AdditiveBlending, depthWrite: false, transparent: true }));
    root.add(g); root.add(starfield(3000, 600));
    const core = new T.Sprite(new T.SpriteMaterial({ map: radial("#ffe6b0"), blending: T.AdditiveBlending, transparent: true, depthWrite: false })); core.scale.set(size * 0.4, size * 0.4, 1); root.add(core);
    update = (dt) => { g.rotation.y += dt * 0.03; };
    U.panel(`<div class="wp-title">${p.name || "Senin galaksin"}</div><div class="wp-grid"><i>Yıldız (gösterilen)</i><b>${U.fmt(n)}</b><i>Kol</i><b>${arms}</b><i>Sarmallık</i><b>${spin}</b><i>Çekirdek oranı</i><b>%${Math.round(bulge * 100)}</b></div><p class="note">"5 kollu, kırmızı merkezli bir galaksi oluştur" gibi değiştirebilirsin.</p>`);
  }

  // ================= EVREN (kozmik ağ) =================
  function universe() {
    reset(); camera.position.set(0, 80, 260); controls.maxDistance = 1500;
    const nodes = Array.from({ length: 60 }, () => new T.Vector3((Math.random() - 0.5) * 500, (Math.random() - 0.5) * 300, (Math.random() - 0.5) * 500));
    const pos = [], col = [];
    nodes.forEach((a, i) => nodes.forEach((b, j) => { if (j <= i || a.distanceTo(b) > 140) return; for (let k = 0; k < 220; k++) { const t = Math.random(), p = a.clone().lerp(b, t).add(new T.Vector3((Math.random() - 0.5) * 8, (Math.random() - 0.5) * 8, (Math.random() - 0.5) * 8)); pos.push(p.x, p.y, p.z); const c = new T.Color().setHSL(0.6 - Math.random() * 0.1, 0.6, 0.5 + Math.random() * 0.2); col.push(c.r, c.g, c.b); } }));
    nodes.forEach((a) => { for (let k = 0; k < 900; k++) { const p = a.clone().add(new T.Vector3((Math.random() - 0.5), (Math.random() - 0.5), (Math.random() - 0.5)).multiplyScalar(30 * Math.random())); pos.push(p.x, p.y, p.z); col.push(1, 0.85, 0.65); } });
    root.add(new T.Points(new T.BufferGeometry().setAttribute("position", new T.Float32BufferAttribute(pos, 3)).setAttribute("color", new T.Float32BufferAttribute(col, 3)), new T.PointsMaterial({ size: 0.9, vertexColors: true, blending: T.AdditiveBlending, transparent: true, depthWrite: false })));
    update = (dt) => { root.rotation.y += dt * 0.01; };
    U.panel(`<div class="wp-title">Evrenin büyük ölçekli yapısı</div><div class="wp-grid"><i>Gösterim</i><b>temsili kozmik ağ</b><i>Her nokta</i><b>bir galaksi</b><i>Düğümler</i><b>galaksi kümeleri</b></div><p class="note">Gerçek evrende galaksiler iplikler boyunca kümelenir; aralarda dev boşluklar vardır. Bu sahne bilimsel yapıyı temsil eder, gerçek katalog değildir.</p>`);
  }

  const VIEWS = { system, satellites, sky, moon: () => planet({ name: "Ay" }), mars: () => planet({ name: "Mars" }), planet, blackhole, galaxy, universe };
  JV.worlds.space = {
    scene,
    enter() { if (!root) system(); },
    exit() { document.getElementById("space-time").classList.add("hidden"); },
    update(dt, t) {
      const now = performance.now(); simTime += (now - lastReal) * speed; lastReal = now;
      if (update) update(dt, t);
    },
    click(ray) { if (clickFn) clickFn(ray); },
    cmd(r) { view = r.view; (VIEWS[r.view] || system)(r); },
  };
})();
