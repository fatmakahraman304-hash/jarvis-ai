/* ORTAM SESİ TANIMA: YAMNet (521 ses sınıfı, MediaPipe Audio Classifier) tarayıcıda, mikrofondan sürekli dinler.
   Duman/yangın alarmı, cam kırılması, bebek ağlaması, kapı zili, kapı çalınması, köpek havlaması, siren, çığlık, su akması… algılanınca
   ekranda ve sesli uyarır; önemli olanları sunucuya bildirir (Telegram'a da gider). Ses bilgisayardan dışarı çıkmaz. */
(function () {
  const JV = (window.JV = window.JV || {});
  const VER = "0.10.14", BASE = `https://cdn.jsdelivr.net/npm/@mediapipe/tasks-audio@${VER}`;
  const MODEL = "https://storage.googleapis.com/mediapipe-models/audio_classifier/yamnet/float32/1/yamnet.tflite";
  // YAMNet sınıf adı → [Türkçe, önem: 2 = güvenlik, 1 = bilgi, 0 = sadece gösterge]
  const MAP = {
    "Smoke detector, smoke alarm": ["Duman alarmı", 2], "Fire alarm": ["Yangın alarmı", 2], "Glass": ["Cam sesi", 1], "Shatter": ["Cam kırılması", 2],
    "Breaking": ["Kırılma sesi", 2], "Screaming": ["Çığlık", 2], "Siren": ["Siren", 1], "Civil defense siren": ["Sivil savunma sireni", 2], "Emergency vehicle": ["Acil durum aracı", 1],
    "Alarm": ["Alarm", 1], "Car alarm": ["Araba alarmı", 1], "Baby cry, infant cry": ["Bebek ağlıyor", 2], "Crying, sobbing": ["Ağlama", 1],
    "Doorbell": ["Kapı zili", 1], "Ding-dong": ["Kapı zili", 1], "Knock": ["Kapı çalınıyor", 1], "Dog": ["Köpek", 1], "Bark": ["Köpek havlıyor", 1], "Cat": ["Kedi", 0], "Meow": ["Kedi miyavlıyor", 0],
    "Water tap, faucet": ["Musluk akıyor", 1], "Running water": ["Su akıyor", 0], "Telephone bell ringing": ["Telefon çalıyor", 1], "Ringtone": ["Telefon çalıyor", 1],
    "Gunshot, gunfire": ["Silah sesi", 2], "Explosion": ["Patlama", 2], "Cough": ["Öksürük", 0], "Sneeze": ["Hapşırık", 0], "Speech": ["Konuşma", 0], "Music": ["Müzik", 0],
    "Silence": ["Sessizlik", 0], "Vehicle horn, car horn, honking": ["Korna", 0], "Microwave oven": ["Mikrodalga", 0], "Beep, bleep": ["Bip sesi", 0],
    "Whistling": ["Islık", 0], "Laughter": ["Gülme", 0], "Applause": ["Alkış", 0], "Clapping": ["El çırpma", 0], "Snoring": ["Horlama", 0], "Footsteps": ["Ayak sesi", 0],
    "Thunder": ["Gök gürültüsü", 0], "Rain": ["Yağmur", 0], "Wind": ["Rüzgâr", 0], "Typing": ["Klavye", 0], "Vacuum cleaner": ["Süpürge", 0], "Blender": ["Blender", 0],
  };
  let clf = null, ctx = null, stream = null, proc = null, src = null, running = false, chip = null;
  const last = {}; // sınıf → son uyarı zamanı
  const hist = [];

  async function load() {
    if (clf) return clf;
    const audio = await import(`${BASE}/audio_bundle.mjs`);
    const files = await audio.FilesetResolver.forAudioTasks(`${BASE}/wasm`);
    clf = await audio.AudioClassifier.createFromOptions(files, { baseOptions: { modelAssetPath: MODEL }, maxResults: 5, scoreThreshold: 0.15 });
    return clf;
  }
  function showChip(t, imp) {
    if (!chip) { chip = document.createElement("div"); chip.id = "ambient-chip"; document.body.append(chip); chip.onclick = () => JV.ambient.stop(); chip.title = "Tıkla: dinlemeyi durdur"; }
    chip.className = imp === 2 ? "alert" : imp === 1 ? "warn" : ""; chip.textContent = "👂 " + t;
  }
  function handle(cats) {
    if (!cats || !cats.length) return;
    const top = cats[0], m = MAP[top.categoryName];
    showChip(`${m ? m[0] : top.categoryName} %${Math.round(top.score * 100)}`, m ? m[1] : 0);
    for (const c of cats) {
      const mm = MAP[c.categoryName]; if (!mm || mm[1] === 0) continue;
      const need = mm[1] === 2 ? 0.35 : 0.5; if (c.score < need) continue;
      const now = Date.now(); if (now - (last[mm[0]] || 0) < 60000) continue; last[mm[0]] = now;
      hist.unshift({ t: now, ad: mm[0], skor: c.score }); hist.length = Math.min(hist.length, 50);
      // sunucu bildirim olarak kaydeder → ekranda + sesli + Telegram (bağlantı yoksa yerel uyarı)
      JV.api("/api/ambient", { body: { label: mm[0], score: c.score, level: mm[1] } }).catch(() => {
        JV.toast && JV.toast(`Ortam sesi: ${mm[0]} (%${Math.round(c.score * 100)})`, 10000);
        if (mm[1] === 2) JV.say && JV.say(`Dikkat: ${mm[0]} algıladım.`, JV.persona ? JV.persona() : "jarvis", undefined, true);
      });
    }
  }
  async function start() {
    if (running) return true;
    try { await load(); } catch (e) { JV.toast && JV.toast("Ses tanıma modeli yüklenemedi (ilk açılışta internet gerekir)."); return false; }
    try { stream = await navigator.mediaDevices.getUserMedia({ audio: { echoCancellation: false, noiseSuppression: false, autoGainControl: true } }); }
    catch (e) { JV.toast && JV.toast("Mikrofon izni yok."); return false; }
    ctx = new (window.AudioContext || window.webkitAudioContext)({ sampleRate: 16000 });
    src = ctx.createMediaStreamSource(stream);
    proc = ctx.createScriptProcessor(16384, 1, 1); // ~1 sn'lik pencereler
    proc.onaudioprocess = (e) => {
      const data = e.inputBuffer.getChannelData(0);
      try { const res = clf.classify(new Float32Array(data), ctx.sampleRate); handle(res && res[0] && res[0].classifications[0] && res[0].classifications[0].categories); } catch (err) {}
    };
    const mute = ctx.createGain(); mute.gain.value = 0; src.connect(proc); proc.connect(mute).connect(ctx.destination);
    running = true; showChip("dinliyorum…", 0); document.body.classList.add("ambient-on");
    const b = document.getElementById("t-ambient"); if (b) b.classList.add("on");
    return true;
  }
  function stop() {
    running = false; try { proc && proc.disconnect(); src && src.disconnect(); } catch (e) {}
    if (stream) stream.getTracks().forEach((t) => t.stop()); if (ctx) ctx.close().catch(() => {}); stream = ctx = proc = src = null;
    if (chip) { chip.remove(); chip = null; } document.body.classList.remove("ambient-on");
    const b = document.getElementById("t-ambient"); if (b) b.classList.remove("on");
  }
  JV.ambient = { start, stop, isOn: () => running, history: () => hist, _handle: handle, MAP };
  document.addEventListener("DOMContentLoaded", () => { const b = document.getElementById("t-ambient"); if (b) b.onclick = () => (running ? stop() : start()); });
})();
