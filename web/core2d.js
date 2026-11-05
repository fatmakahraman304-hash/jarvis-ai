/* YENİ ÇEKİRDEK GÖRSELLERİ (2D, keskin, akıcı):
   • REAKTÖR — dönen kadranlı dış halka, sesle/düşünmeyle yanan 30 bobin dilimi, ses dalgası halkası, altıgen çekirdek, yörüngede ışıklar
   • DALGA   — yan yana akan parlak ses dalgaları (konuşunca/dinleyince büyür)
   visual.js her karede çağırır; Three.js gerekmez. */
(function () {
  const JV = (window.JV = window.JV || {});
  const TAU = Math.PI * 2;
  function rgbOf(hex) {
    const m = /^#?([0-9a-f]{6})$/i.exec(String(hex || "").trim());
    const n = m ? parseInt(m[1], 16) : 0x38d6ff; return `${(n >> 16) & 255},${(n >> 8) & 255},${n & 255}`;
  }
  function stateOf() {
    const b = document.body.classList;
    if (JV.speaking) return "speak"; if (b.contains("listening")) return "listen"; if (b.contains("thinking")) return "think"; return "idle";
  }
  const LABEL = { speak: "KONUŞUYOR", listen: "DİNLİYOR", think: "İŞLENİYOR", idle: "BEKLEMEDE" };
  let smooth = 0, thinkMix = 0;

  function reactor(g, o) {
    const { t, cx, cy, R, hex } = o, rgb = rgbOf(hex), C = (a) => `rgba(${rgb},${Math.max(0, Math.min(1, a))})`;
    const st = stateOf(); smooth += ((o.lvl || 0) - smooth) * 0.25; const lvl = smooth;
    thinkMix += ((st === "think" ? 1 : 0) - thinkMix) * 0.06;
    g.save(); g.translate(cx, cy);
    // yumuşak ışıma
    const gl = g.createRadialGradient(0, 0, 0, 0, 0, R * 1.7);
    gl.addColorStop(0, C(0.16 + lvl * 0.25)); gl.addColorStop(0.42, C(0.05)); gl.addColorStop(1, C(0));
    g.fillStyle = gl; g.fillRect(-R * 1.8, -R * 1.8, R * 3.6, R * 3.6);
    g.globalCompositeOperation = "lighter"; g.lineCap = "round";
    // dış kadran
    g.save(); g.rotate(t * 0.03);
    for (let i = 0; i < 180; i++) {
      const a = (i / 180) * TAU, big = i % 15 === 0, mid = i % 5 === 0;
      const r0 = R * 1.2, r1 = r0 + R * (big ? 0.07 : mid ? 0.04 : 0.022);
      g.strokeStyle = C(big ? 0.75 : mid ? 0.4 : 0.18); g.lineWidth = big ? 1.6 : 1;
      g.beginPath(); g.moveTo(Math.cos(a) * r0, Math.sin(a) * r0); g.lineTo(Math.cos(a) * r1, Math.sin(a) * r1); g.stroke();
    }
    g.restore();
    g.lineWidth = 1; g.strokeStyle = C(0.16); g.beginPath(); g.arc(0, 0, R * 1.13, 0, TAU); g.stroke();
    // ters dönen ince yaylar
    [[1.36, 0.9, -0.11, 0.35], [1.36, 0.35, -0.11, 0.35], [1.43, 2.2, 0.06, 0.16], [1.06, 0.5, 0.5, 0.5], [1.06, 0.25, 0.5, 0.5]].forEach(([rr, len, sp, al], i) => {
      const a = t * sp + i * 2.1; g.strokeStyle = C(al); g.lineWidth = i < 2 ? 2 : 1;
      g.beginPath(); g.arc(0, 0, R * rr, a, a + len); g.stroke();
    });
    // derece yazıları
    g.font = `${Math.max(9, R * 0.045)}px 'JetBrains Mono','Share Tech Mono',monospace`; g.fillStyle = C(0.45); g.textAlign = "center"; g.textBaseline = "middle";
    ["000", "090", "180", "270"].forEach((s, i) => { const a = (i / 4) * TAU - Math.PI / 2; g.fillText(s, Math.cos(a) * R * 1.5, Math.sin(a) * R * 1.5); });
    // bobin dilimleri
    const N = 30, r1 = R * 0.74, r2 = R * 0.9, gap = 0.035;
    const head = t * (1.1 + thinkMix * 4.5);
    for (let i = 0; i < N; i++) {
      const a0 = (i / N) * TAU + gap, a1 = ((i + 1) / N) * TAU - gap, am = (a0 + a1) / 2;
      const sweep = Math.pow(Math.max(0, Math.cos(am - head)), 6);
      const beat = lvl * (0.5 + 0.5 * Math.sin(i * 2.3 + t * 11));
      const k = 0.14 + sweep * (0.45 + thinkMix * 0.35) + beat * 0.7;
      g.beginPath(); g.arc(0, 0, r2, a0, a1); g.arc(0, 0, r1, a1, a0, true); g.closePath();
      g.fillStyle = C(k * 0.55); g.fill(); g.strokeStyle = C(Math.min(1, k + 0.1)); g.lineWidth = 1; g.stroke();
    }
    // ses dalgası halkası
    g.beginPath();
    for (let i = 0; i <= 160; i++) {
      const a = (i / 160) * TAU;
      const d = (Math.sin(a * 6 + t * 3) * 0.5 + Math.sin(a * 11 - t * 5.3) * 0.35 + Math.sin(a * 17 + t * 8) * 0.15) * R * (0.008 + lvl * 0.1);
      const r = R * 0.6 + d; i ? g.lineTo(Math.cos(a) * r, Math.sin(a) * r) : g.moveTo(Math.cos(a) * r, Math.sin(a) * r);
    }
    g.strokeStyle = C(0.55 + lvl * 0.45); g.lineWidth = 1.4 + lvl * 1.5; g.stroke();
    // altıgen çekirdek
    const hexp = (r, rot) => { g.beginPath(); for (let i = 0; i <= 6; i++) { const a = rot + (i / 6) * TAU; i ? g.lineTo(Math.cos(a) * r, Math.sin(a) * r) : g.moveTo(Math.cos(a) * r, Math.sin(a) * r); } };
    hexp(R * 0.42, t * 0.15); g.strokeStyle = C(0.55); g.lineWidth = 1.4; g.stroke();
    hexp(R * 0.33, -t * 0.32); g.strokeStyle = C(0.3); g.lineWidth = 1; g.stroke();
    for (let i = 0; i < 6; i++) { const a = t * 0.15 + (i / 6) * TAU; g.strokeStyle = C(0.22); g.beginPath(); g.moveTo(Math.cos(a) * R * 0.25, Math.sin(a) * R * 0.25); g.lineTo(Math.cos(a) * R * 0.42, Math.sin(a) * R * 0.42); g.stroke(); }
    const cr = R * 0.22 * (1 + lvl * 0.3 + Math.sin(t * 2) * 0.025 + thinkMix * Math.sin(t * 9) * 0.05);
    const cg = g.createRadialGradient(0, 0, 0, 0, 0, cr * 1.6);
    cg.addColorStop(0, "rgba(255,255,255,.95)"); cg.addColorStop(0.35, C(0.9)); cg.addColorStop(0.7, C(0.25)); cg.addColorStop(1, C(0));
    g.fillStyle = cg; g.beginPath(); g.arc(0, 0, cr * 1.6, 0, TAU); g.fill();
    // yörüngedeki ışıklar (iz bırakarak)
    [[0.99, 0.55, 0], [1.06, -0.38, 2], [1.13, 0.8, 4]].forEach(([rr, sp, ph]) => {
      for (let k = 0; k < 14; k++) {
        const a = (t - k * 0.03) * sp + ph, al = (1 - k / 14) * 0.8;
        g.fillStyle = C(al); g.beginPath(); g.arc(Math.cos(a) * R * rr, Math.sin(a) * R * rr, Math.max(0.6, 2.4 - k * 0.15), 0, TAU); g.fill();
      }
    });
    g.globalCompositeOperation = "source-over";
    // alt etiket
    g.textAlign = "center"; g.fillStyle = C(0.85);
    g.font = `600 ${Math.max(10, R * 0.06)}px 'Chakra Petch','Rajdhani',sans-serif`;
    try { g.letterSpacing = "6px"; } catch (e) {}
    g.fillText(o.name || "J.A.R.V.I.S.", 0, R * 1.66);
    g.font = `${Math.max(9, R * 0.042)}px 'JetBrains Mono',monospace`; g.fillStyle = C(0.5);
    try { g.letterSpacing = "4px"; } catch (e) {}
    g.fillText("● " + LABEL[st], 0, R * 1.8);
    try { g.letterSpacing = "0px"; } catch (e) {}
    g.restore();
  }

  function wave(g, o) {
    const { t, cx, cy, R, hex } = o, rgb = rgbOf(hex), C = (a) => `rgba(${rgb},${a})`;
    const st = stateOf(); smooth += ((o.lvl || 0) - smooth) * 0.2; const lvl = smooth;
    thinkMix += ((st === "think" ? 1 : 0) - thinkMix) * 0.06;
    const W = R * 3.4, x0 = cx - W / 2;
    g.save();
    const gl = g.createRadialGradient(cx, cy, 0, cx, cy, R * 1.8); gl.addColorStop(0, C(0.12 + lvl * 0.2)); gl.addColorStop(1, C(0));
    g.fillStyle = gl; g.fillRect(cx - R * 2, cy - R * 2, R * 4, R * 4);
    g.globalCompositeOperation = "lighter";
    g.strokeStyle = C(0.12); g.lineWidth = 1; g.beginPath(); g.moveTo(x0, cy); g.lineTo(x0 + W, cy); g.stroke();
    const amp = R * (0.05 + lvl * 0.8 + thinkMix * 0.12);
    for (let k = 0; k < 6; k++) {
      const f = 1.2 + k * 0.55, sp = (k % 2 ? -1 : 1) * (1.4 + k * 0.4 + thinkMix * 3), ph = k * 1.3;
      g.beginPath();
      for (let i = 0; i <= 200; i++) {
        const u = i / 200, env = Math.pow(Math.sin(Math.PI * u), 2.2);
        const y = cy + Math.sin(u * TAU * f + t * sp + ph) * amp * env * (1 - k * 0.12);
        i ? g.lineTo(x0 + u * W, y) : g.moveTo(x0, y);
      }
      g.strokeStyle = k === 0 ? "rgba(255,255,255,.75)" : C(0.65 - k * 0.08); g.lineWidth = k === 0 ? 2 : 1.4; g.stroke();
    }
    // nokta ızgarası
    for (let i = 0; i < 48; i++) { const x = x0 + (i / 47) * W, h = 2 + Math.abs(Math.sin(i * 0.9 + t * 4)) * lvl * R * 0.35; g.fillStyle = C(0.25); g.fillRect(x - 1, cy + R * 0.95 - h, 2, h); }
    g.globalCompositeOperation = "source-over";
    g.textAlign = "center"; g.fillStyle = C(0.85); g.font = `600 ${Math.max(10, R * 0.06)}px 'Chakra Petch',sans-serif`;
    try { g.letterSpacing = "6px"; } catch (e) {}
    g.fillText(o.name || "J.A.R.V.I.S.", cx, cy - R * 0.85);
    g.font = `${Math.max(9, R * 0.042)}px 'JetBrains Mono',monospace`; g.fillStyle = C(0.5);
    g.fillText("● " + LABEL[st], cx, cy + R * 1.25);
    try { g.letterSpacing = "0px"; } catch (e) {}
    g.restore();
  }
  JV.core2d = { reactor, wave, modes: ["reactor", "wave", "sphere", "face"] };
})();
