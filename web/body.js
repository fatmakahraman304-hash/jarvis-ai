/* VÜCUT — tarayıcıda MediaPipe (görüntü bilgisayardan çıkmaz), küçük bir HUD köşede:
   DURUŞ: ilk 5 sn'deki oturuşunu "iyi" kabul eder; öne eğilir/çökersen ya da ekrana çok yaklaşırsan nazikçe uyarır (5 dk'da en fazla 1).
          20 dakikada bir göz molası (20-20-20: 20 sn boyunca 6 metre uzağa bak).
   EGZERSİZ: squat / şınav / zıplama (jumping jack) tekrarlarını eklem açılarından sayar ve sesli söyler; hedefe ulaşınca kutlar.
   RUH HALİ: yüz ifadesinden (gülümseme, kaş, göz, ağız) mutlu / şaşkın / düşünceli / yorgun / nötr; uzun süre yorgunsan mola önerir. */
(function () {
  const JV = (window.JV = window.JV || {});
  const say = (t) => JV.say && JV.say(t, JV.currentPersona && JV.currentPersona());
  let hud, v, cv, ctx, stream = null, kind = "", raf = 0, lastT = 0, target = 0;
  const S = { reps: 0, phase: "up", base: null, calib: [], badSince: 0, lastWarn: 0, sitSince: 0, lastBreak: 0, mood: "", moodSince: 0, lastMoodSay: 0, lastSaidRep: 0 };

  function build() {
    if (hud) return;
    hud = document.createElement("div"); hud.id = "bodyhud"; hud.className = "hidden";
    hud.innerHTML = `<div class="bh-top"><b id="bh-title"></b><button class="mini" id="bh-x">✕</button></div><div class="bh-cam"><video muted playsinline autoplay></video><canvas></canvas></div><div id="bh-big"></div><div id="bh-sub"></div>`;
    document.body.append(hud); v = hud.querySelector("video"); cv = hud.querySelector("canvas"); ctx = cv.getContext("2d");
    hud.querySelector("#bh-x").onclick = stop;
  }
  const TITLES = { posture: "DURUŞ · GÖZ MOLASI", squat: "SQUAT SAYACI", pushup: "ŞINAV SAYACI", jumping: "ZIPLAMA SAYACI", mood: "RUH HALİ" };
  async function start(k, tgt = 0) {
    if (k === "off") return stop();
    build(); kind = k; target = tgt || 0; Object.assign(S, { reps: 0, phase: "up", base: null, calib: [], badSince: 0, sitSince: performance.now(), lastBreak: performance.now(), mood: "", lastSaidRep: 0 });
    hud.classList.remove("hidden"); hud.querySelector("#bh-title").textContent = TITLES[k] || k;
    set(k === "posture" ? "kalibre ediliyor… dik otur" : k === "mood" ? "…" : "0", k === "mood" ? "" : target ? `hedef ${target}` : "");
    if (!stream) {
      try { stream = await navigator.mediaDevices.getUserMedia({ video: { width: 640, height: 480, facingMode: "user" }, audio: false }); v.srcObject = stream; await v.play().catch(() => {}); }
      catch (e) { set("kamera yok", e.message); return; }
    }
    try { await JV.mp.load(k === "mood" ? "face" : "pose", { numFaces: 1 }); } catch (e) { set("model yüklenemedi", "internet gerekli"); return; }
    if (k !== "posture" && k !== "mood") say(`${TITLES[k].split(" ")[0].toLowerCase()} sayacı hazır. ${target ? target + " tekrar hedef. " : ""}Başlayabilirsiniz.`);
    cancelAnimationFrame(raf); loop();
  }
  function stop() { kind = ""; cancelAnimationFrame(raf); if (stream) stream.getTracks().forEach((t) => t.stop()); stream = null; if (hud) hud.classList.add("hidden"); }
  function set(big, sub) { hud.querySelector("#bh-big").textContent = big; hud.querySelector("#bh-sub").textContent = sub || ""; }

  const ang = (a, b, c) => { const ab = [a.x - b.x, a.y - b.y], cb = [c.x - b.x, c.y - b.y]; const d = (ab[0] * cb[0] + ab[1] * cb[1]) / (Math.hypot(...ab) * Math.hypot(...cb) || 1); return Math.acos(Math.max(-1, Math.min(1, d))) * 180 / Math.PI; };
  const vis = (p) => p && (p.visibility == null || p.visibility > 0.5);
  function loop() {
    if (!kind) return; raf = requestAnimationFrame(loop);
    const now = performance.now(); if (now - lastT < 70 || v.readyState < 2) return; lastT = now;
    cv.width = v.videoWidth || 320; cv.height = v.videoHeight || 240;
    let r;
    try { r = (kind === "mood" ? JV.mp._cache("face") : JV.mp._cache("pose")).detectForVideo(v, now); } catch (e) { return; }
    ctx.clearRect(0, 0, cv.width, cv.height);
    if (kind === "mood") return mood((r.faceBlendshapes || [])[0], now);
    const P = (r.landmarks || [])[0]; if (!P) { set(kind === "posture" ? "—" : String(S.reps), "kadrajda değilsin"); return; }
    ctx.fillStyle = "#4df"; P.forEach((p) => { if (vis(p)) { ctx.beginPath(); ctx.arc((1 - p.x) * cv.width, p.y * cv.height, 3, 0, 7); ctx.fill(); } });
    if (kind === "posture") posture(P, now); else exercise(P, now);
  }
  function rep() {
    S.reps++; set(String(S.reps), target ? `hedef ${target}` : "");
    JV.fxSound && JV.fxSound("found");
    if (target && S.reps >= target) { say(`${S.reps}! Tebrikler, hedefe ulaştınız.`); setTimeout(stop, 2500); }
    else if (!JV.speaking) say(String(S.reps));
  }
  function exercise(P, now) {
    const L = (i, j) => (vis(P[i]) ? P[i] : P[j]);
    if (kind === "squat") {
      const a = Math.min(ang(P[23], P[25], P[27]), ang(P[24], P[26], P[28]));
      if (S.phase === "up" && a < 105) S.phase = "down"; else if (S.phase === "down" && a > 160) { S.phase = "up"; rep(); }
      hud.querySelector("#bh-sub").textContent = `diz açısı ${Math.round(a)}° · ${S.phase === "down" ? "⬇ in" : "⬆ kalk"}${target ? " · hedef " + target : ""}`;
    } else if (kind === "pushup") {
      const a = Math.min(ang(P[11], P[13], P[15]), ang(P[12], P[14], P[16]));
      if (S.phase === "up" && a < 95) S.phase = "down"; else if (S.phase === "down" && a > 155) { S.phase = "up"; rep(); }
      hud.querySelector("#bh-sub").textContent = `dirsek ${Math.round(a)}°${target ? " · hedef " + target : ""}`;
    } else if (kind === "jumping") {
      const handsUp = P[15].y < P[0].y && P[16].y < P[0].y, feetWide = Math.abs(P[27].x - P[28].x) > Math.abs(P[11].x - P[12].x) * 1.4;
      if (S.phase === "up" && handsUp && feetWide) S.phase = "down"; else if (S.phase === "down" && !handsUp && !feetWide) { S.phase = "up"; rep(); }
    }
  }
  function posture(P, now) {
    const sw = Math.hypot(P[11].x - P[12].x, P[11].y - P[12].y) || 0.2; // omuz genişliği (ölçek)
    const shY = (P[11].y + P[12].y) / 2, drop = (shY - P[0].y) / sw; // burun omuzların ne kadar üstünde (çökünce azalır)
    const m = { drop, sw };
    if (!S.base) { S.calib.push(m); if (S.calib.length > 40) { S.base = { drop: S.calib.reduce((a, b) => a + b.drop, 0) / S.calib.length, sw: S.calib.reduce((a, b) => a + b.sw, 0) / S.calib.length }; say("Duruşunuz kaydedildi. Eğilirseniz haber vereceğim."); } return; }
    const slouch = drop < S.base.drop - 0.18, close = sw > S.base.sw * 1.3;
    const bad = slouch || close;
    if (bad) { if (!S.badSince) S.badSince = now; } else S.badSince = 0;
    const mins = Math.floor((now - S.sitSince) / 60000);
    set(bad && now - S.badSince > 3000 ? (close ? "ÇOK YAKIN" : "EĞİK") : "İYİ ✓", `oturuş ${mins} dk · sonraki göz molası ${Math.max(0, 20 - Math.floor((now - S.lastBreak) / 60000))} dk`);
    hud.querySelector("#bh-big").style.color = bad && now - S.badSince > 3000 ? "#ffb347" : "#3cff8a";
    if (S.badSince && now - S.badSince > 20000 && now - S.lastWarn > 300000) { S.lastWarn = now; say(close ? "Efendim, ekrana biraz fazla yaklaştınız; gözleriniz için geri yaslanın." : "Efendim, biraz dik oturur musunuz? Sırtınız teşekkür edecek."); }
    if (now - S.lastBreak > 20 * 60000) { S.lastBreak = now; say("Göz molası: yirmi saniye boyunca altı metre uzağa bakın."); JV.toast && JV.toast("👀 Göz molası: 20 sn uzağa bak (20-20-20)", 20000); }
  }
  function mood(bs, now) {
    if (!bs) { set("—", "yüz görünmüyor"); return; }
    const g = (n) => (bs.categories.find((c) => c.categoryName === n) || { score: 0 }).score;
    const smile = (g("mouthSmileLeft") + g("mouthSmileRight")) / 2, brow = (g("browDownLeft") + g("browDownRight")) / 2, wide = (g("eyeWideLeft") + g("eyeWideRight")) / 2,
      jaw = g("jawOpen"), blink = (g("eyeBlinkLeft") + g("eyeBlinkRight")) / 2, inner = g("browInnerUp"), squint = (g("eyeSquintLeft") + g("eyeSquintRight")) / 2;
    let m = "nötr";
    if (smile > 0.5) m = "mutlu"; else if (jaw > 0.35 && (wide > 0.3 || inner > 0.4)) m = "şaşkın"; else if (brow > 0.35) m = "düşünceli"; else if (blink > 0.45 || (squint > 0.5 && smile < 0.2)) m = "yorgun";
    const E = { mutlu: "😊", şaşkın: "😮", düşünceli: "🤔", yorgun: "😴", nötr: "🙂" };
    if (m !== S.mood) { S.mood = m; S.moodSince = now; }
    set(`${E[m]} ${m.toUpperCase()}`, `gülümseme ${Math.round(smile * 100)} · kaş ${Math.round(brow * 100)} · göz kapağı ${Math.round(blink * 100)}`);
    if (m === "yorgun" && now - S.moodSince > 60000 && now - S.lastMoodSay > 900000) { S.lastMoodSay = now; say("Biraz yorgun görünüyorsunuz efendim. Kısa bir mola ve bir bardak su iyi gelebilir."); }
    if (m === "mutlu" && now - S.moodSince > 1500 && now - S.lastMoodSay > 600000) { S.lastMoodSay = now; say("Gülümsemeniz sistemlerimi de ısıttı efendim."); }
  }
  JV.body = { start, stop, cmd: (r) => start(r.kind || "posture", r.target), get kind() { return kind; }, _state: () => ({ ...S, kind }), _feedPose: (P, now) => (kind === "posture" ? posture(P, now) : exercise(P, now)), _feedMood: (bs, now) => mood(bs, now) };
})();
