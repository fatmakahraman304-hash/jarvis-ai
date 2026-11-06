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


  function buildHome3DParts(p) {
    const width = p.width, depth = p.depth, height = Number(p.wallHeight) || 2.8;
    const rooms = p.roomNames || ["Salon", "Mutfak", "Yatak odası", "Banyo", "Çalışma odası", "Antre"].slice(0, p.rooms);
    const cols = Math.ceil(Math.sqrt(rooms.length)), rows = Math.ceil(rooms.length / cols);
    const cw = width / cols, ch = depth / rows, wall = 0.12, parts = [];
    const floorColor = p.floorColor || "#8b7355", wallColor = p.wallColor || "#e4e0d8";
    p.wires=Array.isArray(p.wires)?p.wires:[];
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
    // Serbest çizilen duvarlar, 2D plandaki koordinatlarla aynı ölçekte 3D'ye aktarılır.
    (p.walls||[]).forEach((w,i)=>{
      const thickness=Math.max(0.06,Number(w.thickness)||wall),steps=w.cx!=null&&w.cz!=null?16:1;
      let prev={x:Number(w.x1),z:Number(w.z1)};
      for(let j=1;j<=steps;j++){
        const t=j/steps,point=w.cx!=null&&w.cz!=null?{x:(1-t)*(1-t)*Number(w.x1)+2*(1-t)*t*Number(w.cx)+t*t*Number(w.x2),z:(1-t)*(1-t)*Number(w.z1)+2*(1-t)*t*Number(w.cz)+t*t*Number(w.z2)}:{x:Number(w.x2),z:Number(w.z2)};
        const dx=point.x-prev.x,dz=point.z-prev.z,len=Math.hypot(dx,dz);
        if(len>=0.04)parts.push({name:"Serbest duvar "+(i+1)+" · "+j,type:"box",size:[len,height,thickness],pos:[(prev.x+point.x)/2,height/2+0.12,(prev.z+point.z)/2],rot:[0,-Math.atan2(dz,dx)/DEG,0],color:w.color||wallColor});
        prev=point;
      }
    });
    p.wires.forEach((w,i)=>{const dx=Number(w.x2)-Number(w.x1),dz=Number(w.z2)-Number(w.z1),len=Math.hypot(dx,dz);if(len<0.05)return;const angle=Math.atan2(dz,dx);parts.push({name:"Elektrik hattı "+(i+1),type:"box",size:[len,0.025,0.025],pos:[(Number(w.x1)+Number(w.x2))/2,Number(w.height)||2.45,(Number(w.z1)+Number(w.z2))/2],rot:[0,-angle/DEG,0],color:w.color||"#f5c542"});});
    if(p.roofOn) parts.push({name:"Çatı döşemesi",type:"box",size:[width+0.35,0.18,depth+0.35],pos:[0,height+0.21,0],color:p.roofColor||"#596a7b"});
    // Mobilya ölçüleri ve dönüş açıları 2D editördeki değerlerle eşleşir.
    (p.objects||[]).forEach((o,i)=>{
      const x=Number(o.x)||0,z=Number(o.z)||0;
      if(o.type==="door") parts.push({name:"Kapı kasası "+(i+1),type:"box",size:[0.07,2.1,0.08],pos:[x-0.46,1.17,z],color:"#80502f"},{name:"Kapı kanadı "+(i+1),type:"box",size:[0.88,2.0,0.045],pos:[x-0.44,1.12,z],rot:[0,-(Number(o.rotation)||0),0],color:o.color||"#a66b3f",hinge:true});
      else if(o.type==="window") { /* Cam ve duvar açıklığı addWall içinde üretilir. */ }
      else if(o.type==="stairs") {
        const ow=Math.max(0.8,Number(o.width)||1),od=Math.max(1.2,Number(o.depth)||2),count=Math.max(6,Math.min(24,Math.ceil(height/0.19))),rise=(height+0.3)/count,run=od/count,angle=-(Number(o.rotation)||0)*DEG,cos=Math.cos(angle),sin=Math.sin(angle),color=o.color||"#9d8063";
        const local=(lx,lz)=>[x+lx*cos+lz*sin,z-lx*sin+lz*cos];
        for(let step=0;step<count;step++){
          const lz=-od/2+(step+0.5)*run,[px,pz]=local(0,lz);
          parts.push({name:"Merdiven "+(i+1)+" · basamak "+(step+1),type:"box",size:[ow,rise,run+0.025],pos:[px,0.12+(step+0.5)*rise,pz],rot:[0,angle/DEG,0],color});
        }
        const railLength=Math.hypot(od,height+0.3),railTilt=Math.atan2(height+0.3,od)/DEG;
        [-1,1].forEach(side=>{
          const [rx,rz]=local(side*(ow/2-0.04),0);
          parts.push({name:"Merdiven korkuluğu "+(i+1),type:"box",size:[0.07,0.08,railLength],pos:[rx,0.12+(height+0.3)/2+0.48,rz],rot:[-railTilt,angle/DEG,0],color:"#d6dce1"});
          for(let post=0;post<=4;post++){
            const t=post/4,lz=-od/2+t*od,lx=side*(ow/2-0.04),[qx,qz]=local(lx,lz);
            parts.push({name:"Korkuluk dikmesi",type:"box",size:[0.045,0.95,0.045],pos:[qx,0.12+t*(height+0.3)+0.42,qz],rot:[0,angle/DEG,0],color:"#d6dce1"});
          }
        });
      } else {
        const specs={sofa:[1.9,0.75,0.85,"#657b8d"],bed:[1.6,0.45,2.0,"#b7a0c9"],table:[1.2,0.75,0.8,"#a8794f"],wardrobe:[1.1,2.1,0.6,"#8d735f"],toilet:[0.48,0.42,0.68,"#f0f4f5"],kitchen:[1.8,0.9,0.65,"#777f87"],desk:[1.2,0.75,0.65,"#9b744d"],plant:[0.45,0.9,0.45,"#39875c"],fridge:[0.7,1.9,0.7,"#c8d2d8"],shower:[0.9,2.0,0.9,"#8acbdc"],sink:[0.6,0.85,0.5,"#e5edf0"],stairs:[1.0,2.8,2.0,"#9d8063"],pool:[3,0.6,2,"#3c9dc4"],tree:[1,2.8,1,"#39875c"],fence:[2,1.2,0.12,"#9b7852"],gate:[1,1.2,0.12,"#a66b3f"],light:[0.25,0.12,0.25,"#ffe08a"],outlet:[0.12,0.12,0.05,"#d9e5ed"],switch:[0.1,0.15,0.04,"#e7e7e7"],radiator:[0.8,0.65,0.15,"#e5edf0"]};
        const s=specs[o.type]||specs.table,ow=Math.max(.1,Number(o.width)||s[0]),od=Math.max(.1,Number(o.depth)||s[2]);
        parts.push({name:(o.label||o.type)+" "+(i+1),type:"box",size:[ow,s[1],od],pos:[x,s[1]/2+0.12,z],rot:[0,-(Number(o.rotation)||0),0],color:o.color||s[3]});
      }
    });
    return {parts,height};
  }

  function buildHome3D(p) {
    const levels=Array.isArray(p.levels)&&p.levels.length?p.levels:[p];
    const active=Math.max(0,Math.min(levels.length-1,Number(p.activeFloor)||0));
    const all=[];let totalHeight=0;
    levels.forEach((stored,index)=>{
      const level=index===active?Object.assign({},stored,p):Object.assign({},stored);
      const generated=buildHome3DParts(level),offset=levels.slice(0,index).reduce((sum,v)=>sum+(Number(v.wallHeight)||2.8)+0.3,0);
      generated.parts.forEach(part=>{const copy=Object.assign({},part,{pos:part.pos.slice()});copy.pos[1]+=offset;copy.name="Kat "+(index+1)+" · "+part.name;all.push(copy);});
      totalHeight=Math.max(totalHeight,offset+generated.height);
    });
    build(all,"Çok katlı ev · "+(p.title||"Yeni proje"));
  }

  function renderHomePlan(p) {
    let el=document.getElementById("home-plan");
    if(!el){el=document.createElement("section");el.id="home-plan";document.body.appendChild(el);}
    p.objects=Array.isArray(p.objects)?p.objects:[];
    p.walls=Array.isArray(p.walls)?p.walls:[];
    p.roomNames=Array.isArray(p.roomNames)?p.roomNames:["Salon","Mutfak","Yatak odası","Banyo","Çalışma odası","Antre"].slice(0,p.rooms||6);
    p.width=Math.max(4,Math.min(30,Number(p.width)||10));p.depth=Math.max(4,Math.min(30,Number(p.depth)||8));
    p.activeFloor=Math.max(0,Number(p.activeFloor)||0);
    const levelFields=["width","depth","roomNames","objects","walls","floorColor","wallColor","roofColor","roofOn","wallHeight"];
    const levelSnapshot=()=>Object.fromEntries(levelFields.map(k=>[k,Array.isArray(p[k])?JSON.parse(JSON.stringify(p[k])):p[k]]));
    if(!Array.isArray(p.levels)||!p.levels.length)p.levels=[levelSnapshot()];
    if(p.activeFloor>=p.levels.length)p.activeFloor=p.levels.length-1;
    const saveFloor=()=>{p.levels[p.activeFloor]=levelSnapshot();};
    const W=900,H=620,pad=58,sx=(W-pad*2)/p.width,sy=(H-pad*2)/p.depth;
    const cols=Math.ceil(Math.sqrt(p.roomNames.length)),rows=Math.ceil(p.roomNames.length/cols),cw=p.width/cols,ch=p.depth/rows;
    const esc=s=>String(s).replace(/[&<>"']/g,c=>({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[c]));
    const xy=(x,z)=>({x:pad+(x+p.width/2)*sx,y:pad+(z+p.depth/2)*sy});
    const selected=Number.isInteger(p.selectedObject)?p.selectedObject:-1;
    const selectedWall=Number.isInteger(p.selectedWall)?p.selectedWall:-1;
    const cells=p.roomNames.map((name,i)=>{
      const x=pad+(i%cols)*cw*sx,y=pad+Math.floor(i/cols)*ch*sy;
      return '<g class="hd-room"><rect x="'+x+'" y="'+y+'" width="'+(cw*sx)+'" height="'+(ch*sy)+'" fill="'+(p.floorColor||"#8b7355")+'" fill-opacity=".55" stroke="'+(p.wallColor||"#e4e0d8")+'" stroke-width="5"/><text x="'+(x+cw*sx/2)+'" y="'+(y+ch*sy/2)+'" fill="#fff" text-anchor="middle" dominant-baseline="middle" font-size="15">'+esc(name)+'</text><text x="'+(x+cw*sx/2)+'" y="'+(y+ch*sy/2+20)+'" fill="#b7d7e7" text-anchor="middle" font-size="10">'+cw.toFixed(2)+' × '+ch.toFixed(2)+' m · '+(cw*ch).toFixed(1)+' m²</text></g>';
    }).join("");
    const objects=p.objects.map((o,i)=>{
      const q=xy(o.x,o.z),w=Math.max(0.25,Number(o.width)||0.9)*sx,h=Math.max(0.25,Number(o.depth)||0.55)*sy;
      const color=o.color||({door:"#d99b53",window:"#58d8ff",sofa:"#8b9bab",bed:"#b9a2d5",plant:"#5ba879",light:"#ffe08a",outlet:"#d9e5ed"}[o.type]||"#b9a2e8");
      const label=({door:"Kapı",window:"Pencere",sofa:"Koltuk",bed:"Yatak",table:"Masa",wardrobe:"Dolap",toilet:"Klozet",kitchen:"Mutfak",desk:"Çalışma",plant:"Bitki",stairs:"Merdiven",pool:"Havuz",tree:"Ağaç",light:"Lamba",outlet:"Priz",switch:"Anahtar",radiator:"Petek",fridge:"Buzdolabı",shower:"Duş",sink:"Lavabo",fence:"Çit",gate:"Kapı"}[o.type]||o.type);
      const stroke=i===selected?"#ffe17b":"#102331";
      return '<g class="hd-object" data-index="'+i+'" transform="translate('+q.x+' '+q.y+') rotate('+(Number(o.rotation)||0)+')" style="cursor:move"><rect x="'+(-w/2)+'" y="'+(-h/2)+'" width="'+w+'" height="'+h+'" rx="4" fill="'+color+'" fill-opacity=".92" stroke="'+stroke+'" stroke-width="'+(i===selected?4:2)+'"/><text x="0" y="4" fill="#101b24" text-anchor="middle" font-size="10" pointer-events="none">'+esc(label)+'</text></g>';
    }).join("");
    const wires=(p.wires||[]).map((w,i)=>{const a=xy(w.x1,w.z1),b=xy(w.x2,w.z2);return "<line data-wire=\""+i+"\" x1=\""+a.x+"\" y1=\""+a.y+"\" x2=\""+b.x+"\" y2=\""+b.y+"\" stroke=\""+(w.color||"#f5c542")+"\" stroke-width=\"3\" stroke-dasharray=\"7 4\" style=\"cursor:pointer\"/>";}).join("");
    const walls=p.walls.map((w,i)=>{const a=xy(w.x1,w.z1),b=xy(w.x2,w.z2),stroke=i===selectedWall?"#ffd66b":(w.color||p.wallColor||"#e4e0d8"),width=Math.max(0.06,Number(w.thickness)||0.12)*Math.min(sx,sy);if(w.cx!=null&&w.cz!=null){const q=xy(w.cx,w.cz);return '<path data-wall="'+i+'" d="M '+a.x+' '+a.y+' Q '+q.x+' '+q.y+' '+b.x+' '+b.y+'" fill="none" stroke="'+stroke+'" stroke-width="'+width+'" stroke-linecap="round" style="cursor:pointer"/>';}return '<line data-wall="'+i+'" x1="'+a.x+'" y1="'+a.y+'" x2="'+b.x+'" y2="'+b.y+'" stroke="'+stroke+'" stroke-width="'+width+'" stroke-linecap="square" style="cursor:pointer"/>';}).join("");
    const dims='<g fill="#bce9f5" font-size="12"><text x="'+(W/2)+'" y="28" text-anchor="middle">'+p.width.toFixed(2)+' m</text><text x="20" y="'+(H/2)+'" transform="rotate(-90 20 '+(H/2)+')" text-anchor="middle">'+p.depth.toFixed(2)+' m</text></g>';
    const opts=["sofa","bed","table","wardrobe","toilet","kitchen","desk","plant","fridge","shower","sink","stairs","pool","tree","fence","gate","light","outlet","switch","radiator"].map(v=>'<option value="'+v+'">'+({sofa:"Koltuk",bed:"Yatak",table:"Masa",wardrobe:"Dolap",toilet:"Klozet",kitchen:"Mutfak tezgâhı",desk:"Çalışma masası",plant:"Bitki",fridge:"Buzdolabı",shower:"Duş",sink:"Lavabo",stairs:"Merdiven",pool:"Havuz",tree:"Ağaç",fence:"Çit",gate:"Bahçe kapısı",light:"Aydınlatma",outlet:"Priz",switch:"Anahtar",radiator:"Petek"}[v])+'</option>').join("");
    const tools='<option value="select">Seç / taşı</option><option value="wall">Düz duvar çiz</option><option value="curve">Eğri duvar çiz</option><option value="wire">Elektrik hattı çiz</option><option value="door">Kapı</option><option value="window">Pencere</option>'+opts;
    const area=p.width*p.depth;
    el.innerHTML='<style>#home-plan{position:fixed;inset:3vh 3vw;z-index:10020;background:#101d29;color:#eaf6ff;border:1px solid #3a6075;border-radius:16px;padding:14px;overflow:auto;box-shadow:0 20px 80px #000b;font:13px system-ui}#home-plan .hd-head{display:flex;justify-content:space-between;align-items:center;gap:12px;margin-bottom:10px}#home-plan .hd-head b{font-size:18px;letter-spacing:.08em}#home-plan small{display:block;color:#9db7c8;margin-top:4px}#home-plan .hd-toolbar{display:flex;flex-wrap:wrap;gap:8px;align-items:center;margin:10px 0}#home-plan label{display:inline-flex;align-items:center;gap:5px;color:#c8dce8}#home-plan button,#home-plan select,#home-plan input{background:#203747;color:#eaf6ff;border:1px solid #45677a;border-radius:7px;padding:7px}#home-plan input[type=color]{width:38px;height:30px;padding:2px}#home-plan input[type=number]{width:76px}#home-plan svg{display:block;width:100%;max-height:66vh;background:#142534;border:1px solid #34556a;border-radius:10px;touch-action:none}#home-plan .hd-help{color:#9bb6c7;font-size:12px;margin:8px 2px}#home-plan .hd-side{display:flex;gap:8px;flex-wrap:wrap;align-items:center}#home-plan .hd-selected{border-color:#e9c66c!important}#home-plan .hd-hidden{display:none}</style>'+
      '<div class="hd-head"><div><b>EV TASARIM STÜDYOSU · PRO</b><small>'+esc(p.title||"Yeni proje")+' · '+p.width.toFixed(2)+' × '+p.depth.toFixed(2)+' m · '+area.toFixed(1)+' m² brüt alan · '+p.objects.length+' öğe</small></div><button id="hd-close">KAPAT ✕</button></div>'+
      '<div class="hd-toolbar"><label>Kat <select id="hd-floor-level">'+p.levels.map((v,i)=>'<option value="'+i+'" '+(i===p.activeFloor?'selected':'')+'>'+(i+1)+'. Kat</option>').join("")+'</select></label><button id="hd-add-floor">+ Kat ekle</button><label>Araç <select id="hd-tool">'+tools+'</select></label><label>En <input id="hd-width" type="number" min="4" max="30" step=".1" value="'+p.width+'"> m</label><label>Boy <input id="hd-depth" type="number" min="4" max="30" step=".1" value="'+p.depth+'"> m</label><label>Duvar yüksekliği <input id="hd-height" type="number" min="2.2" max="5" step=".1" value="'+(p.wallHeight||2.8)+'"> m</label><label>Izgara <select id="hd-snap"><option value="0.1">10 cm</option><option value="0.25">25 cm</option><option value="0.5">50 cm</option><option value="1">1 m</option><option value="0">Kapalı</option></select></label></div>'+
      '<div class="hd-toolbar"><label>Zemin <input id="hd-floor" type="color" value="'+(p.floorColor||"#8b7355")+'"></label><label>Duvar <input id="hd-wall" type="color" value="'+(p.wallColor||"#e4e0d8")+'"></label><label>Çatı <input id="hd-roof" type="color" value="'+(p.roofColor||"#596a7b")+'"></label><label><input id="hd-roof-on" type="checkbox" '+(p.roofOn?"checked":"")+'> Çatı göster</label><label><input id="hd-labels" type="checkbox" '+(p.showLabels===false?"":"checked")+'> Oda etiketleri</label><label><input id="hd-dims" type="checkbox" '+(p.showDimensions===false?"":"checked")+'> Ölçüler</label><label><input id="hd-furniture" type="checkbox" '+(p.showFurniture===false?"":"checked")+'> Mobilyalar</label></div>'+
      '<div class="hd-toolbar"><button id="hd-undo">↶ Geri al</button><button id="hd-redo">↷ Yinele</button><button id="hd-duplicate">Kopyala</button><button id="hd-rotate">90° döndür</button><button id="hd-delete">Öğeyi sil</button><button id="hd-wall-delete">Seçili duvarı sil</button><label>Seçili öğe <input id="hd-label" placeholder="Öğe adı" value="'+esc(selected>=0&&p.objects[selected]?p.objects[selected].label||"":"")+'"></label><label>En <input id="hd-obj-w" type="number" min=".1" max="10" step=".05" value="'+(selected>=0&&p.objects[selected]?(p.objects[selected].width||.9):.9)+'"></label><label>Boy <input id="hd-obj-d" type="number" min=".1" max="10" step=".05" value="'+(selected>=0&&p.objects[selected]?(p.objects[selected].depth||.55):.55)+'"></label><label>Renk <input id="hd-obj-color" type="color" value="'+(selected>=0&&p.objects[selected]&&/^#[0-9a-f]{6}$/i.test(p.objects[selected].color||"")?p.objects[selected].color:"#b9a2e8")+'"></label></div>'+
      '<div class="hd-toolbar"><button id="hd-save">Projeyi kaydet</button><button id="hd-load">Projeyi yükle</button><button id="hd-export">JSON</button><button id="hd-svg">SVG plan</button><button id="hd-dxf">DXF CAD</button><button id="hd-print">Yazdır / PDF</button><button id="hd-import">JSON içe aktar</button><input id="hd-import-file" type="file" accept="application/json,.json" hidden><button id="hd-photo">Plan fotoğrafı</button><input id="hd-photo-file" type="file" accept="image/png,image/jpeg,image/webp" hidden><button id="hd-3d">3D görünümü yenile</button><button id="hd-walk">İçeride gez</button><label>Odalar <input id="hd-rooms" value="'+esc(p.roomNames.join(", "))+'" size="28"></label><button id="hd-rooms-apply">Uygula</button></div>'+
      '<svg id="hd-plan" viewBox="0 0 '+W+' '+H+'" role="img" aria-label="Ölçülü ev planı"><rect x="'+pad+'" y="'+pad+'" width="'+(p.width*sx)+'" height="'+(p.depth*sy)+'" fill="#172a38" stroke="#fff" stroke-width="7"/>'+(p.referenceImage?'<image href="'+p.referenceImage+'" x="'+pad+'" y="'+pad+'" width="'+(p.width*sx)+'" height="'+(p.depth*sy)+'" opacity=".28" preserveAspectRatio="none"/>':'')+'<g id="hd-grid" opacity=".18">'+Array.from({length:Math.floor(p.width*2)+1},(_,i)=>'<line x1="'+(pad+i*sx/2)+'" y1="'+pad+'" x2="'+(pad+i*sx/2)+'" y2="'+(H-pad)+'" stroke="#8fb0c2" stroke-width=".6"/>').join("")+Array.from({length:Math.floor(p.depth*2)+1},(_,i)=>'<line x1="'+pad+'" y1="'+(pad+i*sy/2)+'" x2="'+(W-pad)+'" y2="'+(pad+i*sy/2)+'" stroke="#8fb0c2" stroke-width=".6"/>').join("")+'</g><g id="hd-rooms-layer" '+(p.showLabels===false?'class="hd-hidden"':'')+'>'+cells+'</g><g id="hd-walls-layer">'+walls+'</g><g id="hd-wires-layer">'+wires+'</g><g id="hd-objects-layer" '+(p.showFurniture===false?'class="hd-hidden"':'')+'>'+objects+'</g><g id="hd-dims-layer" '+(p.showDimensions===false?'class="hd-hidden"':'')+'>'+dims+'</g></svg>'+
      '<div class="hd-help" id="hd-status">Mobilyayı sürükleyerek taşı. Duvar çizmek için araçtan “Serbest duvar çiz” seç, başlangıç ve bitiş noktalarına tıkla. Öğeyi seçip ölçüsünü, rengini ve yönünü değiştirebilirsin. Ctrl+Z geri al · Ctrl+Y yinele · Delete sil.</div>';
    el.classList.add("open");
    const by=id=>document.getElementById(id), redraw=()=>renderHomePlan(p), snap=Number(by("hd-snap").value);
    const remember=()=>{try{const key="jarvis.homeDesign.history";const h=JSON.parse(localStorage.getItem(key)||"[]");h.push(JSON.stringify(p));localStorage.setItem(key,JSON.stringify(h.slice(-30)));localStorage.removeItem("jarvis.homeDesign.redo");}catch(e){}};
    const updateObject=fn=>{const o=p.objects[p.selectedObject];if(!o)return;remember();fn(o);redraw();};
    by("hd-close").onclick=()=>el.classList.remove("open");
    by("hd-floor-level").onchange=e=>{saveFloor();const next=Number(e.target.value);if(p.levels[next]){Object.assign(p,p.levels[next]);p.activeFloor=next;redraw();buildHome3D(p);}};
    by("hd-add-floor").onclick=()=>{saveFloor();p.levels.push({width:p.width,depth:p.depth,roomNames:["Yeni kat"],objects:[],walls:[],floorColor:p.floorColor,wallColor:p.wallColor,roofColor:p.roofColor,roofOn:false,wallHeight:p.wallHeight});p.activeFloor=p.levels.length-1;Object.assign(p,p.levels[p.activeFloor]);redraw();};
    by("hd-photo").onclick=()=>by("hd-photo-file").click();
    by("hd-photo-file").onchange=e=>{const file=e.target.files&&e.target.files[0];if(!file)return;if(file.size>5*1024*1024){JV.toast&&JV.toast("Referans görseli en fazla 5 MB olabilir.");e.target.value="";return;}const reader=new FileReader();reader.onload=()=>{p.referenceImage=String(reader.result);redraw();};reader.readAsDataURL(file);e.target.value="";};
    by("hd-plan").addEventListener("pointerdown",ev=>{
      const svg=ev.currentTarget,rect=svg.getBoundingClientRect(),pt={x:(ev.clientX-rect.left)/rect.width*W,y:(ev.clientY-rect.top)/rect.height*H};
      const x0=(pt.x-pad)/sx-p.width/2,z0=(pt.y-pad)/sy-p.depth/2,grid=Number(by("hd-snap").value),x=Math.max(-p.width/2,Math.min(p.width/2,grid?Math.round(x0/grid)*grid:x0)),z=Math.max(-p.depth/2,Math.min(p.depth/2,grid?Math.round(z0/grid)*grid:z0));
      const target=ev.target.closest("[data-index]");
      if(target){
        const index=Number(target.dataset.index);p.selectedObject=index;p.selectedWall=-1;remember();
        const move=(e)=>{const q=svg.getBoundingClientRect(),px=(e.clientX-q.left)/q.width*W,pz=(e.clientY-q.top)/q.height*H,g=Number(by("hd-snap").value);p.objects[index].x=Math.max(-p.width/2,Math.min(p.width/2,(px-pad)/sx-p.width/2));p.objects[index].z=Math.max(-p.depth/2,Math.min(p.depth/2,(pz-pad)/sy-p.depth/2));if(g){p.objects[index].x=Math.round(p.objects[index].x/g)*g;p.objects[index].z=Math.round(p.objects[index].z/g)*g;}};
        const up=()=>{svg.removeEventListener("pointermove",move);window.removeEventListener("pointerup",up);redraw();};svg.setPointerCapture(ev.pointerId);svg.addEventListener("pointermove",move);window.addEventListener("pointerup",up,{once:true});return;
      }
      const wallTarget=ev.target.closest("[data-wall]");
      if(wallTarget){p.selectedWall=Number(wallTarget.dataset.wall);p.selectedObject=-1;redraw();return;}
      const type=by("hd-tool").value;
      if(type==="wall"){
        if(!p._wallStart){p._wallStart={x,z};by("hd-status").textContent="Düz duvarın bitiş noktasını seç.";}
        else{remember();p.walls.push({x1:p._wallStart.x,z1:p._wallStart.z,x2:x,z2:z,thickness:.12});delete p._wallStart;redraw();}return;
      }
      if(type==="curve"){
        if(!p._curveStart){p._curveStart={x,z};by("hd-status").textContent="Eğri duvarın kontrol noktasını seç.";}
        else if(!p._curveControl){p._curveControl={x,z};by("hd-status").textContent="Eğri duvarın bitiş noktasını seç.";}
        else{remember();p.walls.push({x1:p._curveStart.x,z1:p._curveStart.z,cx:p._curveControl.x,cz:p._curveControl.z,x2:x,z2:z,thickness:.12});delete p._curveStart;delete p._curveControl;redraw();}return;
      }
      if(type==="wire"){
        if(!p._wireStart){p._wireStart={x,z};by("hd-status").textContent="Elektrik hattının bitiş noktasını seç.";}
        else{remember();p.wires=p.wires||[];p.wires.push({x1:p._wireStart.x,z1:p._wireStart.z,x2:x,z2:z,height:2.45,color:"#f5c542"});delete p._wireStart;redraw();}return;
      }
      if(type==="select"){p.selectedObject=-1;redraw();return;}
      remember();const defaults={door:[.9,.12],window:[1.3,.12],sofa:[1.9,.85],bed:[1.6,2],table:[1.2,.8],wardrobe:[1.1,.6],toilet:[.48,.68],kitchen:[1.8,.65],desk:[1.2,.65],plant:[.45,.45],fridge:[.7,.7],shower:[.9,.9],sink:[.6,.5],stairs:[1,2],pool:[3,2],tree:[1,1],fence:[2,.12],gate:[1,.12],light:[.2,.2],outlet:[.12,.08],switch:[.12,.08],radiator:[.8,.15]};
      const size=defaults[type]||[.8,.6];p.objects.push({type,x,z,width:size[0],depth:size[1],rotation:0,label:type});p.selectedObject=p.objects.length-1;redraw();
    });
    ["hd-floor","hd-wall","hd-roof"].forEach((id,i)=>by(id).onchange=e=>{remember();p[["floorColor","wallColor","roofColor"][i]]=e.target.value;redraw();});
    by("hd-height").onchange=e=>{remember();p.wallHeight=Math.max(2.2,Math.min(5,+e.target.value||2.8));redraw();};
    ["hd-width","hd-depth"].forEach((id,i)=>by(id).onchange=e=>{remember();p[i?"depth":"width"]=Math.max(4,Math.min(30,+e.target.value||10));p.objects.forEach(o=>{o.x=Math.max(-p.width/2,Math.min(p.width/2,o.x));o.z=Math.max(-p.depth/2,Math.min(p.depth/2,o.z));});redraw();});
    by("hd-roof-on").onchange=e=>{p.roofOn=e.target.checked;};
    by("hd-labels").onchange=e=>{p.showLabels=e.target.checked;redraw();};
    by("hd-dims").onchange=e=>{p.showDimensions=e.target.checked;redraw();};
    by("hd-furniture").onchange=e=>{p.showFurniture=e.target.checked;redraw();};
    by("hd-undo").onclick=()=>{const h=JSON.parse(localStorage.getItem("jarvis.homeDesign.history")||"[]");if(h.length){const r=JSON.parse(localStorage.getItem("jarvis.homeDesign.redo")||"[]");r.push(JSON.stringify(p));localStorage.setItem("jarvis.homeDesign.redo",JSON.stringify(r.slice(-30)));p=Object.assign(p,JSON.parse(h.pop()));localStorage.setItem("jarvis.homeDesign.history",JSON.stringify(h));redraw();buildHome3D(p);}};
    by("hd-redo").onclick=()=>{const key="jarvis.homeDesign.redo",r=JSON.parse(localStorage.getItem(key)||"[]");if(!r.length)return;const h=JSON.parse(localStorage.getItem("jarvis.homeDesign.history")||"[]");h.push(JSON.stringify(p));localStorage.setItem("jarvis.homeDesign.history",JSON.stringify(h.slice(-30)));p=Object.assign(p,JSON.parse(r.pop()));localStorage.setItem(key,JSON.stringify(r));redraw();buildHome3D(p);};
    by("hd-duplicate").onclick=()=>updateObject(o=>{const n=Object.assign({},o,{x:o.x+.4,z:o.z+.4});p.objects.push(n);p.selectedObject=p.objects.length-1;});
    by("hd-rotate").onclick=()=>updateObject(o=>o.rotation=((Number(o.rotation)||0)+90)%360);
    by("hd-delete").onclick=()=>{if(p.selectedObject>=0){remember();p.objects.splice(p.selectedObject,1);p.selectedObject=-1;redraw();}};
    by("hd-wall-delete").onclick=()=>{if(p.selectedWall>=0&&p.walls[p.selectedWall]){remember();p.walls.splice(p.selectedWall,1);p.selectedWall=-1;redraw();}};
    by("hd-label").onchange=e=>updateObject(o=>o.label=e.target.value.slice(0,40));
    by("hd-obj-w").onchange=e=>updateObject(o=>o.width=Math.max(.1,Math.min(10,+e.target.value||.9)));
    by("hd-obj-d").onchange=e=>updateObject(o=>o.depth=Math.max(.1,Math.min(10,+e.target.value||.55)));
    by("hd-obj-color").onchange=e=>updateObject(o=>o.color=e.target.value);
    by("hd-3d").onclick=()=>{saveFloor();buildHome3D(p);};
    by("hd-walk").onclick=()=>{saveFloor();buildHome3D(p);action("walk");};
    by("hd-rooms-apply").onclick=()=>{remember();p.roomNames=by("hd-rooms").value.split(",").map(s=>s.trim().slice(0,40)).filter(Boolean).slice(0,16);if(!p.roomNames.length)p.roomNames=["Salon"];p.rooms=p.roomNames.length;redraw();buildHome3D(p);};
    by("hd-save").onclick=()=>{try{saveFloor();localStorage.setItem("jarvis.homeDesign",JSON.stringify(p));JV.toast&&JV.toast("Ev projesi kaydedildi.");}catch(e){JV.toast&&JV.toast("Proje kaydedilemedi.");}};
    by("hd-load").onclick=()=>{try{const saved=JSON.parse(localStorage.getItem("jarvis.homeDesign")||"null");if(saved){p=Object.assign({},saved);redraw();buildHome3D(p);}else JV.toast&&JV.toast("Kayıtlı proje bulunamadı.");}catch(e){JV.toast&&JV.toast("Kayıt okunamadı.");}};
    const download=(blob,name)=>{const url=URL.createObjectURL(blob),a=document.createElement("a");a.href=url;a.download=name;a.click();setTimeout(()=>URL.revokeObjectURL(url),1000);};
    by("hd-export").onclick=()=>{saveFloor();download(new Blob([JSON.stringify(p,null,2)],{type:"application/json"}),"jarvis-ev-projesi.json");};
    by("hd-svg").onclick=()=>{const svg=by("hd-plan").cloneNode(true);svg.setAttribute("xmlns","http://www.w3.org/2000/svg");download(new Blob([new XMLSerializer().serializeToString(svg)],{type:"image/svg+xml"}),"jarvis-kat-plani.svg");};
    by("hd-dxf").onclick=()=>{const lines=["0","SECTION","2","ENTITIES"];const line=(x1,z1,x2,z2,layer="WALLS")=>lines.push("0","LINE","8",layer,"10",String(x1),"20",String(z1),"30","0","11",String(x2),"21",String(z2),"31","0");line(-p.width/2,-p.depth/2,p.width/2,-p.depth/2);line(p.width/2,-p.depth/2,p.width/2,p.depth/2);line(p.width/2,p.depth/2,-p.width/2,p.depth/2);line(-p.width/2,p.depth/2,-p.width/2,-p.depth/2);(p.walls||[]).forEach(w=>line(w.x1,w.z1,w.x2,w.z2));(p.wires||[]).forEach(w=>line(w.x1,w.z1,w.x2,w.z2,"ELECTRICAL"));(p.objects||[]).forEach(o=>{const a=(Number(o.rotation)||0)*Math.PI/180,hw=(Number(o.width)||.9)/2,hh=(Number(o.depth)||.55)/2,c=Math.cos(a),s=Math.sin(a),pts=[[-hw,-hh],[hw,-hh],[hw,hh],[-hw,hh]].map(([x,z])=>[o.x+x*c-z*s,o.z+x*s+z*c]);for(let i=0;i<4;i++)line(...pts[i],...pts[(i+1)%4]);});lines.push("0","ENDSEC","0","EOF");download(new Blob([lines.join("\n")],{type:"application/dxf"}),"jarvis-kat-plani.dxf");};
    by("hd-print").onclick=()=>{const svg=by("hd-plan").outerHTML,w=window.open("","_blank");if(!w){JV.toast&&JV.toast("Yazdırma penceresi engellendi.");return;}w.document.write('<html><head><title>Ev planı</title><style>body{margin:10mm}svg{width:100%;height:auto}</style></head><body>'+svg+'</body></html>');w.document.close();w.focus();w.print();};
    by("hd-import").onclick=()=>by("hd-import-file").click();
    by("hd-import-file").onchange=async e=>{const file=e.target.files&&e.target.files[0];if(!file)return;try{
      if(file.size>2*1024*1024)throw new Error("large");
      const data=JSON.parse(await file.text()),allowed=["door","window","sofa","bed","table","wardrobe","toilet","kitchen","desk","plant","fridge","shower","sink","stairs","pool","tree","fence","gate","light","outlet","switch","radiator"];
      if(!data||!Array.isArray(data.roomNames)||!Array.isArray(data.objects)||!Number.isFinite(+data.width)||!Number.isFinite(+data.depth)||data.width<4||data.width>30||data.depth<4||data.depth>30||data.objects.length>250)throw new Error("invalid");
      const roomNames=data.roomNames.map(n=>String(n).trim().slice(0,40)).filter(Boolean).slice(0,16);if(!roomNames.length)throw new Error("rooms");
      const objects=data.objects.map(o=>{if(!o||!allowed.includes(o.type)||!Number.isFinite(+o.x)||!Number.isFinite(+o.z))throw new Error("object");return {type:o.type,x:Math.max(-data.width/2,Math.min(data.width/2,+o.x)),z:Math.max(-data.depth/2,Math.min(data.depth/2,+o.z)),width:Math.max(.1,Math.min(10,+o.width||.9)),depth:Math.max(.1,Math.min(10,+o.depth||.55)),rotation:Number(o.rotation)||0,label:String(o.label||o.type).slice(0,40),color:/^#[0-9a-f]{6}$/i.test(o.color||"")?o.color:undefined};});
      p=Object.assign({},data,{roomNames,objects,walls:Array.isArray(data.walls)?data.walls.slice(0,500):[],wallHeight:Math.max(2.2,Math.min(5,+data.wallHeight||2.8))});redraw();buildHome3D(p);JV.toast&&JV.toast("Ev projesi içe aktarıldı.");
    }catch(err){JV.toast&&JV.toast("JSON proje dosyası geçersiz veya desteklenmiyor.");}e.target.value="";};
    if(el._hdKeys)window.removeEventListener("keydown",el._hdKeys);el._hdKeys=function(e){if(!el.classList.contains("open"))return;if((e.ctrlKey||e.metaKey)&&e.key.toLowerCase()==="z"){e.preventDefault();by("hd-undo").click();}else if((e.ctrlKey||e.metaKey)&&e.key.toLowerCase()==="y"){e.preventDefault();by("hd-redo").click();}else if(e.key==="Delete")by("hd-delete").click();};window.addEventListener("keydown",el._hdKeys);
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
    } else if (a === "walk_exit") { walkMode=false; walkKeys=Object.create(null); controls.minDistance=2; U.caption("Gezinti modu kapatıldı");
    } else if (a === "door_toggle") { const near=doorParts.reduce((best,d)=>{const dist=d.getWorldPosition(new T.Vector3()).distanceTo(camera.position);return !best||dist<best.dist?{door:d,dist}:best;},null); if(near&&near.dist<2.4)near.door.userData.doorOpen=!near.door.userData.doorOpen; else U.caption("Yakında açılabilir kapı yok");
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

  window.addEventListener("keydown",e=>{if(!walkMode)return;if(["KeyW","KeyA","KeyS","KeyD","ArrowUp","ArrowDown","ArrowLeft","ArrowRight","ShiftLeft"].includes(e.code)){walkKeys[e.code]=true;e.preventDefault();}if(e.code==="KeyE")action("door_toggle");if(e.code==="Escape")action("walk_exit");});
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
      doorParts.forEach(d=>{const target=d.userData.doorOpen?Math.PI/2:0;d.rotation.y+=(target-d.rotation.y)*Math.min(1,dt*7);});
      if (walkMode) {
        const forward = new T.Vector3(); camera.getWorldDirection(forward); forward.y = 0; forward.normalize();
        const right = new T.Vector3().crossVectors(forward, new T.Vector3(0,1,0)).normalize();
        const move = new T.Vector3();
        if (walkKeys.KeyW || walkKeys.ArrowUp) move.add(forward);
        if (walkKeys.KeyS || walkKeys.ArrowDown) move.sub(forward);
        if (walkKeys.KeyD || walkKeys.ArrowRight) move.add(right);
        if (walkKeys.KeyA || walkKeys.ArrowLeft) move.sub(right);
        if (move.lengthSq()) {
          move.normalize().multiplyScalar(dt*(walkKeys.ShiftLeft?3.2:1.8));
          const next=camera.position.clone().add(move);
          if(model&&model.userData.size){const hw=Math.max(.8,model.userData.size.x*.43),hd=Math.max(.8,model.userData.size.z*.43);next.x=Math.max(-hw,Math.min(hw,next.x));next.z=Math.max(-hd,Math.min(hd,next.z));}
          next.y=.85;const delta=next.clone().sub(camera.position);camera.position.copy(next);
          if(controls.target){controls.target.add(delta);controls.target.y=.8;}
        }
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
