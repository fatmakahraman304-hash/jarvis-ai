/* SANAL DÜNYA / ŞEHİR KURUCU: prosedürel şehir (1 birim = 1 metre), gece-gündüz döngüsü ve zaman ölçeği, trafik ışıklı ve
   takip mesafeli araç trafiği, hava (yağmur/kar/sis/rüzgâr), ayarlanabilir yerçekimi ile gerçek fizik (serbest düşme, sekme, çarpışma),
   parçacık sistemleri (ateş, duman, fıskiye suyu), Verlet kumaş (bayrak). Tıklayarak bina/ev/ağaç/park ekle, sil, top bırak, ateş yak. */
(function () {
  const JV = window.JV; if (!JV || !JV.wutil) return;
  const U = JV.wutil, T = U.T, camera = U.camera, controls = U.controls;
  const scene = new T.Scene();
  const TILE = 10, N = 36, HALF = (N * TILE) / 2, BLOCK = 6; // 360 m × 360 m, her 6 karede bir yol
  const PLANETS = { "Dünya": 9.81, "Ay": 1.62, "Mars": 3.71, "Venüs": 8.87, "Jüpiter": 24.79, "Satürn": 10.44, "Sıfır": 0 };

  const S = { time: 9 * 3600, speed: 60, g: 9.81, planet: "Dünya", weather: "açık", wind: 3, traffic: 60, tool: "bak", seed: 7, built: false };
  let rng = mulberry(S.seed);
  function mulberry(a) { return () => { a |= 0; a = (a + 0x6d2b79f5) | 0; let t = Math.imul(a ^ (a >>> 15), 1 | a); t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t; return ((t ^ (t >>> 14)) >>> 0) / 4294967296; }; }

  // ---------- ışık ve gökyüzü ----------
  const hemi = new T.HemisphereLight(0xbfd8ff, 0x3a3a2a, 0.6); scene.add(hemi);
  const sun = new T.DirectionalLight(0xffffff, 1); scene.add(sun); scene.add(sun.target);
  const moonL = new T.DirectionalLight(0x8899cc, 0.0); moonL.position.set(-200, 200, -100); scene.add(moonL);
  scene.fog = new T.Fog(0x87b5e0, 300, 1400);
  const skyCol = new T.Color();
  const sunBall = new T.Mesh(new T.SphereGeometry(18, 16, 12), new T.MeshBasicMaterial({ color: 0xfff1c0, fog: false })); scene.add(sunBall);
  const starPts = new T.Points(new T.BufferGeometry().setAttribute("position", new T.Float32BufferAttribute(Array.from({ length: 4500 }, () => { const v = new T.Vector3(Math.random() - 0.5, Math.random() * 0.9 + 0.05, Math.random() - 0.5).normalize().multiplyScalar(1500); return [v.x, v.y, v.z]; }).flat(), 3)), new T.PointsMaterial({ color: 0xffffff, size: 2, sizeAttenuation: false, transparent: true, opacity: 0, fog: false }));
  scene.add(starPts);

  // ---------- zemin ----------
  const ground = new T.Mesh(new T.PlaneGeometry(N * TILE + 400, N * TILE + 400), new T.MeshLambertMaterial({ color: 0x3d5a35 }));
  ground.rotation.x = -Math.PI / 2; ground.position.y = -0.05; scene.add(ground);
  let root = new T.Group(); scene.add(root);
  const isRoad = (i) => i % BLOCK === 0;
  const tileCenter = (i) => -HALF + i * TILE + TILE / 2;
  const roadLines = []; for (let i = 0; i <= N; i += BLOCK) roadLines.push(-HALF + i * TILE + TILE / 2);

  // pencere dokusu (gece yanan pencereler)
  function facadeTex(lit) {
    const c = document.createElement("canvas"); c.width = 64; c.height = 128; const g = c.getContext("2d");
    g.fillStyle = lit ? "#000" : "#9aa7b4"; g.fillRect(0, 0, 64, 128);
    for (let y = 4; y < 128; y += 16) for (let x = 4; x < 64; x += 15) {
      if (lit) { g.fillStyle = Math.random() < 0.45 ? `hsl(${40 + Math.random() * 15},90%,${55 + Math.random() * 25}%)` : "#000"; }
      else g.fillStyle = "#2b3a4a";
      g.fillRect(x, y, 9, 10);
    }
    const t = new T.CanvasTexture(c); t.wrapS = t.wrapT = T.RepeatWrapping; return t;
  }
  const dayTex = facadeTex(false);
  const bMats = [0xffffff, 0xcfe0f0, 0xf0e2cc, 0xb8c4cc, 0xd8d0e8].map((tint) => new T.MeshLambertMaterial({ map: dayTex, color: tint, emissiveMap: facadeTex(true), emissive: new T.Color(0xffd27a), emissiveIntensity: 0 }));
  const bMat = bMats[0];
  const roofMat = new T.MeshLambertMaterial({ color: 0x55606b });
  const houseMat = new T.MeshLambertMaterial({ color: 0xd9c7a7, emissive: new T.Color(0xffc870), emissiveIntensity: 0 });
  const redRoof = new T.MeshLambertMaterial({ color: 0xa2412e });
  const roadMat = new T.MeshLambertMaterial({ color: 0x2b2e33 });
  const parkMat = new T.MeshLambertMaterial({ color: 0x4f8a3c });
  const treeMat = new T.MeshLambertMaterial({ color: 0x2f6b2a });
  const trunkMat = new T.MeshLambertMaterial({ color: 0x5b3b22 });

  function boxUV(w, h, d) { // pencereler bina boyuna göre tekrar etsin
    const g = new T.BoxGeometry(w, h, d); const uv = g.attributes.uv;
    const faces = [[d, h], [d, h], [w, d], [w, d], [w, h], [w, h]];
    for (let f = 0; f < 6; f++) for (let k = 0; k < 4; k++) { const i = f * 4 + k; uv.setXY(i, uv.getX(i) * faces[f][0] / 8, uv.getY(i) * faces[f][1] / 25.6); }
    return g;
  }

  const buildings = []; // {mesh, i, j, kind, floors, box}
  const grid = {}; // "i,j" → yapı
  function addStructure(kind, i, j, h) {
    const key = i + "," + j; if (grid[key] || isRoad(i) || isRoad(j) || i < 0 || j < 0 || i >= N || j >= N) return null;
    const x = tileCenter(i), z = tileCenter(j); let obj, floors = 0;
    if (kind === "bina") {
      const H = h || Math.round(10 + Math.pow(rng(), 4) * 130 + Math.max(0, 1 - Math.hypot(x, z) / HALF) * 35 * rng());
      floors = Math.max(3, Math.round(H / 3.2));
      obj = new T.Mesh(boxUV(8, floors * 3.2, 8), bMats[Math.floor(rng() * bMats.length)]); obj.position.set(x, floors * 1.6, z);
      const roof = new T.Mesh(new T.BoxGeometry(8.4, 0.6, 8.4), roofMat); roof.position.y = floors * 1.6 + 0.3; obj.add(roof);
    } else if (kind === "ev") {
      floors = 2; obj = new T.Group();
      const body = new T.Mesh(new T.BoxGeometry(7, 5, 6), houseMat); body.position.y = 2.5; obj.add(body);
      const roof = new T.Mesh(new T.ConeGeometry(5.6, 3, 4), redRoof); roof.position.y = 6.5; roof.rotation.y = Math.PI / 4; obj.add(roof);
      obj.position.set(x, 0, z);
    } else if (kind === "ağaç" || kind === "park") {
      obj = new T.Group();
      const grass = new T.Mesh(new T.BoxGeometry(TILE, 0.15, TILE), parkMat); grass.position.y = 0.08; obj.add(grass);
      const nT = kind === "park" ? 3 : 1;
      for (let k = 0; k < nT; k++) {
        const tr = new T.Mesh(new T.CylinderGeometry(0.25, 0.35, 3, 6), trunkMat); const leaf = new T.Mesh(new T.ConeGeometry(2 + rng(), 5 + rng() * 2, 7), treeMat);
        const ox = nT > 1 ? (rng() - 0.5) * 6 : 0, oz = nT > 1 ? (rng() - 0.5) * 6 : 0;
        tr.position.set(ox, 1.5, oz); leaf.position.set(ox, 5.5, oz); obj.add(tr, leaf);
      }
      obj.position.set(x, 0, z);
    } else return null;
    obj.userData = { kind, i, j, floors }; root.add(obj);
    const box = new T.Box3().setFromObject(obj);
    const b = { mesh: obj, i, j, kind, floors, box }; buildings.push(b); grid[key] = b; return b;
  }
  function removeAt(i, j) {
    const key = i + "," + j, b = grid[key]; if (!b) return false;
    root.remove(b.mesh); U.disposeTree(b.mesh); buildings.splice(buildings.indexOf(b), 1); delete grid[key]; return true;
  }

  // ---------- yollar, sokak lambaları, trafik ışıkları ----------
  let lampPts, lightPts, lightCols;
  function buildRoads() {
    for (const p of roadLines) {
      const a = new T.Mesh(new T.PlaneGeometry(TILE, N * TILE), roadMat); a.rotation.x = -Math.PI / 2; a.position.set(p, 0.02, 0); root.add(a);
      const b = new T.Mesh(new T.PlaneGeometry(N * TILE, TILE), roadMat); b.rotation.x = -Math.PI / 2; b.position.set(0, 0.021, p); root.add(b);
      // şerit çizgisi
      const dash = new T.LineSegments(new T.BufferGeometry().setFromPoints(Array.from({ length: N * 2 }, (_, k) => new T.Vector3(p, 0.05, -HALF + k * 5 + (k % 2) * 0))), new T.LineDashedMaterial({ color: 0xe8e2b0, dashSize: 3, gapSize: 3 }));
      dash.computeLineDistances(); root.add(dash);
      const dash2 = new T.LineSegments(new T.BufferGeometry().setFromPoints(Array.from({ length: N * 2 }, (_, k) => new T.Vector3(-HALF + k * 5, 0.05, p))), new T.LineDashedMaterial({ color: 0xe8e2b0, dashSize: 3, gapSize: 3 }));
      dash2.computeLineDistances(); root.add(dash2);
    }
    const lamps = [];
    for (const p of roadLines) for (let s = -HALF; s <= HALF; s += 20) { lamps.push(p + 5.5, 7, s, s, 7, p + 5.5); }
    lampPts = new T.Points(new T.BufferGeometry().setAttribute("position", new T.Float32BufferAttribute(lamps, 3)), new T.PointsMaterial({ color: 0xffd38a, size: 2.2, transparent: true, opacity: 0, depthWrite: false, blending: T.AdditiveBlending }));
    root.add(lampPts);
    const lp = []; lightCols = [];
    for (const x of roadLines) for (const z of roadLines) { lp.push(x + 5.5, 5, z + 5.5, x - 5.5, 5, z - 5.5); lightCols.push(0, 1, 0, 1, 0, 0); }
    lightPts = new T.Points(new T.BufferGeometry().setAttribute("position", new T.Float32BufferAttribute(lp, 3)).setAttribute("color", new T.Float32BufferAttribute(lightCols, 3)), new T.PointsMaterial({ size: 2.4, vertexColors: true }));
    root.add(lightPts);
  }
  const LIGHT_CYCLE = 24; // sn: 10 yeşil + 2 sarı her yön
  function lightState(axis, t) { // axis 'x' (doğu-batı) ya da 'z' (kuzey-güney)
    const ph = t % LIGHT_CYCLE, nsGreen = ph < 10, nsYellow = ph >= 10 && ph < 12, ewGreen = ph >= 12 && ph < 22;
    if (axis === "z") return nsGreen ? "yeşil" : nsYellow ? "sarı" : "kırmızı";
    return ewGreen ? "yeşil" : ph >= 22 ? "sarı" : "kırmızı";
  }

  // ---------- araçlar ----------
  const cars = []; const carGeo = new T.BoxGeometry(2, 1.5, 4.4); const cabGeo = new T.BoxGeometry(1.8, 0.9, 2.2);
  const carCols = [0xd8342c, 0x2c6fd8, 0xeeeeee, 0x222222, 0xf2c230, 0x3aa655, 0x8b8f96];
  const headMat = new T.MeshBasicMaterial({ color: 0xfff3c0 });
  function spawnCar() {
    const axis = rng() < 0.5 ? "x" : "z", dir = rng() < 0.5 ? 1 : -1, line = roadLines[Math.floor(rng() * roadLines.length)];
    const m = new T.Group(); const body = new T.Mesh(carGeo, new T.MeshLambertMaterial({ color: carCols[Math.floor(rng() * carCols.length)] })); body.position.y = 1; m.add(body);
    const cab = new T.Mesh(cabGeo, new T.MeshLambertMaterial({ color: 0x1b2633 })); cab.position.set(0, 2.1, -0.3); m.add(cab);
    const hl = new T.Mesh(new T.BoxGeometry(1.6, 0.3, 0.1), headMat); hl.position.set(0, 1.1, 2.25); m.add(hl);
    const c = { m, axis, dir, line, s: (rng() - 0.5) * N * TILE, v: 0, vmax: 8 + rng() * 6 }; // 30–50 km/s
    root.add(m); cars.push(c); placeCar(c); return c;
  }
  function placeCar(c) {
    const lane = 2.5 * c.dir; // sağdan gidiş
    if (c.axis === "z") { c.m.position.set(c.line - lane, 0, c.s); c.m.rotation.y = c.dir > 0 ? 0 : Math.PI; }
    else { c.m.position.set(c.s, 0, c.line + lane); c.m.rotation.y = c.dir > 0 ? Math.PI / 2 : -Math.PI / 2; }
  }
  function setTraffic(n) {
    n = Math.max(0, Math.min(250, Math.round(n))); S.traffic = n;
    while (cars.length < n) spawnCar();
    while (cars.length > n) { const c = cars.pop(); root.remove(c.m); }
  }
  function updateCars(dt, tsec) {
    const buckets = {};
    for (const c of cars) (buckets[c.axis + c.line + c.dir] = buckets[c.axis + c.line + c.dir] || []).push(c);
    for (const c of cars) {
      // önündeki araç
      let gap = 1e9;
      for (const o of buckets[c.axis + c.line + c.dir]) { if (o === c) continue; const d = (o.s - c.s) * c.dir; if (d > 0 && d < gap) gap = d; }
      // sonraki kavşak
      let stop = 1e9;
      for (const p of roadLines) { const d = (p - c.s) * c.dir - 7; if (d > -1 && d < stop) { const st = lightState(c.axis, tsec); if (st !== "yeşil" && !(st === "sarı" && d < 3)) stop = Math.max(0, d); } }
      const free = Math.min(gap - 7, stop);
      const target = free < 1 ? 0 : Math.min(c.vmax, Math.sqrt(2 * 4 * Math.max(0, free))); // 4 m/s² ile güvenli fren mesafesi
      c.v += Math.max(-8, Math.min(2.5, (target - c.v) * 2)) * dt;
      if (c.v < 0) c.v = 0;
      const prev = c.s; c.s += c.v * dt * c.dir;
      // kavşakta dönüş (yeşilde, %20)
      for (const p of roadLines) {
        if ((prev - p) * (c.s - p) < 0 && rng() < 0.2) {
          const cross = c.axis === "z" ? c.line : c.line; c.axis = c.axis === "z" ? "x" : "z"; c.line = p; c.s = cross; c.dir = rng() < 0.5 ? 1 : -1; break;
        }
      }
      if (c.s > HALF) c.s -= N * TILE; if (c.s < -HALF) c.s += N * TILE;
      placeCar(c);
    }
    // ışık renkleri
    const col = lightPts.geometry.attributes.color; let k = 0;
    const cz = { "yeşil": [0, 1, 0.2], "sarı": [1, 0.8, 0], "kırmızı": [1, 0.05, 0.05] };
    for (let a = 0; a < roadLines.length; a++) for (let b = 0; b < roadLines.length; b++) { col.setXYZ(k++, ...cz[lightState("z", tsec)]); col.setXYZ(k++, ...cz[lightState("x", tsec)]); }
    col.needsUpdate = true;
  }

  // ---------- fizik: toplar ----------
  const balls = []; const ballGeo = new T.SphereGeometry(1, 20, 14);
  let dropLog = null;
  function dropBall(x, z, h = 60, r = 1) {
    const m = new T.Mesh(ballGeo, new T.MeshPhongMaterial({ color: new T.Color().setHSL(rng(), 0.7, 0.55), shininess: 80 })); m.scale.setScalar(r);
    m.position.set(x, h + r, z); root.add(m); // alt yüzey tam h metrede
    const b = { m, v: new T.Vector3(0, 0, 0), r, t0: 0, h0: h, landed: false, life: 0 }; balls.push(b);
    if (balls.length > 60) { const o = balls.shift(); root.remove(o.m); }
    dropLog = { h, g: S.g, teori: S.g > 0 ? Math.sqrt(2 * h / S.g) : Infinity, ölçülen: null, b };
    return b;
  }
  function updateBalls(dt) {
    const sub = 1, h = dt / sub;
    for (let s = 0; s < sub; s++) for (const b of balls) {
      const windF = new T.Vector3(S.wind * 0.02, 0, 0); // küçük hava sürüklemesi
      b.v.y -= S.g * h; b.v.addScaledVector(windF, h); b.m.position.addScaledVector(b.v, h); b.life += h;
      if (b.m.position.y < b.r) {
        if (!b.landed && dropLog && dropLog.b === b) { dropLog.ölçülen = b.life - (b.m.position.y - b.r) / Math.min(-1e-6, b.v.y); b.landed = true; }
        b.m.position.y = b.r; b.v.y = -b.v.y * 0.6; b.v.x *= 0.98; b.v.z *= 0.98; if (Math.abs(b.v.y) < 0.4) b.v.y = 0;
      }
      const bi = Math.floor((b.m.position.x + HALF) / TILE), bj = Math.floor((b.m.position.z + HALF) / TILE);
      for (const bd of [grid[bi + "," + bj]].filter(Boolean)) { // bulunduğu karedeki yapıyla çarpışma
        if (!bd.box.containsPoint(b.m.position)) continue;
        const p = b.m.position, bx = bd.box; const dx = Math.min(p.x - bx.min.x, bx.max.x - p.x), dz = Math.min(p.z - bx.min.z, bx.max.z - p.z), dy = bx.max.y - p.y;
        if (dy < dx && dy < dz) { if (!b.landed && dropLog && dropLog.b === b) { dropLog.çatı = Math.round(bx.max.y); dropLog.ölçülen = b.life; b.landed = true; } p.y = bx.max.y + b.r; b.v.y = Math.abs(b.v.y) * 0.6; }
        else if (dx < dz) { p.x = p.x - bx.min.x < bx.max.x - p.x ? bx.min.x - b.r : bx.max.x + b.r; b.v.x *= -0.6; }
        else { p.z = p.z - bx.min.z < bx.max.z - p.z ? bx.min.z - b.r : bx.max.z + b.r; b.v.z *= -0.6; }
      }
    }
    for (let i = 0; i < balls.length; i++) for (let j = i + 1; j < balls.length; j++) { // top-top esnek çarpışma (eşit kütle)
      const a = balls[i], c = balls[j], d = a.m.position.clone().sub(c.m.position), L = d.length(), R = a.r + c.r;
      if (L > 0 && L < R) { const n = d.divideScalar(L), rel = a.v.clone().sub(c.v).dot(n); a.m.position.addScaledVector(n, (R - L) / 2); c.m.position.addScaledVector(n, -(R - L) / 2); if (rel < 0) { a.v.addScaledVector(n, -rel * 0.9); c.v.addScaledVector(n, rel * 0.9); } }
    }
  }

  // ---------- parçacıklar: ateş, duman, fıskiye, yağmur/kar ----------
  function particleSystem(max, opts) {
    const pos = new Float32Array(max * 3), col = new Float32Array(max * 3);
    const geo = new T.BufferGeometry(); geo.setAttribute("position", new T.BufferAttribute(pos, 3)); geo.setAttribute("color", new T.BufferAttribute(col, 3));
    const pts = new T.Points(geo, new T.PointsMaterial({ size: opts.size, vertexColors: true, transparent: true, opacity: opts.opacity || 1, depthWrite: false, blending: opts.additive ? T.AdditiveBlending : T.NormalBlending, map: dotTex() }));
    pts.frustumCulled = false; root.add(pts);
    return { pts, pos, col, p: [], max };
  }
  let _dot;
  function dotTex() {
    if (_dot) return _dot; const c = document.createElement("canvas"); c.width = c.height = 64; const g = c.getContext("2d");
    const gr = g.createRadialGradient(32, 32, 0, 32, 32, 32); gr.addColorStop(0, "rgba(255,255,255,1)"); gr.addColorStop(1, "rgba(255,255,255,0)"); g.fillStyle = gr; g.fillRect(0, 0, 64, 64);
    return (_dot = new T.CanvasTexture(c));
  }
  let fireSys, smokeSys, waterSys, rainSys; const fires = [], fountains = [];
  function makeParticles() {
    fireSys = particleSystem(3000, { size: 2.2, additive: true });
    smokeSys = particleSystem(2500, { size: 5, opacity: 0.45 });
    waterSys = particleSystem(2500, { size: 0.9, additive: true });
    rainSys = particleSystem(6000, { size: 0.5, opacity: 0.7 });
  }
  function emit(sys, n, f) { for (let k = 0; k < n && sys.p.length < sys.max; k++) sys.p.push(f()); }
  function flush(sys, colorFn) {
    const P = sys.p; let k = 0;
    for (let i = 0; i < P.length; i++) { const q = P[i]; sys.pos.set([q.x, q.y, q.z], k * 3); sys.col.set(colorFn(q), k * 3); k++; }
    for (let i = k; i < sys.max; i++) sys.pos[i * 3 + 1] = -9999;
    sys.pts.geometry.attributes.position.needsUpdate = true; sys.pts.geometry.attributes.color.needsUpdate = true;
    sys.pts.geometry.setDrawRange(0, Math.max(1, k));
  }
  function updateParticles(dt) {
    const wx = S.wind;
    for (const f of fires) {
      emit(fireSys, Math.round(220 * dt * f.size), () => ({ x: f.x + (Math.random() - 0.5) * 3 * f.size, y: 0.3 + f.y, z: f.z + (Math.random() - 0.5) * 3 * f.size, vx: (Math.random() - 0.5) * 1.2, vy: 4 + Math.random() * 4, vz: (Math.random() - 0.5) * 1.2, t: 0, L: 0.6 + Math.random() * 0.7 }));
      emit(smokeSys, Math.round(40 * dt * f.size), () => ({ x: f.x + (Math.random() - 0.5) * 2, y: f.y + 5 * f.size, z: f.z + (Math.random() - 0.5) * 2, vx: 0, vy: 2 + Math.random() * 1.5, vz: 0, t: 0, L: 4 + Math.random() * 3 }));
    }
    for (const w of fountains) emit(waterSys, Math.round(500 * dt), () => { const a = Math.random() * Math.PI * 2, s = 1.2 + Math.random() * 1.6; return { x: w.x, y: w.y + 1.2, z: w.z, vx: Math.cos(a) * s, vy: 9 + Math.random() * 2.5, vz: Math.sin(a) * s, t: 0, L: 9 }; });
    const step = (sys, fn) => { const P = sys.p; for (let i = P.length - 1; i >= 0; i--) { const q = P[i]; q.t += dt; fn(q); q.x += q.vx * dt; q.y += q.vy * dt; q.z += q.vz * dt; if (q.t > q.L || q.y < -0.2) { P[i] = P[P.length - 1]; P.pop(); } } };
    step(fireSys, (q) => { q.vy += 3 * dt; q.vx += wx * 0.4 * dt; }); // kaldırma kuvveti
    step(smokeSys, (q) => { q.vx += (wx * 0.6 - q.vx) * 0.5 * dt; q.vy *= 1 - 0.15 * dt; });
    step(waterSys, (q) => { q.vy -= S.g * dt; q.vx += wx * 0.05 * dt; }); // su gerçek yerçekimiyle düşer
    flush(fireSys, (q) => { const k = q.t / q.L; return [1, Math.max(0, 0.85 - k * 1.1), Math.max(0, 0.35 - k)]; });
    flush(smokeSys, (q) => { const k = 0.35 - (q.t / q.L) * 0.25; return [k, k, k * 1.05]; });
    flush(waterSys, () => [0.45, 0.7, 1]);
    // yağmur / kar
    const want = S.weather === "yağmur" ? 6000 : S.weather === "kar" ? 4000 : S.weather === "fırtına" ? 6000 : 0;
    const snow = S.weather === "kar";
    emit(rainSys, Math.min(want - rainSys.p.length, want ? 3000 * dt * 4 : 0), () => ({ x: camera.position.x + (Math.random() - 0.5) * 400, y: 120 + Math.random() * 40, z: camera.position.z + (Math.random() - 0.5) * 400, vx: wx * (snow ? 0.3 : 0.4), vy: snow ? -2 - Math.random() : -38, vz: 0, t: 0, L: 60 }));
    if (!want) rainSys.p.length = 0;
    step(rainSys, (q) => { if (snow) { q.vx = wx * 0.3 + Math.sin(q.t * 2 + q.x) * 0.6; } });
    flush(rainSys, () => (snow ? [1, 1, 1] : [0.6, 0.7, 0.85]));
    rainSys.pts.material.size = snow ? 1.4 : 0.5;
  }

  // ---------- kumaş (Verlet bayrak) ----------
  let cloth;
  function makeCloth(x, z) {
    const W = 6, H = 4, nx = 24, ny = 16, pole = new T.Mesh(new T.CylinderGeometry(0.12, 0.15, 14, 8), new T.MeshLambertMaterial({ color: 0xcccccc }));
    pole.position.set(x, 7, z); root.add(pole);
    const geo = new T.PlaneGeometry(W, H, nx - 1, ny - 1);
    const tex = (() => { const c = document.createElement("canvas"); c.width = 128; c.height = 86; const g = c.getContext("2d"); g.fillStyle = "#c8102e"; g.fillRect(0, 0, 128, 86); g.fillStyle = "#fff"; g.beginPath(); g.arc(50, 43, 21, 0, Math.PI * 2); g.fill(); g.fillStyle = "#c8102e"; g.beginPath(); g.arc(56, 43, 17, 0, Math.PI * 2); g.fill(); g.fillStyle = "#fff"; g.beginPath(); for (let i = 0; i < 10; i++) { const a = -Math.PI / 2 + i * Math.PI / 5, r = i % 2 ? 4.2 : 10; g.lineTo(80 + r * Math.cos(a), 43 + r * Math.sin(a)); } g.fill(); return new T.CanvasTexture(c); })();
    const mesh = new T.Mesh(geo, new T.MeshLambertMaterial({ map: tex, side: T.DoubleSide })); mesh.frustumCulled = false; root.add(mesh);
    const P = [], prev = [], rest = W / (nx - 1);
    for (let j = 0; j < ny; j++) for (let i = 0; i < nx; i++) { const p = new T.Vector3(x + i * rest, 13.5 - j * rest, z); P.push(p); prev.push(p.clone()); }
    const C = [];
    for (let j = 0; j < ny; j++) for (let i = 0; i < nx; i++) { const k = j * nx + i; if (i < nx - 1) C.push([k, k + 1, rest]); if (j < ny - 1) C.push([k, k + nx, rest]); if (i < nx - 2) C.push([k, k + 2, rest * 2]); }
    cloth = { mesh, P, prev, C, nx, ny, pin: (k) => k % nx === 0, x, z, t: 0 };
  }
  function updateCloth(dt) {
    if (!cloth) return; dt = Math.min(dt, 1 / 30); cloth.t += dt;
    const { P, prev, C, nx } = cloth, g = S.g, damp = 0.985;
    for (let k = 0; k < P.length; k++) {
      if (cloth.pin(k)) continue;
      const p = P[k], v = p.clone().sub(prev[k]).multiplyScalar(damp); prev[k].copy(p);
      const gust = S.wind * (0.8 + 0.4 * Math.sin(cloth.t * 1.7 + (k % nx) * 0.3) + 0.2 * Math.sin(cloth.t * 5.3 + k));
      p.add(v).add(new T.Vector3(gust * 0.9, -g, Math.sin(cloth.t * 3 + k * 0.1) * S.wind * 0.15).multiplyScalar(dt * dt));
      if (p.y < 0.1) p.y = 0.1;
    }
    for (let it = 0; it < 4; it++) for (const [a, b, r] of C) {
      const pa = P[a], pb = P[b], d = pb.clone().sub(pa), L = d.length() || 1e-6, diff = (L - r) / L;
      const pa_ = cloth.pin(a), pb_ = cloth.pin(b);
      if (pa_ && pb_) continue;
      if (pa_) pb.addScaledVector(d, -diff); else if (pb_) pa.addScaledVector(d, diff); else { pa.addScaledVector(d, diff / 2); pb.addScaledVector(d, -diff / 2); }
    }
  }
  function renderCloth() {
    if (!cloth) return; const P = cloth.P, pos = cloth.mesh.geometry.attributes.position;
    for (let k = 0; k < P.length; k++) pos.setXYZ(k, P[k].x, P[k].y, P[k].z);
    pos.needsUpdate = true; cloth.mesh.geometry.computeVertexNormals();
  }

  // ---------- şehir kurulumu ----------
  function build(seed) {
    scene.remove(root); U.disposeTree(root); root = new T.Group(); scene.add(root);
    buildings.length = 0; cars.length = 0; balls.length = 0; fires.length = 0; fountains.length = 0; cloth = null;
    for (const k in grid) delete grid[k];
    S.seed = seed || S.seed; rng = mulberry(S.seed);
    buildRoads(); makeParticles();
    const cx = Math.floor(N / 2), park = (i, j) => Math.abs(i - cx) < 3 && Math.abs(j - cx) < 3;
    for (let i = 0; i < N; i++) for (let j = 0; j < N; j++) {
      if (isRoad(i) || isRoad(j)) continue;
      const d = Math.hypot(i - cx, j - cx) / (N / 2);
      if (park(i, j)) { addStructure(rng() < 0.6 ? "park" : "ağaç", i, j); continue; }
      const r = rng();
      if (d < 0.45) addStructure(r < 0.82 ? "bina" : r < 0.92 ? "park" : "ağaç", i, j);
      else if (d < 0.8) addStructure(r < 0.45 ? "bina" : r < 0.85 ? "ev" : "ağaç", i, j);
      else addStructure(r < 0.55 ? "ev" : r < 0.8 ? "ağaç" : "park", i, j);
    }
    // merkez park: fıskiye + bayrak
    const pc = tileCenter(cx);
    const basin = new T.Mesh(new T.CylinderGeometry(6, 6.5, 1, 32, 1, true), new T.MeshLambertMaterial({ color: 0xbbbbbb, side: T.DoubleSide })); basin.position.set(pc - 5, 0.5, pc - 5); root.add(basin);
    const water = new T.Mesh(new T.CircleGeometry(6, 32), new T.MeshPhongMaterial({ color: 0x2e7fd0, shininess: 100, transparent: true, opacity: 0.85 })); water.rotation.x = -Math.PI / 2; water.position.set(pc - 5, 0.8, pc - 5); root.add(water);
    fountains.push({ x: pc - 5, y: 0.8, z: pc - 5 });
    makeCloth(pc + 8, pc + 6);
    loadEdits();
    setTraffic(S.traffic); S.built = true;
  }

  // ---------- düzenlemeleri sakla (tarayıcıya) ----------
  let edits = [];
  function saveEdits() { try { localStorage.setItem("jv_city_" + S.seed, JSON.stringify(edits.slice(-500))); } catch (e) {} }
  function loadEdits() {
    try { edits = JSON.parse(localStorage.getItem("jv_city_" + S.seed) || "[]"); } catch (e) { edits = []; }
    for (const e of edits) { if (e.op === "sil") removeAt(e.i, e.j); else { removeAt(e.i, e.j); addStructure(e.op, e.i, e.j, e.h); } }
  }

  // ---------- zaman, gece-gündüz ----------
  let nightK = 0, trafficT = 0, physAcc = 0, lastReal = performance.now();
  const PSTEP = 1 / 120;
  function realDt() { const n = performance.now(), d = (n - lastReal) / 1000; lastReal = n; return d; }
  function updateSky() {
    const h = (S.time / 3600) % 24, ang = (h - 6) / 12 * Math.PI, elev = Math.sin(ang);
    sun.position.set(Math.cos(ang) * 600, Math.max(-200, elev * 600), 220); sunBall.position.copy(sun.position).setLength(1300);
    sunBall.visible = elev > -0.05;
    const day = Math.max(0, Math.min(1, (elev + 0.08) / 0.35)); nightK = 1 - day;
    const dusk = Math.max(0, 1 - Math.abs(elev) / 0.25) * (elev > -0.2 ? 1 : 0);
    skyCol.setRGB(0.02, 0.04, 0.09).lerp(new T.Color(0x87b5e0), day).lerp(new T.Color(0xf08a4b), dusk * 0.55);
    if (S.weather === "sis") skyCol.lerp(new T.Color(0xaab3bb), 0.7 * day + 0.2);
    if (S.weather === "yağmur" || S.weather === "fırtına") skyCol.multiplyScalar(0.6);
    scene.background = skyCol; scene.fog.color.copy(skyCol);
    scene.fog.near = S.weather === "sis" ? 20 : 300; scene.fog.far = S.weather === "sis" ? 260 : S.weather === "açık" ? 1600 : 900;
    sun.intensity = day * (S.weather === "açık" ? 1.05 : 0.5); sun.color.setRGB(1, 0.85 + 0.15 * (1 - dusk), 0.7 + 0.3 * (1 - dusk));
    hemi.intensity = 0.15 + 0.5 * day; moonL.intensity = 0.25 * nightK;
    starPts.material.opacity = S.weather === "açık" ? nightK : nightK * 0.2;
    bMats.forEach((m) => (m.emissiveIntensity = nightK * 1.3)); houseMat.emissiveIntensity = nightK * 0.25;
    if (lampPts) lampPts.material.opacity = nightK; headMat.color.setRGB(1, 0.95, 0.75).multiplyScalar(0.4 + nightK);
  }

  // ---------- arayüz ----------
  const fmtT = () => { const h = Math.floor((S.time / 3600) % 24), m = Math.floor((S.time / 60) % 60); return `${String(h).padStart(2, "0")}:${String(m).padStart(2, "0")}`; };
  let bar;
  function buildBar() {
    if (bar) return; bar = document.createElement("div"); bar.id = "city-bar"; bar.className = "hidden";
    const tools = [["bak", "👁 BAK"], ["bina", "🏢 BİNA"], ["ev", "🏠 EV"], ["ağaç", "🌳 AĞAÇ"], ["park", "🟩 PARK"], ["sil", "✖ SİL"], ["top", "⚪ TOP BIRAK"], ["ateş", "🔥 ATEŞ"]];
    bar.innerHTML = `<b id="cb-time">09:00</b>
      ${[0, 1, 60, 600, 3600].map((s) => `<button class="mini" data-spd="${s}">${s === 0 ? "⏸" : s + "×"}</button>`).join("")}
      <select id="cb-weather">${["açık", "yağmur", "kar", "sis", "fırtına"].map((w) => `<option>${w}</option>`).join("")}</select>
      <select id="cb-g">${Object.keys(PLANETS).map((p) => `<option>${p}</option>`).join("")}</select>
      <label>rüzgâr <input id="cb-wind" type="range" min="0" max="25" value="3"></label>
      <label>trafik <input id="cb-traffic" type="range" min="0" max="250" value="60"></label>
      <span class="cb-sep"></span>${tools.map(([k, t]) => `<button class="mini" data-tool="${k}">${t}</button>`).join("")}
      <button class="mini" id="cb-new">🎲 YENİ ŞEHİR</button><button class="mini" id="cb-stl">⬇ STL</button>`;
    document.body.append(bar);
    bar.addEventListener("click", (e) => {
      const b = e.target.closest("button"); if (!b) return;
      if (b.dataset.spd != null) cmd({ action: "speed", value: +b.dataset.spd });
      else if (b.dataset.tool) cmd({ action: "tool", value: b.dataset.tool });
      else if (b.id === "cb-new") cmd({ action: "new" });
      else if (b.id === "cb-stl") exportSTL();
    });
    bar.querySelector("#cb-weather").onchange = (e) => cmd({ action: "weather", value: e.target.value });
    bar.querySelector("#cb-g").onchange = (e) => cmd({ action: "gravity", value: e.target.value });
    bar.querySelector("#cb-wind").oninput = (e) => (S.wind = +e.target.value);
    bar.querySelector("#cb-traffic").onchange = (e) => setTraffic(+e.target.value);
  }
  function syncBar() {
    if (!bar) return;
    bar.querySelectorAll("[data-spd]").forEach((b) => b.classList.toggle("on", +b.dataset.spd === S.speed));
    bar.querySelectorAll("[data-tool]").forEach((b) => b.classList.toggle("on", b.dataset.tool === S.tool));
    bar.querySelector("#cb-weather").value = S.weather; bar.querySelector("#cb-g").value = S.planet in PLANETS ? S.planet : "Dünya";
    bar.querySelector("#cb-wind").value = S.wind; bar.querySelector("#cb-traffic").value = S.traffic;
  }
  function stats() {
    const nb = buildings.filter((b) => b.kind === "bina"), nh = buildings.filter((b) => b.kind === "ev");
    const pop = nb.reduce((s, b) => s + b.floors * 4 * 2.6, 0) + nh.length * 4;
    const tallest = nb.reduce((m, b) => Math.max(m, b.floors * 3.2), 0);
    const moving = cars.filter((c) => c.v > 0.5), avg = moving.length ? moving.reduce((s, c) => s + c.v, 0) / moving.length * 3.6 : 0;
    return { saat: fmtT(), hız: S.speed + "×", hava: S.weather, rüzgâr_ms: S.wind, yerçekimi: `${S.g} m/s² (${S.planet})`, bina: nb.length, ev: nh.length,
      yeşil_alan: buildings.filter((b) => b.kind === "park" || b.kind === "ağaç").length, nüfus_tahmini: Math.round(pop), en_yüksek_m: Math.round(tallest),
      araç: cars.length, duran_araç: cars.length - moving.length, ort_hız_kmh: Math.round(avg), top: balls.length, ateş: fires.length };
  }
  let panelT = 0;
  function renderPanel() {
    const s = stats();
    let drop = "";
    if (dropLog) drop = `<div class="wp-title" style="font-size:12px;margin-top:8px">SERBEST DÜŞME DENEYİ</div><div class="wp-grid"><i>Yükseklik</i><b>${dropLog.h} m</b><i>g</i><b>${dropLog.g} m/s²</b><i>Teori √(2h/g)</i><b>${isFinite(dropLog.teori) ? dropLog.teori.toFixed(2) + " s" : "düşmez"}</b><i>Ölçülen</i><b>${dropLog.ölçülen ? dropLog.ölçülen.toFixed(2) + " s" + (dropLog.çatı ? ` (${dropLog.çatı} m çatıya düştü)` : "") : "düşüyor…"}</b><i>Çarpma hızı</i><b>${(Math.sqrt(2 * dropLog.g * dropLog.h) * 3.6).toFixed(0)} km/s</b></div>`;
    U.panel(`<div class="wp-title">SANAL ŞEHİR</div><div class="wp-grid">${[["Saat", s.saat], ["Zaman ölçeği", s.hız], ["Hava", s.hava + ", rüzgâr " + s.rüzgâr_ms + " m/s"], ["Yerçekimi", s.yerçekimi], ["Bina / ev", s.bina + " / " + s.ev], ["Yeşil alan", s.yeşil_alan + " kare"], ["Nüfus (tahmini)", U.fmt(s.nüfus_tahmini)], ["En yüksek", s.en_yüksek_m + " m"], ["Araç", s.araç + " (" + s.duran_araç + " duruyor)"], ["Ortalama hız", s.ort_hız_kmh + " km/s"]].map(([a, b]) => `<i>${a}</i><b>${b}</b>`).join("")}</div>${drop}
      <p class="note">Araç: ${S.tool.toUpperCase()} — zemine tıkla. Trafik ışıkları 24 sn döngüyle çalışır; araçlar fren mesafesine göre yavaşlar. Fıskiye suyu, toplar ve bayrak seçilen yerçekimine göre hareket eder.</p>`);
  }

  function exportSTL() {
    if (!T.STLExporter) return JV.toast && JV.toast("STL dışa aktarıcı yüklenemedi.");
    const g = new T.Group(); buildings.forEach((b) => g.add(b.mesh.clone()));
    const s = new T.STLExporter().parse(g, { binary: true });
    const a = document.createElement("a"); a.href = URL.createObjectURL(new Blob([s], { type: "model/stl" })); a.download = `sehir_${S.seed}.stl`; a.click();
  }

  // ---------- komutlar (arayüz ve JARVIS) ----------
  function cmd(r) {
    const a = r.action, v = r.value;
    if (!S.built && a !== "new") build(S.seed);
    if (a === "time") S.time = (((+v % 24) + 24) % 24) * 3600;
    else if (a === "speed") S.speed = Math.max(0, Math.min(36000, +v));
    else if (a === "weather") S.weather = ["açık", "yağmur", "kar", "sis", "fırtına"].includes(v) ? v : "açık", S.wind = S.weather === "fırtına" ? Math.max(S.wind, 18) : S.wind;
    else if (a === "wind") S.wind = Math.max(0, Math.min(40, +v));
    else if (a === "traffic") setTraffic(+v);
    else if (a === "gravity") { if (v in PLANETS) { S.planet = v; S.g = PLANETS[v]; } else if (!isNaN(+v)) { S.planet = "özel"; S.g = +v; } }
    else if (a === "tool") S.tool = v;
    else if (a === "new") { S.seed = +v || Math.floor(Math.random() * 1e6); build(S.seed); }
    else if (a === "build") { const n = Math.max(1, Math.min(200, +r.count || 1)); let k = 0, tries = 0; while (k < n && tries++ < 5000) { const i = Math.floor(rng() * N), j = Math.floor(rng() * N); if (!isRoad(i) && !isRoad(j)) { const kind = r.kind || "bina"; if (grid[i + "," + j] && kind !== "bina") continue; removeAt(i, j); if (addStructure(kind, i, j, r.height)) { edits.push({ op: kind, i, j, h: r.height }); k++; } } } saveEdits(); }
    else if (a === "drop") { const L = roadLines[Math.floor(roadLines.length / 2)]; const b = dropBall(L + (rng() - 0.5) * 4, L + 20 + rng() * 20, +v || 60); controls.target.copy(b.m.position).setY(0); } // yol üstüne: engelsiz düşüş
    else if (a === "fire") { const i = Math.floor(rng() * N), j = Math.floor(rng() * N); fires.push({ x: tileCenter(i), y: 0, z: tileCenter(j), size: 1 }); }
    else if (a === "extinguish") fires.length = 0;
    else if (a === "clear") { balls.forEach((b) => root.remove(b.m)); balls.length = 0; fires.length = 0; dropLog = null; }
    else if (a === "reset_edits") { edits = []; saveEdits(); build(S.seed); }
    syncBar(); renderPanel();
    return stats();
  }

  // tıklama: araç kullan
  const plane = new T.Plane(new T.Vector3(0, 1, 0), 0);
  function click(ray) {
    if (S.tool === "bak") { const h = ray.intersectObjects(buildings.map((b) => b.mesh), true)[0]; if (h) { let o = h.object; while (o && !o.userData.kind) o = o.parent; if (o) U.caption(`${o.userData.kind.toUpperCase()}${o.userData.floors ? ` · ${o.userData.floors} kat · ${Math.round(o.userData.floors * 3.2)} m` : ""}`); } return; }
    const hitB = ray.intersectObjects(buildings.map((b) => b.mesh), true)[0];
    const p = hitB ? hitB.point : ray.ray.intersectPlane(plane, new T.Vector3()); if (!p) return;
    const i = Math.floor((p.x + HALF) / TILE), j = Math.floor((p.z + HALF) / TILE);
    if (S.tool === "top") { dropBall(p.x, p.z, 60); return renderPanel(); }
    if (S.tool === "ateş") { fires.push({ x: p.x, y: hitB ? p.y : 0, z: p.z, size: 1 }); return; }
    if (S.tool === "sil") { if (removeAt(i, j)) { edits.push({ op: "sil", i, j }); saveEdits(); } return renderPanel(); }
    removeAt(i, j); if (addStructure(S.tool, i, j)) { edits.push({ op: S.tool, i, j }); saveEdits(); } renderPanel();
  }

  JV.worlds.city = {
    scene,
    enter() {
      buildBar(); bar.classList.remove("hidden");
      if (!S.built) build(S.seed);
      lastReal = performance.now(); physAcc = 0;
      camera.position.set(260, 220, 300); controls.target.set(0, 0, 0); controls.enablePan = true; controls.minDistance = 5; controls.maxDistance = 1400; controls.maxPolarAngle = Math.PI / 2 - 0.02;
      syncBar(); renderPanel();
    },
    exit() { if (bar) bar.classList.add("hidden"); controls.maxPolarAngle = Math.PI; U.caption(""); },
    update(dt) {
      S.time += dt * S.speed;
      // fizik sabit adımla gerçek zamanlı ilerler (kare hızı düşse de süreler doğru kalır; duraklatmada durur)
      physAcc += S.speed > 0 ? Math.min(realDt(), 0.25) : 0;
      updateSky();
      if (S.speed > 0) { const cdt = Math.min(0.05, dt * Math.min(S.speed, 4)); trafficT += cdt; updateCars(cdt, trafficT); updateParticles(Math.min(dt, 0.05)); while (physAcc >= PSTEP) { physAcc -= PSTEP; updateBalls(PSTEP); updateCloth(PSTEP); } renderCloth(); }
      if (bar) bar.querySelector("#cb-time").textContent = fmtT();
      if ((panelT += dt) > 0.5) { panelT = 0; renderPanel(); }
    },
    click,
    cmd,
    stats,
    _test: { lightState, S, PLANETS, cars, buildings, balls, dropBall, updateBalls, cloth: () => cloth },
  };
})();
