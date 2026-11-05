/* GÜNCELLE: tek tuşla güncelleme. Yeni sürüm varsa düğmede rozet çıkar; basınca notları gösterir, onaylayınca indirir,
   test eder, kurar ve JARVIS kendini yeniden başlatır; sayfa yeni sürümle kendiliğinden yenilenir. */
(function () {
  const JV = (window.JV = window.JV || {});
  const $ = (s, r = document) => r.querySelector(s);
  const esc = (t) => String(t == null ? "" : t).replace(/[&<>"]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" })[c]);
  let root, info = null;

  function build() {
    if (root) return; root = document.createElement("div"); root.id = "updater"; root.className = "hidden";
    root.innerHTML = `<div class="up-card"><div class="s-head"><span>GÜNCELLEME</span><button class="mini" id="up-x">KAPAT ✕</button></div>
      <div id="up-body" class="up-body"></div><div class="up-bar"><b id="up-prog"></b></div><div id="up-step" class="note"></div>
      <div class="cam-row"><button class="btn-primary" id="up-go">⟳ GÜNCELLE</button><button class="mini" id="up-check">KONTROL ET</button><button class="mini" id="up-back">↶ ÖNCEKİ SÜRÜME DÖN</button></div></div>`;
    document.body.append(root);
    $("#up-x", root).onclick = () => root.classList.add("hidden");
    $("#up-check", root).onclick = () => check(true);
    $("#up-go", root).onclick = apply;
    $("#up-back", root).onclick = async () => { if (!confirmBox("Önceki sürüme dönülsün mü?")) return; await JV.api("/api/update", { body: { action: "rollback" } }); waitRestart(); };
  }
  const confirmBox = (t) => window.confirm(t);
  function render() {
    const b = $("#up-body", root);
    if (!info) { b.textContent = "Kontrol ediliyor…"; return; }
    if (info.hata) { b.innerHTML = `<p>Şu anki sürüm: <b>v${esc(info.yerel)}</b></p><p class="dn">${esc(info.hata)}</p>`; $("#up-go", root).disabled = true; return; }
    $("#up-go", root).disabled = !info.yeni_var;
    b.innerHTML = info.yeni_var
      ? `<p>Şu anki sürüm: <b>v${esc(info.yerel)}</b> → yeni sürüm: <b class="up">v${esc(info.uzak)}</b> ${info.tarih ? `<small>(${esc(info.tarih)})</small>` : ""}</p>
         <ul>${(info.notlar || []).map((n) => `<li>${esc(n)}</li>`).join("")}</ul>
         <p class="note">Hafızan, ayarların, anahtarların (.env) ve eklentilerin korunur. Önce yeni sürüm test edilir; sorun çıkarsa hiçbir şey değişmez. Eski sürüm yedeklenir.</p>`
      : `<p>JARVIS güncel: <b>v${esc(info.yerel)}</b> ✓</p>${(info.yedekler || []).length ? `<p class="note">Yedekler: ${info.yedekler.map(esc).join(", ")}</p>` : ""}`;
    $("#up-back", root).style.display = (info.yedekler || []).length ? "" : "none";
  }
  async function check(force) {
    build(); info = null; render();
    try { info = await JV.api("/api/update" + (force ? "?force=1" : "")); } catch (e) { info = { hata: e.message, yerel: "?" }; }
    render(); badge();
  }
  function badge() { const t = $("#t-update"); if (t) t.classList.toggle("has-update", !!(info && info.yeni_var)); }
  async function apply() {
    $("#up-go", root).disabled = true;
    const poll = setInterval(async () => { try { const s = await JV.api("/api/update?state=1"); $("#up-prog", root).style.width = (s.ilerleme || 0) + "%"; $("#up-step", root).textContent = s.adım || ""; } catch (e) {} }, 700);
    let r; try { r = await JV.api("/api/update", { body: { action: "apply" } }); } catch (e) { r = { durum: "hata", hata: e.message }; }
    clearInterval(poll);
    if (r.durum === "güncellendi") { $("#up-prog", root).style.width = "100%"; $("#up-step", root).textContent = `v${r.yeni} kuruldu. Yeniden başlatılıyor…`; JV.say && JV.say("Güncelleme tamamlandı, yeniden başlıyorum.", JV.persona ? JV.persona() : "jarvis"); waitRestart(); }
    else { $("#up-step", root).innerHTML = `<span class="dn">${esc(r.hata || r.durum)}</span>`; $("#up-go", root).disabled = false; }
  }
  function waitRestart() {
    let down = false;
    const t = setInterval(async () => {
      try { const r = await fetch("/api/state", { cache: "no-store" }); if (r.ok && down) { clearInterval(t); location.reload(); } else if (!r.ok) down = true; }
      catch (e) { down = true; }
    }, 1500);
    setTimeout(() => { clearInterval(t); location.reload(); }, 60000);
  }
  JV.updater = { open: () => { build(); root.classList.remove("hidden"); check(false); }, check };
  document.addEventListener("DOMContentLoaded", () => {
    const b = $("#t-update"); if (b) b.onclick = JV.updater.open;
    setTimeout(async () => { try { info = await JV.api("/api/update"); badge(); } catch (e) {} }, 5000);
  });
})();
