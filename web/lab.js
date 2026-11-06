/* HOLOGRAM ATÖLYESİ: sanal masa üzerinde 3D tasarım, parçalara ayırma, model görüntüleme, STL dışa aktarma, 3D grafik. */
(function () {
  const JV = window.JV; if (!JV || !JV.wutil) return;
  const U = JV.wutil, T = U.T, DEG = U.DEG, camera = U.camera, controls = U.controls;
  const scene = new T.Scene();
  scene.fog = new T.FogExp2(0x02060a, 0.05);
  scene.add(new T.AmbientLight(0x557788, 0.7));
  const key = new T.DirectionalLight(0xffffff, 0.9); key.position.set(4, 8, 5); scene.add(key);
  const rim = new T.PointLight(0x38d6ff, 1.2, 30); rim.position.set(-5, 4, -4); scene.add(rim);

  // ---- sanal masa ----
  const table = new T.Group(); scene.add(table);
  const disc = new T.Mesh(new T.CircleGeometry(3.4, 96), new T.MeshBasicMaterial({ color: 0x38d6ff, transparent: true, opacity: 0.06, side: T.DoubleSide }));
  disc.rotation.x = -Math.PI / 2; table.add(disc);
  const grid = new T.PolarGridHelper(3.4, 16, 8, 96, 0x38d6ff, 0x1a5d74); grid.material.transparent = true; grid.material.opacity = 0.45; table.add(grid);
  const rings = [3.45, 3.6].map((r, i) => { const m = new T.Mesh(new T.RingGeometry(r, r + 0.02 + i * 0.02, 128), new T.MeshBasicMaterial({ color: 0x38d6ff, transparent: true, opacity: 0.6 - i * 0.3, side: T.DoubleSide })); m.rotation.x = -Math.PI / 2; table.add(m); return m; });
  const beam = new T.Mesh(new T.CylinderGeometry(3.4, 3.4, 4, 64, 1, true), new T.MeshBasicMaterial({ color: 0x38d6ff, transparent: true, opacity: 0.035, side: T.DoubleSide, depthWrite: false }));
  beam.position.y = 2; table.add(beam);

  let model = null, title = "", explodeK = 0, explodeTarget = 0, autoRotate = true, wire = false, selected = null;
  let walkMode = false, walkKeys = Object.create(null), doorParts = [];

  function tint() { const c = U.color(); grid.material.color = c; disc.material.color = c; rings.forEach((r) => (r.material.color = c)); beam.material.color = c; rim.color = c; }

  // ---- hologram malzemesi ----
  function holoMesh(geom, color) {
    const c = new T.Color(color || U.color());
    const g = new T.Group();
    const fill = new T.Mesh(geom, new T.MeshPhongMaterial({ color: c, emissive: c, emissiveIntensity: 0.28, transparent: true, opacity: 0.32, side: T.DoubleSide, depthWrite: false, shininess: 60 }));
    const edges = new T.LineSegments(new T.EdgesGeometry(geom, 25), new T.LineBasicMaterial({ color: c.clone().lerp(new T.Color(1, 1, 1), 0.35), transparent: true, opacity: 0.95 }));
    g.add(fill, edges); g.userData.fill = fill; g.userData.edges = edges;
    return g;
  }

  function geometry(p) {
    const s = p.size || [];
    switch ((p.type || "box").toLowerCase()) {
      case "sphere": return new T.SphereGeometry(s[0] || 0.5, 32, 20);
      case "cylinder": return new T.CylinderGeometry(s[2] != null ? s[2] : (s[0] || 0.3), s[0] || 0.3, s[1] || 1, 32);
      case "cone": return new T.ConeGeometry(s[0] || 0.4, s[1] || 1, 32);
      case "torus": return new T.TorusGeometry(s[0] || 0.5, s[1] || 0.12, 16, 48);
      case "wedge": {
        const [w, h, d] = [s[0] || 1, s[1] || 0.6, s[2] || 1];
        const sh = new T.Shape(); sh.moveTo(-w / 2, 0); sh.lineTo(w / 2, 0); sh.lineTo(0, h); sh.lineTo(-w / 2, 0);
        const g = new T.ExtrudeGeometry(sh, { depth: d, bevelEnabled: false }); g.translate(0, 0, -d / 2); return g;
      }
      default: return new T.BoxGeometry(s[0] || 1, s[1] || 1, s[2] || 1);
    }
  }

  function build(parts, name) {
    clear();
    title = name || "Model";
    const root = new T.Group(), inner = new T.Group(); root.add(inner);
    parts.forEach((p, i) => {
      const m = holoMesh(geometry(p), p.color);
      if (p.hinge) {
        const pivot = new T.Group(); pivot.position.fromArray(p.pos || [0,0,0]);
        m.position.set(0.44,0,0); pivot.add(m);
        pivot.userData.name = p.name || 'Kapı kanadı'; pivot.userData.home = pivot.position.clone();
        pivot.userData.door = true; pivot.userData.doorOpen = false;
        inner.add(pivot); doorParts.push(pivot);
      } else {
        m.position.fromArray(p.pos || [0,0,0]);
        if (p.rot) m.rotation.set(p.rot[0]*DEG,(p.rot[1]||0)*DEG,(p.rot[2]||0)*DEG);
        m.userData.name = p.name || ('parça '+(i+1)); m.userData.home = m.position.clone(); inner.add(m);
      }
    });
    fit(root, inner);
    model = root; scene.add(model);
    // patlatma yönleri
    const center = new T.Box3().setFromObject(inner).getCenter(new T.Vector3()).applyMatrix4(new T.Matrix4().copy(inner.matrixWorld).invert());
    inner.children.forEach((m) => { const d = m.userData.home.clone().sub(center); m.userData.dir = d.lengthSq() < 1e-6 ? new T.Vector3(0, 1, 0) : d.normalize(); });
    explodeK = explodeTarget = 0;
    renderPanel();
    return root;
  }

  function fit(root, inner) {
    inner.updateMatrixWorld(true);
    const box = new T.Box3().setFromObject(inner), size = box.getSize(new T.Vector3()), c = box.getCenter(new T.Vector3());
    const k = 3.2 / Math.max(size.x, size.y, size.z, 0.001);
    inner.position.set(-c.x, -box.min.y, -c.z); root.scale.setScalar(k); root.position.y = 0.02;
    root.userData.size = size.clone().multiplyScalar(k);
  }

  function clear() {
    if (model) { scene.remove(model); U.disposeTree(model); model = null; }
    selected = null; doorParts = [];
  }

  // ---- parametrik tasarımlar ----
  const C = { a: "#38d6ff", b: "#7af0ff", w: "#ffffff", r: "#ff4d5e", y: "#ffd34d", g: "#5dff9a", o: "#ffa03a", p: "#b78cff" };
  const D = {
    building(p) {
      const n = Math.max(2, Math.min(60, p.floors || 12)), w = p.width || 2, d = p.depth || 2, fh = 0.32, parts = [];
      parts.push({ name: "temel", type: "box", size: [w * 1.25, 0.25, d * 1.25], pos: [0, 0.125, 0] });
      for (let i = 0; i < n; i++) {
        const taper = 1 - (p.taper ?? 0.25) * (i / n);
        parts.push({ name: `kat ${i + 1}`, type: "box", size: [w * taper, fh * 0.92, d * taper], pos: [0, 0.25 + fh * i + fh / 2, 0], color: i % 5 === 4 ? C.b : C.a });
      }
      const top = 0.25 + fh * n;
      parts.push({ name: "çatı", type: "box", size: [w * 0.5, 0.25, d * 0.5], pos: [0, top + 0.125, 0], color: C.b });
      parts.push({ name: "anten", type: "cylinder", size: [0.03, 1.2], pos: [0, top + 0.85, 0], color: C.w });
      parts.push({ name: "uyarı ışığı", type: "sphere", size: [0.07], pos: [0, top + 1.48, 0], color: C.r });
      return parts;
    },
    house(p) {
      const w = p.width || 4, d = p.depth || 3, h = p.height || 1.6, parts = [
        { name: "zemin", type: "box", size: [w + 0.4, 0.15, d + 0.4], pos: [0, 0.075, 0] },
        { name: "duvarlar", type: "box", size: [w, h, d], pos: [0, 0.15 + h / 2, 0] },
        { name: "çatı", type: "wedge", size: [w + 0.5, 1.3, d + 0.5], pos: [0, 0.15 + h, 0], color: p.roof || C.o },
        { name: "kapı", type: "box", size: [0.6, 1.0, 0.06], pos: [0, 0.65, d / 2 + 0.03], color: C.y },
        { name: "baca", type: "box", size: [0.35, 0.9, 0.35], pos: [w * 0.28, 0.15 + h + 0.75, -d * 0.15], color: C.r },
        { name: "basamak", type: "box", size: [1.0, 0.12, 0.4], pos: [0, 0.06, d / 2 + 0.35] },
      ];
      [-1, 1].forEach((s) => parts.push({ name: `pencere ${s < 0 ? "sol" : "sağ"}`, type: "box", size: [0.7, 0.55, 0.06], pos: [s * w * 0.3, 0.15 + h * 0.6, d / 2 + 0.03], color: C.b }));
      [-1, 1].forEach((s) => parts.push({ name: `yan pencere ${s < 0 ? "sol" : "sağ"}`, type: "box", size: [0.06, 0.55, 0.7], pos: [s * (w / 2 + 0.03), 0.15 + h * 0.6, 0], color: C.b }));
      for (let i = 0; i < (p.rooms || 0); i++) parts.push({ name: `oda ${i + 1}`, type: "box", size: [w / (p.rooms || 1) - 0.1, h * 0.95, d * 0.95], pos: [-w / 2 + (i + 0.5) * w / p.rooms, 0.15 + h / 2, 0], color: C.p });
      return parts;
    },
    car(p) {
      const sport = p.type === "sport", suv = p.type === "suv", col = p.color || C.a;
      const L = sport ? 4.4 : 4.2, H = suv ? 0.9 : sport ? 0.55 : 0.7, wr = suv ? 0.42 : 0.34;
      const parts = [
        { name: "şasi", type: "box", size: [L, H, 1.8], pos: [0, wr + H / 2, 0], color: col },
        { name: "kabin", type: "box", size: [sport ? 1.6 : 2.2, sport ? 0.45 : 0.65, 1.6], pos: [sport ? -0.2 : -0.15, wr + H + (sport ? 0.22 : 0.32), 0], color: C.b },
        { name: "kaput", type: "wedge", size: [1.8, 0.25, 1.0], pos: [L * 0.32, wr + H, 0], rot: [0, 90, 0], color: col },
      ];
      [[1, 1], [1, -1], [-1, 1], [-1, -1]].forEach(([x, z], i) => {
        parts.push({ name: `tekerlek ${i + 1}`, type: "cylinder", size: [wr, 0.3], pos: [x * L * 0.32, wr, z * 0.92], rot: [90, 0, 0], color: C.w });
        parts.push({ name: `jant ${i + 1}`, type: "torus", size: [wr * 0.6, 0.04], pos: [x * L * 0.32, wr, z * 1.08], color: C.y });
      });
      [-1, 1].forEach((z) => parts.push({ name: `far ${z < 0 ? "sol" : "sağ"}`, type: "sphere", size: [0.1], pos: [L / 2, wr + H * 0.65, z * 0.6], color: C.y }));
      [-1, 1].forEach((z) => parts.push({ name: `stop ${z < 0 ? "sol" : "sağ"}`, type: "box", size: [0.05, 0.12, 0.35], pos: [-L / 2, wr + H * 0.65, z * 0.6], color: C.r }));
      if (sport) parts.push({ name: "spoiler", type: "box", size: [0.4, 0.06, 1.7], pos: [-L / 2 + 0.2, wr + H + 0.35, 0], color: C.r }, { name: "spoiler ayağı", type: "box", size: [0.1, 0.3, 0.1], pos: [-L / 2 + 0.2, wr + H + 0.17, 0] });
      if (suv) parts.push({ name: "tavan rafı", type: "box", size: [1.8, 0.08, 1.5], pos: [-0.15, wr + H + 0.7, 0], color: C.w });
      return parts;
    },
    robot(p) {
      if (p.type === "arm") return D.arm(p);
      if (p.type === "rover") return D.rover(p);
      const parts = [
        { name: "gövde", type: "box", size: [1.2, 1.4, 0.7], pos: [0, 2.6, 0] },
        { name: "göğüs çekirdeği", type: "sphere", size: [0.18], pos: [0, 2.8, 0.37], color: C.b },
        { name: "boyun", type: "cylinder", size: [0.15, 0.25], pos: [0, 3.42, 0], color: C.w },
        { name: "kafa", type: "box", size: [0.75, 0.6, 0.6], pos: [0, 3.85, 0] },
        { name: "anten", type: "cylinder", size: [0.03, 0.4], pos: [0, 4.35, 0], color: C.w },
        { name: "anten ucu", type: "sphere", size: [0.07], pos: [0, 4.58, 0], color: C.r },
        { name: "kalça", type: "box", size: [1.0, 0.35, 0.6], pos: [0, 1.75, 0] },
      ];
      [-1, 1].forEach((s) => {
        const side = s < 0 ? "sol" : "sağ";
        parts.push({ name: `göz ${side}`, type: "sphere", size: [0.09], pos: [s * 0.18, 3.9, 0.31], color: C.y });
        parts.push({ name: `omuz ${side}`, type: "sphere", size: [0.22], pos: [s * 0.78, 3.15, 0], color: C.w });
        parts.push({ name: `üst kol ${side}`, type: "cylinder", size: [0.14, 0.8], pos: [s * 0.85, 2.65, 0] });
        parts.push({ name: `dirsek ${side}`, type: "sphere", size: [0.15], pos: [s * 0.85, 2.2, 0], color: C.w });
        parts.push({ name: `ön kol ${side}`, type: "cylinder", size: [0.12, 0.75], pos: [s * 0.85, 1.75, 0] });
        parts.push({ name: `el ${side}`, type: "box", size: [0.25, 0.3, 0.2], pos: [s * 0.85, 1.25, 0], color: C.b });
        parts.push({ name: `üst bacak ${side}`, type: "cylinder", size: [0.18, 0.75], pos: [s * 0.3, 1.2, 0] });
        parts.push({ name: `diz ${side}`, type: "sphere", size: [0.18], pos: [s * 0.3, 0.8, 0], color: C.w });
        parts.push({ name: `alt bacak ${side}`, type: "cylinder", size: [0.15, 0.6], pos: [s * 0.3, 0.45, 0] });
        parts.push({ name: `ayak ${side}`, type: "box", size: [0.35, 0.15, 0.6], pos: [s * 0.3, 0.075, 0.1], color: C.b });
      });
      return parts;
    },
    arm() {
      return [
        { name: "taban", type: "cylinder", size: [0.8, 0.25], pos: [0, 0.125, 0] },
        { name: "döner tabla", type: "cylinder", size: [0.5, 0.3], pos: [0, 0.4, 0], color: C.b },
        { name: "omuz eklemi", type: "sphere", size: [0.3], pos: [0, 0.75, 0], color: C.w },
        { name: "üst kol", type: "box", size: [0.25, 1.6, 0.25], pos: [0.3, 1.45, 0], rot: [0, 0, -22] },
        { name: "dirsek eklemi", type: "sphere", size: [0.22], pos: [0.6, 2.2, 0], color: C.w },
        { name: "ön kol", type: "box", size: [1.4, 0.2, 0.2], pos: [1.25, 2.35, 0], rot: [0, 0, 12] },
        { name: "bilek", type: "cylinder", size: [0.13, 0.25], pos: [1.95, 2.5, 0], rot: [0, 0, 90], color: C.w },
        { name: "kıskaç üst", type: "box", size: [0.35, 0.06, 0.12], pos: [2.25, 2.6, 0], color: C.y },
        { name: "kıskaç alt", type: "box", size: [0.35, 0.06, 0.12], pos: [2.25, 2.4, 0], color: C.y },
        { name: "servo motor", type: "box", size: [0.3, 0.2, 0.35], pos: [0, 0.75, 0.3], color: C.o },
      ];
    },
    rover() {
      const parts = [{ name: "şasi", type: "box", size: [2.4, 0.4, 1.4], pos: [0, 0.75, 0] },
        { name: "güneş paneli", type: "box", size: [2.0, 0.05, 1.6], pos: [-0.2, 1.05, 0], color: C.p },
        { name: "direk", type: "cylinder", size: [0.06, 1.0], pos: [0.8, 1.5, 0.4], color: C.w },
        { name: "kamera kafası", type: "box", size: [0.35, 0.22, 0.25], pos: [0.8, 2.05, 0.4], color: C.y },
        { name: "anten çanağı", type: "cone", size: [0.3, 0.15], pos: [-0.8, 1.35, -0.4], color: C.w },
        { name: "robot kolu", type: "box", size: [0.9, 0.08, 0.08], pos: [1.5, 0.75, -0.3], color: C.o }];
      [-1, 0, 1].forEach((x) => [-1, 1].forEach((z) => parts.push({ name: `tekerlek ${x + 2}${z > 0 ? "R" : "L"}`, type: "cylinder", size: [0.3, 0.25], pos: [x * 0.9, 0.3, z * 0.85], rot: [90, 0, 0], color: C.w })));
      return parts;
    },
    rocket(p) {
      const st = Math.max(1, Math.min(4, p.stages || 2)), parts = []; let y = 0;
      for (let i = 0; i < st; i++) { const h = 2.2 - i * 0.4, r = 0.5 - i * 0.06; parts.push({ name: `${i + 1}. kademe`, type: "cylinder", size: [r, h], pos: [0, y + h / 2, 0], color: i % 2 ? C.b : C.a }); parts.push({ name: `ayırıcı ${i + 1}`, type: "cylinder", size: [r + 0.03, 0.06], pos: [0, y + h, 0], color: C.w }); y += h + 0.06; }
      parts.push({ name: "burun konisi", type: "cone", size: [0.38, 1.0], pos: [0, y + 0.5, 0], color: C.w });
      [0, 90, 180, 270].forEach((a, i) => parts.push({ name: `kanatçık ${i + 1}`, type: "box", size: [0.06, 0.8, 0.5], pos: [Math.sin(a * DEG) * 0.6, 0.4, Math.cos(a * DEG) * 0.6], rot: [0, a, 0], color: C.r }));
      parts.push({ name: "motor", type: "cone", size: [0.35, 0.4], pos: [0, -0.2, 0], rot: [180, 0, 0], color: C.o });
      return parts;
    },
    bridge(p) {
      const span = p.span || 8, parts = [{ name: "yol tabliyesi", type: "box", size: [span, 0.2, 1.2], pos: [0, 1.2, 0] }];
      [-1, 1].forEach((s) => { parts.push({ name: `kule ${s < 0 ? "sol" : "sağ"}`, type: "box", size: [0.3, 3, 1.4], pos: [s * span * 0.3, 1.5, 0], color: C.b }); parts.push({ name: `ayak ${s < 0 ? "sol" : "sağ"}`, type: "box", size: [0.6, 1.2, 1.4], pos: [s * span * 0.3, 0.6, 0] }); });
      for (let i = 1; i <= 5; i++) [-1, 1].forEach((s) => [-1, 1].forEach((z) => { const x0 = s * span * 0.3, x1 = s * span * 0.3 - s * i * span * 0.055, len = Math.hypot(x0 - x1, 1.7); parts.push({ name: `kablo ${i}`, type: "cylinder", size: [0.015, len], pos: [(x0 + x1) / 2, 1.3 + 0.85 + 0.0, z * 0.6], rot: [0, 0, Math.atan2(x0 - x1, 1.7) / DEG], color: C.y }); }));
      return parts;
    },
    table() {
      const parts = [{ name: "tabla", type: "box", size: [3, 0.12, 1.6], pos: [0, 1.5, 0] }];
      [[1, 1], [1, -1], [-1, 1], [-1, -1]].forEach(([x, z], i) => parts.push({ name: `ayak ${i + 1}`, type: "box", size: [0.12, 1.45, 0.12], pos: [x * 1.35, 0.72, z * 0.65] }));
      return parts;
    },
    drone() {
      const parts = [{ name: "gövde", type: "box", size: [0.8, 0.25, 0.8] , pos: [0, 0.6, 0]}, { name: "kamera", type: "sphere", size: [0.16], pos: [0, 0.4, 0.3], color: C.y }, { name: "batarya", type: "box", size: [0.5, 0.12, 0.3], pos: [0, 0.79, 0], color: C.o }];
      [45, 135, 225, 315].forEach((a, i) => {
        const x = Math.sin(a * DEG), z = Math.cos(a * DEG);
        parts.push({ name: `kol ${i + 1}`, type: "box", size: [0.08, 0.06, 1.1], pos: [x * 0.6, 0.62, z * 0.6], rot: [0, a, 0] });
        parts.push({ name: `motor ${i + 1}`, type: "cylinder", size: [0.1, 0.15], pos: [x * 1.1, 0.72, z * 1.1], color: C.w });
        parts.push({ name: `pervane ${i + 1}`, type: "box", size: [0.9, 0.02, 0.08], pos: [x * 1.1, 0.82, z * 1.1], rot: [0, a + 45, 0], color: C.b, spin: true });
      });
      [-1, 1].forEach((s) => parts.push({ name: "iniş ayağı", type: "box", size: [0.05, 0.4, 0.7], pos: [s * 0.3, 0.25, 0], color: C.w }));
      return parts;
    },
  };

  // ---- dış model yükleme ----
  function loadModel(url, ext, name) {
    clear(); title = name || "Model";
    const done = (obj) => {
      const root = new T.Group(), inner = new T.Group(); root.add(inner);
      obj.traverse((o) => { if (o.isMesh) { const m = holoMesh(o.geometry.clone().applyMatrix4(o.matrixWorld)); m.userData.name = o.name || "parça"; m.userData.home = new T.Vector3(); inner.add(m); } });
      if (!inner.children.length) return JV.toast && JV.toast("Modelde görüntülenecek yüzey yok.");
      fit(root, inner); model = root; scene.add(root);
      inner.children.forEach((m) => { m.geometry = m.userData.fill.geometry; m.geometry.computeBoundingBox(); const c = m.geometry.boundingBox.getCenter(new T.Vector3()); m.userData.dir = c.lengthSq() > 1e-6 ? c.normalize() : new T.Vector3(0, 1, 0); });
      renderPanel();
    };
    const err = () => JV.toast && JV.toast("Model açılamadı.");
    const url2 = url + (url.includes("?") ? "&" : "?") + "token=" + encodeURIComponent(JV.token || "");
    if (ext === "stl") new T.STLLoader().load(url2, (g) => { const o = new T.Mesh(g); o.updateMatrixWorld(); done(o); }, undefined, err);
    else if (ext === "obj") new T.OBJLoader().load(url2, (o) => { o.updateMatrixWorld(true); done(o); }, undefined, err);
    else new T.GLTFLoader().load(url2, (g) => { g.scene.updateMatrixWorld(true); done(g.scene); }, undefined, err);
  }

  // ---- 3D grafik ----
  function chart3d(titleText, data) {
    let entries = Array.isArray(data) ? data : Object.entries(data || {});
    entries = entries.filter((e) => isFinite(+e[1])).slice(0, 24);
    if (!entries.length) return;
    const max = Math.max(...entries.map((e) => +e[1])) || 1, n = entries.length, parts = [];
    entries.forEach(([k, v], i) => { const h = Math.max(0.05, (+v / max) * 3); parts.push({ name: `${k}: ${U.fmt(+v, 2)}`, type: "box", size: [0.5, h, 0.5], pos: [(i - (n - 1) / 2) * 0.7, h / 2, 0], color: new T.Color().setHSL(0.52 - i / n * 0.45, 0.9, 0.6).getStyle() }); });
    build(parts, titleText);
    const inner = model.children[0];
    entries.forEach(([k, v], i) => { const s = U.label(`${k} ${U.fmt(+v, 1)}`, "#e8f8ff", 40); const b = inner.children[i]; s.position.set(b.position.x, b.position.y * 2 + 0.35, 0.4); s.scale.set(0.25 * s.userData.aspect, 0.25, 1); inner.add(s); });
  }


  function buildHome3D(p) {
    const width = p.width, depth = p.depth, height = Number(p.wallHeight) || 2.8;
    const rooms = p.roomNames || ["Salon", "Mutfak", "Yatak odası", "Banyo", "Çalışma odası", "Antre"].slice(0, p.rooms);
    const cols = Math.ceil(Math.sqrt(rooms.length)), rows = Math.ceil(rooms.length / cols);
    const cw = width / cols, ch = depth / rows, wall = 0.12, parts = [];
    const floorColor = p.floorColor || "#8b7355", wallColor = p.wallColor || "#e4e0d8";
    parts.push({name:"Zemin döşemesi",type:"box",size:[width,0.12,depth],pos:[0,0.06,0],color:floorColor});
    const addWall=(name,x,z,sx,sz)=> {
      const horizontal = sx > sz, length = horizontal ? sx : sz, center = horizontal ? x : z;
      const line = horizontal ? z : x;
      const openings = (p.objects||[]).filter(o => (o.type==="door"||o.type==="window") &&
        Math.abs((horizontal?o.z:o.x)-line)<0.45).map(o => ({
          at:(horizontal?o.x:o.z)-center+length/2,
          width:o.type==="door"?0.95:1.3, type:o.type
        })).sort((u,v)=>u.at-v.at);
      let cursor=0;
      const segment=(from,to,label,y=height/2+0.12,h=height)=>{
        if(to-from<0.08)return;
        const size=horizontal?[to-from,h,wall]:[wall,h,to-from];
        const pos=horizontal?[center-length/2+(from+to)/2,y,line]:[line,y,center-length/2+(from+to)/2];
        parts.push({name:label,type:"box",size,pos,color:wallColor});
      };
      openings.forEach((o,i)=>{
        const left=Math.max(cursor,o.at-o.width/2),right=Math.min(length,o.at+o.width/2);
        segment(cursor,left,name+" duvar bölümü");
        if(o.type==="window"){
          const sill=0.85,top=2.15;
          const lower=horizontal?[right-left,sill,wall]:[wall,sill,right-left];
          const upper=horizontal?[right-left,Math.max(0.1,height-top),wall]:[wall,Math.max(0.1,height-top),right-left];
          const mid=horizontal?[center-length/2+(left+right)/2,0.12+sill/2,line]:[line,0.12+sill/2,center-length/2+(left+right)/2];
          parts.push({name:"Pencere alt duvarı",type:"box",size:lower,pos:mid,color:wallColor});
          const topPos=mid.slice();topPos[1]=0.12+top+Math.max(0.1,height-top)/2;
          parts.push({name:"Pencere üst duvarı",type:"box",size:upper,pos:topPos,color:wallColor});
          parts.push({name:"Cam pencere",type:"box",size:horizontal?[right-left,1.15,0.035]:[0.035,1.15,right-left],pos:horizontal?[mid[0],1.55,line]:[line,1.55,mid[2]],color:"#69c9ed"});
        }
        cursor=Math.max(cursor,right);
      });
      segment(cursor,length,name);
    };
    addWall("Arka dış duvar",0,-depth/2,width,wall);
    addWall("Ön dış duvar",0,depth/2,width,wall);
    addWall("Sol dış duvar",-width/2,0,wall,depth);
    addWall("Sağ dış duvar",width/2,0,wall,depth);
    for(let col=1;col<cols;col++) addWall("İç bölme",-width/2+col*cw,0,wall,depth);
    for(let row=1;row<rows;row++) addWall("İç bölme",0,-depth/2+row*ch,width,wall);
    // Kapı ve pencereler 3D modelde renkli, duvara oturan elemanlar olarak gösterilir.
    (p.objects||[]).forEach((o,i)=>{
      const x=Number(o.x)||0,z=Number(o.z)||0;
      if(o.type==="door") parts.push({name:"Kapı kasası "+(i+1),type:"box",size:[0.07,2.1,0.08],pos:[x-0.46,1.17,z],color:"#80502f"},{name:"Kapı kanadı "+(i+1),type:"box",size:[0.88,2.0,0.045],pos:[x-0.44,1.12,z],color:"#a66b3f",hinge:true});
      else if(o.type==="window") { /* Cam ve duvar açıklığı addWall içinde üretilir. */ }
      else {
        const specs={sofa:[1.9,0.75,0.85,"#657b8d"],bed:[1.6,0.45,2.0,"#b7a0c9"],table:[1.2,0.75,0.8,"#a8794f"],wardrobe:[1.1,2.1,0.6,"#8d735f"],toilet:[0.48,0.42,0.68,"#f0f4f5"],kitchen:[1.8,0.9,0.65,"#777f87"],desk:[1.2,0.75,0.65,"#9b744d"],plant:[0.45,0.9,0.45,"#39875c"]};
        const s=specs[o.type]||specs.table;
        parts.push({name:(o.label||o.type)+" "+(i+1),type:"box",size:s.slice(0,3),pos:[x,s[1]/2+0.12,z],color:o.color||s[3]});
      }
    });
    build(parts,"Ev iç mekânı · "+(p.title||"Yeni proje"));
  }

  function renderHomePlan(p) {
    let el=document.getElementById("home-plan");
    if(!el){el=document.createElement("section");el.id="home-plan";document.body.appendChild(el);}
    p.objects=Array.isArray(p.objects)?p.objects:[];
    p.roomNames=Array.isArray(p.roomNames)?p.roomNames:["Salon","Mutfak","Yatak odası","Banyo","Çalışma odası","Antre","Çocuk odası","Depo"].slice(0,p.rooms);
    const W=720,H=520,pad=48,sx=(W-pad*2)/p.width,sy=(H-pad*2)/p.depth;
    const cols=Math.ceil(Math.sqrt(p.roomNames.length)),rows=Math.ceil(p.roomNames.length/cols),cw=p.width/cols,ch=p.depth/rows;
    const esc=s=>String(s).replace(/[&<>"']/g,c=>({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[c]));
    const cells=p.roomNames.map((name,i)=>{
      const x=pad+(i%cols)*cw*sx,y=pad+Math.floor(i/cols)*ch*sy;
      return '<g><rect x="'+x+'" y="'+y+'" width="'+(cw*sx)+'" height="'+(ch*sy)+'" fill="'+(p.floorColor||"#243746")+'" stroke="'+(p.wallColor||"#e4e0d8")+'" stroke-width="7"/><text x="'+(x+cw*sx/2)+'" y="'+(y+ch*sy/2)+'" fill="#fff" text-anchor="middle" dominant-baseline="middle" font-size="16">'+esc(name)+'</text><text x="'+(x+cw*sx/2)+'" y="'+(y+ch*sy/2+20)+'" fill="#a9d9e8" text-anchor="middle" font-size="10">'+cw.toFixed(1)+' × '+ch.toFixed(1)+' m</text></g>';
    }).join("");
    const objects=p.objects.map((o,i)=>{
      const x=pad+(o.x+p.width/2)*sx,y=pad+(o.z+p.depth/2)*sy;
      const color=o.type==="door"?"#d99b53":o.type==="window"?"#58d8ff":"#b9a2e8";
      const label=o.type==="door"?"K":o.type==="window"?"P":({sofa:"Koltuk",bed:"Yatak",table:"Masa",wardrobe:"Dolap",toilet:"Klozet",kitchen:"Mutfak",desk:"Çalışma",plant:"Bitki"}[o.type]||o.type);
      return '<g><rect x="'+(x-18)+'" y="'+(y-11)+'" width="36" height="22" rx="4" fill="'+color+'" stroke="#07131e" stroke-width="2"/><text x="'+x+'" y="'+(y+4)+'" fill="#07131e" text-anchor="middle" font-size="10">'+label+'</text></g>';
    }).join("");
    const opts=["sofa","bed","table","wardrobe","toilet","kitchen","desk","plant"].map(v=>'<option value="'+v+'">'+({sofa:"Koltuk",bed:"Yatak",table:"Masa",wardrobe:"Dolap",toilet:"Klozet",kitchen:"Mutfak tezgâhı",desk:"Çalışma masası",plant:"Bitki"}[v])+'</option>').join("");
    el.innerHTML='<div class="hd-head"><div><b>EV TASARIM STÜDYOSU</b><small>'+esc(p.title)+' · '+p.width+' × '+p.depth+' m · '+(p.width*p.depth).toFixed(1)+' m²</small></div><button id="hd-close">KAPAT ✕</button></div>'+
      '<div class="hd-toolbar"><label>Yerleştir <select id="hd-tool"><option value="select">Seçim</option><option value="door">Kapı</option><option value="window">Pencere</option>'+opts+'</select></label><label>Zemin <input id="hd-floor" type="color" value="'+(p.floorColor||"#8b7355")+'"></label><label>Duvar <input id="hd-wall" type="color" value="'+(p.wallColor||"#e4e0d8")+'"></label><label>Duvar yüksekliği <input id="hd-height" type="number" min="2.2" max="5" step=".1" value="'+(p.wallHeight||2.8)+'"></label>'+
      '<button id="hd-undo">Son öğeyi sil</button><button id="hd-save">Projeyi kaydet</button><button id="hd-load">Projeyi yükle</button><button id="hd-export">JSON dışa aktar</button><button id="hd-import">JSON içe aktar</button><input id="hd-import-file" type="file" accept="application/json,.json" hidden><button id="hd-3d">3D iç mekânı yenile</button><button id="hd-walk">İçeride gez</button><label>Odalar <input id="hd-rooms" value="'+esc(p.roomNames.join(", "))+'" size="34"></label><button id="hd-rooms-apply">Oda adlarını uygula</button></div>'+
      '<svg id="hd-plan" viewBox="0 0 '+W+' '+H+'" role="img" aria-label="Düzenlenebilir ölçülü ev planı"><rect x="'+pad+'" y="'+pad+'" width="'+(p.width*sx)+'" height="'+(p.depth*sy)+'" fill="#142534" stroke="#fff" stroke-width="8"/>'+cells+objects+'</svg>'+
      '<p>Plan üzerine tıklayarak seçtiğin kapı, pencere veya mobilyayı yerleştir. 3D görünümde fareyle döndürüp yakınlaştır. Proje bu tarayıcıda saklanır.</p>';
    el.classList.add("open");
    document.getElementById("hd-close").onclick=()=>el.classList.remove("open");
    document.getElementById("hd-plan").onclick=(ev)=>{
      if(ev.target.closest("text"))return;
      const rect=ev.currentTarget.getBoundingClientRect(),pt={x:(ev.clientX-rect.left)/rect.width*W,y:(ev.clientY-rect.top)/rect.height*H};
      const x=Math.max(-p.width/2,Math.min(p.width/2,(pt.x-pad)/sx-p.width/2));
      const z=Math.max(-p.depth/2,Math.min(p.depth/2,(pt.y-pad)/sy-p.depth/2));
      const type=document.getElementById("hd-tool").value;
      if(type==="select"){const near=p.objects.reduce((best,o,i)=>!best||Math.hypot(o.x-x,o.z-z)<best.d?{i,d:Math.hypot(o.x-x,o.z-z)}:best,null);if(near&&near.d<1.2){p.objects.splice(near.i,1);renderHomePlan(p);}return;}
      p.objects.push({type,x,z,label:type});renderHomePlan(p);
    };
    document.getElementById("hd-floor").onchange=e=>{p.floorColor=e.target.value;renderHomePlan(p);};
    document.getElementById("hd-wall").onchange=e=>{p.wallColor=e.target.value;renderHomePlan(p);};
    document.getElementById("hd-height").onchange=e=>{p.wallHeight=Math.max(2.2,Math.min(5,+e.target.value||2.8));renderHomePlan(p);};
    document.getElementById("hd-undo").onclick=()=>{p.objects.pop();renderHomePlan(p);};
    document.getElementById("hd-3d").onclick=()=>buildHome3D(p);
    document.getElementById("hd-walk").onclick=()=>action("walk");
    document.getElementById("hd-rooms-apply").onclick=()=>{p.roomNames=document.getElementById("hd-rooms").value.split(",").map(s=>s.trim()).filter(Boolean).slice(0,16);p.rooms=p.roomNames.length;renderHomePlan(p);buildHome3D(p);};
    document.getElementById("hd-save").onclick=()=>{try{localStorage.setItem("jarvis.homeDesign",JSON.stringify(p));JV.toast&&JV.toast("Ev projesi kaydedildi.");}catch(e){JV.toast&&JV.toast("Proje kaydedilemedi.");}};
    document.getElementById("hd-load").onclick=()=>{try{const saved=JSON.parse(localStorage.getItem("jarvis.homeDesign")||"null");if(saved){p= saved;renderHomePlan(p);buildHome3D(p);}else JV.toast&&JV.toast("Kayıtlı proje bulunamadı.");}catch(e){JV.toast&&JV.toast("Kayıt okunamadı.");}};
    document.getElementById("hd-export").onclick=()=>{const blob=new Blob([JSON.stringify(p,null,2)],{type:"application/json"}),url=URL.createObjectURL(blob),a=document.createElement("a");a.href=url;a.download="jarvis-ev-projesi.json";a.click();URL.revokeObjectURL(url);};
     document.getElementById("hd-import").onclick=()=>document.getElementById("hd-import-file").click();
     document.getElementById("hd-import-file").onchange=async e=>{const file=e.target.files&&e.target.files[0];if(!file)return;try{const data=JSON.parse(await file.text());if(!data||!Array.isArray(data.roomNames)||!Array.isArray(data.objects)||!Number.isFinite(+data.width)||!Number.isFinite(+data.depth))throw new Error("invalid");p=Object.assign({},data);renderHomePlan(p);buildHome3D(p);JV.toast&&JV.toast("Ev projesi içe aktarıldı.");}catch(err){JV.toast&&JV.toast("JSON proje dosyası geçersiz.");}e.target.value="";};
  }

  // ---- yüzen panel ----
  function renderPanel() {
    const p = document.getElementById("holo-panel");
    if (!model) { p.classList.add("hidden"); return; }
    const inner = model.children[0];
    const names = inner.children.filter((c) => c.userData.name).map((c, i) => `<li data-i="${i}">${c.userData.name}</li>`).join("");
    p.innerHTML = `<div class="hp-title">${title}</div><div class="hp-sub">${inner.children.length} parça · ${U.fmt(model.userData.size.x, 1)}×${U.fmt(model.userData.size.y, 1)}×${U.fmt(model.userData.size.z, 1)}</div>
      <div class="hp-btns"><button class="mini" data-a="explode">PARÇALA</button><button class="mini" data-a="assemble">BİRLEŞTİR</button><button class="mini" data-a="rotate">DÖNDÜR</button><button class="mini" data-a="wireframe">TEL KAFES</button><button class="mini" data-a="export_stl">STL KAYDET</button><button class="mini" data-a="clear">TEMİZLE</button></div>
      <ul class="hp-parts">${names}</ul>`;
    p.classList.remove("hidden");
    p.querySelectorAll("[data-a]").forEach((b) => (b.onclick = () => action(b.dataset.a)));
    p.querySelectorAll("li").forEach((li) => (li.onclick = () => select(inner.children.filter((c) => c.userData.name)[+li.dataset.i])));
  }

  function select(m) {
    if (selected) selected.userData.edges.material.color.set(selected.userData.edgeColor || 0xffffff);
    selected = m;
    if (!m) return;
    m.userData.edgeColor = m.userData.edges.material.color.getHex();
    m.userData.edges.material.color.set(0xffd34d);
    U.caption(m.userData.name); setTimeout(() => U.caption(""), 2500);
  }

  function action(a, v) {
    if (a === "walk") {
      walkMode = true; autoRotate = false;
      const from=camera.position.clone(),to=new T.Vector3(0,0.85,1.15);
      U.tween(700,e=>camera.position.lerpVectors(from,to,e));
      if(controls&&controls.target){controls.target.set(0,0.8,0);controls.update();}
      U.caption("İç mekân görünümü · fareyle bakış yönünü değiştir");
    } else if (a === "explode") explodeTarget = v ? +v : 1;
    else if (a === "assemble") explodeTarget = 0;
    else if (a === "rotate") autoRotate = v === "" || v == null ? !autoRotate : /on|aç|true|1/.test(v);
    else if (a === "wireframe") { wire = !wire; if (model) model.traverse((o) => o.userData.fill && (o.userData.fill.visible = !wire)); }
    else if (a === "clear") { clear(); renderPanel(); }
    else if (a === "view") {
      const d = 7, pos = { front: [0, 1.6, d], top: [0, d + 1, 0.01], side: [d, 1.6, 0], iso: [d * 0.7, d * 0.6, d * 0.7] }[v || "iso"] || [d * 0.7, d * 0.6, d * 0.7];
      const from = camera.position.clone(), to = new T.Vector3(...pos);
      U.tween(900, (e) => camera.position.lerpVectors(from, to, e));
    } else if (a === "scale" && model) model.scale.multiplyScalar(+v || 1.2);
    else if (a === "export_stl" && model) {
      const exp = new T.STLExporter(), only = new T.Group();
      model.updateMatrixWorld(true);
      model.traverse((o) => { if (o.isMesh && o.parent && o.parent.userData.fill === o) { const m = new T.Mesh(o.geometry.clone().applyMatrix4(o.matrixWorld)); only.add(m); } });
      const stl = exp.parse(only);
      fetch(`/api/holo/save?name=${encodeURIComponent(title)}`, { method: "POST", headers: { "x-token": JV.token || "" }, body: stl })
        .then((r) => r.json()).then((j) => JV.toast && JV.toast("STL kaydedildi: " + (j.path || j.error)));
    }
  }

  // ---- el hareketiyle tutma ----
  let grab = null;
  JV.lab = {
    grab(on, sx, sy) {
      if (!model) return;
      if (on) {
        const ray = JV.pickAt(sx, sy);
        const hit = ray.intersectObjects(model.children[0].children, true).find((h) => h.object.parent && h.object.parent.userData.name);
        grab = hit ? { obj: hit.object.parent, sx, sy, start: hit.object.parent.position.clone() } : { obj: model, sx, sy, start: model.position.clone() };
        if (hit) select(hit.object.parent);
      } else grab = null;
    },
    move(sx, sy) {
      if (!grab) return;
      const k = (grab.obj === model ? 0.012 : 0.012 / model.scale.x) * camera.position.distanceTo(controls.target) / 7;
      const right = new T.Vector3().setFromMatrixColumn(camera.matrixWorld, 0), up = new T.Vector3().setFromMatrixColumn(camera.matrixWorld, 1);
      grab.obj.position.copy(grab.start).addScaledVector(right, (sx - grab.sx) * k).addScaledVector(up, -(sy - grab.sy) * k);
    },
    rotate(dx, dy) { if (model) { model.rotation.y += dx; model.rotation.x = Math.max(-0.8, Math.min(0.8, model.rotation.x + dy)); autoRotate = false; } },
    scale(f) { if (model) model.scale.multiplyScalar(f); },
    action,
  };

  window.addEventListener("keydown", e => { if (!walkMode) return; if (["KeyW","KeyA","KeyS","KeyD","ArrowUp","ArrowDown","ArrowLeft","ArrowRight"].includes(e.code)) { walkKeys[e.code]=true; e.preventDefault(); } if (e.code==="Escape") walkMode=false; });
  window.addEventListener("keyup", e => { if (walkMode) walkKeys[e.code]=false; });
  window.addEventListener("blur", () => { walkKeys=Object.create(null); });

  JV.worlds.lab = {
    scene,
    enter() {
      controls.minDistance = 2; controls.maxDistance = 30; controls.enablePan = true; controls.rotateSpeed = 0.8; controls.zoomSpeed = 1;
      controls.target.set(0, 1.4, 0); camera.position.set(5, 4.2, 6.5); tint();
      if (!model) build(D.robot({}), "Holografik robot (örnek)");
      renderPanel();
    },
    exit() { walkMode=false; walkKeys=Object.create(null); document.getElementById("holo-panel").classList.add("hidden"); },
    update(dt, t) {
      if (walkMode) {
        const forward = new T.Vector3(); camera.getWorldDirection(forward); forward.y = 0; forward.normalize();
        const right = new T.Vector3().crossVectors(forward, new T.Vector3(0,1,0)).normalize();
        const move = new T.Vector3();
        if (walkKeys.KeyW || walkKeys.ArrowUp) move.add(forward);
        if (walkKeys.KeyS || walkKeys.ArrowDown) move.sub(forward);
        if (walkKeys.KeyD || walkKeys.ArrowRight) move.add(right);
        if (walkKeys.KeyA || walkKeys.ArrowLeft) move.sub(right);
        if (move.lengthSq()) { move.normalize().multiplyScalar(dt * 1.8); camera.position.add(move); if (controls.target) controls.target.add(move); camera.position.y = 0.85; if (controls.target) controls.target.y = 0.8; }
      }
      rings[0].rotation.z += dt * 0.3; rings[1].rotation.z -= dt * 0.2;
      beam.material.opacity = 0.03 + 0.015 * Math.sin(t * 2);
      if (model) {
        if (autoRotate && !grab) model.rotation.y += dt * 0.25;
        explodeK += (explodeTarget - explodeK) * Math.min(1, dt * 4);
        const inner = model.children[0];
        const ext = Math.max(...(model.userData.size ? [model.userData.size.x, model.userData.size.y, model.userData.size.z] : [3])) / model.scale.x;
        inner.children.forEach((m) => {
          if (m.userData.home && m.userData.dir && !(grab && grab.obj === m)) m.position.copy(m.userData.home).addScaledVector(m.userData.dir, explodeK * ext * 0.22);
          if (/pervane/.test(m.userData.name || "")) m.rotation.y += dt * 25;
        });
      }
    },
    click(ray) {
      if (!model) return;
      const hit = ray.intersectObjects(model.children[0].children, true).find((h) => h.object.parent && h.object.parent.userData.name);
      select(hit ? hit.object.parent : null);
    },
    cmd(ui, r, args) {
      if (ui === "holo_design") { const f = D[r.kind] || D.robot; build(f(r.params || {}), ({ building: "Gökdelen", house: "Ev", car: "Araç", robot: "Robot", arm: "Robot kol", rover: "Gezgin robot", rocket: "Roket", bridge: "Köprü", table: "Masa", drone: "Dron" })[r.kind] || r.kind); }
      else if (ui === "home_design") {
        const p = r.params || {};
        const width = Math.max(4, Math.min(30, Number(p.width) || 10));
        const depth = Math.max(4, Math.min(30, Number(p.depth) || 8));
        const rooms = Math.max(2, Math.min(8, Number(p.rooms) || 4));
        const plan = { width, depth, rooms, title: r.title || "Yeni ev", style: p.style || "Modern", roomNames: Array.isArray(p.roomNames) ? p.roomNames.slice(0, 16) : ["Salon","Mutfak","Yatak odası","Banyo","Çalışma odası","Antre","Çocuk odası","Depo"].slice(0, rooms), objects: Array.isArray(p.objects) ? p.objects : [], wallHeight: Number(p.wallHeight) || 2.8, wallColor: p.wallColor || "#e4e0d8", floorColor: p.floorColor || "#8b7355" };
        buildHome3D(plan);
        renderHomePlan(plan);
      }
      else if (ui === "holo_scene") { let parts = args.parts; try { parts = typeof parts === "string" ? JSON.parse(parts) : parts; } catch (e) { return; } build(parts, r.title || args.title); }
      else if (ui === "holo_action") action(r.action, r.value);
      else if (ui === "holo_model") loadModel(r.url, r.ext, r.ad);
      else if (ui === "chart3d") { let d = args.data; try { d = typeof d === "string" ? JSON.parse(d) : d; } catch (e) { return; } chart3d(r.title || args.title, d); }
    },
    designs: D,
    build,
  };
})();
