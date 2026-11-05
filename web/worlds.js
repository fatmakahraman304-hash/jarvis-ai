/* Çok sahneli 3D motor: DÜNYA (küre), ATÖLYE (hologram), BİLİM (simülasyonlar).
   Çekirdek görünüm (küre/yüz) visual.js'te; burası diğer modları yönetir. */
(function () {
  const JV = (window.JV = window.JV || {});
  if (!window.THREE) return;
  const T = THREE, DEG = Math.PI / 180;
  const canvas = document.getElementById("world");
  const renderer = new T.WebGLRenderer({ canvas, antialias: true, alpha: true });
  renderer.setPixelRatio(Math.min(devicePixelRatio, 2));
  const camera = new T.PerspectiveCamera(45, 1, 0.005, 5000);
  const controls = new T.OrbitControls(camera, canvas);
  controls.enableDamping = true; controls.dampingFactor = 0.08;
  const raycaster = new T.Raycaster();
  const W = (JV.worlds = JV.worlds || {});   // kayıtlı dünyalar
  let current = null, view = "core";

  // ---------------- ortak yardımcılar ----------------
  const U = (JV.wutil = {
    T, DEG, camera, controls, renderer,
    color: () => new T.Color(getComputedStyle(document.documentElement).getPropertyValue("--c").trim() || "#38d6ff"),
    ll2v(lat, lon, r = 1) {
      const phi = (90 - lat) * DEG, th = (lon + 180) * DEG;
      return new T.Vector3(-r * Math.sin(phi) * Math.cos(th), r * Math.cos(phi), r * Math.sin(phi) * Math.sin(th));
    },
    v2ll(v) {
      const r = v.length(), lat = 90 - Math.acos(v.y / r) / DEG;
      let lon = Math.atan2(v.z, -v.x) / DEG - 180; if (lon < -180) lon += 360;
      return { lat, lon };
    },
    label(text, color = "#cfefff", size = 48) {
      const c = document.createElement("canvas"), g = c.getContext("2d");
      g.font = `600 ${size}px Rajdhani, Segoe UI, sans-serif`;
      const w = Math.ceil(g.measureText(text).width) + 24; c.width = w; c.height = size + 20;
      g.font = `600 ${size}px Rajdhani, Segoe UI, sans-serif`;
      g.fillStyle = "rgba(0,10,20,.55)"; g.fillRect(0, 0, w, c.height);
      g.fillStyle = color; g.textBaseline = "middle"; g.fillText(text, 12, c.height / 2);
      const tex = new T.CanvasTexture(c); tex.minFilter = T.LinearFilter;
      const s = new T.Sprite(new T.SpriteMaterial({ map: tex, depthTest: false, transparent: true }));
      s.scale.set(w / c.height * 0.1, 0.1, 1); s.renderOrder = 10; s.userData.aspect = w / c.height;
      return s;
    },
    panel(html) {
      const p = document.getElementById("world-panel");
      if (html == null) { p.classList.add("hidden"); return; }
      p.innerHTML = html; p.classList.remove("hidden");
    },
    caption(t) { const c = document.getElementById("world-caption"); c.textContent = t || ""; c.style.opacity = t ? 1 : 0; },
    fmt: (n, d = 0) => (n == null ? "—" : Number(n).toLocaleString("tr-TR", { maximumFractionDigits: d })),
    tween(ms, fn, done) {
      const t0 = performance.now();
      (function step(now) {
        const k = Math.min(1, (now - t0) / ms), e = k < 0.5 ? 2 * k * k : 1 - Math.pow(-2 * k + 2, 2) / 2;
        fn(e); if (k < 1) requestAnimationFrame(step); else done && done();
      })(t0);
    },
    disposeTree(o) { o.traverse((x) => { x.geometry && x.geometry.dispose(); if (x.material) [].concat(x.material).forEach((m) => { m.map && m.map.dispose(); m.dispose(); }); }); },
  });

  function resize() {
    const w = innerWidth, h = innerHeight;
    renderer.setSize(w, h, false); camera.aspect = w / h; camera.updateProjectionMatrix();
  }
  addEventListener("resize", resize); resize();

  // ---------------- mod değiştirme ----------------
  JV.setView = function (v) {
    if (JV.stage && JV.stage.current()) JV.stage.clear();
    if (v === view && (v === "core" || current)) return;
    if (current && current.exit) current.exit();
    view = v; current = W[v] || null;
    const world = v !== "core";
    document.body.classList.toggle("world-mode", world);
    ["globe", "lab", "science", "space", "city", "graph", "twin", "bio"].forEach((x) => document.body.classList.toggle("view-" + x, v === x));
    JV.coreHidden = world;
    U.panel(null); U.caption("");
    document.getElementById("map-panel").classList.add("hidden");
    if (current) { current.enter(); controls.update(); }
    document.querySelectorAll("[data-view]").forEach((b) => b.classList.toggle("on", b.dataset.view === v));
  };
  JV.getView = () => view;

  // arayüz komutları (beynin araç sonuçlarından gelir)
  JV.uiCommand = function (name, args, result) {
    let r = result;
    try { r = typeof result === "string" ? JSON.parse(result) : result; } catch (e) { r = {}; }
    if (!r || !r.ui) return;
    const ui = r.ui;
    if (ui === "view") return JV.setView(r.view);
    if (ui === "translator") return JV.translator && JV.translator.open(r);
    if (ui === "image" || ui === "gallery") return JV.studio && JV.studio.open(r);
    if (ui === "mode") return JV.applyMode && JV.applyMode(r.mode);
    if (ui === "command") return JV.command && (r.open === false ? JV.command.close() : JV.command.open());
    if (ui === "panel") return JV.openPanel && JV.openPanel(r.panel, r.open);
    if (ui.startsWith("globe") || ui === "map") { JV.setView("globe"); return W.globe.cmd(ui, r, args); }
    if (ui.startsWith("holo") || ui === "chart3d") { JV.setView("lab"); return W.lab.cmd(ui, r, args); }
    if (ui === "sim") { JV.setView("science"); return W.science.cmd(r.kind, r.params || {}, r); }
    if (ui === "space") { JV.setView("space"); return W.space.cmd(r); }
    if (ui === "city") { JV.setView("city"); return W.city.cmd(r); }
    if (ui === "graph") { JV.setView("graph"); return W.graph.cmd(r); }
    if (ui === "twin") { JV.setView("twin"); return W.twin.cmd(r); }
    if (ui === "bio") { JV.setView("bio"); return W.bio.cmd(r); }
    if (ui === "quiz") return JV.knowledge && JV.knowledge.quiz(r);
    if (ui === "finlab") return JV.finlab && JV.finlab.open(r);
    if (ui === "ambient") return JV.ambient && (r.on === false ? JV.ambient.stop() : JV.ambient.start());
    if (ui === "xr") { if (r.view) JV.setView(r.view); return xrPrompt(r.mode === "ar" ? "immersive-ar" : "immersive-vr"); }
    if (ui === "weather") return JV.weather && JV.weather.open(r);
    if (ui === "meeting") return JV.meeting && JV.meeting.cmd(r);
    if (ui === "focus") return JV.focus && JV.focus.cmd(r);
    if (ui === "newsshow") return JV.newsshow && JV.newsshow.open(r);
    if (ui === "scan") return JV.scan && JV.scan.cmd(r);
    if (ui === "body") return JV.body && JV.body.cmd(r);
    if (ui === "video") return JV.video && JV.video.open(r);
    if (ui === "stage") return JV.stage && JV.stage.cmd(r, args || {});
    if (ui === "call") return JV.call && (r.incoming ? JV.call.incoming(r.message || "") : JV.call.start());
    if (ui === "lock") return JV.lock && (r.on === false ? JV.lock.off() : JV.lock.on());
    if (ui === "core") { if (JV.stage) JV.stage.clear(); if (JV.getView() !== "core") JV.setView("core"); return JV.setCoreStyle && r.style && JV.setCoreStyle(r.style); }
    if (ui === "library") return JV.library && JV.library.cmd(r);
    if (ui === "handfx") return JV.handfx && JV.handfx.cmd(r);
    if (ui === "fortune") return JV.fortune && JV.fortune();
    if (ui === "sleep") return JV.sleep && (r.on === false ? JV.sleep.wake("komut") : setTimeout(() => JV.sleep.enter(), 2500));
    if (ui === "music") { if (JV.music) { JV.music.open(r); JV.music.play(); } return; }
  };

  // ---------------- tıklama / üzerine gelme ----------------
  const mouse = new T.Vector2();
  let downAt = null;
  canvas.addEventListener("pointerdown", (e) => (downAt = [e.clientX, e.clientY]));
  canvas.addEventListener("pointerup", (e) => {
    if (!downAt || Math.hypot(e.clientX - downAt[0], e.clientY - downAt[1]) > 5 || !current || !current.click) return;
    mouse.set((e.clientX / innerWidth) * 2 - 1, -(e.clientY / innerHeight) * 2 + 1);
    raycaster.setFromCamera(mouse, camera);
    current.click(raycaster, e);
  });
  let hoverT = 0;
  canvas.addEventListener("pointermove", (e) => {
    if (!current || !current.hover || performance.now() - hoverT < 80) return;
    hoverT = performance.now();
    mouse.set((e.clientX / innerWidth) * 2 - 1, -(e.clientY / innerHeight) * 2 + 1);
    raycaster.setFromCamera(mouse, camera);
    current.hover(raycaster, e);
  });
  JV.pickAt = function (sx, sy) { // el hareketleri için ekran koordinatından seçim
    mouse.set((sx / innerWidth) * 2 - 1, -(sy / innerHeight) * 2 + 1);
    raycaster.setFromCamera(mouse, camera);
    return raycaster;
  };

  // ---------------- el hareketi API'si ----------------
  JV.world = {
    orbit(dx, dy) { // radyan
      const off = camera.position.clone().sub(controls.target);
      const sph = new T.Spherical().setFromVector3(off);
      sph.theta -= dx; sph.phi = Math.max(0.05, Math.min(Math.PI - 0.05, sph.phi - dy));
      off.setFromSpherical(sph); camera.position.copy(controls.target).add(off); camera.lookAt(controls.target);
    },
    zoom(f) {
      const off = camera.position.clone().sub(controls.target);
      const d = Math.max(controls.minDistance || 0.01, Math.min(controls.maxDistance || 1e4, off.length() * f));
      camera.position.copy(controls.target).add(off.setLength(d));
    },
    active: () => !!current,
    current: () => current,
  };

  // ---------------- döngü ----------------
  let last = performance.now();
  renderer.xr.enabled = true; // WebXR (VR gözlük / AR telefon) — setAnimationLoop hem normal hem XR'de çalışır
  renderer.setAnimationLoop(function loop(now) {
    now = now || performance.now();
    const dt = Math.min(0.05, (now - last) / 1000); last = now;
    if (current) {
      if (!renderer.xr.isPresenting) controls.update();
      current.update && current.update(dt, now / 1000);
      renderer.render(current.scene, camera);
    }
  });

  // ---------------- WebXR: VR / AR ----------------
  const xrState = { session: null, bg: null, fog: null, rays: [] };
  async function xrSupported(mode) { try { return !!(navigator.xr && await navigator.xr.isSessionSupported(mode)); } catch (e) { return false; } }
  async function xrEnter(mode = "immersive-vr") {
    if (!current) JV.setView("globe");
    if (!navigator.xr) throw new Error("Bu tarayıcı WebXR desteklemiyor.");
    if (!window.isSecureContext) throw new Error("VR/AR için güvenli bağlantı gerekli: JARVIS'i 'python run.py --lan --https' ile başlatıp https:// adresinden aç.");
    if (!(await xrSupported(mode))) throw new Error(mode === "immersive-ar" ? "Bu cihaz AR oturumu desteklemiyor (ARCore'lu Android Chrome gerekir)." : "VR gözlük bulunamadı (Quest tarayıcısı ya da SteamVR/WMR ile Chrome/Edge gerekir).");
    const session = await navigator.xr.requestSession(mode, { optionalFeatures: ["local-floor", "bounded-floor", "hand-tracking"] });
    xrState.session = session;
    renderer.xr.setReferenceSpaceType("local-floor");
    await renderer.xr.setSession(session);
    // kullanıcıyı mevcut kamera konumuna yerleştir (ışınlanma: başlangıç uzayını kaydır)
    const ref = renderer.xr.getReferenceSpace();
    const p = camera.position;
    if (ref && window.XRRigidTransform) renderer.xr.setReferenceSpace(ref.getOffsetReferenceSpace(new XRRigidTransform({ x: -p.x, y: -p.y + 1.6, z: -p.z, w: 1 })));
    if (mode === "immersive-ar") { const sc = current.scene; xrState.bg = sc.background; xrState.fog = sc.fog; sc.background = null; sc.fog = null; }
    // kumandalar: tetik = tıklama (dünyadaki nesneyi seç)
    for (let i = 0; i < 2; i++) {
      const ctl = renderer.xr.getController(i);
      const line = new T.Line(new T.BufferGeometry().setFromPoints([new T.Vector3(0, 0, 0), new T.Vector3(0, 0, -5)]), new T.LineBasicMaterial({ color: 0x38d6ff }));
      ctl.add(line);
      ctl.addEventListener("select", () => {
        if (!current || !current.click) return;
        const m = new T.Matrix4().extractRotation(ctl.matrixWorld);
        raycaster.ray.origin.setFromMatrixPosition(ctl.matrixWorld); raycaster.ray.direction.set(0, 0, -1).applyMatrix4(m);
        current.click(raycaster, {});
      });
      current.scene.add(ctl); xrState.rays.push([current.scene, ctl]);
    }
    session.addEventListener("end", () => {
      xrState.rays.forEach(([sc, c]) => sc.remove(c)); xrState.rays = [];
      if (xrState.bg !== null || xrState.fog !== null) { current.scene.background = xrState.bg; current.scene.fog = xrState.fog; xrState.bg = xrState.fog = null; }
      xrState.session = null; resize();
    });
    return true;
  }
  function xrPrompt(mode) { // tarayıcılar XR oturumunu yalnızca bir dokunuşla başlatır
    let b = document.getElementById("xr-prompt");
    if (!b) { b = document.createElement("button"); b.id = "xr-prompt"; b.className = "btn-primary"; document.body.append(b); }
    b.textContent = mode === "immersive-ar" ? "📱 AR'YE GEÇMEK İÇİN DOKUN" : "🥽 VR'YE GİRMEK İÇİN DOKUN";
    b.onclick = () => { b.remove(); xrEnter(mode).catch((e) => JV.toast && JV.toast(e.message, 9000)); };
    setTimeout(() => b.remove(), 30000);
  }
  (async () => { // destek varsa üst menüye VR / AR düğmeleri
    const nav = document.getElementById("views"); if (!nav) return;
    for (const [mode, label] of [["immersive-vr", "🥽 VR"], ["immersive-ar", "📱 AR"]]) {
      if (await xrSupported(mode)) { const b = document.createElement("button"); b.textContent = label; b.title = "Bu dünyayı " + (mode === "immersive-ar" ? "artırılmış gerçeklikte" : "VR gözlükte") + " aç";
        b.onclick = () => xrEnter(mode).catch((e) => JV.toast && JV.toast(e.message, 9000)); nav.append(b); }
    }
  })();
  JV.xr = { prompt: xrPrompt, supported: xrSupported, enter: xrEnter, exit: () => xrState.session && xrState.session.end(), active: () => !!xrState.session };

  // ======================================================================
  // DÜNYA
  // ======================================================================
  W.globe = (function () {
    const scene = new T.Scene();
    const tex = new T.TextureLoader();
    const P = "/static/vendor/textures/";
    const earth = new T.Mesh(new T.SphereGeometry(1, 128, 96), new T.MeshPhongMaterial({
      map: tex.load(P + "earth_atmos_2048.jpg"), normalMap: tex.load(P + "earth_normal_2048.jpg"), normalScale: new T.Vector2(0.9, 0.9),
      specularMap: tex.load(P + "earth_specular_2048.jpg"), specular: new T.Color(0x334455), shininess: 18,
      emissiveMap: tex.load(P + "earth_lights_2048.png"), emissive: new T.Color(0xffd9a0), emissiveIntensity: 0.0,
    }));
    scene.add(earth);
    const clouds = new T.Mesh(new T.SphereGeometry(1.012, 96, 64), new T.MeshLambertMaterial({ map: tex.load(P + "earth_clouds_1024.png"), transparent: true, opacity: 0.55, depthWrite: false }));
    scene.add(clouds);
    const atmo = new T.Mesh(new T.SphereGeometry(1.09, 64, 48), new T.ShaderMaterial({
      uniforms: { c: { value: new T.Color("#38d6ff") } }, side: T.BackSide, transparent: true, blending: T.AdditiveBlending, depthWrite: false,
      vertexShader: "varying vec3 n; void main(){ n = normalize(normalMatrix*normal); gl_Position = projectionMatrix*modelViewMatrix*vec4(position,1.0);}",
      fragmentShader: "uniform vec3 c; varying vec3 n; void main(){ float i = pow(0.72 - dot(n, vec3(0,0,1.0)), 3.0); gl_FragColor = vec4(c, 1.0)*i; }",
    }));
    scene.add(atmo);
    const stars = new T.Points(new T.BufferGeometry().setAttribute("position", new T.Float32BufferAttribute(
      Array.from({ length: 6000 }, () => (Math.random() - 0.5) * 400), 3)), new T.PointsMaterial({ size: 0.6, color: 0x9fb8c8, sizeAttenuation: true }));
    scene.add(stars);
    scene.add(new T.AmbientLight(0x404a58, 0.55));
    const sun = new T.DirectionalLight(0xffffff, 1.25); scene.add(sun);

    function sunPos() { // gerçek saatle güneşin dik geldiği nokta
      const d = new Date(), doy = (Date.UTC(d.getUTCFullYear(), d.getUTCMonth(), d.getUTCDate()) - Date.UTC(d.getUTCFullYear(), 0, 0)) / 864e5;
      const decl = 23.44 * Math.sin(2 * Math.PI * (doy - 81) / 365);
      const lon = -((d.getUTCHours() + d.getUTCMinutes() / 60) - 12) * 15;
      return U.ll2v(decl, lon, 10);
    }

    // ---- veriler ----
    let countries = [], cities = [];
    const borders = new T.Group(); scene.add(borders);
    const cityG = new T.Group(); scene.add(cityG);
    const marks = new T.Group(); scene.add(marks);
    const layers = { flights: null, quakes: null, ships: null, events: null, fires: null, news: null, ships_live: null, gibs: null };
    const baseMap = earth.material.map;
    let highlight = null, flightTimer = null;
    const layerState = { borders: true, cities: true, clouds: true, night: false };

    async function loadData() {
      if (countries.length) return;
      countries = await (await fetch("/static/data/countries.json")).json();
      cities = await (await fetch("/static/data/cities.json")).json();
      const pos = [];
      countries.forEach((c) => {
        let mnx = 999, mny = 999, mxx = -999, mxy = -999;
        c.poly.forEach((poly) => poly.forEach((ring, ri) => {
          for (let i = 0; i < ring.length; i++) {
            const [x, y] = ring[i];
            if (ri === 0) { mnx = Math.min(mnx, x); mxx = Math.max(mxx, x); mny = Math.min(mny, y); mxy = Math.max(mxy, y); }
            const a = U.ll2v(y, x, 1.003), b = U.ll2v(ring[(i + 1) % ring.length][1], ring[(i + 1) % ring.length][0], 1.003);
            pos.push(a.x, a.y, a.z, b.x, b.y, b.z);
          }
        }));
        c.bb = [mnx, mny, mxx, mxy];
      });
      const g = new T.BufferGeometry().setAttribute("position", new T.Float32BufferAttribute(pos, 3));
      borders.add(new T.LineSegments(g, new T.LineBasicMaterial({ color: U.color(), transparent: true, opacity: 0.55 })));
      // şehirler
      const cp = [];
      cities.forEach((c) => { const v = U.ll2v(c.lat, c.lon, 1.004); cp.push(v.x, v.y, v.z); });
      cityG.add(new T.Points(new T.BufferGeometry().setAttribute("position", new T.Float32BufferAttribute(cp, 3)),
        new T.PointsMaterial({ color: 0xffe08a, size: 0.012, sizeAttenuation: true })));
      cities.filter((c) => c.cap || c.pop > 8e6).sort((a, b) => b.pop - a.pop).slice(0, 60).forEach((c) => {
        const s = U.label(c.n, "#ffe7a8", 40); s.position.copy(U.ll2v(c.lat, c.lon, 1.02)); s.userData.base = 0.035; cityG.add(s);
      });
    }

    function inRing(x, y, ring) {
      let ins = false;
      for (let i = 0, j = ring.length - 1; i < ring.length; j = i++) {
        const [xi, yi] = ring[i], [xj, yj] = ring[j];
        if (((yi > y) !== (yj > y)) && x < ((xj - xi) * (y - yi)) / (yj - yi) + xi) ins = !ins;
      }
      return ins;
    }
    function countryAt(lat, lon) {
      for (const c of countries) {
        if (lon < c.bb[0] - 1 || lon > c.bb[2] + 1 || lat < c.bb[1] - 1 || lat > c.bb[3] + 1) continue;
        for (const poly of c.poly) if (inRing(lon, lat, poly[0]) && !poly.slice(1).some((h) => inRing(lon, lat, h))) return c;
      }
      return null;
    }
    function highlightCountry(c) {
      if (highlight) { scene.remove(highlight); U.disposeTree(highlight); highlight = null; }
      if (!c) return;
      const pos = [];
      c.poly.forEach((poly) => { const ring = poly[0]; for (let i = 0; i < ring.length; i++) { const a = U.ll2v(ring[i][1], ring[i][0], 1.006), b = U.ll2v(ring[(i + 1) % ring.length][1], ring[(i + 1) % ring.length][0], 1.006); pos.push(a.x, a.y, a.z, b.x, b.y, b.z); } });
      highlight = new T.LineSegments(new T.BufferGeometry().setAttribute("position", new T.Float32BufferAttribute(pos, 3)), new T.LineBasicMaterial({ color: 0xffffff }));
      scene.add(highlight);
    }
    function capitalOf(c) { return cities.find((x) => x.cap && x.c === c.en); }
    function showCountry(c) {
      highlightCountry(c);
      const cap = capitalOf(c);
      U.panel(`<div class="wp-title">${c.n}</div><div class="wp-sub">${c.cont} · ${c.sub}</div>
        <div class="wp-grid">
          <i>Başkent</i><b>${cap ? cap.n : "—"}</b>
          <i>Nüfus</i><b>${U.fmt(c.pop)} <small>(${c.popy})</small></b>
          <i>Yüzölçümü</i><b>${U.fmt(c.area)} km²</b>
          <i>Yoğunluk</i><b>${U.fmt(c.pop / c.area, 1)} kişi/km²</b>
          <i>GSYH</i><b>${U.fmt(c.gdp / 1000, 1)} milyar $ <small>(${c.gdpy})</small></b>
          <i>Kişi başı</i><b>${U.fmt(c.gdp * 1e6 / c.pop)} $</b>
          <i>Gelir grubu</i><b>${(c.inc || "").replace(/^\d\.\s*/, "")}</b>
        </div>
        <div class="wp-row"><button class="mini" id="wp-weather">HAVA DURUMU</button><button class="mini" id="wp-street">HARİTA / UYDU</button><button class="mini" id="wp-close">KAPAT</button></div>
        <div id="wp-extra"></div>`);
      document.getElementById("wp-close").onclick = () => { U.panel(null); highlightCountry(null); };
      document.getElementById("wp-street").onclick = () => openMap(cap ? cap.lat : c.ly, cap ? cap.lon : c.lx, cap ? 11 : 6, true);
      document.getElementById("wp-weather").onclick = async () => {
        const lat = cap ? cap.lat : c.ly, lon = cap ? cap.lon : c.lx;
        const w = await JV.api(`/api/geo/weather?lat=${lat}&lon=${lon}`);
        document.getElementById("wp-extra").innerHTML = typeof w === "object" && w.sıcaklık ? `<div class="wp-grid"><i>${cap ? cap.n : c.n}</i><b>${w.sıcaklık} · ${w.durum}</b><i>Hissedilen</i><b>${w.hissedilen}</b><i>Nem / rüzgar</i><b>${w.nem} · ${w.rüzgar_kmh} km/s</b></div>` : "Hava durumu alınamadı.";
      };
    }

    // ---- kamera uçuşu ----
    function flyTo(lat, lon, dist = 2.2, ms = 1800) {
      const from = camera.position.clone(), fd = from.length();
      const to = U.ll2v(lat, lon, 1).normalize();
      const fdir = from.clone().normalize();
      const q0 = new T.Quaternion(), q1 = new T.Quaternion().setFromUnitVectors(fdir, to);
      U.tween(ms, (e) => {
        const q = q0.clone().slerp(q1, e);
        const hop = Math.sin(e * Math.PI) * 0.6 * fdir.angleTo(to);
        camera.position.copy(fdir.clone().applyQuaternion(q).multiplyScalar(fd + (dist - fd) * e + hop));
        camera.lookAt(0, 0, 0);
      });
    }

    // ---- işaret / mesafe ----
    function addMark(lat, lon, label, color = 0xff4d6d) {
      const m = new T.Mesh(new T.SphereGeometry(0.008, 12, 12), new T.MeshBasicMaterial({ color }));
      m.position.copy(U.ll2v(lat, lon, 1.006)); marks.add(m);
      const ring = new T.Mesh(new T.RingGeometry(0.012, 0.016, 32), new T.MeshBasicMaterial({ color, side: T.DoubleSide, transparent: true }));
      ring.position.copy(m.position); ring.lookAt(m.position.clone().multiplyScalar(2)); ring.userData.pulse = true; marks.add(ring);
      if (label) { const s = U.label(label, "#ffd0d8", 44); s.position.copy(U.ll2v(lat, lon, 1.045)); s.userData.base = 0.04; marks.add(s); }
    }
    function addArc(a, b, km) {
      const va = U.ll2v(a.lat, a.lon, 1), vb = U.ll2v(b.lat, b.lon, 1), pts = [];
      const ang = va.angleTo(vb);
      for (let i = 0; i <= 96; i++) {
        const t = i / 96, v = va.clone().lerp(vb, t).normalize();
        pts.push(v.multiplyScalar(1.004 + Math.sin(Math.PI * t) * ang * 0.18));
      }
      const line = new T.Line(new T.BufferGeometry().setFromPoints(pts), new T.LineBasicMaterial({ color: 0xffd34d }));
      marks.add(line);
      const mid = pts[48].clone().multiplyScalar(1.03), s = U.label(`${U.fmt(km)} km`, "#ffe58a", 46); s.position.copy(mid); s.userData.base = 0.05; marks.add(s);
    }

    // ---- katmanlar ----
    async function flightsLayer(on) {
      if (layers.flights) { scene.remove(layers.flights); U.disposeTree(layers.flights); layers.flights = null; }
      clearInterval(flightTimer);
      if (!on) return;
      const load = async () => {
        const f = await JV.api("/api/geo/flights?limit=4000");
        if (!Array.isArray(f)) { JV.toast && JV.toast("Uçuş verisi alınamadı (OpenSky yoğun olabilir)."); return; }
        const pos = [], col = [];
        f.forEach((p) => { const v = U.ll2v(p.lat, p.lon, 1.01 + Math.min(p.alt, 13000) / 6.371e6 * 6); pos.push(v.x, v.y, v.z); const c = new T.Color().setHSL(0.55 - Math.min(p.alt, 12000) / 12000 * 0.45, 1, 0.6); col.push(c.r, c.g, c.b); });
        const g = new T.BufferGeometry().setAttribute("position", new T.Float32BufferAttribute(pos, 3)).setAttribute("color", new T.Float32BufferAttribute(col, 3));
        if (layers.flights) { scene.remove(layers.flights); U.disposeTree(layers.flights); }
        layers.flights = new T.Points(g, new T.PointsMaterial({ size: 0.008, vertexColors: true, sizeAttenuation: true }));
        layers.flights.userData.count = f.length; scene.add(layers.flights);
        U.caption(`✈ ${U.fmt(f.length)} canlı uçuş`); setTimeout(() => U.caption(""), 4000);
      };
      await load(); flightTimer = setInterval(() => view === "globe" && load(), 30000);
    }
    async function quakesLayer(on) {
      if (layers.quakes) { scene.remove(layers.quakes); U.disposeTree(layers.quakes); layers.quakes = null; }
      if (!on) return;
      const q = await JV.api("/api/geo/quakes?period=week&min=4");
      if (!Array.isArray(q)) return;
      const g = new T.Group();
      q.forEach((e) => {
        const s = 0.004 + (e.büyüklük - 4) * 0.004;
        const m = new T.Mesh(new T.SphereGeometry(s, 10, 10), new T.MeshBasicMaterial({ color: e.büyüklük >= 6 ? 0xff2020 : 0xff8a30, transparent: true, opacity: 0.85 }));
        m.position.copy(U.ll2v(e.lat, e.lon, 1.005)); m.userData = { quake: e, pulse: true }; g.add(m);
      });
      layers.quakes = g; scene.add(g);
      U.caption(`◉ Son 7 günde ${q.length} deprem (≥4)`); setTimeout(() => U.caption(""), 4000);
    }
    async function shipsLayer(on) {
      if (layers.ships) { scene.remove(layers.ships); U.disposeTree(layers.ships); layers.ships = null; }
      if (!on) return;
      const routes = await JV.api("/api/geo/ships");
      const g = new T.Group();
      routes.forEach((r) => {
        const pts = [];
        for (let i = 0; i < r.nokta.length - 1; i++) {
          const a = U.ll2v(r.nokta[i][0], r.nokta[i][1], 1.004), b = U.ll2v(r.nokta[i + 1][0], r.nokta[i + 1][1], 1.004);
          for (let k = 0; k < 20; k++) pts.push(a.clone().lerp(b, k / 20).normalize().multiplyScalar(1.004));
        }
        const l = new T.Line(new T.BufferGeometry().setFromPoints(pts), new T.LineDashedMaterial({ color: 0x4dffd2, dashSize: 0.02, gapSize: 0.012 }));
        l.computeLineDistances(); g.add(l);
        const s = U.label("⚓ " + r.ad, "#9ffff0", 36); s.position.copy(pts[Math.floor(pts.length / 2)].clone().multiplyScalar(1.03)); s.userData.base = 0.03; g.add(s);
      });
      layers.ships = g; scene.add(g);
      U.caption("⚓ Ana deniz ticaret rotaları (temsili, canlı değil)"); setTimeout(() => U.caption(""), 5000);
    }
    function clearLayer(id) { if (layers[id] && layers[id].isObject3D) { scene.remove(layers[id]); U.disposeTree(layers[id]); } layers[id] = null; }
    const EV_COL = { wildfires: 0xff5a1f, severeStorms: 0x7ab8ff, floods: 0x2f7dff, volcanoes: 0xff2a2a, dustHaze: 0xd9b26a, seaLakeIce: 0xbfefff, snow: 0xffffff, landslides: 0x9b6a3a, drought: 0xffc04d };
    async function eventsLayer(on, cat) {
      clearLayer("events"); if (!on) return;
      const ev = await JV.api("/api/watch/events?days=30" + (cat ? "&category=" + cat : ""));
      if (!Array.isArray(ev)) { JV.toast && JV.toast(ev.error || "Olay verisi alınamadı"); return; }
      const g = new T.Group();
      ev.forEach((e) => {
        const col = EV_COL[e.tür] || 0xffffff, [lat, lon] = e.son;
        const m = new T.Mesh(new T.SphereGeometry(0.009, 10, 10), new T.MeshBasicMaterial({ color: col })); m.position.copy(U.ll2v(lat, lon, 1.006)); m.userData = { ev: e, pulse: true }; g.add(m);
        if (e.iz.length > 1) g.add(new T.Line(new T.BufferGeometry().setFromPoints(e.iz.map((p) => U.ll2v(p[0], p[1], 1.005))), new T.LineBasicMaterial({ color: col, transparent: true, opacity: 0.8 })));
      });
      layers.events = g; scene.add(g);
      const cnt = {}; ev.forEach((e) => (cnt[e.tür_tr] = (cnt[e.tür_tr] || 0) + 1));
      U.panel(`<div class="wp-title">Doğal olaylar (son 30 gün)</div><div class="wp-sub">NASA EONET · açık olaylar</div><div class="wp-grid">${Object.entries(cnt).map(([k, v]) => `<i>${k}</i><b>${v}</b>`).join("")}</div><p class="note">Bir olaya tıkla. Fırtınaların çizgisi izlediği rotadır.</p>`);
    }
    async function firesLayer(on) {
      clearLayer("fires"); if (!on) return;
      const f = await JV.api("/api/watch/fires?days=1");
      if (!Array.isArray(f)) { JV.toast && JV.toast(f.error || "Yangın verisi alınamadı"); return; }
      const pos = []; f.forEach(([lat, lon]) => { const v = U.ll2v(lat, lon, 1.004); pos.push(v.x, v.y, v.z); });
      layers.fires = new T.Points(new T.BufferGeometry().setAttribute("position", new T.Float32BufferAttribute(pos, 3)), new T.PointsMaterial({ color: 0xff6a1f, size: 0.006, transparent: true, opacity: 0.9 }));
      scene.add(layers.fires); U.caption(`🔥 Son 24 saatte ${U.fmt(f.length)} aktif yangın noktası (NASA FIRMS)`); setTimeout(() => U.caption(""), 5000);
    }
    async function gibsLayer(on, date) {
      if (!on) { earth.material.map = baseMap; earth.material.needsUpdate = true; layers.gibs = null; return; }
      U.caption("NASA uydu görüntüsü indiriliyor (ilk sefer ~10 sn)…");
      const r = await fetch("/api/watch/gibs" + (date ? "?date=" + date : ""), { headers: { "x-token": JV.token || "" } });
      if (!r.ok) { U.caption(""); JV.toast && JV.toast("Uydu görüntüsü alınamadı"); return; }
      const d = r.headers.get("X-Date"), url = URL.createObjectURL(await r.blob());
      new T.TextureLoader().load(url, (t) => { earth.material.map = t; earth.material.needsUpdate = true; layers.gibs = true; U.caption(`🛰 ${d} tarihli gerçek uydu mozaiği (NASA GIBS)`); setTimeout(() => U.caption(""), 5000); });
      clouds.visible = false; layerState.clouds = false;
    }
    async function newsLayer(on, topic) {
      clearLayer("news"); if (!on) return;
      U.caption("Haberler toplanıyor…");
      const n = await JV.api("/api/watch/news" + (topic ? "?topic=" + encodeURIComponent(topic) : "")); U.caption("");
      if (!Array.isArray(n)) return;
      const g = new T.Group();
      n.forEach((c) => {
        const m = new T.Mesh(new T.ConeGeometry(0.008, 0.03, 8), new T.MeshBasicMaterial({ color: 0xffd34d })); const v = U.ll2v(c.lat, c.lon, 1.02); m.position.copy(v); m.lookAt(0, 0, 0); m.rotateX(-Math.PI / 2); m.userData = { news: c }; g.add(m);
        const s = U.label(c.ülke + ": " + c.haberler[0].başlık.slice(0, 40) + "…", "#ffe9a8", 32); s.position.copy(U.ll2v(c.lat, c.lon, 1.05)); s.userData.base = 0.022; g.add(s);
      });
      layers.news = g; scene.add(g);
      U.panel(`<div class="wp-title">Dünyadan haberler${topic ? ": " + topic : ""}</div><div class="wp-story">${n.map((c) => `<div class="st on"><b>${c.ülke}</b> ${c.haberler.map((h) => `<div><a href="${h.link}" target="_blank">${h.başlık}</a></div>`).join("")}</div>`).join("")}</div>`);
    }
    async function shipsLiveLayer(on, box) {
      clearLayer("ships_live"); if (!on) return;
      const b = box || [30, -6, 46, 37];
      U.caption("Gemi sinyalleri dinleniyor (~20 sn)…");
      const s = await JV.api(`/api/watch/ships?lat1=${b[0]}&lon1=${b[1]}&lat2=${b[2]}&lon2=${b[3]}`); U.caption("");
      if (!Array.isArray(s)) { JV.toast && JV.toast(s.error || "Gemi verisi alınamadı"); return; }
      const pos = [], col = []; s.forEach((x) => { const v = U.ll2v(x.lat, x.lon, 1.003); pos.push(v.x, v.y, v.z); const c = new T.Color(x.hız_knot > 1 ? 0x4dffd2 : 0x8899aa); col.push(c.r, c.g, c.b); });
      layers.ships_live = new T.Points(new T.BufferGeometry().setAttribute("position", new T.Float32BufferAttribute(pos, 3)).setAttribute("color", new T.Float32BufferAttribute(col, 3)), new T.PointsMaterial({ size: 0.006, vertexColors: true }));
      layers.ships_live.userData.list = s; scene.add(layers.ships_live);
      U.caption(`⚓ ${s.length} gemi (canlı AIS) · yeşil: hareket hâlinde`); setTimeout(() => U.caption(""), 6000);
    }
    function setLayer(id, on, extra = {}) {
      if (id === "events") return eventsLayer(on, extra.category);
      if (id === "fires") return firesLayer(on);
      if (id === "gibs") return gibsLayer(on, extra.date);
      if (id === "news") return newsLayer(on, extra.topic);
      if (id === "ships_live") return shipsLiveLayer(on, extra.box);
      if (id === "flights") return flightsLayer(on);
      if (id === "quakes") return quakesLayer(on);
      if (id === "ships") return shipsLayer(on);
      if (id === "borders") borders.visible = on;
      if (id === "cities") cityG.visible = on;
      if (id === "clouds") clouds.visible = on;
      if (id === "night") earth.material.emissiveIntensity = on ? 0.9 : 0;
      layerState[id] = on; renderLayerBar();
    }
    function renderLayerBar() {
      const bar = document.getElementById("globe-layers");
      const items = [["borders", "Sınırlar"], ["cities", "Şehirler"], ["clouds", "Bulutlar"], ["night", "Gece ışıkları"], ["gibs", "🛰 Bugünün uydu görüntüsü"], ["events", "🌪 Doğal olaylar"], ["fires", "🔥 Yangınlar"], ["flights", "✈ Uçuşlar"], ["quakes", "◉ Depremler"], ["ships_live", "⚓ Canlı gemiler"], ["ships", "⚓ Deniz rotaları"], ["news", "📰 Haberler"]];
      bar.innerHTML = "";
      items.forEach(([id, t]) => {
        const on = id in layers ? !!layers[id] : layerState[id];
        const b = document.createElement("button"); b.className = "tog" + (on ? " on" : ""); b.textContent = t;
        b.onclick = async () => { b.classList.add("on"); await setLayer(id, !on); renderLayerBar(); }; bar.append(b);
      });
      const s = document.createElement("input"); s.placeholder = "Yer ara… (Enter)"; s.className = "globe-search";
      s.onkeydown = async (e) => { if (e.key !== "Enter") return; const g = await JV.api("/api/geo/geocode?q=" + encodeURIComponent(s.value)); if (g.lat != null) { flyTo(g.lat, g.lon, g.zoom); addMark(g.lat, g.lon, g.ad.split(",")[0]); } else JV.toast && JV.toast(g.error || "Bulunamadı"); };
      bar.append(s);
    }

    // ---- sokak seviyesi (Leaflet) ----
    let map = null, base = null;
    async function ensureLeaflet() {
      if (window.L) return;
      await new Promise((ok, bad) => {
        const l = document.createElement("link"); l.rel = "stylesheet"; l.href = "https://unpkg.com/leaflet@1.9.4/dist/leaflet.css"; document.head.append(l);
        const s = document.createElement("script"); s.src = "https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"; s.onload = ok; s.onerror = bad; document.head.append(s);
      });
    }
    async function openMap(lat, lon, z = 16, sat = true, radar = false) {
      const panel = document.getElementById("map-panel"); panel.classList.remove("hidden");
      try { await ensureLeaflet(); } catch (e) { panel.innerHTML = "<p class='note'>Harita kütüphanesi yüklenemedi (internet?).</p>"; return; }
      if (!map) {
        map = L.map("map-view", { zoomControl: true });
        const osm = L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", { maxZoom: 19, attribution: "© OpenStreetMap" });
        const esri = L.tileLayer("https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}", { maxZoom: 19, attribution: "© Esri World Imagery" });
        const yd = new Date(Date.now() - 864e5).toISOString().slice(0, 10);
        const gibs = L.tileLayer(`https://gibs.earthdata.nasa.gov/wmts/epsg3857/best/VIIRS_SNPP_CorrectedReflectance_TrueColor/default/${yd}/GoogleMapsCompatible_Level9/{z}/{y}/{x}.jpg`, { maxZoom: 9, attribution: "NASA GIBS" });
        const over = {};
        try { const rv = await JV.api("/api/watch/radar"); const f = rv.frames[rv.frames.length - 1]; if (f) over["☔ Yağış radarı (canlı)"] = L.tileLayer(`${rv.host}${f.path}/256/{z}/{x}/{y}/2/1_1.png`, { opacity: 0.7, attribution: "RainViewer" }); } catch (e) {}
        map._layersJV = { osm, esri, over }; L.control.layers({ "Sokak": osm, "Uydu": esri, "NASA dünkü uydu": gibs }, over).addTo(map);
      }
      if (base) map.removeLayer(base);
      base = sat ? map._layersJV.esri : map._layersJV.osm; base.addTo(map);
      map.setView([lat, lon], z); setTimeout(() => map.invalidateSize(), 50);
      L.marker([lat, lon]).addTo(map);
      if (radar && map._layersJV.over["☔ Yağış radarı (canlı)"]) { map._layersJV.over["☔ Yağış radarı (canlı)"].addTo(map); map.setZoom(7); }
    }
    document.getElementById("map-close").onclick = () => document.getElementById("map-panel").classList.add("hidden");

    // ---- hikâye (tarih turu) ----
    let story = null;
    function playStory(title, events) {
      story = { i: 0, events };
      marks.clear && marks.children.slice().forEach((c) => marks.remove(c));
      U.panel(`<div class="wp-title">${title}</div><div id="story-list" class="wp-story"></div>`);
      const list = document.getElementById("story-list");
      events.forEach((e, i) => { const d = document.createElement("div"); d.className = "st"; d.id = "st" + i; d.innerHTML = `<b>${e.year ?? ""}</b> ${e.text}`; list.append(d); });
      const next = () => {
        if (!story || story.i >= events.length) { U.caption(""); return; }
        const e = events[story.i];
        flyTo(e.lat, e.lon, 1.7, 1600); addMark(e.lat, e.lon, String(e.year ?? ""), 0xffb02e);
        if (story.i > 0) { const p = events[story.i - 1]; addArc(p, e, 0); }
        document.querySelectorAll(".wp-story .st").forEach((d, k) => d.classList.toggle("on", k === story.i));
        U.caption(`${e.year ?? ""}  ${e.text}`);
        story.i++; story.t = setTimeout(next, 5200);
      };
      next();
    }

    // ---- dünya nesnesi ----
    let hoverEl = null;
    return {
      scene,
      async enter() {
        controls.minDistance = 1.03; controls.maxDistance = 8; controls.enablePan = false; controls.rotateSpeed = 0.5; controls.zoomSpeed = 0.7;
        controls.target.set(0, 0, 0);
        if (camera.position.length() < 1.05 || camera.position.length() > 10) camera.position.set(0, 0.8, 3.2);
        atmo.material.uniforms.c.value = U.color();
        document.getElementById("globe-layers").classList.remove("hidden");
        await loadData(); renderLayerBar();
        sun.position.copy(sunPos());
      },
      exit() { document.getElementById("globe-layers").classList.add("hidden"); clearTimeout(story && story.t); story = null; if (hoverEl) hoverEl.style.display = "none"; },
      update(dt, t) {
        clouds.rotation.y += dt * 0.004;
        const d = camera.position.length();
        controls.rotateSpeed = Math.max(0.05, (d - 1) * 0.35);
        [...cityG.children, ...marks.children, ...["ships", "news", "events"].flatMap((k) => (layers[k] && layers[k].children) || [])].forEach((s) => {
          if (s.isSprite) { const k = s.userData.base * Math.max(0.15, (d - 1) / 1.5); s.scale.set(k * s.userData.aspect, k, 1); }
          if (s.userData && s.userData.pulse) { const k = 1 + 0.35 * Math.sin(t * 4); s.scale.setScalar(k); }
        });
        if (layers.quakes) layers.quakes.children.forEach((m, i) => m.scale.setScalar(1 + 0.4 * Math.sin(t * 3 + i)));
        cityG.children.forEach((s) => { if (s.isSprite) s.visible = d < 2.6; });
        document.getElementById("street-hint").classList.toggle("hidden", d > 1.12);
      },
      click(ray) {
        const hit = ray.intersectObject(earth)[0];
        if (!hit) return;
        if (layers.quakes) {
          const q = ray.intersectObjects(layers.quakes.children)[0];
          if (q) { const e = q.object.userData.quake; U.panel(`<div class="wp-title">Deprem M${e.büyüklük}</div><div class="wp-grid"><i>Yer</i><b>${e.yer}</b><i>Zaman</i><b>${e.zaman}</b><i>Derinlik</i><b>${U.fmt(e.derinlik_km, 1)} km</b></div>`); return; }
        }
        for (const id of ["events", "news"]) {
          if (!layers[id]) continue;
          const h2 = ray.intersectObjects(layers[id].children.filter((x) => !x.isSprite && !x.isLine))[0];
          if (h2 && h2.object.userData.ev) { const e = h2.object.userData.ev; U.panel(`<div class="wp-title">${e.ad}</div><div class="wp-grid"><i>Tür</i><b>${e.tür_tr}</b><i>Son konum</i><b>${e.son[0]}°, ${e.son[1]}°</b><i>Tarih</i><b>${e.son[2]}</b>${e.son[3] ? `<i>Şiddet</i><b>${e.son[3]} ${e.son[4] || ""}</b>` : ""}<i>İz noktası</i><b>${e.iz.length}</b></div>${e.kaynak ? `<a href="${e.kaynak}" target="_blank">kaynak ↗</a>` : ""}`); return; }
          if (h2 && h2.object.userData.news) { const c = h2.object.userData.news; U.panel(`<div class="wp-title">${c.ülke}</div>${c.haberler.map((h) => `<div class="st on"><a href="${h.link}" target="_blank">${h.başlık}</a><div class="wp-sub">${h.tarih}</div></div>`).join("")}`); return; }
        }
        const ll = U.v2ll(hit.point);
        const c = countryAt(ll.lat, ll.lon);
        if (c) showCountry(c); else { highlightCountry(null); U.panel(`<div class="wp-title">Okyanus / deniz</div><div class="wp-grid"><i>Konum</i><b>${ll.lat.toFixed(2)}°, ${ll.lon.toFixed(2)}°</b></div>`); }
      },
      hover(ray, e) {
        hoverEl = hoverEl || document.getElementById("world-tip");
        const hit = ray.intersectObject(earth)[0];
        const c = hit && countryAt(...Object.values(U.v2ll(hit.point)));
        if (c) { hoverEl.textContent = c.n; hoverEl.style.display = "block"; hoverEl.style.left = e.clientX + 14 + "px"; hoverEl.style.top = e.clientY + 10 + "px"; }
        else hoverEl.style.display = "none";
      },
      streetHere() { const ll = U.v2ll(camera.position); openMap(ll.lat, ll.lon, 15, true); },
      cmd(ui, r, args) {
        if (ui === "globe_fly") {
          flyTo(r.lat, r.lon, r.zoom || 2);
          if (r.bilgi) { const c = countries.find((x) => x.n === r.bilgi.ülke); if (c) setTimeout(() => showCountry(c), 1900); }
          else setTimeout(() => addMark(r.lat, r.lon, (r.ad || "").split(",")[0]), 1800);
          if (r.katman) setLayer(r.katman, true);
        } else if (ui === "globe_layer") Promise.resolve(setLayer(r.layer, r.on, r)).then(renderLayerBar);
        else if (ui === "globe_mark") { addMark(r.lat, r.lon, r.label); flyTo(r.lat, r.lon, 1.8); }
        else if (ui === "globe_distance") {
          addMark(r.a.lat, r.a.lon, r.a.ad.split(",")[0], 0x4dd2ff); addMark(r.b.lat, r.b.lon, r.b.ad.split(",")[0], 0x4dd2ff); addArc(r.a, r.b, r.km);
          const m = U.ll2v(r.a.lat, r.a.lon).add(U.ll2v(r.b.lat, r.b.lon)).normalize(); const ll = U.v2ll(m);
          flyTo(ll.lat, ll.lon, 1.6 + Math.min(2, r.km / 6000));
        } else if (ui === "globe_story") playStory(r.title, r.events || []);
        else if (ui === "map") { flyTo(r.lat, r.lon, 1.2); setTimeout(() => openMap(r.lat, r.lon, r.radar ? 7 : 17, r.uydu !== false, !!r.radar), 1700); }
      },
      flyTo, addMark,
    };
  })();
  document.getElementById("street-hint").onclick = () => W.globe.streetHere();
})();
