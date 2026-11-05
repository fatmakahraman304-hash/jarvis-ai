/* ARAYÜZ KABUĞU
   - ⊞ UYGULAMALAR: alttaki kalabalık düğmeler kategorili, hologram bir başlatıcıya taşındı (alt şeritte yalnızca temel düğmeler kalır).
   - KOMUT PALETİ (Ctrl+K ya da "/"): her özelliği ve sık komutu yazarak bul, Enter ile çalıştır.
   - Üst bar: tarih + mini hava (tıkla → büyük hava paneli). Bildirimler sağ üstte HUD kartı (ilerleme çizgili).
   - Diyalog: saat damgası, kopyala düğmesi, "yazıyor" animasyonu, araç adları Türkçe.
   - Öneri çipleri (günün saatine göre), uyku ekranında büyük saat + hava. */
(function () {
  const JV = (window.JV = window.JV || {});
  const $ = (s, r = document) => r.querySelector(s);
  const esc = (s) => String(s == null ? "" : s).replace(/[&<>"]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]));
  const norm = (s) => (s || "").toLocaleLowerCase("tr").replace(/[ıİ]/g, "i").replace(/ğ/g, "g").replace(/ü/g, "u").replace(/ş/g, "s").replace(/ö/g, "o").replace(/ç/g, "c");
  const cmd = (t) => JV.sendCommand && JV.sendCommand(t);
  const CORE = ["t-visual", "t-voice", "t-wake", "t-camera", "t-gesture", "t-estop", "t-settings"];
  // [kategori, id ya da sanal, ikon, ad, açıklama, eylem (sanal için)]
  const APPS = [
    ["GÖRÜŞ & AR", "t-scan", "🔎", "Tara", "Odayı tara → tıkla, hologram; nesne bul, belge, QR, renk, bitki"],
    ["GÖRÜŞ & AR", "v-arfx", "✨", "AR Efekt", "Ateş, mühür, gezegen, şimşek, kitaplık", () => JV.gesture && JV.gesture.start("efekt")],
    ["GÖRÜŞ & AR", "v-ardesk", "🖥", "AR Masaüstü", "Avuçta menü, elle taşınan paneller", () => JV.handfx && JV.handfx.cmd({ action: "desktop" })],
    ["GÖRÜŞ & AR", "v-helmet", "🛡", "Kask Modu", "Yüzüne Iron Man kaskı + HUD", () => JV.handfx && JV.handfx.cmd({ action: "extra", extra: "mask" })],
    ["GÖRÜŞ & AR", "t-cams", "📹", "Kameralar", "Telefon kameraları, güvenlik modu"],
    ["GÖRÜŞ & AR", "t-body", "🧍", "Vücut", "Duruş, göz molası, egzersiz sayacı, ruh hali"],
    ["ÜRETKENLİK", "t-meet", "🎙", "Toplantı", "Canlı döküm, özet, kararlar, yapılacaklar"],
    ["ÜRETKENLİK", "t-focus", "⏳", "Odak", "25 dk pomodoro, bildirimler susar"],
    ["ÜRETKENLİK", "v-weather", "⛅", "Hava", "Büyük hava paneli, 7 gün", () => JV.weather && JV.weather.open()],
    ["ÜRETKENLİK", "t-news", "📰", "Gündem", "Aydınlat beni: haber sahneleri"],
    ["ÜRETKENLİK", "t-books", "📖", "Kitaplık", "Kitapların, notlar, raftan kitap çek"],
    ["ÜRETKENLİK", "t-library", "📚", "Bilgi Merkezi", "Belgelerine soru sor, sınav, harita"],
    ["ÜRETKENLİK", "t-translate", "🌐", "Çevirmen", "Canlı karşılıklı tercüman"],
    ["YAŞAM & EĞLENCE", "t-music", "🎵", "Müzik", "Müzik stüdyosu"],
    ["YAŞAM & EĞLENCE", "t-finlab", "📈", "Finans", "Piyasa, kredi, birikim laboratuvarı"],
    ["YAŞAM & EĞLENCE", "v-rps", "✊", "Taş-Kağıt-Makas", "Elinle JARVIS'e karşı", () => JV.handfx && JV.handfx.cmd({ action: "game", game: "rps" })],
    ["YAŞAM & EĞLENCE", "v-balloon", "🎈", "Balon Patlat", "30 saniye, rekor tut", () => JV.handfx && JV.handfx.cmd({ action: "game", game: "balloons" })],
    ["YAŞAM & EĞLENCE", "v-fortune", "☕", "Kahve Falı", "Fincanı kameraya göster", () => JV.fortune && JV.fortune()],
    ["YAŞAM & EĞLENCE", "t-ambient", "🎧", "Ortam Sesleri", "Alarm, cam kırılması, bebek, kapı zili"],
    ["SİSTEM", "t-command", "⌘", "Komuta Merkezi", "Modlar, makrolar, modüller"],
    ["SİSTEM", "v-sleep", "😴", "Uyku", "Ekran kararır, iki alkışla uyan", () => JV.sleep && JV.sleep.enter()],
    ["SİSTEM", "t-update", "⟳", "Güncelle", "Tek tuşla yeni sürüm"],
  ];
  const QUICK = [
    ["☀", "Sabah brifingi", "Sabah brifingini ver"], ["⛅", "Hava durumu", "Hava durumunu göster"], ["📰", "Gündem", "Aydınlat beni"],
    ["📧", "Maillerim", "Okunmamış maillerimi özetle"], ["📅", "Bugünkü programım", "Bugünkü programım ne?"], ["✅", "Yapılacaklar", "Yapılacaklar listemde ne var?"],
    ["🔎", "Odayı tara", "Odayı tara"], ["🔍", "Kumandayı bul", "Kumandayı bul"], ["💱", "Dolar kaç TL", "Dolar şu an kaç TL?"], ["🥇", "Altın fiyatları", "Gram altın kaç TL?"],
    ["⏳", "50 dk odak", "50 dakika odak modu başlat"], ["📔", "Günlüğe yaz", "Günlüğüme yaz: "], ["🎙", "Toplantıyı kaydet", "Toplantıyı kaydet"],
  ];

  // ================= başlatıcı =================
  let launcher, palette, pIdx = 0, pList = [];
  function buildLauncher() {
    const row = $("#bottom .ctrl-row"); if (!row) return;
    const apps = document.createElement("button"); apps.className = "tog tog-apps"; apps.id = "t-apps"; apps.title = "Uygulamalar (Ctrl+K: komut paleti)"; apps.innerHTML = "⊞ UYGULAMALAR";
    row.insertBefore(apps, $("#t-estop") || null);
    launcher = document.createElement("div"); launcher.id = "launcher"; launcher.className = "hidden";
    launcher.innerHTML = `<div class="ln-card"><div class="ln-top"><b>⊞ UYGULAMALAR</b><input id="ln-q" placeholder="ara… (Ctrl+K)"><button class="mini" id="ln-x">✕</button></div><div class="ln-body"></div></div>`;
    document.body.append(launcher);
    const body = $(".ln-body", launcher); let cat = "";
    APPS.forEach(([c, id, ic, name, desc, fn]) => {
      if (c !== cat) { cat = c; body.insertAdjacentHTML("beforeend", `<h5>${c}</h5><div class="ln-grid" data-cat="${c}"></div>`); }
      const grid = body.lastElementChild;
      const tile = document.createElement("button"); tile.className = "ln-tile"; tile.dataset.k = norm(name + " " + desc); tile.innerHTML = `<span>${ic}</span><b>${esc(name)}</b><small>${esc(desc)}</small>`;
      const real = id.startsWith("t-") ? document.getElementById(id) : null;
      if (real) { real.classList.add("ln-src"); } // asıl düğme gizlenir, tıklaması korunur
      tile.onclick = () => { closeLauncher(); real ? real.click() : fn && fn(); };
      grid.append(tile);
    });
    // asıl şeritten temel olmayanları gizle (bağlı kodlar çalışmaya devam eder)
    row.querySelectorAll(".tog").forEach((b) => { if (b.id && !CORE.includes(b.id) && b.id !== "t-apps") b.classList.add("ln-src"); });
    apps.onclick = () => (launcher.classList.contains("hidden") ? openLauncher() : closeLauncher());
    $("#ln-x", launcher).onclick = closeLauncher;
    launcher.addEventListener("click", (e) => { if (e.target === launcher) closeLauncher(); });
    $("#ln-q", launcher).oninput = (e) => { const q = norm(e.target.value); launcher.querySelectorAll(".ln-tile").forEach((t) => (t.style.display = !q || t.dataset.k.includes(q) ? "" : "none")); };
  }
  function openLauncher() { launcher.classList.remove("hidden"); $("#t-apps").classList.add("on"); setTimeout(() => $("#ln-q", launcher).focus(), 50); }
  function closeLauncher() { launcher.classList.add("hidden"); $("#t-apps") && $("#t-apps").classList.remove("on"); $("#ln-q", launcher).value = ""; launcher.querySelectorAll(".ln-tile").forEach((t) => (t.style.display = "")); }

  // ================= komut paleti =================
  function buildPalette() {
    palette = document.createElement("div"); palette.id = "palette"; palette.className = "hidden";
    palette.innerHTML = `<div class="pl-card"><input id="pl-q" placeholder="Bir özellik ya da komut yaz… (Enter: çalıştır · Esc: kapat)"><ul id="pl-list"></ul><div class="pl-foot">↑↓ seç · Enter çalıştır · bulunamazsa JARVIS'e sorulur</div></div>`;
    document.body.append(palette);
    palette.addEventListener("click", (e) => { if (e.target === palette) closePalette(); });
    const q = $("#pl-q", palette);
    q.oninput = () => renderPalette(q.value);
    q.onkeydown = (e) => {
      if (e.key === "ArrowDown") { pIdx = Math.min(pList.length - 1, pIdx + 1); paint(); e.preventDefault(); }
      if (e.key === "ArrowUp") { pIdx = Math.max(0, pIdx - 1); paint(); e.preventDefault(); }
      if (e.key === "Enter") { e.preventDefault(); runPalette(pList[pIdx], q.value); }
      if (e.key === "Escape") closePalette();
    };
  }
  function items() {
    return APPS.map(([c, id, ic, name, desc, fn]) => ({ ic, name, desc, cat: c, run: () => (id.startsWith("t-") ? document.getElementById(id).click() : fn && fn()) }))
      .concat(QUICK.map(([ic, name, text]) => ({ ic, name, desc: "“" + text + "”", cat: "KOMUT", run: () => (text.endsWith(": ") ? ($("#q").value = text, $("#q").focus()) : cmd(text)) })));
  }
  function renderPalette(v) {
    const q = norm(v).trim(), all = items();
    pList = q ? all.filter((x) => norm(x.name + " " + x.desc + " " + x.cat).includes(q)) : all.slice(0, 12);
    if (q) pList.push({ ic: "💬", name: `JARVIS'e sor: “${v}”`, desc: "", cat: "SOR", run: () => cmd(v) });
    pIdx = 0; paint();
  }
  function paint() {
    const ul = $("#pl-list", palette); ul.innerHTML = "";
    pList.slice(0, 14).forEach((x, i) => { const li = document.createElement("li"); li.className = i === pIdx ? "on" : ""; li.innerHTML = `<span>${x.ic}</span><b>${esc(x.name)}</b><small>${esc(x.desc)}</small><i>${esc(x.cat)}</i>`; li.onmouseenter = () => { pIdx = i; paint(); }; li.onclick = () => runPalette(x); ul.append(li); });
  }
  function runPalette(x, raw) { closePalette(); if (x) x.run(); else if (raw && raw.trim()) cmd(raw); }
  function openPalette() {
    palette.classList.remove("hidden"); const q = $("#pl-q", palette); q.value = ""; renderPalette("");
    if (document.activeElement && document.activeElement.blur) document.activeElement.blur();
    q.focus(); setTimeout(() => q.focus(), 30); setTimeout(() => q.focus(), 150);
  }
  function closePalette() { palette.classList.add("hidden"); }

  // ================= üst bar: tarih + mini hava =================
  let wxBox;
  function buildHeader() {
    const clock = $("#clock"); if (!clock) return;
    wxBox = document.createElement("div"); wxBox.id = "hdr-extra"; wxBox.innerHTML = `<span id="hdr-date"></span><button id="hdr-wx" title="Hava durumu (tıkla: büyük panel)"></button>`;
    clock.after(wxBox);
    $("#hdr-wx").onclick = () => JV.weather && JV.weather.open();
    const tick = () => { $("#hdr-date").textContent = new Date().toLocaleDateString("tr-TR", { weekday: "long", day: "numeric", month: "long" }).toUpperCase(); };
    tick(); setInterval(tick, 60000);
    loadWx(); setInterval(loadWx, 15 * 60000);
  }
  let lastWx = null;
  async function loadWx() {
    try { const w = await JV.api("/api/hud/weather"); if (w && !w.error) { lastWx = w; $("#hdr-wx").innerHTML = `${JV.wxIcon ? JV.wxIcon(w.ikon, 22) : ""}<b>${w.derece}°</b><small>${esc(w.şehir)}</small>`; } } catch (e) {}
  }

  // ================= bildirimler (HUD kartı) =================
  function upgradeToasts() {
    const box = $("#toasts"); if (!box) return;
    new MutationObserver((ms) => ms.forEach((m) => m.addedNodes.forEach((n) => {
      if (!(n instanceof HTMLElement) || !n.classList.contains("toast") || n._up) return; n._up = true;
      const t = n.textContent, ic = /^[\p{Extended_Pictographic}⚠⛔✓✗]/u.test(t) ? "" : (/hata|başarısız|olmadı|açılamadı|geçersiz/i.test(t) ? "⚠" : /kaydedildi|tamam|eklendi|bağlandı|✓/i.test(t) ? "✓" : "ℹ");
      if (ic) n.dataset.ic = ic;
      if (/hata|başarısız|geçersiz|⚠|✗/i.test(t)) n.classList.add("t-bad"); else if (/kaydedildi|eklendi|bağlandı|✓|hazır/i.test(t)) n.classList.add("t-ok");
      n.insertAdjacentHTML("beforeend", `<i class="t-bar"></i>`);
    }))).observe(box, { childList: true });
  }

  // ================= diyalog süsleri =================
  const TOOL = { web_search: "🔎 internette arıyor", news_search: "📰 haberlere bakıyor", read_webpage: "📄 sayfayı okuyor", weather: "⛅ hava", weather_panel: "⛅ hava paneli",
    gmail_search: "📧 mailler", calendar_events: "📅 takvim", room_scan: "🔎 oda taraması", room_camera_look: "📹 kameraya bakıyor", camera_look: "📷 kameraya bakıyor", screen_look: "🖥 ekrana bakıyor",
    remember: "🧠 hatırlıyor", recall: "🧠 hafızada arıyor", deep_recall: "🧠 hafızada arıyor", todo_add: "✅ işe ekliyor", todo_list: "✅ işler", set_alarm: "⏰ alarm", set_reminder: "⏰ hatırlatıcı",
    market_price: "💱 piyasa", gold_prices: "🥇 altın", currency: "💱 kur", youtube_play: "▶ YouTube", spotify_play: "🎵 Spotify", open_app: "🚀 uygulama açıyor", news_show: "📰 gündem", book_list: "📖 kitaplık" };
  function upgradeLog() {
    const log = $("#log"); if (!log) return;
    new MutationObserver((ms) => ms.forEach((m) => m.addedNodes.forEach((n) => {
      if (!(n instanceof HTMLElement) || n._up) return; n._up = true;
      if (n.classList.contains("tool")) { const name = (n.textContent.match(/⚙\s*([\w]+)/) || [])[1]; if (name && TOOL[name]) n.textContent = TOOL[name] + " …"; return; }
      if (!n.classList.contains("msg")) return;
      const who = n.querySelector(".who"); if (who) who.insertAdjacentHTML("beforeend", `<time>${new Date().toLocaleTimeString("tr-TR", { hour: "2-digit", minute: "2-digit" })}</time>`);
      if (n.classList.contains("ai")) {
        const b = document.createElement("button"); b.className = "msg-copy"; b.title = "Kopyala"; b.textContent = "⧉";
        b.onclick = () => { const t = n.querySelector(".body").textContent; navigator.clipboard && navigator.clipboard.writeText(t); b.textContent = "✓"; setTimeout(() => (b.textContent = "⧉"), 1200); };
        n.append(b);
      }
    }))).observe(log, { childList: true });
  }

  // ================= öneri çipleri =================
  function buildChips() {
    const ask = $("#ask"); if (!ask) return;
    const box = document.createElement("div"); box.id = "chips"; ask.before(box);
    const render = () => {
      const h = new Date().getHours();
      const pick = h < 11 ? ["Sabah brifingi", "Hava durumu", "Bugünkü programım", "Maillerim", "Gündem"] : h < 18 ? ["Yapılacaklar", "50 dk odak", "Maillerim", "Dolar kaç TL", "Odayı tara"] : ["Gündem", "Hava durumu", "Günlüğe yaz", "Altın fiyatları", "Kumandayı bul"];
      box.innerHTML = ""; pick.forEach((n) => { const q = QUICK.find((x) => x[1] === n); if (!q) return; const c = document.createElement("button"); c.type = "button"; c.className = "chip"; c.innerHTML = `${q[0]} ${esc(q[1])}`; c.onclick = () => (q[2].endsWith(": ") ? ($("#q").value = q[2], $("#q").focus()) : cmd(q[2])); box.append(c); });
    };
    render(); setInterval(render, 30 * 60000);
    const q = $("#q"); q.addEventListener("input", () => box.classList.toggle("hide", !!q.value));
  }

  // ================= uyku ekranı: büyük saat =================
  function sleepClock() {
    const ov = document.getElementById("sleepov"); if (!ov || ov._clock) return; ov._clock = true;
    const c = document.createElement("div"); c.className = "sl-clock"; ov.prepend(c);
    const draw = () => { const d = new Date(); c.innerHTML = `<b>${d.toLocaleTimeString("tr-TR", { hour: "2-digit", minute: "2-digit" })}</b><span>${d.toLocaleDateString("tr-TR", { weekday: "long", day: "numeric", month: "long" })}</span>${lastWx ? `<small>${lastWx.şehir} ${lastWx.derece}° · ${esc(lastWx.durum)}</small>` : ""}`; };
    draw(); setInterval(draw, 10000);
  }

  // ================= kısayollar =================
  addEventListener("keydown", (e) => {
    const typing = /INPUT|TEXTAREA|SELECT/.test((e.target.tagName || "")) || e.target.isContentEditable;
    if ((e.ctrlKey || e.metaKey) && (e.key === "k" || e.key === "K") && !e.shiftKey) { e.preventDefault(); palette.classList.contains("hidden") ? openPalette() : closePalette(); }
    else if (e.key === "/" && !typing) { e.preventDefault(); openPalette(); }
    else if (e.key === "Escape") { if (!palette.classList.contains("hidden")) closePalette(); if (launcher && !launcher.classList.contains("hidden")) closeLauncher(); }
  });

  function init() {
    if (JV.isCamRole) return;
    buildLauncher(); buildPalette(); buildHeader(); upgradeToasts(); upgradeLog(); buildChips();
    const t = setInterval(() => { if (document.getElementById("sleepov")) { sleepClock(); clearInterval(t); } }, 1000);
    document.addEventListener("click", () => { if (document.getElementById("sleepov")) sleepClock(); }, { once: true });
  }
  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", init); else init();
  JV.shell = { openLauncher, closeLauncher, openPalette, closePalette, apps: () => APPS.map((a) => a[3]) };
})();
