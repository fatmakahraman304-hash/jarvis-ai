/* GÜNCELLE: tek tuşla güncelleme. Yeni sürüm varsa düğmede rozet çıkar; basınca notları gösterir, onaylayınca indirir,
   test eder, kurar ve JARVIS kendini yeniden başlatır; sayfa yeni sürümle kendiliğinden yenilenir. */
(function () {
  const JV = (window.JV = window.JV || {});
  const $ = (s, r = document) => r.querySelector(s);
  const esc = (t) => String(t == null ? "" : t).replace(/[&<>"]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" })[c]);
  let root, info = null, busy = false;

  function controls(active) {
    busy = active;
    $("#up-go", root).disabled = active || !info || !!info.hata || !info.yeni_var;
    $("#up-check", root).disabled = active;
    $("#up-back", root).disabled = active;
  }

  function build() {
    if (root) return; root = document.createElement("div"); root.id = "updater"; root.className = "hidden";
    root.innerHTML = `<div class="up-card"><div class="s-head"><span>GÜNCELLEME</span><button class="mini" id="up-x">KAPAT ✕</button></div>
      <div id="up-body" class="up-body"></div><div class="up-bar"><b id="up-prog"></b></div><div id="up-step" class="note"></div>
      <div class="cam-row"><button class="btn-primary" id="up-go">⟳ GÜNCELLE</button><button class="mini" id="up-check">KONTROL ET</button><button class="mini" id="up-back">↶ ÖNCEKİ SÜRÜME DÖN</button></div></div>`;
    document.body.append(root);
    $("#up-x", root).onclick = () => root.classList.add("hidden");
    $("#up-check", root).onclick = () => check(true);
    $("#up-go", root).onclick = apply;
    $("#up-back", root).onclick = rollback;
  }
  const confirmBox = (t) => window.confirm(t);
  function render() {
    const b = $("#up-body", root);
    if (!info) { b.textContent = "Kontrol ediliyor…"; return; }
    if (info.hata) { b.innerHTML = `<p>Şu anki sürüm: <b>v${esc(info.yerel)}</b></p><p class="dn">${esc(info.hata)}</p>`; $("#up-go", root).disabled = true; return; }
    $("#up-go", root).disabled = busy || !info.yeni_var;
    b.innerHTML = info.yeni_var
      ? `<p>Şu anki sürüm: <b>v${esc(info.yerel)}</b> → yeni sürüm: <b class="up">v${esc(info.uzak)}</b> ${info.tarih ? `<small>(${esc(info.tarih)})</small>` : ""}</p>
         <ul>${(info.notlar || []).map((n) => `<li>${esc(n)}</li>`).join("")}</ul>
         <p class="note">Hafızan, ayarların, anahtarların (.env) ve eklentilerin korunur. Önce yeni sürüm test edilir; sorun çıkarsa hiçbir şey değişmez. Eski sürüm yedeklenir.</p>`
      : `<p>JARVIS güncel: <b>v${esc(info.yerel)}</b> ✓</p>${(info.yedekler || []).length ? `<p class="note">Yedekler: ${info.yedekler.map(esc).join(", ")}</p>` : ""}`;
    $("#up-back", root).style.display = (info.yedekler || []).length ? "" : "none";
  }
  async function check(force) {
    if (busy) return;
    build(); info = null; render();
    try { info = await JV.api("/api/update" + (force ? "?force=1" : "")); } catch (e) { info = { hata: e.message, yerel: "?" }; }
    render(); badge();
  }
  function badge() { const t = $("#t-update"); if (t) t.classList.toggle("has-update", !!(info && info.yeni_var)); }
  async function apply() {
    if (busy) return;
    controls(true);
    let polling = true, timer = null;
    async function poll() {
      if (!polling) return;
      try {
        const s = await JV.api("/api/update?state=1");
        if (!polling) return;
        $("#up-prog", root).style.width = Math.max(0, Math.min(100, Number(s.ilerleme) || 0)) + "%";
        $("#up-step", root).textContent = s.adım || "Güncelleme hazırlanıyor…";
      } catch (e) {
        if (!polling) return;
        $("#up-step", root).textContent = "Güncelleme durumu okunamıyor; bağlantı yeniden denenecek…";
      }
      if (polling) timer = setTimeout(poll, 900);
    }
    poll();
    let r;
    try { r = await JV.api("/api/update", { body: { action: "apply" } }); }
    catch (e) { r = { durum: "hata", hata: e.message }; }
    polling = false;
    if (timer) clearTimeout(timer);
    if (r.durum === "güncellendi") {
      $("#up-prog", root).style.width = "100%";
      $("#up-step", root).textContent = `v${r.yeni} kuruldu. Yeniden başlatılıyor…`;
      JV.say && JV.say("Güncelleme tamamlandı, yeniden başlıyorum.", JV.persona ? JV.persona() : "jarvis");
      waitRestart(r.yeni);
    } else {
      $("#up-step", root).textContent = r.hata || r.durum || "Güncelleme tamamlanamadı.";
      controls(false);
    }
  }
  async function rollback() {
    if (busy || !confirmBox("Önceki sürüme dönülsün mü?")) return;
    controls(true);
    $("#up-step", root).textContent = "Önceki sürüm geri yükleniyor…";
    try {
      const r = await JV.api("/api/update", { body: { action: "rollback" } });
      if (r.durum !== "geri alındı") throw new Error(r.hata || r.error || r.durum || "Geri dönüş tamamlanamadı.");
      $("#up-step", root).textContent = "Önceki sürüm geri yüklendi. Yeniden başlatılıyor…";
      waitRestart();
    } catch (e) {
      $("#up-step", root).textContent = e.message;
      controls(false);
    }
  }
  function waitRestart(expectedVersion) {
    let down = false, pending = false, done = false;
    const reopen = () => {
      if (done) return;
      done = true;
      clearInterval(t);
      clearTimeout(fallback);
      location.reload();
    };
    const t = setInterval(async () => {
      if (pending || done) return;
      pending = true;
      const controller = new AbortController();
      const timeout = setTimeout(() => controller.abort(), 4000);
      try {
        const r = await fetch("/api/state", { cache: "no-store", headers: { "x-token": JV.token || "" }, signal: controller.signal });
        if (r.ok) {
          const state = await r.json();
          if (down || (expectedVersion && state.version === expectedVersion)) reopen();
        } else down = true;
      } catch (e) {
        down = true;
      } finally {
        clearTimeout(timeout);
        pending = false;
      }
    }, 1500);
    const fallback = setTimeout(reopen, 60000);
  }
  JV.updater = { open: () => { build(); root.classList.remove("hidden"); check(false); }, check };
  document.addEventListener("DOMContentLoaded", () => {
    const b = $("#t-update"); if (b) b.onclick = JV.updater.open;
    setTimeout(async () => { try { info = await JV.api("/api/update"); badge(); } catch (e) {} }, 5000);
  });
})();
