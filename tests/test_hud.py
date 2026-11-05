"""Hava paneli (Open-Meteo, sahte cevap), AR masaüstü veri uçları.  python tests/test_hud.py"""
import os
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
os.environ["JARVIS_DATA"] = tempfile.mkdtemp(prefix="jv_hud_")
from starlette.testclient import TestClient  # noqa: E402
from core import server, tools  # noqa: E402
from core.skills import hud  # noqa: E402

ok_all = True


def check(name, cond, extra=""):
    global ok_all
    print(("  ✓ " if cond else "  ✗ ") + name + (f"  [{extra}]" if extra and not cond else ""))
    ok_all = ok_all and bool(cond)


urls = []
H = [f"2026-11-05T{h:02d}:00" for h in range(24)] + [f"2026-11-06T{h:02d}:00" for h in range(24)]


def fake_get(url, timeout=10):
    urls.append(url)
    if "geocoding" in url:
        return {"results": [{"name": "İstanbul", "country": "Türkiye", "admin1": "İstanbul", "latitude": 41.01, "longitude": 28.97}]}
    return {"current": {"time": "2026-11-05T18:15", "temperature_2m": 18.2, "apparent_temperature": 15.1, "weather_code": 2, "relative_humidity_2m": 63, "wind_speed_10m": 14, "is_day": 0},
            "hourly": {"time": H, "temperature_2m": [17 + (i % 5) for i in range(48)], "precipitation_probability": [i % 60 for i in range(48)], "weather_code": [61] * 48},
            "daily": {"time": [f"2026-11-{5 + i:02d}" for i in range(7)], "weather_code": [61, 3, 2, 0, 0, 95, 71], "temperature_2m_max": [19.4, 20, 21, 19, 20, 21, 19],
                      "temperature_2m_min": [16, 15, 14, 15, 14, 15, 14], "precipitation_probability_max": [63, 40, 10, 0, 0, 80, 30],
                      "sunrise": ["2026-11-05T07:01"] * 7, "sunset": ["2026-11-05T18:44"] * 7, "uv_index_max": [4.6] * 7}}


hud._get = fake_get
c = TestClient(server.app)
print("HUD")
w = c.get("/api/hud/weather?city=Istanbul").json()
check("Open-Meteo: şehir + anlık + gün doğumu/batımı + UV", w["şehir"] == "İstanbul" and w["derece"] == 18 and w["durum"] == "Parçalı bulutlu" and w["doğuş"] == "07:01" and w["batış"] == "18:44" and w["uv"] == 5, w)
check("24 saatlik eğri şu andan başlar", len(w["saatlik"]) == 24 and w["saatlik"][0]["saat"] == "18:00", w["saatlik"][:2])
check("7 gün: BUGÜN + Türkçe gün adları + durum", [d["gün"] for d in w["günler"]][:3] == ["BUGÜN", "CUM", "CMT"] and w["günler"][5]["ikon"] == "storm")
n = len(urls); c.get("/api/hud/weather?city=Istanbul")
check("10 dk önbellek (tekrar istek yok)", len(urls) == n)
wp = tools.TOOLS["weather_panel"][0]("Istanbul")
check("'hava durumunu göster' → panel + kısa özet", wp["ui"] == "weather" and "18°" in wp["özet"])
check("kısa hava aracı da Open-Meteo kullanır", tools.weather("Istanbul")["sıcaklık"] == "18°C")
s = c.get("/api/hud/system").json()
check("sistem halkaları verisi", all(k in s for k in ("cpu", "ram", "disk")), s)
check("işler uç noktası", isinstance(c.get("/api/hud/tasks").json(), list))
check("AR masaüstü komutu", tools.TOOLS["ar_desktop"][0]("system")["action"] == "desktop")
check("komut grupları", "hud" in tools.pick_groups("hava durumunu göster") and "hud" in tools.pick_groups("ar masaüstünü aç"))
print("\nSONUÇ:", "BAŞARILI" if ok_all else "HATA VAR")
sys.exit(0 if ok_all else 1)
