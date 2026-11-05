/* ODAK MODU (pomodoro) — sağ üstte hologram halka sayaç; süre boyunca JARVIS sessiz (yalnızca güvenlik/hata konuşur).
   Bitince ses + "mola" hatırlatması; istatistik kaydedilir ("bugün kaç dakika odaklandım"). */
(function () {
  const JV = (window.JV = window.JV || {});
  let el, end = 0, total = 0, task = "", brk = 5, phase = "", iv = 0, wasQuiet = false, startedAt = 0;
  function build() {
    if (el) return;
    el = document.createElement("div"); el.id = "focusring"; el.className = "hidden";
    el.innerHTML = `<svg viewBox="0 0 120 120"><circle cx="60" cy="60" r="52" class="fr-bg"/><circle cx="60" cy="60" r="52" class="fr-fg"/></svg>
      <div class="fr-in"><b id="fr-t">25:00</b><span id="fr-p">ODAK</span></div><div id="fr-task"></div>
      <div class="fr-btns"><button class="mini" id="fr-pause">⏸</button><button class="mini" id="fr-stop">■</button></div>`;
    document.body.append(el);
    el.querySelector("#fr-stop").onclick = () => stop(true);
    el.querySelector("#fr-pause").onclick = () => { if (iv) { clearInterval(iv); iv = 0; el.dataset.left = end - Date.now(); el.querySelector("#fr-pause").textContent = "▶"; } else { end = Date.now() + +el.dataset.left; iv = setInterval(tick, 500); el.querySelector("#fr-pause").textContent = "⏸"; } };
  }
  function start(min = 25, t = "", b = 5) {
    build(); total = min * 60000; end = Date.now() + total; task = t; brk = b; phase = "odak"; startedAt = Date.now();
    wasQuiet = !!JV.quiet; JV.quiet = true;
    el.classList.remove("hidden", "break"); el.querySelector("#fr-p").textContent = "ODAK"; el.querySelector("#fr-task").textContent = t;
    clearInterval(iv); iv = setInterval(tick, 500); tick();
    JV.say && JV.say(`Odak modu ${min} dakika. Bildirimleri susturdum.`, JV.currentPersona && JV.currentPersona(), undefined, true);
  }
  function tick() {
    const left = Math.max(0, end - Date.now()), k = 1 - left / total, s = Math.ceil(left / 1000);
    el.querySelector("#fr-t").textContent = `${String(Math.floor(s / 60)).padStart(2, "0")}:${String(s % 60).padStart(2, "0")}`;
    el.querySelector(".fr-fg").style.strokeDashoffset = String(327 * (1 - k));
    if (left <= 0) phase === "odak" ? done() : stop(false);
  }
  async function done() {
    clearInterval(iv); JV.quiet = wasQuiet;
    JV.fxSound && JV.fxSound("found");
    let st = {}; try { st = await (await fetch("/api/life/focus_log", { method: "POST", headers: { "x-token": JV.token || "", "Content-Type": "application/json" }, body: JSON.stringify({ minutes: total / 60000, task, done: true }) })).json(); } catch (e) {}
    JV.say && JV.say(`Odak süresi bitti, tebrikler. Bugün toplam ${st.bugün_dk || Math.round(total / 60000)} dakika odaklandınız. ${brk} dakika mola verin.`, JV.currentPersona && JV.currentPersona(), undefined, true);
    phase = "mola"; total = brk * 60000; end = Date.now() + total; el.classList.add("break"); el.querySelector("#fr-p").textContent = "MOLA";
    iv = setInterval(tick, 500);
  }
  function stop(manual) {
    clearInterval(iv); iv = 0; JV.quiet = wasQuiet;
    if (manual && phase === "odak") { const m = (Date.now() - startedAt) / 60000; if (m > 1) fetch("/api/life/focus_log", { method: "POST", headers: { "x-token": JV.token || "", "Content-Type": "application/json" }, body: JSON.stringify({ minutes: m, task, done: false }) }).catch(() => {}); }
    if (!manual && phase === "mola") JV.say && JV.say("Mola bitti. Yeni bir odak turu için 'odak modu' deyin.", JV.currentPersona && JV.currentPersona());
    phase = ""; if (el) el.classList.add("hidden");
  }
  JV.focus = { start, stop, cmd: (r) => start(r.minutes || 25, r.task || "", r.break || 5), get phase() { return phase; }, _end: () => end, _finishNow: () => { end = Date.now(); tick(); } };
})();
