"""Orta sahne: animasyonlar çekirdeğin YERİNE ekranın ortasında oynar (YouTube videoları da oraya gelir).
Hazır animasyonlar tarayıcıda çizilir; hazır olmayan bir şey istenirse model kısa bir HTML/JS animasyonu yazar —
korumalı (sandbox) bir çerçevede, internet erişimi kapalı olarak çalışır. Ayrıca çekirdeğin görünümü değiştirilebilir."""
from ..tools import S, _schema

PRESETS = {
    "solar": "güneş sistemi gezegen gezegenler yörünge",
    "atom": "atom elektron çekirdek proton",
    "dna": "dna sarmal gen genetik",
    "heart": "kalp nabız atış ekg",
    "galaxy": "galaksi samanyolu yıldız evren",
    "fireworks": "havai fişek kutlama yılbaşı",
    "matrix": "matrix dijital yağmur kod",
    "waves": "dalga okyanus deniz",
    "clock": "saat zaman",
}
MAX_CODE = 60000


def _guess(text):
    t = (text or "").lower()
    for k, kws in PRESETS.items():
        if k in t or any(w in t for w in kws.split()):
            return k
    return ""


def stage_animation(title="", preset="", code=""):
    """Ortadaki sahnede animasyon oynatır (çekirdek geçici olarak kalkar)."""
    preset = (preset or "").strip().lower()
    if preset and preset not in PRESETS:
        preset = _guess(preset)
    code = code or ""
    if not preset and not code.strip():
        preset = _guess(title)
    if not preset and not code.strip():
        return {"error": "Hazır animasyon bulunamadı; 'code' ile kısa bir HTML/JS animasyonu yaz ya da hazırlardan seç: " + ", ".join(PRESETS)}
    if len(code) > MAX_CODE:
        return {"error": f"Kod çok uzun ({len(code)} karakter); {MAX_CODE} altına indir."}
    return {"ui": "stage", "kind": "anim", "preset": preset if not code.strip() else "", "title": (title or "")[:80],
            "not": "Animasyon ortadaki sahnede oynuyor; ✕ ya da Esc ile çekirdeğe dönülür."}


def stage_clear():
    """Ortadaki sahneyi (video/animasyon) kapatıp çekirdeğe döner."""
    return {"ui": "stage", "kind": "clear"}


def core_style(style="reactor"):
    """Çekirdeğin görünümü: reactor (reaktör) | wave (ses dalgası) | sphere (nokta küre) | face (hologram yüz)."""
    s = (style or "").lower().strip()
    s = {"reaktör": "reactor", "reaktor": "reactor", "dalga": "wave", "ses": "wave", "küre": "sphere", "kure": "sphere",
         "yüz": "face", "yuz": "face"}.get(s, s)
    if s not in ("reactor", "wave", "sphere", "face"):
        return {"error": "Görünümler: reactor, wave, sphere, face"}
    return {"ui": "core", "style": s}


GROUP = "stage"
TOOLS = {
    "stage_animation": (stage_animation, _schema(
        "Ekranın ORTASINDA (çekirdeğin yerine) animasyon oynatır. Önce hazırlardan uygun olanı seç: "
        + ", ".join(f"{k} ({v.split()[0]})" for k, v in PRESETS.items())
        + ". Hazırı yoksa 'code' alanına KISA, kendi başına çalışan bir animasyon yaz: ya tam HTML belgesi (<canvas> + satır içi <script>), "
          "ya da sadece JS — o zaman hazır değişkenler: g (2D bağlam), W, H, TAU, COL (vurgu rengi), rgba(alfa); "
          "function draw(t, w, h) her karede çağrılır (ekran zaten temizlenir). Arka plan şeffaf/koyu olsun. "
          "İnternet, fetch, harici dosya YOK (yalnız /static/vendor/three.min.js kullanılabilir). Videolar için youtube_play kullan.",
        {"title": S("kısa başlık"), "preset": S("hazır animasyon adı (boşsa code)"), "code": S("HTML ya da draw(t,w,h) içeren JS")}), False),
    "stage_clear": (stage_clear, _schema("Ortadaki videoyu/animasyonu kapatıp çekirdeğe döner."), False),
    "core_style": (core_style, _schema("Ortadaki çekirdeğin görünümünü değiştirir: reactor (reaktör), wave (ses dalgası), sphere (küre), face (yüz).",
                                       {"style": S("reactor | wave | sphere | face")}, ["style"]), False),
}
