/* Görsel stüdyo görüntüleyici: üretilen/düzenlenen resim, logo, video ve galeriyi büyük ekranda gösterir. */
(function () {
  const JV = (window.JV = window.JV || {});
  let root;
  const src = (p) => "/api/files/download?path=" + encodeURIComponent(p) + "&token=" + encodeURIComponent(JV.token || "");
  const isVid = (p) => /\.(mp4|webm|mov|mkv)$/i.test(p);
  function build() {
    if (root) return;
    root = document.createElement("div"); root.id = "studio"; root.className = "hidden";
    root.innerHTML = `<div class="st-card"><div class="s-head"><span id="st-title">STÜDYO</span><span><a class="mini" id="st-dl" download>İNDİR</a> <button class="mini" id="st-close">KAPAT ✕</button></span></div>
      <div class="st-main" id="st-main"></div><div class="st-strip" id="st-strip"></div><div class="note" id="st-note"></div></div>`;
    document.body.append(root);
    root.querySelector("#st-close").onclick = () => root.classList.add("hidden");
    root.addEventListener("click", (e) => { if (e.target === root) root.classList.add("hidden"); });
  }
  function showOne(p) {
    const m = root.querySelector("#st-main"); m.innerHTML = "";
    const el = document.createElement(isVid(p) ? "video" : "img");
    el.src = src(p); if (isVid(p)) { el.controls = true; el.autoplay = true; }
    el.onerror = () => { m.innerHTML = '<div class="note">Dosya gösterilemedi: ' + p.replace(/</g, "&lt;") + "</div>"; };
    m.append(el);
    const dl = root.querySelector("#st-dl"); dl.href = src(p); dl.setAttribute("download", p.split(/[\\/]/).pop());
    root.querySelectorAll(".st-strip > *").forEach((t) => t.classList.toggle("on", t.dataset.p === p));
  }
  function open(r) {
    build();
    const files = r.files && r.files.length ? r.files : [r.path];
    root.querySelector("#st-title").textContent = (r.title || "STÜDYO").toUpperCase();
    root.querySelector("#st-note").textContent = r.path ? r.path : "";
    const strip = root.querySelector("#st-strip"); strip.innerHTML = "";
    if (files.length > 1) files.forEach((f) => {
      const t = document.createElement(isVid(f) ? "video" : "img"); t.src = src(f); t.dataset.p = f; t.muted = true; t.onclick = () => showOne(f); strip.append(t);
    });
    showOne(r.path && !(r.ui === "gallery") ? r.path : files[0]);
    root.classList.remove("hidden");
  }
  JV.studio = { open };
})();
