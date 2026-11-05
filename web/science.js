/* BİLİM LABORATUVARI: güneş sistemi, galaksi, atom, molekül, eğik atış, sarkaç, çarpışma, yerçekimi (n-cisim),
   hava akışı, elektrik devresi, DNA, insan vücudu. Hepsi gerçek fizik/kimya formülleriyle hesaplanır. */
(function () {
  const JV = window.JV; if (!JV || !JV.wutil) return;
  const U = JV.wutil, T = U.T, DEG = U.DEG, camera = U.camera, controls = U.controls;
  const scene = new T.Scene();
  scene.add(new T.AmbientLight(0x667788, 0.6));
  const key = new T.DirectionalLight(0xffffff, 0.9); key.position.set(5, 8, 6); scene.add(key);
  const stars = new T.Points(new T.BufferGeometry().setAttribute("position", new T.Float32BufferAttribute(Array.from({ length: 9000 }, () => (Math.random() - 0.5) * 900), 3)), new T.PointsMaterial({ size: 0.7, color: 0x8fa6b8 }));
  scene.add(stars);
  let root = null, sim = null, kind = "";
  const tex = new T.TextureLoader();

  function reset(name) {
    if (root) { scene.remove(root); U.disposeTree(root); }
    root = new T.Group(); scene.add(root); sim = null; kind = name; U.panel(null); U.caption("");
    controls.target.set(0, 0, 0); controls.enablePan = true; controls.minDistance = 0.5; controls.maxDistance = 600;
  }
  const mat = (c, e = 0.25, o = 1) => new T.MeshPhongMaterial({ color: c, emissive: c, emissiveIntensity: e, transparent: o < 1, opacity: o, shininess: 50 });
  const ball = (r, c, e, o) => new T.Mesh(new T.SphereGeometry(r, 32, 20), mat(c, e, o));
  function info(title, rows, extra = "") { U.panel(`<div class="wp-title">${title}</div><div class="wp-grid">${rows.map(([a, b]) => `<i>${a}</i><b>${b}</b>`).join("")}</div>${extra}`); }
  function cam(x, y, z, tx = 0, ty = 0, tz = 0) { camera.position.set(x, y, z); controls.target.set(tx, ty, tz); }

  // ================= GÜNEŞ SİSTEMİ =================
  const PLANETS = [ // ad, yarıçap(görsel), yörünge(görsel), periyot(gün), renk, gerçek çap km, güneşe uzaklık milyon km, uydu, gün uzunluğu
    ["Merkür", 0.38, 8, 88, 0xb1aca3, 4879, 57.9, 0, "58,6 gün"], ["Venüs", 0.95, 11, 225, 0xe3c27a, 12104, 108.2, 0, "243 gün"],
    ["Dünya", 1, 15, 365.25, 0x3b7bd6, 12742, 149.6, 1, "24 saat"], ["Mars", 0.53, 19, 687, 0xc1440e, 6779, 227.9, 2, "24,6 saat"],
    ["Jüpiter", 2.6, 28, 4333, 0xd8b48a, 139820, 778.5, 95, "9,9 saat"], ["Satürn", 2.2, 37, 10759, 0xe8d39c, 116460, 1432, 146, "10,7 saat"],
    ["Uranüs", 1.5, 45, 30687, 0x9fe3ef, 50724, 2867, 28, "17,2 saat"], ["Neptün", 1.45, 52, 60190, 0x4062d8, 49244, 4515, 16, "16,1 saat"],
  ];
  function solar(p) {
    reset("solar"); cam(0, 45, 70);
    const sun = ball(4, 0xffb030, 1.2); root.add(sun);
    const glow = new T.Sprite(new T.SpriteMaterial({ map: radial("#ffcc66"), blending: T.AdditiveBlending, transparent: true, depthWrite: false })); glow.scale.set(22, 22, 1); root.add(glow);
    const light = new T.PointLight(0xfff0d0, 2.2, 400); root.add(light);
    const bodies = [];
    PLANETS.forEach((d, i) => {
      const [n, r, a, per, col] = d;
      const orbit = new T.LineLoop(new T.BufferGeometry().setFromPoints(Array.from({ length: 180 }, (_, k) => new T.Vector3(Math.cos(k / 180 * Math.PI * 2) * a, 0, Math.sin(k / 180 * Math.PI * 2) * a))), new T.LineBasicMaterial({ color: 0x38d6ff, transparent: true, opacity: 0.25 }));
      root.add(orbit);
      const m = n === "Dünya" ? new T.Mesh(new T.SphereGeometry(r, 48, 32), new T.MeshPhongMaterial({ map: tex.load("/static/vendor/textures/earth_atmos_2048.jpg") })) : ball(r, col, 0.15);
      m.userData = { planet: d, angle: Math.random() * Math.PI * 2 };
      root.add(m);
      if (n === "Satürn") { const ring = new T.Mesh(new T.RingGeometry(r * 1.3, r * 2.2, 64), new T.MeshBasicMaterial({ color: 0xd9c38f, side: T.DoubleSide, transparent: true, opacity: 0.6 })); ring.rotation.x = Math.PI / 2.4; m.add(ring); }
      if (n === "Dünya") { const moon = new T.Mesh(new T.SphereGeometry(0.27, 24, 16), new T.MeshPhongMaterial({ map: tex.load("/static/vendor/textures/moon_1024.jpg") })); moon.userData.moon = true; m.add(moon); }
      const l = U.label(n, "#cfefff", 44); l.scale.set(1.6 * l.userData.aspect, 1.6, 1); l.position.y = r + 1.2; m.add(l);
      bodies.push(m);
    });
    let days = 0;
    sim = (dt) => {
      days += dt * (sim.speed || 30);
      bodies.forEach((m) => {
        const [, , a, per] = m.userData.planet;
        const th = m.userData.angle + (days / per) * Math.PI * 2;
        m.position.set(Math.cos(th) * a, 0, Math.sin(th) * a); m.rotation.y += dt;
        m.children.forEach((c) => { if (c.userData.moon) { const t = days / 27.3 * Math.PI * 2; c.position.set(Math.cos(t) * 2, 0, Math.sin(t) * 2); } });
      });
      U.caption(`Simülasyon zamanı: +${Math.floor(days)} gün  ·  hız ×${sim.speed}/sn`);
    };
    sim.speed = p.speed || 30;
    sim.click = (ray) => {
      const h = ray.intersectObjects(bodies)[0]; if (!h) return;
      const d = h.object.userData.planet;
      info(d[0], [["Çap", `${U.fmt(d[5])} km`], ["Güneşe uzaklık", `${U.fmt(d[6], 1)} milyon km`], ["Yıl", `${U.fmt(d[3])} Dünya günü`], ["Gün", d[8]], ["Uydu", d[7]]]);
    };
    info("Güneş sistemi", [["Gezegen", 8], ["Ölçek", "boyut ve uzaklık temsili"], ["Yörünge süreleri", "gerçek oranlarda"]], `<p class="note">Bir gezegene tıkla. "Simülasyonu hızlandır" diyebilirsin.</p>`);
  }
  function radial(color) {
    const c = document.createElement("canvas"); c.width = c.height = 128; const g = c.getContext("2d");
    const gr = g.createRadialGradient(64, 64, 0, 64, 64, 64); gr.addColorStop(0, color); gr.addColorStop(0.3, color + "88"); gr.addColorStop(1, "#0000");
    g.fillStyle = gr; g.fillRect(0, 0, 128, 128); return new T.CanvasTexture(c);
  }

  // ================= GALAKSİ =================
  function galaxy(p) {
    reset("galaxy"); cam(0, 30, 45);
    const n = 60000, arms = p.arms || 4, elliptical = p.type === "elliptical", pos = new Float32Array(n * 3), col = new Float32Array(n * 3);
    const inner = new T.Color("#ffd9a0"), outer = new T.Color(p.color || "#5fa8ff");
    for (let i = 0; i < n; i++) {
      const r = Math.pow(Math.random(), 1.6) * 25;
      let x, y, z;
      if (elliptical) { const u = Math.random() * 2 - 1, a = Math.random() * Math.PI * 2, s = Math.sqrt(1 - u * u); x = r * s * Math.cos(a); y = r * u * 0.6; z = r * s * Math.sin(a); }
      else {
        const arm = (i % arms) / arms * Math.PI * 2, spin = r * 0.28, rnd = () => Math.pow(Math.random(), 3) * (Math.random() < 0.5 ? 1 : -1) * (1 + r * 0.12);
        x = Math.cos(arm + spin) * r + rnd(); y = rnd() * 0.35; z = Math.sin(arm + spin) * r + rnd();
      }
      pos.set([x, y, z], i * 3);
      const c = inner.clone().lerp(outer, r / 25); col.set([c.r, c.g, c.b], i * 3);
    }
    const g = new T.Points(new T.BufferGeometry().setAttribute("position", new T.BufferAttribute(pos, 3)).setAttribute("color", new T.BufferAttribute(col, 3)),
      new T.PointsMaterial({ size: 0.09, vertexColors: true, blending: T.AdditiveBlending, depthWrite: false, transparent: true }));
    root.add(g);
    const core = new T.Sprite(new T.SpriteMaterial({ map: radial("#ffe6b0"), blending: T.AdditiveBlending, transparent: true, depthWrite: false })); core.scale.set(12, 12, 1); root.add(core);
    if (p.blackhole !== false) { const bh = ball(0.6, 0x000000, 0); root.add(bh); const disk = new T.Mesh(new T.RingGeometry(0.8, 2.2, 96), new T.MeshBasicMaterial({ color: 0xffa040, side: T.DoubleSide, transparent: true, opacity: 0.55, blending: T.AdditiveBlending })); disk.rotation.x = Math.PI / 2; root.add(disk); }
    sim = (dt) => { g.rotation.y += dt * 0.04; };
    info(elliptical ? "Eliptik galaksi" : "Sarmal galaksi", [["Yıldız (gösterilen)", U.fmt(n)], ["Kol sayısı", elliptical ? "—" : arms], ["Merkez", "süper kütleli kara delik"]], `<p class="note">Samanyolu ~100–400 milyar yıldız, ~100.000 ışık yılı çapındadır.</p>`);
  }

  // ================= ATOM =================
  const SYM = "H He Li Be B C N O F Ne Na Mg Al Si P S Cl Ar K Ca Sc Ti V Cr Mn Fe Co Ni Cu Zn Ga Ge As Se Br Kr Rb Sr Y Zr Nb Mo Tc Ru Rh Pd Ag Cd In Sn Sb Te I Xe Cs Ba La Ce Pr Nd Pm Sm Eu Gd Tb Dy Ho Er Tm Yb Lu Hf Ta W Re Os Ir Pt Au Hg Tl Pb Bi Po At Rn Fr Ra Ac Th Pa U Np Pu Am Cm Bk Cf Es Fm Md No Lr Rf Db Sg Bh Hs Mt Ds Rg Cn Nh Fl Mc Lv Ts Og".split(" ");
  const NAMES = { H: "Hidrojen", He: "Helyum", Li: "Lityum", Be: "Berilyum", B: "Bor", C: "Karbon", N: "Azot", O: "Oksijen", F: "Flor", Ne: "Neon", Na: "Sodyum", Mg: "Magnezyum", Al: "Alüminyum", Si: "Silisyum", P: "Fosfor", S: "Kükürt", Cl: "Klor", Ar: "Argon", K: "Potasyum", Ca: "Kalsiyum", Ti: "Titanyum", Cr: "Krom", Mn: "Mangan", Fe: "Demir", Co: "Kobalt", Ni: "Nikel", Cu: "Bakır", Zn: "Çinko", Br: "Brom", Kr: "Kripton", Ag: "Gümüş", Sn: "Kalay", I: "İyot", Xe: "Ksenon", W: "Tungsten", Pt: "Platin", Au: "Altın", Hg: "Cıva", Pb: "Kurşun", U: "Uranyum", Ra: "Radyum", Pu: "Plütonyum" };
  const MASS = [1.008, 4.003, 6.94, 9.012, 10.81, 12.011, 14.007, 15.999, 18.998, 20.18, 22.99, 24.305, 26.982, 28.085, 30.974, 32.06, 35.45, 39.948, 39.098, 40.078, 44.956, 47.867, 50.942, 51.996, 54.938, 55.845, 58.933, 58.693, 63.546, 65.38, 69.723, 72.63, 74.922, 78.971, 79.904, 83.798];
  function shells(Z) { // Aufbau (Madelung) kuralıyla kabuk doluluğu
    const order = [[1, 0], [2, 0], [2, 1], [3, 0], [3, 1], [4, 0], [3, 2], [4, 1], [5, 0], [4, 2], [5, 1], [6, 0], [4, 3], [5, 2], [6, 1], [7, 0], [5, 3], [6, 2], [7, 1]];
    const sh = []; let left = Z;
    for (const [n, l] of order) { if (left <= 0) break; const k = Math.min(left, 2 * (2 * l + 1)); sh[n - 1] = (sh[n - 1] || 0) + k; left -= k; }
    return sh.map((x) => x || 0);
  }
  function atom(p) {
    reset("atom"); cam(0, 6, 18);
    let e = String(p.element || "C").trim(); let Z = +e;
    if (!Z) { const i = SYM.findIndex((s) => s.toLowerCase() === e.toLowerCase()); Z = i >= 0 ? i + 1 : (Object.entries(NAMES).find(([, v]) => v.toLowerCase() === e.toLowerCase()) || [])[0] ? SYM.indexOf(Object.entries(NAMES).find(([, v]) => v.toLowerCase() === e.toLowerCase())[0]) + 1 : 6; }
    Z = Math.max(1, Math.min(118, Z));
    const sym = SYM[Z - 1], mass = MASS[Z - 1] || Math.round(Z * 2.45), A = Math.round(mass), N = A - Z, sh = shells(Z);
    const nuc = new T.Group(); root.add(nuc);
    const nr = 0.22, R = Math.cbrt(A) * nr * 0.9;
    for (let i = 0; i < A; i++) { const s = ball(nr, i < Z ? 0xff4d5e : 0x9aa7b4, 0.3); const u = Math.random() * 2 - 1, a = Math.random() * Math.PI * 2, r = Math.cbrt(Math.random()) * R; s.position.set(r * Math.sqrt(1 - u * u) * Math.cos(a), r * u, r * Math.sqrt(1 - u * u) * Math.sin(a)); nuc.add(s); }
    const electrons = [];
    sh.forEach((cnt, k) => {
      const rad = 2.2 + k * 1.6, tilt = new T.Euler(Math.random() * 1.2, Math.random() * 3, 0);
      const ring = new T.Mesh(new T.TorusGeometry(rad, 0.015, 8, 128), new T.MeshBasicMaterial({ color: 0x38d6ff, transparent: true, opacity: 0.5 }));
      ring.rotation.copy(tilt); root.add(ring);
      for (let j = 0; j < cnt; j++) { const el = ball(0.14, 0x7af0ff, 0.9); el.userData = { rad, tilt, ph: (j / cnt) * Math.PI * 2, w: 1.6 / (k + 1) }; root.add(el); electrons.push(el); }
    });
    sim = (dt, t) => { nuc.rotation.y += dt * 0.3; electrons.forEach((el) => { const a = el.userData.ph + t * el.userData.w; el.position.set(Math.cos(a) * el.userData.rad, 0, Math.sin(a) * el.userData.rad).applyEuler(el.userData.tilt); }); };
    info(`${NAMES[sym] || sym} (${sym})`, [["Atom numarası (proton)", Z], ["Nötron (en yaygın izotop ~)", N], ["Elektron", Z], ["Atom kütlesi", `${mass} u`], ["Kabuklar", sh.join(" · ")], ["Değerlik elektronu", sh[sh.length - 1]]], `<p class="note">Bohr modeli gösterimidir; gerçekte elektronlar olasılık bulutlarıdır.</p>`);
  }

  // ================= MOLEKÜL =================
  const CPK = { H: [0xffffff, 0.31], C: [0x404040, 0.7], N: [0x3050f8, 0.65], O: [0xff0d0d, 0.6], F: [0x90e050, 0.5], Cl: [0x1ff01f, 0.8], Br: [0xa62929, 0.9], I: [0x940094, 1.0], S: [0xffff30, 0.85], P: [0xff8000, 0.85], Na: [0xab5cf2, 0.9], K: [0x8f40d4, 1.0], Fe: [0xe06633, 0.9], Ca: [0x3dff00, 0.95], Mg: [0x8aff00, 0.85] };
  async function molecule(p) {
    reset("molecule"); cam(0, 2, 14);
    U.caption("Molekül yapısı PubChem'den alınıyor…");
    const d = await JV.api("/api/sci/molecule?name=" + encodeURIComponent(p.name || "caffeine"));
    U.caption("");
    if (d.error) { info("Bulunamadı", [["Hata", d.error]]); return; }
    const c = new T.Vector3(); d.atomlar.forEach((a) => c.add(new T.Vector3(...a.p))); c.divideScalar(d.atomlar.length);
    const pts = d.atomlar.map((a) => new T.Vector3(...a.p).sub(c).multiplyScalar(1.4));
    d.atomlar.forEach((a, i) => { const [col, r] = CPK[a.e] || [0xff69b4, 0.8]; const s = ball(r * 0.55, col, 0.15); s.position.copy(pts[i]); s.userData.el = a.e; root.add(s); });
    d.bağlar.forEach(([i, j, order]) => {
      const a = pts[i], b = pts[j], len = a.distanceTo(b), mid = a.clone().add(b).multiplyScalar(0.5);
      const dir = b.clone().sub(a).normalize(), q = new T.Quaternion().setFromUnitVectors(new T.Vector3(0, 1, 0), dir);
      const side = new T.Vector3(1, 0, 0).applyQuaternion(q).multiplyScalar(0.12);
      for (let k = 0; k < order; k++) {
        const cyl = new T.Mesh(new T.CylinderGeometry(0.07, 0.07, len, 10), mat(0xc8d6e0, 0.1));
        cyl.position.copy(mid).addScaledVector(side, (k - (order - 1) / 2)); cyl.quaternion.copy(q); root.add(cyl);
      }
    });
    const box = new T.Box3().setFromObject(root), r = box.getSize(new T.Vector3()).length();
    camera.position.set(0, r * 0.2, r * 1.3);
    sim = (dt) => { root.rotation.y += dt * 0.3; };
    const counts = {}; d.atomlar.forEach((a) => (counts[a.e] = (counts[a.e] || 0) + 1));
    info(p.name, [["Formül", d.formül], ["Atom sayısı", d.atomlar.length], ["Bağ sayısı", d.bağlar.length], ["Kaynak", "PubChem (NIH)"]],
      `<div class="wp-legend">${Object.keys(counts).map((e) => `<span style="--d:#${((CPK[e] || [0xff69b4])[0]).toString(16).padStart(6, "0")}">${e} ×${counts[e]}</span>`).join("")}</div>`);
  }

  // ================= EĞİK ATIŞ =================
  function ground(size = 80) {
    const g = new T.GridHelper(size, size / 2, 0x38d6ff, 0x123a48); g.material.transparent = true; g.material.opacity = 0.5; root.add(g);
  }
  function projectile(p) {
    reset("projectile");
    const ang = (p.angle ?? 45) * DEG, v0 = p.speed ?? 20, g = p.gravity ?? 9.81, h0 = p.height ?? 0;
    const tFlight = (v0 * Math.sin(ang) + Math.sqrt((v0 * Math.sin(ang)) ** 2 + 2 * g * h0)) / g;
    const range = v0 * Math.cos(ang) * tFlight, hmax = h0 + (v0 * Math.sin(ang)) ** 2 / (2 * g);
    const s = 40 / Math.max(range, 2 * hmax, 1);
    ground(); cam(range * s * 0.5 - 20, hmax * s * 0.6 + 8, 40, range * s * 0.5 - 20, hmax * s * 0.3, 0);
    const cannon = new T.Mesh(new T.CylinderGeometry(0.4, 0.5, 2.4, 20), mat(0x7af0ff, 0.3)); cannon.position.set(-20, h0 * s + 0.3, 0); cannon.rotation.z = -(Math.PI / 2 - ang); root.add(cannon);
    const b = ball(0.5, 0xffd34d, 0.6); root.add(b);
    const path = []; for (let i = 0; i <= 120; i++) { const t = (i / 120) * tFlight; path.push(new T.Vector3(-20 + v0 * Math.cos(ang) * t * s, (h0 + v0 * Math.sin(ang) * t - g * t * t / 2) * s, 0)); }
    root.add(new T.Line(new T.BufferGeometry().setFromPoints(path), new T.LineDashedMaterial({ color: 0xffd34d, dashSize: 0.6, gapSize: 0.3 }))).children;
    root.children[root.children.length - 1].computeLineDistances();
    let t = 0;
    sim = (dt) => { t += dt; const tt = t % (tFlight + 1); const k = Math.min(tt, tFlight); b.position.set(-20 + v0 * Math.cos(ang) * k * s, Math.max(0, (h0 + v0 * Math.sin(ang) * k - g * k * k / 2) * s) + 0.5, 0); };
    info("Eğik atış", [["Açı", `${(ang / DEG).toFixed(0)}°`], ["İlk hız", `${v0} m/s`], ["Yerçekimi", `${g} m/s²`], ["Uçuş süresi", `${tFlight.toFixed(2)} s`], ["Menzil", `${range.toFixed(1)} m`], ["Maks. yükseklik", `${hmax.toFixed(1)} m`]], `<p class="note">Hava direnci yok sayılmıştır. "Açıyı 30 yap", "Ay'daki yerçekimiyle (1.62) dene" diyebilirsin.</p>`);
  }

  // ================= SARKAÇ =================
  function pendulum(p) {
    reset("pendulum"); cam(0, -2, 12, 0, -2, 0);
    const L = p.length ?? 2, g = p.gravity ?? 9.81, th0 = (p.angle ?? 30) * DEG, sc = 3 / L;
    const pivot = ball(0.15, 0xffffff, 0.4); root.add(pivot);
    const rod = new T.Mesh(new T.CylinderGeometry(0.03, 0.03, L * sc, 8), mat(0x7af0ff, 0.3)); root.add(rod);
    const bob = ball(0.45, 0xffd34d, 0.5); root.add(bob);
    let th = th0, w = 0;
    sim = (dt) => {
      for (let i = 0; i < 8; i++) { const h = dt / 8; const a = -(g / L) * Math.sin(th); w += a * h; th += w * h; } // yarı-örtük Euler
      const x = Math.sin(th) * L * sc, y = -Math.cos(th) * L * sc;
      bob.position.set(x, y, 0); rod.position.set(x / 2, y / 2, 0); rod.rotation.z = th;
    };
    info("Basit sarkaç", [["Uzunluk", `${L} m`], ["Başlangıç açısı", `${(th0 / DEG).toFixed(0)}°`], ["Periyot (küçük açı)", `${(2 * Math.PI * Math.sqrt(L / g)).toFixed(3)} s`], ["Frekans", `${(1 / (2 * Math.PI * Math.sqrt(L / g))).toFixed(3)} Hz`]], `<p class="note">Doğrusal olmayan denklem sayısal olarak çözülür: θ'' = −(g/L)·sinθ</p>`);
  }

  // ================= ÇARPIŞMA =================
  function collision(p) {
    reset("collision"); ground(30); cam(0, 22, 18);
    const n = p.balls || 12, e = p.elasticity ?? 1, balls = [];
    for (let i = 0; i < n; i++) { const r = 0.4 + Math.random() * 0.6, m = r ** 3; const b = ball(r, new T.Color().setHSL(i / n, 0.8, 0.6).getHex(), 0.3); b.position.set((Math.random() - 0.5) * 18, r, (Math.random() - 0.5) * 18); b.userData = { v: new T.Vector3((Math.random() - 0.5) * 8, 0, (Math.random() - 0.5) * 8), r, m }; root.add(b); balls.push(b); }
    const wall = new T.LineLoop(new T.BufferGeometry().setFromPoints([[-10, 10], [10, 10], [10, -10], [-10, -10]].map(([x, z]) => new T.Vector3(x, 0.05, z))), new T.LineBasicMaterial({ color: 0x38d6ff })); root.add(wall);
    sim = (dt) => {
      balls.forEach((b) => { b.position.addScaledVector(b.userData.v, dt); ["x", "z"].forEach((ax) => { if (Math.abs(b.position[ax]) > 10 - b.userData.r) { b.position[ax] = Math.sign(b.position[ax]) * (10 - b.userData.r); b.userData.v[ax] *= -e; } }); });
      for (let i = 0; i < n; i++) for (let j = i + 1; j < n; j++) {
        const a = balls[i], b = balls[j], d = b.position.clone().sub(a.position), dist = d.length(), min = a.userData.r + b.userData.r;
        if (dist < min && dist > 0) {
          const nrm = d.divideScalar(dist), rv = b.userData.v.clone().sub(a.userData.v).dot(nrm);
          if (rv < 0) { const J = -(1 + e) * rv / (1 / a.userData.m + 1 / b.userData.m); a.userData.v.addScaledVector(nrm, -J / a.userData.m); b.userData.v.addScaledVector(nrm, J / b.userData.m); }
          const corr = (min - dist) / 2; a.position.addScaledVector(nrm, -corr); b.position.addScaledVector(nrm, corr);
        }
      }
      const P = balls.reduce((s, b) => s.add(b.userData.v.clone().multiplyScalar(b.userData.m)), new T.Vector3()), K = balls.reduce((s, b) => s + 0.5 * b.userData.m * b.userData.v.lengthSq(), 0);
      U.caption(`Toplam momentum: ${P.length().toFixed(2)}  ·  Kinetik enerji: ${K.toFixed(2)}`);
    };
    info("Çarpışma", [["Top", n], ["Esneklik (e)", e], ["Not", e === 1 ? "esnek: enerji korunur" : "esnek olmayan: enerji kaybolur"]]);
  }

  // ================= YERÇEKİMİ (N-CİSİM) =================
  function gravity(p) {
    reset("gravity"); cam(0, 40, 50);
    const G = p.G ?? 1, n = Math.min(40, p.bodies || 8), bodies = [];
    const star = ball(1.6, 0xffb030, 1); star.userData = { m: 1000, v: new T.Vector3(), trail: [] }; root.add(star); bodies.push(star);
    for (let i = 0; i < n; i++) {
      const r = 8 + i * 3 + Math.random() * 2, a = Math.random() * Math.PI * 2, b = ball(0.3 + Math.random() * 0.4, new T.Color().setHSL(Math.random(), 0.7, 0.6).getHex(), 0.4);
      b.position.set(Math.cos(a) * r, (Math.random() - 0.5), Math.sin(a) * r);
      const vmag = Math.sqrt(G * 1000 / r) * (0.85 + Math.random() * 0.3);
      b.userData = { m: 0.5 + Math.random() * 3, v: new T.Vector3(-Math.sin(a) * vmag, 0, Math.cos(a) * vmag), trail: [] };
      const line = new T.Line(new T.BufferGeometry(), new T.LineBasicMaterial({ color: b.material.color, transparent: true, opacity: 0.5 })); root.add(line); b.userData.line = line;
      root.add(b); bodies.push(b);
    }
    sim = (dt) => {
      const steps = 6, h = dt * (sim.speed || 1) / steps;
      for (let s = 0; s < steps; s++) {
        const acc = bodies.map(() => new T.Vector3());
        for (let i = 0; i < bodies.length; i++) for (let j = 0; j < bodies.length; j++) { if (i === j) continue; const d = bodies[j].position.clone().sub(bodies[i].position), r2 = d.lengthSq() + 0.5; acc[i].addScaledVector(d.normalize(), G * bodies[j].userData.m / r2); }
        bodies.forEach((b, i) => { b.userData.v.addScaledVector(acc[i], h); b.position.addScaledVector(b.userData.v, h); });
      }
      bodies.forEach((b) => { if (!b.userData.line) return; b.userData.trail.push(b.position.clone()); if (b.userData.trail.length > 240) b.userData.trail.shift(); b.userData.line.geometry.setFromPoints(b.userData.trail); });
    };
    sim.speed = p.speed || 1;
    info("Yerçekimi (n-cisim)", [["Cisim", n + 1], ["Yöntem", "Newton kütle çekimi, sayısal entegrasyon"], ["G", G]], `<p class="note">Cisimler birbirini de çeker; yörüngeler bu yüzden zamanla bozulabilir.</p>`);
  }

  // ================= HAVA AKIŞI =================
  function airflow(p) {
    reset("airflow"); cam(0, 0, 26);
    const Uinf = p.speed ?? 1, R = 2.2, wing = p.shape === "wing", Gamma = wing ? -(p.lift ?? 8) : (p.spin ?? 0);
    if (wing) { // NACA 0012 benzeri profil (görsel)
      const sh = new T.Shape(); for (let i = 0; i <= 40; i++) { const x = i / 40, t = 0.12 * 5 * (0.2969 * Math.sqrt(x) - 0.126 * x - 0.3516 * x * x + 0.2843 * x ** 3 - 0.1015 * x ** 4); i ? sh.lineTo((x - 0.5) * 2 * R * 1.6, t * 2 * R * 1.6) : sh.moveTo(-R * 1.6, 0); }
      for (let i = 40; i >= 0; i--) { const x = i / 40, t = 0.12 * 5 * (0.2969 * Math.sqrt(x) - 0.126 * x - 0.3516 * x * x + 0.2843 * x ** 3 - 0.1015 * x ** 4); sh.lineTo((x - 0.5) * 2 * R * 1.6, -t * 2 * R * 1.6); }
      const m = new T.Mesh(new T.ExtrudeGeometry(sh, { depth: 2, bevelEnabled: false }), mat(0x9aa7b4, 0.2)); m.position.z = -1; m.rotation.z = -6 * DEG; root.add(m);
    } else { const c = new T.Mesh(new T.CylinderGeometry(R, R, 3, 48), mat(0x9aa7b4, 0.2)); c.rotation.x = Math.PI / 2; root.add(c); }
    const N = 3500, pos = new Float32Array(N * 3), col = new Float32Array(N * 3), P = [];
    for (let i = 0; i < N; i++) P.push([-18 + Math.random() * 36, -10 + Math.random() * 20]);
    const geo = new T.BufferGeometry().setAttribute("position", new T.BufferAttribute(pos, 3)).setAttribute("color", new T.BufferAttribute(col, 3));
    root.add(new T.Points(geo, new T.PointsMaterial({ size: 0.2, vertexColors: true, transparent: true, opacity: 0.9 })));
    const vel = (x, y) => { // silindir etrafında potansiyel akış + sirkülasyon
      const r2 = x * x + y * y; if (r2 < R * R) return [0, 0];
      const r4 = r2 * r2;
      let u = Uinf * (1 - R * R * (x * x - y * y) / r4), v = -Uinf * 2 * R * R * x * y / r4;
      u += Gamma * y / (2 * Math.PI * r2); v += -Gamma * x / (2 * Math.PI * r2);
      return [u, v];
    };
    const c = new T.Color();
    sim = (dt) => {
      for (let i = 0; i < N; i++) {
        let [x, y] = P[i]; const [u, v] = vel(x, y); x += u * dt * 4; y += v * dt * 4;
        if (x > 18 || x * x + y * y < R * R * 0.98 || Math.abs(y) > 10) { x = -18; y = -10 + Math.random() * 20; }
        P[i] = [x, y]; pos.set([x, y, (i % 7 - 3) * 0.15], i * 3);
        const sp = Math.hypot(u, v) / Uinf; c.setHSL(0.6 - Math.min(1, sp / 2) * 0.6, 1, 0.55); col.set([c.r, c.g, c.b], i * 3);
      }
      geo.attributes.position.needsUpdate = true; geo.attributes.color.needsUpdate = true;
    };
    const lift = 1.225 * Uinf * Math.abs(Gamma);
    info(wing ? "Kanat etrafında hava akışı" : "Silindir etrafında hava akışı", [["Akış hızı", `${Uinf} (göreli)`], ["Sirkülasyon Γ", Gamma], ["Kaldırma (Kutta–Joukowski, birim boy)", `${lift.toFixed(2)} N/m (ρ=1.225)`], ["Renk", "mavi yavaş → kırmızı hızlı"]], `<p class="note">İdeal (sürtünmesiz) potansiyel akış modelidir; kanat görseli için silindir+sirkülasyon yaklaşımı kullanılır.</p>`);
  }

  // ================= ELEKTRİK DEVRESİ =================
  function circuit(p, r) {
    reset("circuit"); cam(0, 0.5, 21);
    const V = +(p.voltage ?? 9), rs = (p.resistors || [100, 220]).map(Number), par = p.mode === "parallel";
    const res = r && r.sonuç ? r.sonuç : (() => { const Rt = par ? 1 / rs.reduce((s, x) => s + 1 / x, 0) : rs.reduce((s, x) => s + x, 0); const I = V / Rt; return { toplam_direnç_ohm: Rt, toplam_akım_mA: I * 1000, toplam_güç_mW: V * I * 1000, dirençler: rs.map((R) => par ? { R, V, I_mA: V / R * 1000 } : { R, V: I * R, I_mA: I * 1000 }) }; })();
    const wire = (pts) => root.add(new T.Line(new T.BufferGeometry().setFromPoints(pts.map((q) => new T.Vector3(q[0], q[1], 0))), new T.LineBasicMaterial({ color: 0x38d6ff })));
    const bat = new T.Group(); bat.add(new T.Mesh(new T.BoxGeometry(0.8, 2, 0.8), mat(0x5dff9a, 0.3))); bat.position.set(-6, 0, 0); root.add(bat);
    const bl = U.label(`${V} V`, "#5dff9a", 48); bl.scale.set(0.5 * bl.userData.aspect, 0.5, 1); bl.position.set(-6, 1.6, 0); root.add(bl);
    const n = rs.length, path = [];
    if (par) {
      wire([[-6, 1], [-6, 3], [6, 3]]); wire([[-6, -1], [-6, -3], [6, -3]]);
      rs.forEach((R, i) => { const x = -3 + (i + 0.5) * 9 / n; wire([[x, 3], [x, 1]]); wire([[x, -1], [x, -3]]); addR(x, 0, R, res.dirençler[i], true); });
      for (let i = 0; i <= 60; i++) path.push(new T.Vector3(-6 + 12 * i / 60, 3, 0));
    } else {
      wire([[-6, 1], [-6, 3], [6, 3], [6, -3], [-6, -3], [-6, -1]]);
      rs.forEach((R, i) => addR(-4 + (i + 0.5) * 8 / n, 3, R, res.dirençler[i], false));
      [[-6, 3], [6, 3], [6, -3], [-6, -3]].forEach((q, i, a) => { const b = a[(i + 1) % 4]; for (let k = 0; k < 30; k++) path.push(new T.Vector3(q[0] + (b[0] - q[0]) * k / 30, q[1] + (b[1] - q[1]) * k / 30, 0)); });
    }
    function addR(x, y, R, d, vertical) {
      const m = new T.Mesh(new T.BoxGeometry(vertical ? 0.5 : 1.4, vertical ? 1.4 : 0.5, 0.5), mat(0xffa03a, 0.35)); m.position.set(x, y, 0); root.add(m);
      const l = U.label(`${R}Ω · ${d.V.toFixed(2)}V · ${d.I_mA.toFixed(1)}mA`, "#ffd9a0", 40); l.scale.set(0.38 * l.userData.aspect, 0.38, 1); l.position.set(x, y + (vertical ? 0 : 0.9), 0.6); root.add(l);
    }
    const dots = Array.from({ length: 24 }, (_, i) => { const d = ball(0.09, 0xffff66, 1); d.userData.k = i / 24; root.add(d); return d; });
    const speed = Math.min(0.5, res.toplam_akım_mA / 400 + 0.03);
    sim = (dt) => dots.forEach((d) => { d.userData.k = (d.userData.k + dt * speed) % 1; d.position.copy(path[Math.floor(d.userData.k * (path.length - 1))]); });
    info(par ? "Paralel devre" : "Seri devre", [["Gerilim", `${V} V`], ["Toplam direnç", `${(+res.toplam_direnç_ohm).toFixed(2)} Ω`], ["Toplam akım", `${(+res.toplam_akım_mA).toFixed(2)} mA`], ["Toplam güç", `${(+res.toplam_güç_mW).toFixed(1)} mW`]], `<p class="note">Ohm yasası: V = I·R. Sarı noktalar akımın yönünü ve göreli hızını gösterir.</p>`);
  }

  // ================= DNA =================
  function dna(p) {
    reset("dna"); cam(0, 0, 22);
    const seq = (p.sequence || "ATGCGTACGTTAGCCTAGGCATCGATCGGA").toUpperCase().replace(/[^ATGC]/g, "").slice(0, 80);
    const pair = { A: "T", T: "A", G: "C", C: "G" }, colB = { A: 0xff4d5e, T: 0x4d8bff, G: 0x5dff9a, C: 0xffd34d };
    const g = new T.Group(); root.add(g);
    const rise = 0.34 * 1.5, turn = 36 * DEG, rad = 2;
    [...seq].forEach((b, i) => {
      const y = (i - seq.length / 2) * rise, a = i * turn;
      const p1 = new T.Vector3(Math.cos(a) * rad, y, Math.sin(a) * rad), p2 = new T.Vector3(Math.cos(a + Math.PI) * rad, y, Math.sin(a + Math.PI) * rad);
      const s1 = ball(0.25, 0xcfefff, 0.3), s2 = ball(0.25, 0xcfefff, 0.3); s1.position.copy(p1); s2.position.copy(p2); g.add(s1, s2);
      const mid = p1.clone().add(p2).multiplyScalar(0.5);
      [[p1, b], [p2, pair[b]]].forEach(([q, base]) => { const h = q.clone().add(mid).multiplyScalar(0.5), len = q.distanceTo(mid); const c = new T.Mesh(new T.CylinderGeometry(0.12, 0.12, len, 8), mat(colB[base], 0.4)); c.position.copy(h); c.quaternion.setFromUnitVectors(new T.Vector3(0, 1, 0), mid.clone().sub(q).normalize()); g.add(c); });
    });
    sim = (dt) => { g.rotation.y += dt * 0.4; };
    const gc = [...seq].filter((x) => x === "G" || x === "C").length;
    info("DNA çift sarmalı", [["Dizi", seq.length > 24 ? seq.slice(0, 24) + "…" : seq], ["Baz çifti", seq.length], ["GC oranı", `%${(gc / seq.length * 100).toFixed(1)}`], ["Tamamlayıcı", [...seq.slice(0, 16)].map((x) => pair[x]).join("") + "…"]], `<div class="wp-legend"><span style="--d:#ff4d5e">A</span><span style="--d:#4d8bff">T</span><span style="--d:#5dff9a">G</span><span style="--d:#ffd34d">C</span></div><p class="note">B-DNA: tur başına ~10 baz çifti, 3,4 nm adım.</p>`);
  }

  // ================= İNSAN VÜCUDU =================
  const ORGANS = [
    ["beyin", "Beyin", 0xff9ab0, [0, 6.95, 0], [0.55, 0.45, 0.6], "~1,4 kg; vücut enerjisinin ~%20'sini kullanır, ~86 milyar nöron içerir."],
    ["kalp", "Kalp", 0xff2a40, [0.18, 4.75, 0.15], [0.28, 0.33, 0.25], "Dakikada ~60–100 atım; günde ~7.500 litre kan pompalar."],
    ["akciger_sol", "Sol akciğer", 0xff8fa0, [0.48, 4.85, 0], [0.32, 0.6, 0.3], "Sol akciğer kalbe yer açmak için 2 lobludur."],
    ["akciger_sag", "Sağ akciğer", 0xff8fa0, [-0.48, 4.85, 0], [0.35, 0.62, 0.3], "Sağ akciğer 3 lobludur; toplam ~480 milyon alveol."],
    ["karaciger", "Karaciğer", 0x9b4a2a, [-0.3, 4.05, 0.05], [0.55, 0.3, 0.32], "En büyük iç organ (~1,5 kg); 500'den fazla görevi var."],
    ["mide", "Mide", 0xffa860, [0.35, 3.95, 0.08], [0.3, 0.25, 0.22], "~1–1,5 litre kapasite; asidi pH 1,5–3,5."],
    ["bobrek_sol", "Sol böbrek", 0xb04ac8, [0.32, 3.55, -0.15], [0.14, 0.22, 0.12], "Günde ~180 litre kanı süzer."],
    ["bobrek_sag", "Sağ böbrek", 0xb04ac8, [-0.32, 3.5, -0.15], [0.14, 0.22, 0.12], "Karaciğer yüzünden soldakinden biraz aşağıdadır."],
    ["bagirsak", "Bağırsaklar", 0xffc4a0, [0, 3.15, 0.05], [0.55, 0.42, 0.28], "İnce bağırsak ~6–7 m, kalın bağırsak ~1,5 m."],
    ["mesane", "Mesane", 0xffe066, [0, 2.6, 0.08], [0.18, 0.15, 0.15], "~400–600 ml idrar depolayabilir."],
  ];
  function body() {
    reset("body"); cam(0, 4.5, 9, 0, 4.2, 0);
    const skin = (geo, x, y, z, rz = 0) => { const m = new T.Mesh(geo, new T.MeshPhongMaterial({ color: 0x38d6ff, emissive: 0x0a3a50, transparent: true, opacity: 0.16, depthWrite: false, side: T.DoubleSide })); m.position.set(x, y, z); m.rotation.z = rz; root.add(m); const e = new T.LineSegments(new T.EdgesGeometry(geo, 30), new T.LineBasicMaterial({ color: 0x38d6ff, transparent: true, opacity: 0.25 })); e.position.copy(m.position); e.rotation.copy(m.rotation); root.add(e); };
    skin(new T.SphereGeometry(0.7, 24, 18), 0, 6.9, 0);
    skin(new T.CylinderGeometry(0.25, 0.3, 0.5, 16), 0, 6.05, 0);
    skin(new T.CylinderGeometry(0.95, 0.75, 2.6, 24), 0, 4.55, 0);
    skin(new T.CylinderGeometry(0.75, 0.85, 0.8, 24), 0, 2.9, 0);
    [-1, 1].forEach((s) => { skin(new T.CylinderGeometry(0.22, 0.18, 2.6, 12), s * 1.25, 4.6, 0, s * 0.12); skin(new T.CylinderGeometry(0.3, 0.2, 3.2, 12), s * 0.42, 0.95, 0); });
    const org = ORGANS.map(([id, n, c, p, sc, txt]) => { const m = ball(1, c, 0.35, 0.95); m.scale.set(...sc); m.position.set(...p); m.userData = { n, txt }; root.add(m); return m; });
    // iskelet (basitleştirilmiş): omurga ve kaburgalar
    for (let i = 0; i < 24; i++) { const v = ball(0.07, 0xeeeeee, 0.2); v.position.set(0, 2.9 + i * 0.13, -0.35); root.add(v); }
    for (let i = 0; i < 10; i++) { const r = new T.Mesh(new T.TorusGeometry(0.75 - Math.abs(i - 4) * 0.03, 0.02, 6, 32, Math.PI * 1.6), mat(0xeeeeee, 0.2, 0.6)); r.rotation.x = Math.PI / 2; r.rotation.z = Math.PI * 0.7; r.position.set(0, 4.0 + i * 0.16, -0.05); root.add(r); }
    sim = (dt, t) => { org[1].scale.setScalar(1).multiply(new T.Vector3(0.28, 0.33, 0.25)).multiplyScalar(1 + 0.08 * Math.max(0, Math.sin(t * 7.5))); };
    sim.click = (ray) => { const h = ray.intersectObjects(org)[0]; if (h) info(h.object.userData.n, [["Bilgi", h.object.userData.txt]]); };
    info("İnsan vücudu", [["Organ", ORGANS.length], ["Kalp", "atıyor (~72 atım/dk)"]], `<p class="note">Bir organa tıkla. Eğitim amaçlı basitleştirilmiş modeldir.</p>`);
  }

  const SIMS = { solar, galaxy, atom, molecule, projectile, pendulum, collision, gravity, airflow, circuit, dna, body };
  JV.science = { speed(f) { if (sim) sim.speed = (sim.speed || 1) * f; }, rotate(dx, dy) { if (root) { root.rotation.y += dx; root.rotation.x += dy; } } };
  JV.worlds.science = {
    scene,
    enter() { controls.enablePan = true; controls.rotateSpeed = 0.8; if (!root) solar({}); },
    exit() {},
    update(dt, t) { if (sim) sim(dt, t); },
    click(ray) { if (sim && sim.click) sim.click(ray); },
    cmd(k, p, r) { (SIMS[k] || solar)(p || {}, r); },
    sims: SIMS,
  };
})();
