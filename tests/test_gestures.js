// El hareketi çekirdeği testi: yapay el noktalarıyla.  node tests/test_gestures.js
const G = require("../web/gesture-core.js");
let ok = true;
const check = (n, c, x) => { console.log((c ? "  ✓ " : "  ✗ ") + n + (c ? "" : "  [" + JSON.stringify(x) + "]")); ok = ok && !!c; };

// dik duran sağ el; ext = [başparmak, işaret, orta, yüzük, serçe] açık mı
function hand(ext, opt = {}) {
  const ox = opt.x || 0, oy = opt.y || 0, s = opt.s || 1, P = (x, y) => ({ x: 0.5 + (x - 0.5) * s + ox, y: 0.8 + (y - 0.8) * s + oy, z: 0 });
  const lm = new Array(21);
  lm[0] = P(0.5, 0.8);
  // başparmak
  lm[1] = P(0.44, 0.76); lm[2] = P(0.40, 0.71);
  if (opt.thumbUp) { lm[3] = P(0.38, 0.62); lm[4] = P(0.37, 0.52); }
  else if (opt.pinch) { lm[3] = P(0.40, 0.58); lm[4] = P(0.43, 0.47); }
  else if (opt.thumbWide) { lm[3] = P(0.34, 0.68); lm[4] = P(0.24, 0.64); }
  else if (ext[0]) { lm[3] = P(0.36, 0.67); lm[4] = P(0.31, 0.63); }
  else { lm[3] = P(0.43, 0.68); lm[4] = P(0.47, 0.66); }
  const xs = [0.44, 0.49, 0.54, 0.585];
  [1, 2, 3, 4].forEach((f, k) => {
    const b = 1 + f * 4, x = xs[k];
    lm[b] = P(x, 0.6);
    if (ext[f]) { lm[b + 1] = P(x, 0.5); lm[b + 2] = P(x, 0.44); lm[b + 3] = P(x, 0.38); }
    else if (opt.pinch && f === 1) { lm[b + 1] = P(x - 0.01, 0.5); lm[b + 2] = P(x - 0.01, 0.46); lm[b + 3] = P(0.44, 0.46); }
    else { lm[b + 1] = P(x, 0.55); lm[b + 2] = P(x, 0.62); lm[b + 3] = P(x, 0.64); }
  });
  return lm;
}

console.log("POZLAR");
check("açık el", G.pose(hand([1, 1, 1, 1, 1])) === "open", G.pose(hand([1, 1, 1, 1, 1])));
check("yumruk", G.pose(hand([0, 0, 0, 0, 0])) === "fist", G.pose(hand([0, 0, 0, 0, 0])));
check("işaret", G.pose(hand([0, 1, 0, 0, 0])) === "point", G.pose(hand([0, 1, 0, 0, 0])));
check("zafer (2)", G.pose(hand([0, 1, 1, 0, 0])) === "peace", G.pose(hand([0, 1, 1, 0, 0])));
check("üç", G.pose(hand([0, 1, 1, 1, 0])) === "three");
check("dört", G.pose(hand([0, 1, 1, 1, 1])) === "four");
check("rock", G.pose(hand([0, 1, 0, 0, 1])) === "rock");
check("L (yakınlaştırma)", G.pose(hand([1, 1, 0, 0, 0])) === "L", G.pose(hand([1, 1, 0, 0, 0])));
check("başparmak yukarı", G.pose(hand([1, 0, 0, 0, 0], { thumbUp: true })) === "thumbs_up", G.pose(hand([1, 0, 0, 0, 0], { thumbUp: true })));
check("kıstırma", G.pose(hand([0, 0, 0, 0, 0], { pinch: true })) === "pinch", G.pose(hand([0, 0, 0, 0, 0], { pinch: true })));

console.log("OLAYLAR");
const E = new G.Engine({ holdMs: 500 });
let ev = [];
const run = (frames) => { ev = []; frames.forEach(([lm, t]) => (ev = ev.concat(E.update([{ lm, handed: "Right" }], t)))); return ev; };
run([[hand([1, 1, 1, 1, 1]), 0], [hand([1, 1, 1, 1, 1]), 300], [hand([1, 1, 1, 1, 1]), 600]]);
check("açık el bekletme → pose_hold", ev.some((e) => e.type === "pose_hold" && e.pose === "open"));
run([[hand([0, 0, 0, 0, 0], { pinch: true }), 1000], [hand([0, 1, 0, 0, 0]), 1200]]);
check("hızlı kıstır-bırak → click", ev.some((e) => e.type === "click"));
run([[hand([0, 0, 0, 0, 0]), 2000], [hand([0, 0, 0, 0, 0], { x: 0.05 }), 2050], [hand([1, 1, 1, 1, 1]), 2100]]);
check("yumruk → tut / taşı / bırak", ["grab_start", "grab_move", "grab_end"].every((t) => ev.some((e) => e.type === t)));
const gm = ev.find((e) => e.type === "grab_move");
check("aynalı yön (kamerada sağa = ekranda sola)", gm && gm.dx < 0, gm);
run([[hand([1, 1, 1, 1, 1]), 3000], [hand([1, 1, 1, 1, 1], { x: -0.03 }), 3050]]);
check("açık el hareketi → rotate", ev.some((e) => e.type === "rotate"));
run([[hand([1, 1, 1, 1, 1], { x: 0.2 }), 5000], [hand([1, 1, 1, 1, 1], { x: 0.05 }), 5100], [hand([1, 1, 1, 1, 1], { x: -0.15 }), 5200]]);
check("hızlı el → swipe", ev.some((e) => e.type === "swipe"), ev.map((e) => e.type));
run([[hand([1, 1, 0, 0, 0]), 7000], [hand([1, 1, 0, 0, 0], { thumbWide: true }), 7050]]);
const z = ev.find((e) => e.type === "zoom");
check("parmaklar açılınca → zoom > 1", z && z.f > 1, ev.map((e) => e.type));
run([[hand([1, 1, 1, 1, 1]), 7080], [hand([1, 1, 0, 0, 0], { s: 1.0 }), 7100], [hand([1, 1, 0, 0, 0], { s: 1.4 }), 7150]]);
check("el kameraya yaklaşınca yanlış zoom yok", !ev.some((e) => e.type === "zoom" && Math.abs(1 - e.f) > 0.05));

console.log("İKİ EL");
const E2 = new G.Engine();
let e2 = E2.update([{ lm: hand([0, 0, 0, 0, 0], { x: -0.15 }), handed: "Left" }, { lm: hand([0, 0, 0, 0, 0], { x: 0.15 }), handed: "Right" }], 0);
e2 = E2.update([{ lm: hand([0, 0, 0, 0, 0], { x: -0.25 }), handed: "Left" }, { lm: hand([0, 0, 0, 0, 0], { x: 0.25 }), handed: "Right" }], 50);
const sc = e2.find((e) => e.type === "two_hand_scale");
check("iki el açılınca büyüt", sc && sc.f > 1.3, sc);

console.log("ÖZEL HAREKET");
const vRock = G.normVec(hand([0, 1, 0, 0, 1])), vPeace = G.normVec(hand([0, 1, 1, 0, 0]));
const lib = [{ name: "rock_tanım", vec: vRock }, { name: "zafer_tanım", vec: vPeace }];
check("kendi hareketini tanır", G.matchCustom(G.normVec(hand([0, 1, 0, 0, 1], { x: 0.1, s: 1.2 })), lib).gesture.name === "rock_tanım");
check("başka hareketi karıştırmaz", G.matchCustom(G.normVec(hand([1, 1, 1, 1, 1])), lib) === null);

console.log("\nSONUÇ:", ok ? "BAŞARILI" : "HATA VAR");
process.exit(ok ? 0 : 1);
