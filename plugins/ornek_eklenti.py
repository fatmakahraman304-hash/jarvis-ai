"""ÖRNEK EKLENTİ — JARVIS'e yeni yetenek eklemenin en kolay yolu.

Bu klasöre .py dosyası koy, TOOLS sözlüğünü doldur, JARVIS'i yeniden başlat. Bu kadar.
Biçim: "araç_adı": (fonksiyon, şema, kritik_mi)
kritik_mi=True ise JARVIS çalıştırmadan önce senden onay ister.
"""
import random


def zar_at(adet=1):
    return [random.randint(1, 6) for _ in range(int(adet))]


TOOLS = {
    "zar_at": (zar_at, {
        "description": "Zar atar.",
        "parameters": {"type": "object", "properties": {"adet": {"type": "number", "description": "kaç zar"}}, "required": []},
    }, False),
}
