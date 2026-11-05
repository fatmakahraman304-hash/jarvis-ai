/* Görsel çekirdek: Three.js ile dönen nokta küresi + hologram 3D yüz, üstünde 2D HUD halkaları. */
(function () {
  const JV = (window.JV = window.JV || {});
  const canvas = document.getElementById("three");
  const hud = document.getElementById("hud");
  const hctx = hud.getContext("2d");
  let color = new (window.THREE ? THREE.Color : Object)("#38d6ff");
  let colorHex = "#38d6ff";
  let mode = "sphere";
  let mix = 0; // 0 küre, 1 yüz
  const mouse = { x: 0, y: 0 };
  addEventListener("pointermove", (e) => { mouse.x = e.clientX / innerWidth - 0.5; mouse.y = e.clientY / innerHeight - 0.5; });

  JV.setVisual = (m) => { mode = m; };
  JV.setColor = (hex) => { colorHex = hex; if (window.THREE) color.set(hex); };

  if (!window.THREE) {
    console.warn("Three.js yüklenemedi (internet?) — sadece HUD çizilecek");
  }

  // ------------------------------------------------ THREE kurulum
  let renderer, scene, camera, sphere, rings = [], face, eyes, dust, matSphere, matFace, matEyes, matRing, matDust;
  const uniforms = { uTime: { value: 0 }, uLevel: { value: 0 }, uColor: { value: color }, uPx: { value: devicePixelRatio || 1 }, uAlpha: { value: 1 }, uBlink: { value: 1 } };

  const VERT = `
    uniform float uTime, uLevel, uPx, uBlink; attribute float aSeed; attribute float aJaw; attribute float aKind;
    varying float vSeed; varying float vKind; varying float vDepth;
    uniform float uMode; // 0 küre, 1 yüz
    void main(){
      vec3 p = position; vSeed = aSeed; vKind = aKind;
      if (uMode < 0.5) {
        vec3 n = normalize(p);
        float d = sin(n.x*4.0+uTime*1.3)*sin(n.y*5.0+uTime*0.9)*sin(n.z*3.0+uTime*0.7);
        float spike = pow(max(0.0, sin(aSeed*40.0 + uTime*6.0)), 8.0);
        p *= 1.0 + d*(0.035 + uLevel*0.22) + uLevel*0.10 + spike*uLevel*0.25;
      } else {
        p.y -= aJaw * (uLevel*0.20);
        p.z += aJaw * uLevel * 0.02;
        if (aKind > 1.5) { p.y = mix(p.y, 0.13, 1.0 - uBlink); }
        p += 0.004*vec3(sin(uTime*2.0+aSeed*50.0), cos(uTime*1.7+aSeed*30.0), 0.0);
      }
      vec4 mv = modelViewMatrix * vec4(p,1.0);
      vDepth = -mv.z;
      float base = aKind > 1.5 ? 3.4 : (aKind > 0.5 ? 1.3 : 1.9 + aSeed*1.6);
      gl_PointSize = (base + uLevel*1.6) * uPx * (3.2 / -mv.z) * 1.9;
      gl_Position = projectionMatrix * mv;
    }`;
  const FRAG = `
    uniform vec3 uColor; uniform float uAlpha; varying float vSeed; varying float vKind; varying float vDepth;
    void main(){
      vec2 c = gl_PointCoord - 0.5; float r = length(c); if (r > 0.5) discard;
      float a = smoothstep(0.5, 0.0, r);
      vec3 col = mix(uColor, vec3(1.0), (vKind > 1.5 ? 0.55 : vSeed*0.35));
      float fog = clamp(1.6 - vDepth*0.28, 0.25, 1.0);
      float lum = vKind > 1.5 ? 1.0 : (vKind > 0.5 ? 0.55 : 0.25 + vSeed*0.95);
      gl_FragColor = vec4(col * (0.7 + lum*0.6), a * uAlpha * fog * lum);
    }`;

  function mkMat(modeVal, alphaUniform) {
    return new THREE.ShaderMaterial({
      uniforms: Object.assign({}, uniforms, { uMode: { value: modeVal }, uAlpha: alphaUniform, uBlink: { value: 1 } }),
      vertexShader: VERT, fragmentShader: FRAG, transparent: true, depthWrite: false, blending: THREE.AdditiveBlending,
    });
  }

  function randDir() { const u = Math.random() * 2 - 1, a = Math.random() * Math.PI * 2, r = Math.sqrt(1 - u * u); return new THREE.Vector3(r * Math.cos(a), u, r * Math.sin(a)); }

  function geom(pos, seed, jaw, kind) {
    const g = new THREE.BufferGeometry();
    g.setAttribute("position", new THREE.Float32BufferAttribute(pos, 3));
    g.setAttribute("aSeed", new THREE.Float32BufferAttribute(seed, 1));
    g.setAttribute("aJaw", new THREE.Float32BufferAttribute(jaw, 1));
    g.setAttribute("aKind", new THREE.Float32BufferAttribute(kind, 1));
    return g;
  }

  function buildSphere() {
    const N = 4200, pos = [], seed = [], jaw = [], kind = [];
    const ga = Math.PI * (3 - Math.sqrt(5));
    for (let i = 0; i < N; i++) {
      const y = 1 - (i / (N - 1)) * 2, r = Math.sqrt(1 - y * y), th = ga * i;
      pos.push(Math.cos(th) * r, y, Math.sin(th) * r); seed.push(0.45 + Math.random() * 0.55); jaw.push(0); kind.push(0);
    }
    for (let i = 0; i < 900; i++) { // iç çekirdek
      const v = randDir().multiplyScalar(0.35 + Math.random() * 0.4);
      pos.push(v.x, v.y, v.z); seed.push(Math.random()); jaw.push(0); kind.push(1);
    }
    return geom(pos, seed, jaw, kind);
  }

  function buildRing(radius, count, tilt) {
    const pos = [], seed = [], jaw = [], kind = [];
    for (let i = 0; i < count; i++) {
      if (Math.random() < 0.18) continue; // kesikli halka
      const a = (i / count) * Math.PI * 2;
      pos.push(Math.cos(a) * radius, (Math.random() - 0.5) * 0.015, Math.sin(a) * radius);
      seed.push(Math.random()); jaw.push(0); kind.push(1);
    }
    const p = new THREE.Points(geom(pos, seed, jaw, kind), matRing);
    p.rotation.x = tilt[0]; p.rotation.z = tilt[1];
    return p;
  }

  // ---- hologram yüz (tamamen prosedürel, enlem çizgileri) ----
  const smooth = (a, b, x) => { const t = Math.min(1, Math.max(0, (x - a) / (b - a))); return t * t * (3 - 2 * t); };
  const G = (dx, dy) => Math.exp(-(dx * dx + dy * dy));
  function headPoint(phi, th) {
    const x = Math.sin(phi) * Math.sin(th), y = Math.cos(phi), z = Math.sin(phi) * Math.cos(th);
    let X = x * 0.74, Y = y * 1.0, Z = z * 0.86;
    if (Y < -0.15) { const t = (-0.15 - Y) / 0.85; X *= 1 - 0.42 * t * t; Z *= 1 - 0.12 * t; }
    if (Y > 0.55) { Z *= 1 - 0.1 * (Y - 0.55); }
    const f = smooth(0.15, 0.65, z);
    const ax = Math.abs(X);
    let dz = 0;
    // burun
    const ridge = smooth(0.14, 0.02, Y) * smooth(-0.3, -0.18, Y);
    dz += 0.2 * Math.exp(-Math.pow(X / 0.065, 2)) * ridge;
    dz += 0.09 * G(X / 0.085, (Y + 0.2) / 0.07);
    dz += 0.03 * G((ax - 0.07) / 0.04, (Y + 0.23) / 0.04);
    // göz çukurları, kaş, elmacık
    dz -= 0.11 * G((ax - 0.26) / 0.12, (Y - 0.12) / 0.08);
    dz += 0.075 * G((ax - 0.24) / 0.2, (Y - 0.25) / 0.05);
    dz += 0.04 * G((ax - 0.38) / 0.12, (Y + 0.04) / 0.11);
    // dudak ve çene
    dz += 0.065 * G(X / 0.17, (Y + 0.42) / 0.06);
    dz += 0.07 * G(X / 0.15, (Y + 0.74) / 0.08);
    Z += dz * f;
    const mouthGap = f > 0.4 && ax < 0.16 && Math.abs(Y + 0.425) < 0.02;
    let jaw = 0;
    if (Y < -0.425) jaw = f * Math.exp(-Math.pow(X / 0.3, 2)) * smooth(-0.425, -0.47, Y) * (Y < -0.9 ? 0.5 : 1);
    return { X, Y, Z, jaw, gap: mouthGap, f };
  }

  // ışık: sol-üst-ön; hatlar (burun, kaş, dudak, çene) parlak, yanlar ve arka sönük
  function shade(phi, th, h) {
    const e = 0.01, a = headPoint(phi + e, th), b = headPoint(phi, th + e);
    const ux = a.X - h.X, uy = a.Y - h.Y, uz = a.Z - h.Z, vx = b.X - h.X, vy = b.Y - h.Y, vz = b.Z - h.Z;
    let nx = uy * vz - uz * vy, ny = uz * vx - ux * vz, nz = ux * vy - uy * vx;
    const l = Math.hypot(nx, ny, nz) || 1; nx /= l; ny /= l; nz /= l;
    if (nx * h.X + ny * h.Y + nz * h.Z < 0) { nx = -nx; ny = -ny; nz = -nz; }
    const lx = -0.62, ly = 0.45, lz = 0.6, ll = Math.hypot(lx, ly, lz);
    const diff = Math.max(0, (nx * lx + ny * ly + nz * lz) / ll);
    const rim = Math.pow(1 - Math.abs(nz), 3) * 0.5;
    return Math.min(1, 0.06 + diff * diff * 0.95 * (0.35 + h.f * 0.65) + rim * 0.4);
  }

  function buildFace() {
    const pos = [], seed = [], jaw = [], kind = [];
    const ROWS = 86, COLS = 220;
    for (let r = 0; r < ROWS; r++) {
      const phi = 0.06 * Math.PI + (r / (ROWS - 1)) * 0.9 * Math.PI;
      for (let c = 0; c < COLS; c++) {
        const th = (c / COLS) * Math.PI * 2 - Math.PI;
        const front = Math.cos(th) > -0.2;
        if (!front && Math.random() < 0.72) continue; // arka taraf seyrek
        const h = headPoint(phi, th);
        if (h.gap) continue;
        pos.push(h.X, h.Y, h.Z); seed.push(shade(phi, th, h)); jaw.push(h.jaw); kind.push(0);
      }
    }
    // dikey birkaç çizgi (kafes hissi)
    for (let c = 0; c < 26; c++) {
      const th = (c / 26) * Math.PI * 2 - Math.PI;
      for (let r = 0; r < 120; r++) {
        const phi = 0.06 * Math.PI + (r / 119) * 0.9 * Math.PI;
        const h = headPoint(phi, th);
        if (h.gap) continue;
        pos.push(h.X, h.Y, h.Z); seed.push(0.15); jaw.push(h.jaw); kind.push(1);
      }
    }
    // boyun
    for (let r = 0; r < 14; r++) for (let c = 0; c < 90; c++) {
      const a = (c / 90) * Math.PI * 2, y = -0.95 - r * 0.035;
      pos.push(Math.sin(a) * 0.3, y, Math.cos(a) * 0.3 - 0.08); seed.push(Math.random() * 0.4); jaw.push(0); kind.push(1);
    }
    const g = geom(pos, seed, jaw, kind);
    // gözler
    const ep = [], es = [], ej = [], ek = [];
    [-1, 1].forEach((s) => {
      const cx = 0.26 * s, cy = 0.12;
      const zs = 0.86 * Math.sqrt(Math.max(0, 1 - Math.pow(cx / 0.74, 2) - cy * cy)) - 0.04;
      for (let i = 0; i < 46; i++) {
        const a = (i / 46) * Math.PI * 2;
        ep.push(cx + Math.cos(a) * 0.075, cy + Math.sin(a) * 0.032, zs); es.push(1); ej.push(0); ek.push(2);
      }
      for (let i = 0; i < 26; i++) {
        const a = Math.random() * Math.PI * 2, rr = Math.random() * 0.026;
        ep.push(cx + Math.cos(a) * rr, cy + Math.sin(a) * rr, zs + 0.01); es.push(1); ej.push(0); ek.push(2);
      }
    });
    return { g, eg: geom(ep, es, ej, ek) };
  }

  function buildDust() {
    const pos = [], seed = [], jaw = [], kind = [];
    for (let i = 0; i < 700; i++) {
      const v = randDir().multiplyScalar(1.8 + Math.random() * 2.5);
      pos.push(v.x, v.y, v.z); seed.push(Math.random() * 0.3); jaw.push(0); kind.push(1);
    }
    return geom(pos, seed, jaw, kind);
  }

  if (window.THREE) {
    renderer = new THREE.WebGLRenderer({ canvas, antialias: true, alpha: true });
    renderer.setPixelRatio(Math.min(devicePixelRatio, 2));
    scene = new THREE.Scene();
    camera = new THREE.PerspectiveCamera(42, 1, 0.1, 100);
    camera.position.set(0, 0, 4.2);
    const aS = { value: 1 }, aF = { value: 0 }, aR = { value: 0.8 }, aD = { value: 0.35 };
    matSphere = mkMat(0, aS); matFace = mkMat(1, aF); matEyes = mkMat(1, aF); matRing = mkMat(0, aR); matDust = mkMat(0, aD);
    matRing.uniforms.uLevel = { value: 0 }; matDust.uniforms.uLevel = { value: 0 };
    sphere = new THREE.Points(buildSphere(), matSphere); scene.add(sphere);
    rings = [buildRing(1.45, 360, [1.2, 0.2]), buildRing(1.62, 420, [1.9, -0.5]), buildRing(1.8, 500, [Math.PI / 2, 0])];
    rings.forEach((r) => scene.add(r));
    const fb = buildFace();
    face = new THREE.Points(fb.g, matFace); eyes = new THREE.Points(fb.eg, matEyes);
    const faceGroup = new THREE.Group(); faceGroup.add(face); faceGroup.add(eyes); faceGroup.scale.setScalar(0.98);
    scene.add(faceGroup);
    dust = new THREE.Points(buildDust(), matDust); scene.add(dust);
    JV._three = { faceGroup, aS, aF, aR };
  }

  function resize() {
    const w = innerWidth, h = innerHeight, d = Math.min(devicePixelRatio, 2);
    hud.width = w * d; hud.height = h * d; hctx.setTransform(d, 0, 0, d, 0, 0);
    if (renderer) {
      renderer.setSize(w, h, false);
      camera.aspect = w / h;
      camera.position.z = w < 800 ? 5.6 : 4.2;
      camera.position.y = w < 800 ? -0.5 : 0;
      camera.updateProjectionMatrix();
    }
  }
  addEventListener("resize", resize); resize();

  // ------------------------------------------------ 2D HUD
  function drawHUD(t, lvl) {
    const w = innerWidth, h = innerHeight;
    hctx.clearRect(0, 0, w, h);
    const cx = w / 2, cy = w < 800 ? h * 0.36 : h / 2;
    const R = Math.min(w, h) * (w < 800 ? 0.3 : 0.33);
    hctx.strokeStyle = colorHex; hctx.fillStyle = colorHex;
    hctx.shadowColor = colorHex; hctx.shadowBlur = 8;
    const arc = (r, a0, a1, lw, alpha) => { hctx.globalAlpha = alpha; hctx.lineWidth = lw; hctx.beginPath(); hctx.arc(cx, cy, r, a0, a1); hctx.stroke(); };
    // dış segmentli halka
    for (let i = 0; i < 6; i++) { const a = t * 0.15 + (i * Math.PI) / 3; arc(R * 1.08, a, a + 0.75, 2, 0.55); }
    // tik çizgileri
    hctx.globalAlpha = 0.35; hctx.lineWidth = 1;
    for (let i = 0; i < 120; i++) {
      const a = (i / 120) * Math.PI * 2 - t * 0.05, l = i % 10 === 0 ? 12 : 5;
      hctx.beginPath();
      hctx.moveTo(cx + Math.cos(a) * R * 1.15, cy + Math.sin(a) * R * 1.15);
      hctx.lineTo(cx + Math.cos(a) * (R * 1.15 + l), cy + Math.sin(a) * (R * 1.15 + l));
      hctx.stroke();
    }
    // ters dönen ince halkalar
    for (let i = 0; i < 3; i++) { const a = -t * 0.32 + i * 2.1; arc(R * 1.23, a, a + 1.2, 1, 0.4); }
    arc(R * 1.3, -t * 0.08, -t * 0.08 + Math.PI * 1.6, 1, 0.15);
    // ses seviyesi halkası
    arc(R * (1.0 + lvl * 0.06), 0, Math.PI * 2, 1 + lvl * 4, 0.12 + lvl * 0.6);
    // ekolayzer çubukları
    hctx.globalAlpha = 0.5 + lvl * 0.5;
    for (let i = 0; i < 64; i++) {
      const a = (i / 64) * Math.PI * 2 + t * 0.1;
      const v = lvl * (0.4 + 0.6 * Math.abs(Math.sin(i * 1.7 + t * 9))) * R * 0.18;
      hctx.lineWidth = 2;
      hctx.beginPath();
      hctx.moveTo(cx + Math.cos(a) * R * 1.36, cy + Math.sin(a) * R * 1.36);
      hctx.lineTo(cx + Math.cos(a) * (R * 1.36 + 2 + v), cy + Math.sin(a) * (R * 1.36 + 2 + v));
      hctx.stroke();
    }
    // köşe yazıları
    hctx.shadowBlur = 0; hctx.globalAlpha = 0.55;
    hctx.font = "11px 'Share Tech Mono', monospace";
    const st = JV.speaking ? "VOICE OUT" : document.body.classList.contains("listening") ? "AUDIO IN" : document.body.classList.contains("thinking") ? "PROCESSING" : "STANDBY";
    hctx.textAlign = "center"; hctx.fillText(`CORE // ${st}`, cx, cy - R * 1.19);
    hctx.textAlign = "left";
    hctx.globalAlpha = 1;
  }

  // ------------------------------------------------ döngü
  let last = performance.now(), blinkT = 0;
  function frame(now) {
    const dt = Math.min(0.05, (now - last) / 1000); last = now;
    if (JV.coreHidden) { requestAnimationFrame(frame); return; }
    const t = now / 1000, lvl = JV.level || 0;
    mix += ((mode === "face" ? 1 : 0) - mix) * Math.min(1, dt * 3);
    drawHUD(t, lvl);
    if (renderer) {
      [matSphere, matFace, matEyes, matRing, matDust].forEach((m) => { m.uniforms.uTime.value = t; m.uniforms.uLevel.value = lvl; m.uniforms.uColor.value = color; });
      // göz kırpma
      blinkT -= dt; let blink = 1;
      if (blinkT < 0) { blinkT = 2.5 + Math.random() * 4; }
      if (blinkT < 0.14) blink = Math.abs(blinkT - 0.07) / 0.07;
      matEyes.uniforms.uBlink.value = blink; matFace.uniforms.uBlink.value = 1;
      const { faceGroup, aS, aF, aR } = JV._three;
      aS.value = 1 - mix; aF.value = mix; aR.value = 0.8 * (1 - mix * 0.7);
      sphere.visible = mix < 0.99; faceGroup.visible = mix > 0.01;
      sphere.rotation.y += dt * (0.18 + lvl * 0.8); sphere.rotation.x = Math.sin(t * 0.2) * 0.25;
      rings.forEach((r, i) => { r.rotation.y += dt * (0.25 + i * 0.12) * (i % 2 ? -1 : 1) * (1 + lvl * 2); });
      faceGroup.rotation.y += ((Math.sin(t * 0.35) * 0.35 + mouse.x * 0.8) - faceGroup.rotation.y) * 0.05;
      faceGroup.rotation.x += ((mouse.y * 0.4 + Math.sin(t * 0.5) * 0.05) - faceGroup.rotation.x) * 0.05;
      dust.rotation.y += dt * 0.02;
      renderer.render(scene, camera);
    }
    requestAnimationFrame(frame);
  }
  requestAnimationFrame(frame);
})();
