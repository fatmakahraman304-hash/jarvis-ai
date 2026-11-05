/* El hareketi tanıma çekirdeği (tarayıcıdan bağımsız, test edilebilir).
   Girdi: MediaPipe HandLandmarker'ın 21 noktası (x,y 0..1, z göreli), aynalı selfie görüntüsü varsayılır. */
(function (root) {
  const TIP = [4, 8, 12, 16, 20], PIP = [3, 6, 10, 14, 18], MCP = [2, 5, 9, 13, 17];
  const d = (a, b) => Math.hypot(a.x - b.x, a.y - b.y, (a.z || 0) - (b.z || 0));
  const d2 = (a, b) => Math.hypot(a.x - b.x, a.y - b.y);

  function palm(lm) { return d2(lm[0], lm[9]) || 1e-6; }

  function fingers(lm) {
    const p = palm(lm);
    // başparmak: uç, işaret parmağı köküne (5) ve serçe köküne (17) göre uzak mı?
    const thumb = d2(lm[4], lm[17]) > d2(lm[3], lm[17]) * 1.08 && d2(lm[4], lm[5]) > p * 0.45;
    const others = [1, 2, 3, 4].map((i) => d2(lm[0], lm[TIP[i]]) > d2(lm[0], lm[PIP[i]]) * 1.12 && d2(lm[TIP[i]], lm[MCP[i]]) > p * 0.45);
    return [thumb, ...others];
  }

  function pinchRatio(lm) { return d2(lm[4], lm[8]) / palm(lm); }

  function pose(lm) {
    const f = fingers(lm), n = f.filter(Boolean).length, pr = pinchRatio(lm);
    const [t, i, m, r, s] = f;
    const indexOut = d2(lm[8], lm[5]) > palm(lm) * 0.35 && lm[8].y < lm[5].y; // işaret parmağı avuca kıvrılmamış
    if (pr < 0.32 && indexOut && !m && !r) return "pinch";
    if (n === 0 || (!i && !m && !r && !s && !t)) return "fist";
    if (t && !i && !m && !r && !s) return lm[4].y < lm[0].y - palm(lm) * 0.3 ? "thumbs_up" : (lm[4].y > lm[0].y + palm(lm) * 0.3 ? "thumbs_down" : "thumb");
    if (n === 5) return "open";
    if (i && !m && !r && !s) return t ? "L" : "point";
    if (i && m && !r && !s) return "peace";
    if (i && m && r && !s) return "three";
    if (i && m && r && s && !t) return "four";
    if (i && s && !m && !r) return "rock";
    if (t && s && !i && !m && !r) return "call";
    return "other";
  }

  // el şeklinin konum/ölçek/dönmeden bağımsız vektörü (özel hareketler için)
  function normVec(lm) {
    const o = lm[0], p = palm(lm);
    const ang = Math.atan2(lm[9].x - o.x, -(lm[9].y - o.y));
    const c = Math.cos(-ang), s = Math.sin(-ang), v = [];
    for (let k = 1; k < 21; k++) {
      const x = (lm[k].x - o.x) / p, y = (lm[k].y - o.y) / p;
      v.push(x * c - y * s, x * s + y * c, ((lm[k].z || 0) - (o.z || 0)) / p * 0.5);
    }
    return v;
  }
  function vdist(a, b) { let s = 0; for (let i = 0; i < a.length; i++) s += (a[i] - b[i]) ** 2; return Math.sqrt(s / a.length); }
  function matchCustom(vec, lib, thr = 0.22) {
    let best = null, bd = 1e9;
    (lib || []).forEach((g) => { const dd = vdist(vec, g.vec); if (dd < bd) { bd = dd; best = g; } });
    return best && bd < thr ? { gesture: best, distance: bd } : null;
  }
  function center(lm) { return { x: (lm[0].x + lm[5].x + lm[9].x + lm[13].x + lm[17].x) / 5, y: (lm[0].y + lm[5].y + lm[9].y + lm[13].y + lm[17].y) / 5 }; }

  class Engine {
    constructor(opts = {}) {
      this.mirror = opts.mirror !== false;
      this.holdMs = opts.holdMs || 900;
      this.custom = opts.custom || [];
      this.h = {};          // el durumları (Left/Right)
      this.two = null;
    }
    update(hands, t) {
      const ev = [], seen = {};
      hands.forEach((hd) => {
        const lm = hd.lm, side = hd.handed || "Right";
        seen[side] = true;
        const st = this.h[side] || (this.h[side] = { pose: null, poseSince: t, fired: false, pinch: false, pinchAt: 0, grab: false, prevC: null, hist: [], prevPinchD: null });
        const p = pose(lm), c = center(lm), tip = lm[8];
        const X = (v) => (this.mirror ? 1 - v : v);
        const cur = { x: X(tip.x), y: tip.y }, cc = { x: X(c.x), y: c.y };
        ev.push({ type: "cursor", hand: side, x: cur.x, y: cur.y, pose: p });

        // poz bekletme
        if (p !== st.pose) { st.pose = p; st.poseSince = t; st.fired = false; }
        else if (!st.fired && t - st.poseSince > (p === "fist" ? this.holdMs * 2 : this.holdMs) && !["other", "pinch"].includes(p)) {
          st.fired = true; ev.push({ type: "pose_hold", hand: side, pose: p });
        }
        // özel hareket
        if (this.custom.length && !["pinch"].includes(p)) {
          const m = matchCustom(normVec(lm), this.custom);
          if (m) {
            if (st.customName !== m.gesture.name) { st.customName = m.gesture.name; st.customSince = t; st.customFired = false; }
            else if (!st.customFired && t - st.customSince > 800) { st.customFired = true; ev.push({ type: "custom", hand: side, gesture: m.gesture }); }
          } else st.customName = null;
        }
        // kıstırma → tıklama / sürükleme
        const isPinch = p === "pinch";
        if (isPinch && !st.pinch) { st.pinch = true; st.pinchAt = t; st.pinchStart = cur; ev.push({ type: "pinch_start", hand: side, x: cur.x, y: cur.y }); }
        else if (!isPinch && st.pinch) {
          st.pinch = false; ev.push({ type: "pinch_end", hand: side, x: cur.x, y: cur.y });
          if (t - st.pinchAt < 450) ev.push({ type: "click", hand: side, x: st.pinchStart.x, y: st.pinchStart.y });
        } else if (isPinch) ev.push({ type: "pinch_move", hand: side, x: cur.x, y: cur.y, dy: st.prevC ? cc.y - st.prevC.y : 0 });
        // yumruk → tut / bırak
        if (p === "fist" && !st.grab) { st.grab = true; ev.push({ type: "grab_start", hand: side, x: cc.x, y: cc.y }); }
        else if (p !== "fist" && st.grab) { st.grab = false; ev.push({ type: "grab_end", hand: side, x: cc.x, y: cc.y }); }
        else if (st.grab && st.prevC) ev.push({ type: "grab_move", hand: side, x: cc.x, y: cc.y, dx: cc.x - st.prevC.x, dy: cc.y - st.prevC.y });
        // açık el hareketi → döndürme, hızlı → kaydırma
        if (p === "open" && st.prevC) {
          const dx = cc.x - st.prevC.x, dy = cc.y - st.prevC.y;
          if (Math.abs(dx) + Math.abs(dy) > 0.002) ev.push({ type: "rotate", hand: side, dx, dy });
          st.hist.push({ t, x: cc.x }); st.hist = st.hist.filter((q) => t - q.t < 300);
          const span = st.hist.length > 2 ? st.hist[st.hist.length - 1].x - st.hist[0].x : 0;
          if (Math.abs(span) > 0.28 && (!st.lastSwipe || t - st.lastSwipe > 900)) { st.lastSwipe = t; st.hist = []; ev.push({ type: "swipe", hand: side, dir: span > 0 ? "right" : "left" }); }
        } else st.hist = [];
        // L şekli (başparmak + işaret) → parmak aralığıyla yakınlaştır/uzaklaştır
        if (p === "L" || p === "pinch") {
          const pd = pinchRatio(lm);
          if (st.prevPinchD != null && p === "L") { const f = pd / st.prevPinchD; if (Math.abs(1 - f) > 0.01) ev.push({ type: "zoom", hand: side, f }); }
          st.prevPinchD = pd;
        } else st.prevPinchD = null;
        st.prevC = cc;
      });
      Object.keys(this.h).forEach((k) => { if (!seen[k]) { const st = this.h[k]; if (st.grab) ev.push({ type: "grab_end", hand: k }); if (st.pinch) ev.push({ type: "pinch_end", hand: k }); delete this.h[k]; } });
      // iki el: ikisi de kıstırıyorsa aradaki mesafe → ölçekle
      if (hands.length === 2) {
        const [a, b] = hands, pa = pose(a.lm), pb = pose(b.lm);
        if ((pa === "pinch" || pa === "fist") && (pb === "pinch" || pb === "fist")) {
          const dd = d2(center(a.lm), center(b.lm));
          if (this.two != null) { const f = dd / this.two; if (Math.abs(1 - f) > 0.005) ev.push({ type: "two_hand_scale", f }); }
          this.two = dd;
        } else this.two = null;
      } else this.two = null;
      return ev;
    }
  }

  const API = { fingers, pose, pinchRatio, normVec, vdist, matchCustom, center, Engine };
  if (typeof module !== "undefined" && module.exports) module.exports = API;
  else { root.JV = root.JV || {}; root.JV.GestureCore = API; }
})(typeof window !== "undefined" ? window : globalThis);
