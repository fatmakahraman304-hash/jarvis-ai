/* JARVIS içinde video (YouTube): "Fenerbahçe maç özetini aç", "son videoyu aç". Bazı kanallar başka sitede oynatmayı kapatır;
   o durumda "YouTube'da aç" düğmesi kullanılır. Esc ya da ✕ kapatır; yeni soru sorunca kapanmaz (izlemeye devam). */
(function () {
  const JV = (window.JV = window.JV || {});
  let el;
  function build() {
    if (el) return;
    el = document.createElement("div"); el.id = "videopanel"; el.className = "hidden";
    el.innerHTML = `<div class="vp-top"><span id="vp-title"></span><a id="vp-yt" class="mini" target="_blank" rel="noopener">YouTube'da aç ↗</a><button class="mini" id="vp-x">✕</button></div><div class="vp-frame"><iframe id="vp-if" allow="autoplay; encrypted-media; picture-in-picture; fullscreen" allowfullscreen referrerpolicy="strict-origin-when-cross-origin"></iframe></div>`;
    document.body.append(el);
    el.querySelector("#vp-x").onclick = close;
    addEventListener("keydown", (e) => { if (e.key === "Escape" && !el.classList.contains("hidden") && !el.classList.contains("in-stage")) close(); });
  }
  function open(r) {
    build();
    if (!r || !/^[\w-]{11}$/.test(r.id || "")) return;
    el.querySelector("#vp-title").textContent = [r.title, r.channel, r.when].filter(Boolean).join(" · ");
    el.querySelector("#vp-yt").href = r.url || `https://www.youtube.com/watch?v=${r.id}`;
    el.querySelector("#vp-if").src = `https://www.youtube-nocookie.com/embed/${r.id}?autoplay=1&rel=0&modestbranding=1`;
    el.classList.remove("hidden");
    // orta sahneye yerleş: çekirdek gider, video gelir (kapatınca çekirdek geri döner)
    if (JV.stage) { el.classList.add("in-stage"); JV.stage.mount(el, { kind: "VİDEO", title: el.querySelector("#vp-title").textContent, link: el.querySelector("#vp-yt").href, onClose: stop }); }
  }
  function stop() { if (!el) return; el.classList.add("hidden"); el.querySelector("#vp-if").src = "about:blank"; }
  function close() { if (!el) return; if (JV.stage && el.classList.contains("in-stage")) { el.classList.remove("in-stage"); JV.stage.release(el); } stop(); }
  JV.video = { open, close };
})();
