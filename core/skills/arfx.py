"""Kamera üstü AR efektleri (el ile ateş, mühür halkası, avuçta gezegen, şimşek, patlama), yüz kilidi HUD'u,
iki alkışla uyanma / uyku modu ve kahve falı. Görüntü işleme tamamen tarayıcıda (MediaPipe) yapılır; kare bir yere gitmez
(kahve falı hariç: o tek kare Gemini'ye gönderilir)."""
from ..tools import S, _schema

PLANETS = {"dünya": "earth", "dunya": "earth", "earth": "earth", "mars": "mars", "jüpiter": "jupiter", "jupiter": "jupiter",
           "satürn": "saturn", "saturn": "saturn", "ay": "moon", "moon": "moon", "güneş": "sun", "gunes": "sun", "sun": "sun"}


def ar_effects(action="open", planet=""):
    """action: open | close | planet (avuçtaki gezegeni değiştir) | face (yüz kilidi aç/kapa)"""
    a = (action or "open").lower()
    a = {"aç": "open", "ac": "open", "kapat": "close", "kapa": "close", "gezegen": "planet", "yüz": "face"}.get(a, a)
    p = PLANETS.get((planet or "").lower().strip(), "")
    if p and a == "open":
        a = "planet"
    return {"ui": "handfx", "action": a, "planet": p,
            "not": "El efektleri: açık el = ateş, iki açık el = mühür halkası, çimdik = gezegen (taşı, fırlat), iki elle çimdik = büyüt, "
                   "yumruk→aç = patlama, iki işaret parmağı = şimşek, tek işaret parmağı = ışık izi. 👍 1 sn = komut, ✌ = mikrofon, ✊ 2 sn = sus."}


def coffee_fortune():
    """Kameradaki (ya da gösterilen) kahve fincanına bakıp eğlencesine fal okur."""
    return {"ui": "fortune", "not": "Fincanı kameraya göster; tek kare alınıp telvede görünen şekillerden esprili bir fal okunacak."}


def sleep_mode(on=True):
    """Uyku modu: ekran kararır; iki kez alkışlayınca (ya da tıklayınca) uyanır."""
    return {"ui": "sleep", "on": bool(on) if not isinstance(on, str) else on.lower() not in ("false", "0", "hayır", "kapat")}


GROUP = "arfx"
TOOLS = {
    "ar_effects": (ar_effects, _schema("Kamerada el AR efektlerini açar/kapatır ya da avuçtaki gezegeni değiştirir (Dünya, Mars, Jüpiter, Satürn, Ay, Güneş).",
                                       {"action": S("open | close | planet | face"), "planet": S("gezegen adı")}), False),
    "coffee_fortune": (coffee_fortune, _schema("Kahve falı: kameradaki fincana bakıp eğlencesine fal okur."), False),
    "sleep_mode": (sleep_mode, _schema("Uyku modu (ekran kararır, iki alkışla uyanır).", {"on": {"type": "boolean"}}), False),
}
