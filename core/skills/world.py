"""Fizik hesapları: serbest düşme, fren mesafesi ve eğik atış (gerçek formüller)."""
import math

from ..tools import S, _schema

PLANETS = {"dünya": 9.81, "ay": 1.62, "mars": 3.71, "venüs": 8.87, "jüpiter": 24.79, "satürn": 10.44, "sıfır": 0.0}

def _n(t):
    return str(t or "").strip().lower().replace("İ", "i").replace("I", "ı")


def free_fall(height, planet="Dünya", drag=False, mass=1.0, area=0.03, cd=0.47):
    """Serbest düşme: süre, çarpma hızı. drag=True ise hava direnciyle (Dünya, deniz seviyesi, ρ=1.225) sayısal çözüm ve limit hız."""
    g = PLANETS.get(_n(planet), None)
    if g is None:
        try:
            g = float(planet)
        except ValueError:
            return "Bilinmeyen gezegen."
    h = float(height)
    if g <= 0:
        return {"yükseklik_m": h, "g": g, "sonuç": "Yerçekimi yok: cisim düşmez."}
    res = {"yükseklik_m": h, "g_ms2": g, "süre_s": round(math.sqrt(2 * h / g), 3), "çarpma_hızı_ms": round(math.sqrt(2 * g * h), 2),
           "çarpma_hızı_kmh": round(math.sqrt(2 * g * h) * 3.6, 1), "formül": "t = √(2h/g), v = √(2gh)"}
    if str(drag).lower() in ("true", "1"):
        rho, k = 1.225, 0.5 * 1.225 * cd * area / mass
        y, vel, t, dt = h, 0.0, 0.0, 1e-3
        while y > 0 and t < 3600:
            acc = g - k * vel * vel
            vel += acc * dt
            y -= vel * dt
            t += dt
        res.update({"hava_dirençli_süre_s": round(t, 3), "hava_dirençli_hız_ms": round(vel, 2), "limit_hız_ms": round(math.sqrt(g / k), 2),
                    "not": f"Cd={cd}, A={area} m², m={mass} kg, ρ={rho} kg/m³"})
    return res


def braking_distance(speed_kmh, friction=0.7, reaction_s=1.0, g=9.81):
    """Durma mesafesi: tepki mesafesi + fren mesafesi v²/(2μg). Kuru asfalt μ≈0.7, ıslak ≈0.4, kar ≈0.2, buz ≈0.1."""
    v = float(speed_kmh) / 3.6
    mu = float(friction)
    react = v * float(reaction_s)
    brake = v * v / (2 * mu * float(g))
    return {"hız_kmh": float(speed_kmh), "tepki_m": round(react, 1), "fren_m": round(brake, 1), "toplam_m": round(react + brake, 1), "formül": "d = v·t + v²/(2μg)"}


def projectile(speed, angle, height=0.0, g=9.81):
    v, a, h, g = float(speed), math.radians(float(angle)), float(height), float(g)
    vx, vy = v * math.cos(a), v * math.sin(a)
    t = (vy + math.sqrt(vy * vy + 2 * g * h)) / g
    return {"uçuş_süresi_s": round(t, 3), "menzil_m": round(vx * t, 2), "tepe_yükseklik_m": round(h + vy * vy / (2 * g), 2), "formül": "x = v·cosθ·t, y = h + v·sinθ·t − ½gt²"}


def physics_calc(kind, a="", b="", c="", d=""):
    """Fizik hesaplayıcı: free_fall (a=yükseklik m, b=gezegen, c=drag true/false), braking (a=hız km/s, b=sürtünme μ, c=tepki s),
    projectile (a=hız m/s, b=açı °, c=başlangıç yüksekliği m, d=g)."""
    k = _n(kind)
    if k in ("free_fall", "serbest_düşme", "düşme"):
        return free_fall(a or 10, b or "Dünya", c or False)
    if k in ("braking", "fren", "durma"):
        return braking_distance(a or 50, b or 0.7, c or 1.0)
    if k in ("projectile", "atış", "eğik_atış"):
        return projectile(a or 20, b or 45, c or 0, d or 9.81)
    return "Tür: free_fall, braking, projectile"


TOOLS = {
    "physics_calc": (physics_calc, _schema("Gerçek formüllerle fizik hesabı: serbest düşme (hava dirençli dahil, gezegen seçilebilir), fren/durma mesafesi, eğik atış.",
                                           {"kind": S("free_fall/braking/projectile"), "a": S("1. değer"), "b": S("2. değer"), "c": S("3. değer"), "d": S("4. değer")}, ["kind"]), False),
}
