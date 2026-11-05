/* ORTA SAHNE: YouTube videosu, animasyon vb. çekirdeğin YERİNE ortaya gelir; kapatınca çekirdek geri döner.
   JV.stage.mount(node, {kind, title, link, onClose})  ·  JV.stage.anim({preset|code, title})  ·  JV.stage.clear()
   Animasyonlar korumalı iframe'de çalışır (sandbox: sadece script; ağ erişimi CSP ile kapalı) — arayüze/anahtarlara dokunamaz. */
(function () {
  const JV = (window.JV = window.JV || {});
  const esc = (s) => String(s == null ? "" : s).replace(/[&<>"]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]));
  let host, body, cur = null;
  function build() {
    if (host) return;
    host = document.createElement("div"); host.id = "stage-host"; host.className = "hidden";
    host.innerHTML = `<div class="sg-bar"><b id="sg-kind"></b><span id="sg-title"></span><a id="sg-link" class="mini hidden" target="_blank" rel="noopener">↗ AÇ</a><button class="mini" id="sg-full" title="Tam ekran">⛶</button><button class="mini" id="sg-x" title="Kapat (Esc)">✕ ÇEKİRDEĞE DÖN</button></div><div id="sg-body"></div>`;
    document.body.append(host); body = host.querySelector("#sg-body");
    host.querySelector("#sg-x").onclick = () => clear();
    host.querySelector("#sg-full").onclick = () => { host.classList.toggle("full"); };
    addEventListener("keydown", (e) => { if (e.key === "Escape" && cur) { if (host.classList.contains("full")) host.classList.remove("full"); else clear(); } });
  }
  function label(kind, title) {
    const v = document.getElementById("cc-view"), s = document.getElementById("cc-sub");
    if (v) v.textContent = kind; if (s) s.textContent = "// " + (title || "").toUpperCase().slice(0, 60);
  }
  function mount(node, o = {}) {
    build();
    if (cur && cur.node !== node) release(cur.node, true);
    cur = { node, onClose: o.onClose, kind: o.kind || "SAHNE" };
    body.innerHTML = ""; body.append(node);
    host.querySelector("#sg-kind").textContent = cur.kind;
    host.querySelector("#sg-title").textContent = o.title || "";
    const a = host.querySelector("#sg-link"); if (o.link) { a.href = o.link; a.classList.remove("hidden"); } else a.classList.add("hidden");
    host.classList.remove("hidden"); document.body.classList.add("stage-busy");
    label(cur.kind, o.title);
  }
  function release(node, silent) {
    if (!cur || (node && cur.node !== node)) return;
    const c = cur; cur = null;
    if (c.onClose && !silent) try { c.onClose(); } catch (e) {}
    if (!host) return;
    body.innerHTML = ""; host.classList.add("hidden"); host.classList.remove("full"); document.body.classList.remove("stage-busy");
  }
  function clear() { if (cur) release(null); }

  // ---------------- animasyonlar ----------------
  const CSP = () => `<meta http-equiv="Content-Security-Policy" content="default-src 'none'; script-src 'unsafe-inline' ${location.origin}/static/vendor/; style-src 'unsafe-inline'; img-src data: blob:; font-src data:; media-src data: blob:">`;
  // ortak çerçeve: tam ekran tuval, g = 2D bağlam, draw(t, w, h) her karede
  const FRAME = (js, col) => `<!doctype html><html><head>${CSP()}<meta charset="utf-8"><style>html,body{margin:0;height:100%;background:transparent;overflow:hidden}canvas{display:block;width:100%;height:100%}</style></head><body><canvas id="c"></canvas><script>
const c=document.getElementById("c"),g=c.getContext("2d"),COL="${col}",TAU=Math.PI*2;let W=0,H=0;
function rs(){const d=Math.min(devicePixelRatio||1,2);W=innerWidth;H=innerHeight;c.width=W*d;c.height=H*d;g.setTransform(d,0,0,d,0,0)}addEventListener("resize",rs);rs();
const rgba=(a)=>{const n=parseInt(COL.slice(1),16);return "rgba("+(n>>16&255)+","+(n>>8&255)+","+(n&255)+","+a+")"};
${js}
let t0=performance.now();(function f(n){const t=(n-t0)/1000;g.clearRect(0,0,W,H);try{draw(t,W,H)}catch(e){}requestAnimationFrame(f)})(t0);
<\/script></body></html>`;
  const PRESETS = {
    solar: { name: "Güneş Sistemi", js: `
const P=[["Merkür",.16,4.1,2.4,"#b9b1a6"],["Venüs",.23,1.6,4,"#e8c27a"],["Dünya",.31,1,4.2,"#5aa8ff"],["Mars",.39,.53,3.2,"#e0663f"],["Jüpiter",.52,.084,9,"#d9b38c"],["Satürn",.65,.034,7.5,"#e6d29a"],["Uranüs",.77,.012,5.5,"#8fe3e8"],["Neptün",.88,.006,5.3,"#4f7dff"]];
const S=[...Array(220)].map(()=>[Math.random(),Math.random(),Math.random()]);
function draw(t,w,h){const cx=w/2,cy=h/2,R=Math.min(w,h*1.7)*.48;S.forEach(s=>{g.fillStyle="rgba(255,255,255,"+(.15+.4*Math.abs(Math.sin(t+s[2]*9)))+")";g.fillRect(s[0]*w,s[1]*h,1.2,1.2)});
const sg=g.createRadialGradient(cx,cy,0,cx,cy,R*.09);sg.addColorStop(0,"#fff6d0");sg.addColorStop(.4,"#ffc23a");sg.addColorStop(1,"rgba(255,140,0,0)");g.fillStyle=sg;g.beginPath();g.arc(cx,cy,R*.09,0,TAU);g.fill();
g.font="11px monospace";g.textAlign="center";P.forEach(([n,r,sp,sz,col],i)=>{g.strokeStyle=rgba(.18);g.beginPath();g.ellipse(cx,cy,R*r,R*r*.42,0,0,TAU);g.stroke();const a=t*sp*.9+i*1.7,x=cx+Math.cos(a)*R*r,y=cy+Math.sin(a)*R*r*.42;
if(n==="Satürn"){g.strokeStyle="rgba(230,210,154,.7)";g.beginPath();g.ellipse(x,y,sz*2.1,sz*.7,-.3,0,TAU);g.stroke()}g.fillStyle=col;g.beginPath();g.arc(x,y,sz,0,TAU);g.fill();g.fillStyle=rgba(.75);g.fillText(n,x,y-sz-6)})}` },
    atom: { name: "Atom", js: `
function draw(t,w,h){const cx=w/2,cy=h/2,R=Math.min(w,h)*.38;g.globalCompositeOperation="lighter";
for(let i=0;i<14;i++){const a=i*2.4,r=R*.07*Math.sqrt(i/14);g.fillStyle=i%2?"rgba(255,90,90,.9)":"rgba(120,170,255,.9)";g.beginPath();g.arc(cx+Math.cos(a+t)*r,cy+Math.sin(a+t)*r,R*.035,0,TAU);g.fill()}
for(let k=0;k<3;k++){const rot=k*Math.PI/3+t*.1;g.save();g.translate(cx,cy);g.rotate(rot);g.strokeStyle=rgba(.45);g.lineWidth=1.3;g.beginPath();g.ellipse(0,0,R,R*.32,0,0,TAU);g.stroke();
for(let j=0;j<18;j++){const a=t*(2+k*.4)-j*.05;g.fillStyle=rgba((1-j/18)*.9);g.beginPath();g.arc(Math.cos(a)*R,Math.sin(a)*R*.32,Math.max(1,5-j*.25),0,TAU);g.fill()}g.restore()}g.globalCompositeOperation="source-over"}` },
    dna: { name: "DNA Sarmalı", js: `
function draw(t,w,h){const cx=w/2,L=h*.85,top=(h-L)/2,A=Math.min(w*.18,140),N=46;for(let i=0;i<N;i++){const u=i/(N-1),y=top+u*L,a=u*TAU*2.2+t*1.4,x1=cx+Math.cos(a)*A,x2=cx-Math.cos(a)*A,z=Math.sin(a);
g.strokeStyle="rgba(255,255,255,"+(.12+.18*(1+z)/2)+")";g.lineWidth=2;g.beginPath();g.moveTo(x1,y);g.lineTo(x2,y);g.stroke();
g.fillStyle=z>0?rgba(.95):"rgba(255,120,200,.85)";g.beginPath();g.arc(x1,y,3+2*(1+z),0,TAU);g.fill();g.fillStyle=z>0?"rgba(255,120,200,.85)":rgba(.95);g.beginPath();g.arc(x2,y,3+2*(1-z),0,TAU);g.fill()}}` },
    heart: { name: "Kalp Atışı", js: `
const ecg=[];function beat(t){const p=t%1;return p<.12?Math.sin(p/.12*Math.PI):0}
function draw(t,w,h){const cx=w/2,cy=h*.42,s=Math.min(w,h)*.012*(1+beat(t*1.2)*.18);g.save();g.translate(cx,cy);g.scale(s,s);g.beginPath();for(let i=0;i<=100;i++){const a=i/100*TAU,x=16*Math.pow(Math.sin(a),3),y=-(13*Math.cos(a)-5*Math.cos(2*a)-2*Math.cos(3*a)-Math.cos(4*a));i?g.lineTo(x,y):g.moveTo(x,y)}
g.fillStyle="rgba(255,60,90,"+(.35+beat(t*1.2)*.5)+")";g.fill();g.lineWidth=.4;g.strokeStyle="#ff8aa0";g.stroke();g.restore();
const p=(t*1.2)%1,v=p<.05?-.2:p<.09?1:p<.13?-.45:p<.2?0:p<.32?.18*Math.sin((p-.2)/.12*Math.PI):0;ecg.push(v);if(ecg.length>w/3)ecg.shift();g.strokeStyle=rgba(.9);g.lineWidth=2;g.beginPath();ecg.forEach((v,i)=>{const x=i*3,y=h*.82-v*h*.12;i?g.lineTo(x,y):g.moveTo(x,y)});g.stroke();
g.fillStyle=rgba(.8);g.font="600 18px monospace";g.fillText(Math.round(72)+" BPM",20,h*.82-h*.16)}` },
    galaxy: { name: "Sarmal Galaksi", js: `
const S=[...Array(2600)].map((_,i)=>{const arm=i%3,r=Math.pow(Math.random(),.6),a=arm*TAU/3+r*5.2+(Math.random()-.5)*.6;return[r,a,Math.random()]});
function draw(t,w,h){const cx=w/2,cy=h/2,R=Math.min(w,h)*.46;g.globalCompositeOperation="lighter";S.forEach(([r,a,b])=>{const an=a+t*(.25/(r+.3)),x=cx+Math.cos(an)*r*R,y=cy+Math.sin(an)*r*R*.55;g.fillStyle=r<.15?"rgba(255,230,190,"+(.5+b*.5)+")":rgba(.25+b*.6);g.fillRect(x,y,1.4,1.4)});
const cg=g.createRadialGradient(cx,cy,0,cx,cy,R*.18);cg.addColorStop(0,"rgba(255,240,210,.8)");cg.addColorStop(1,"rgba(255,200,120,0)");g.fillStyle=cg;g.beginPath();g.arc(cx,cy,R*.18,0,TAU);g.fill();g.globalCompositeOperation="source-over"}` },
    fireworks: { name: "Havai Fişek", js: `
let parts=[],next=0;function boom(w,h){const x=w*(.2+Math.random()*.6),y=h*(.2+Math.random()*.35),hue=Math.random()*360;for(let i=0;i<90;i++){const a=Math.random()*TAU,v=1+Math.random()*3.2;parts.push({x,y,vx:Math.cos(a)*v,vy:Math.sin(a)*v,l:1,hue})}}
function draw(t,w,h){if(t>next){boom(w,h);next=t+.5+Math.random()*.7}g.globalCompositeOperation="lighter";parts.forEach(p=>{p.x+=p.vx;p.y+=p.vy;p.vy+=.035;p.vx*=.985;p.l-=.011;g.fillStyle="hsla("+p.hue+",100%,65%,"+Math.max(0,p.l)+")";g.fillRect(p.x,p.y,2.2,2.2)});parts=parts.filter(p=>p.l>0);g.globalCompositeOperation="source-over"}` },
    matrix: { name: "Dijital Yağmur", js: `
let cols=[];const CH="アイウエオカキクケコ0123456789ABCDEF<>/{}";function draw(t,w,h){const fs=16,n=Math.ceil(w/fs);while(cols.length<n)cols.push(Math.random()*-50);g.font=fs+"px monospace";
cols.forEach((y,i)=>{for(let k=0;k<14;k++){const yy=(y-k)*fs;if(yy<0||yy>h)continue;g.fillStyle=k?rgba(.9-k*.06):"#eaffff";g.fillText(CH[(i*7+Math.floor(y)-k)%CH.length],i*fs,yy)}cols[i]=y>h/fs+14&&Math.random()>.97?0:y+.35+(i%5)*.05})}` },
    waves: { name: "Okyanus Dalgaları", js: `
function draw(t,w,h){for(let k=0;k<7;k++){const y0=h*(.35+k*.09),A=10+k*6,f=.006-k*.0004;g.beginPath();g.moveTo(0,h);for(let x=0;x<=w;x+=6)g.lineTo(x,y0+Math.sin(x*f+t*(1+k*.2)+k)*A+Math.sin(x*f*2.3-t*1.3)*A*.35);g.lineTo(w,h);g.closePath();g.fillStyle=rgba(.05+k*.035);g.fill();g.strokeStyle=rgba(.25+k*.06);g.stroke()}}` },
    clock: { name: "Hologram Saat", js: `
function draw(t,w,h){const d=new Date(),cx=w/2,cy=h/2,R=Math.min(w,h)*.38;g.strokeStyle=rgba(.3);g.lineWidth=1;g.beginPath();g.arc(cx,cy,R,0,TAU);g.stroke();
for(let i=0;i<60;i++){const a=i/60*TAU,l=i%5?6:16;g.strokeStyle=rgba(i%5?.3:.9);g.beginPath();g.moveTo(cx+Math.cos(a)*(R-l),cy+Math.sin(a)*(R-l));g.lineTo(cx+Math.cos(a)*R,cy+Math.sin(a)*R);g.stroke()}
const hand=(v,len,lw,c)=>{const a=v*TAU-Math.PI/2;g.strokeStyle=c;g.lineWidth=lw;g.lineCap="round";g.beginPath();g.moveTo(cx,cy);g.lineTo(cx+Math.cos(a)*len,cy+Math.sin(a)*len);g.stroke()};
const s=d.getSeconds()+d.getMilliseconds()/1000,m=d.getMinutes()+s/60,hh=d.getHours()%12+m/60;hand(hh/12,R*.5,5,rgba(.95));hand(m/60,R*.75,3,rgba(.85));hand(s/60,R*.88,1.5,"#ff6b7a");
g.fillStyle=rgba(.9);g.font="600 "+Math.round(R*.16)+"px monospace";g.textAlign="center";g.fillText(d.toLocaleTimeString("tr-TR"),cx,cy+R*.42)}` },
  };
  JV.stagePresets = Object.keys(PRESETS);
  function accent() { return (getComputedStyle(document.documentElement).getPropertyValue("--c").trim() || "#38d6ff").replace(/^(#[0-9a-f]{6}).*$/i, "$1"); }
  function wrapCode(code) {
    code = String(code || "");
    if (/<(html|body|canvas|svg|div|script|style)\b/i.test(code)) {
      return /<head[^>]*>/i.test(code) ? code.replace(/<head[^>]*>/i, (m) => m + CSP()) : CSP() + code;
    }
    // sadece JS geldiyse: draw(t,w,h) tanımlıysa ortak çerçeveye koy, değilse düz çalıştır
    return FRAME(/function\s+draw\s*\(/.test(code) ? code : `${code}\nfunction draw(){}`, accent());
  }
  function anim(o = {}) {
    const key = String(o.preset || "").toLowerCase();
    const pre = PRESETS[key];
    if (!pre && !o.code) return false;
    const f = document.createElement("iframe");
    f.id = "sg-anim"; f.setAttribute("sandbox", "allow-scripts"); f.setAttribute("referrerpolicy", "no-referrer");
    f.srcdoc = pre ? FRAME(pre.js, accent()) : wrapCode(o.code);
    mount(f, { kind: "ANİMASYON", title: o.title || (pre && pre.name) || "Animasyon" });
    return true;
  }
  function cmd(r = {}, args = {}) {
    if (r.kind === "clear") return clear();
    if (r.kind === "anim") { const ok = anim({ preset: r.preset || args.preset, code: args.code, title: r.title || args.title }); if (!ok && JV.toast) JV.toast("Animasyon kodu gelmedi"); }
  }
  JV.stage = { mount, release, clear, anim, cmd, current: () => cur && cur.kind };
})();
