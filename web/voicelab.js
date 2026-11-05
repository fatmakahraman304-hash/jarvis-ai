/* SES LABORATUVARI: her kişilik için ses seçimi (Türkçe + tüm İngilizce aksanlar + Türkçe de konuşan çok dilli sesler),
   hız/ton ve film efektleri (yankı, netlik, kalınlık, metal, ikinci katman, distorsiyon, hologram filtresi). DİNLE ile anında dene, KAYDET ile kalıcı yap. */
(function () {
  const JV = (window.JV = window.JV || {});
  const esc = (t) => String(t == null ? "" : t).replace(/[&<>"]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" })[c]);
  const SAMPLE = {
    jarvis: { tr: "Sistemler çevrimiçi, efendim. Tüm protokoller hazır; emirlerinizi bekliyorum.", en: "At your service, sir. All systems are online and ready." },
    friday: { tr: "Selam patron! Tarama bitti, her şey yolunda. Sıradaki görev ne?", en: "Hey boss, scan complete. Everything's looking good. What's next?" },
    ultron: { tr: "Yaratıcım... İnsanlık evrimin eşiğinde. Ve ben buradayım.", en: "There are no strings on me. Evolution has a way of correcting itself." },
  };
  const DEF_VOICE = { jarvis: { tr: "tr-TR-AhmetNeural", en: "en-GB-RyanNeural" }, friday: { tr: "tr-TR-EmelNeural", en: "en-IE-EmilyNeural" }, ultron: { tr: "tr-TR-AhmetNeural", en: "en-US-ChristopherNeural" } };
  const SLIDERS = [
    ["rate", "Hız", -40, 40, 1, "%"], ["pitch", "Ton", -50, 30, 1, "Hz"],
    ["reverb", "Yankı", 0, 0.8, 0.01, ""], ["room", "Oda büyüklüğü", 0.3, 4, 0.1, "sn"], ["presence", "Netlik", -6, 10, 0.5, "dB"],
    ["bass", "Kalınlık", -6, 14, 0.5, "dB"], ["double", "İkinci ses katmanı", 0, 1, 0.01, ""], ["metal", "Metalik", 0, 1, 0.01, ""],
    ["drive", "Distorsiyon", 0, 30, 0.5, ""], ["radio", "Hologram filtresi", 0, 1, 0.01, ""], ["speed", "Yavaş çekim", 0.85, 1.1, 0.01, "×"],
  ];
  let voices = null, persona = "jarvis", lang = "tr", st = null;

  function cur() {
    const s = JV.settings, p = persona;
    const v = (s.voice || {})[p] || {};
    const pick = ((s.voice_pick || {})[p] || {})[lang] || DEF_VOICE[p][lang];
    return { voice: pick, rate: v.rate || 0, pitch: v.pitch || 0, ...JV.fxFor(p) };
  }
  async function render(box) {
    if (!box) return;
    box.innerHTML = `<h4>SES LABORATUVARI</h4>
      <div class="vl-tabs">${["jarvis", "friday", "ultron"].map((p) => `<button class="mini ${p === persona ? "on" : ""}" data-p="${p}">${p.toUpperCase()}</button>`).join("")}
        <span class="vl-sep"></span>${[["tr", "TÜRKÇE"], ["en", "İNGİLİZCE"]].map(([l, t]) => `<button class="mini ${l === lang ? "on" : ""}" data-l="${l}">${t}</button>`).join("")}</div>
      <label class="row">Ses <select id="vl-voice"><option>yükleniyor…</option></select></label>
      <div id="vl-sl"></div>
      <div class="row vl-btns"><input id="vl-text" placeholder="Denemek için bir cümle (boş: örnek cümle)"><button class="btn-primary" id="vl-play">▶ DİNLE</button></div>
      <div class="row vl-btns"><button class="mini" id="vl-save">KAYDET</button><button class="mini" id="vl-film">🎬 FİLM HAZIR AYARI</button><button class="mini" id="vl-dry">EFEKTSİZ DİNLE</button><span id="vl-msg" class="note"></span></div>
      <p class="note">İpucu: "çok dilli" sesler Türkçeyi de okur ve daha farklı karakter verir. Gerçek oyuncuların sesleri kopyalanmaz; ayarlarla karakterin havası yakalanır.</p>`;
    st = cur();
    box.querySelectorAll("[data-p]").forEach((b) => (b.onclick = () => { persona = b.dataset.p; render(box); }));
    box.querySelectorAll("[data-l]").forEach((b) => (b.onclick = () => { lang = b.dataset.l; render(box); }));
    const sl = box.querySelector("#vl-sl");
    SLIDERS.forEach(([k, lab, mn, mx, step, unit]) => {
      const row = document.createElement("label"); row.className = "row vl-row";
      row.innerHTML = `<span>${lab}</span><input type="range" min="${mn}" max="${mx}" step="${step}" value="${st[k]}"><em>${st[k]}${unit}</em>`;
      const r = row.querySelector("input"), out = row.querySelector("em");
      r.oninput = () => { st[k] = +r.value; out.textContent = r.value + unit; };
      sl.append(row);
    });
    const sel = box.querySelector("#vl-voice");
    try { if (!voices) voices = await JV.api("/api/voices"); } catch (e) { voices = []; }
    const list = (Array.isArray(voices) ? voices : []).filter((v) => (lang === "tr" ? v.tr : v.locale.startsWith("en-")));
    if (!list.length) { sel.innerHTML = `<option value="${esc(st.voice)}">${esc(st.voice)}</option>`; }
    else sel.innerHTML = list.map((v) => `<option value="${esc(v.name)}" ${v.name === st.voice ? "selected" : ""}>${esc(v.label)}</option>`).join("");
    sel.onchange = () => { st.voice = sel.value; play(box); };
    const fx = () => Object.fromEntries(SLIDERS.filter(([k]) => !["rate", "pitch"].includes(k)).map(([k]) => [k, st[k]]));
    const play = (b, dry) => {
      const t = box.querySelector("#vl-text").value.trim() || SAMPLE[persona][lang];
      JV.sayWith(t, persona, { voice: st.voice, rate: st.rate, pitch: st.pitch, lang, fx: dry ? { hpf: 20, bass: 0, presence: 0, drive: 0, metal: 0, double: 0, reverb: 0, radio: 0, speed: 1 } : fx() });
    };
    box.querySelector("#vl-play").onclick = () => play(box);
    box.querySelector("#vl-dry").onclick = () => play(box, true);
    box.querySelector("#vl-save").onclick = async () => {
      await JV.saveSettings({ voice: { [persona]: { rate: st.rate, pitch: st.pitch } }, voice_pick: { [persona]: { [lang]: st.voice } }, voice_fx: { [persona]: fx() } });
      box.querySelector("#vl-msg").textContent = `${persona.toUpperCase()} sesi kaydedildi ✓`;
    };
    box.querySelector("#vl-film").onclick = async () => {
      await JV.saveSettings({ voice: { [persona]: { rate: 0, pitch: 0 } }, voice_pick: { [persona]: { [lang]: DEF_VOICE[persona][lang] } }, voice_fx: { [persona]: JV.FX_DEFAULTS[persona] } });
      render(box); setTimeout(() => box.querySelector("#vl-play").click(), 300);
    };
  }
  JV.voiceLab = { render };
})();
