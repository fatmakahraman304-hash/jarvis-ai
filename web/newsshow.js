/* "AYDINLAT BENİ" — gündem sahne sahne: tam ekran hologram kartlar, büyük sayı/kelime, kaynak rozetleri; her sahne sesli okunur,
   konuşma bitince sıradakine geçer. ◀ ▶ ya da ok tuşları, Esc kapatır. */
(function () {
  const JV = (window.JV = window.JV || {});
  const esc = (s) => String(s == null ? "" : s).replace(/[&<>"]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]));
  const COL = { ekonomi: "#ffcf5a", siyaset: "#ff7a7a", dünya: "#7ab8ff", spor: "#5aff9c", teknoloji: "#5ae8ff", bilim: "#c49bff", yaşam: "#ff9bd8", diğer: "#9fe" };
  let el, data = null, i = -1, timer = 0, playing = false;
  function build() {
    if (el) return;
    el = document.createElement("div"); el.id = "newsshow"; el.className = "hidden";
    el.innerHTML = `<div class="ns-top"><b>J.A.R.V.I.S. · GÜNDEM</b><span id="ns-n"></span><button class="mini" id="ns-prev">◀</button><button class="mini" id="ns-play">⏸</button><button class="mini" id="ns-next">▶</button><button class="mini" id="ns-x">✕</button></div>
      <div class="ns-stage"></div><div class="ns-bar"><i></i></div>`;
    document.body.append(el);
    el.querySelector("#ns-x").onclick = close; el.querySelector("#ns-prev").onclick = () => go(i - 1); el.querySelector("#ns-next").onclick = () => go(i + 1);
    el.querySelector("#ns-play").onclick = () => { playing = !playing; el.querySelector("#ns-play").textContent = playing ? "⏸" : "▶"; if (playing) wait(); else { clearTimeout(timer); JV.stopSpeaking && JV.stopSpeaking(); } };
    addEventListener("keydown", (e) => { if (el.classList.contains("hidden")) return; if (e.key === "Escape") close(); if (e.key === "ArrowRight") go(i + 1); if (e.key === "ArrowLeft") go(i - 1); });
  }
  function open(r) {
    build(); data = r; el.classList.remove("hidden"); playing = true; el.querySelector("#ns-play").textContent = "⏸";
    const st = el.querySelector(".ns-stage");
    st.innerHTML = `<div class="ns-card ns-intro on"><div class="ns-tag">${esc(new Date().toLocaleDateString("tr-TR", { weekday: "long", day: "numeric", month: "long" }))}</div><h1>${esc(r.topic ? r.topic.toUpperCase() : "GÜNDEM")}</h1><p>${esc(r.giriş || "")}</p></div>`;
    i = -1; speak(r.giriş || "Gündemi özetliyorum.", () => go(0));
  }
  function card(s, k) {
    const c = COL[(s.etiket || "").toLowerCase()] || COL.diğer;
    return `<div class="ns-card" style="--nc:${c}"><div class="ns-tag">${esc((s.etiket || "gündem").toUpperCase())} · ${k + 1}/${data.sahneler.length}</div>
      ${s.büyük ? `<div class="ns-big">${esc(s.büyük)}</div>` : ""}<h2>${esc(s.başlık)}</h2><p>${esc(s.anlatım)}</p>
      <div class="ns-src">${(s.kaynaklar || []).filter(Boolean).map((x) => `<span>${esc(x)}</span>`).join("")}</div></div>`;
  }
  function go(k) {
    if (!data) return; clearTimeout(timer);
    if (k >= data.sahneler.length) { if (data.kapanış) speak(data.kapanış, () => {}); el.querySelector("#ns-n").textContent = "BİTTİ"; return; }
    i = Math.max(0, k); const st = el.querySelector(".ns-stage");
    st.querySelectorAll(".ns-card").forEach((c) => { c.classList.remove("on"); c.classList.add("out"); setTimeout(() => c.remove(), 700); });
    st.insertAdjacentHTML("beforeend", card(data.sahneler[i], i));
    const c = st.lastElementChild; requestAnimationFrame(() => requestAnimationFrame(() => c.classList.add("on")));
    el.querySelector("#ns-n").textContent = `${i + 1} / ${data.sahneler.length}`;
    el.querySelector(".ns-bar i").style.width = ((i + 1) / data.sahneler.length * 100) + "%";
    JV.fxSound && JV.fxSound("lift");
    if (playing) speak(data.sahneler[i].anlatım, () => playing && go(i + 1));
  }
  function speak(t, next) {
    JV.say && JV.say(t, JV.currentPersona && JV.currentPersona());
    const t0 = Date.now(), minMs = Math.max(3500, t.length * 55);
    const check = () => { if (el.classList.contains("hidden")) return; if (Date.now() - t0 > minMs && !JV.speaking) next(); else timer = setTimeout(check, 400); };
    timer = setTimeout(check, 1200);
  }
  function wait() { speak(data.sahneler[i] ? data.sahneler[i].anlatım : "", () => playing && go(i + 1)); }
  function close() { clearTimeout(timer); playing = false; if (el) el.classList.add("hidden"); JV.stopSpeaking && JV.stopSpeaking(); }
  JV.newsshow = { open, close, go, get index() { return i; } };
})();
