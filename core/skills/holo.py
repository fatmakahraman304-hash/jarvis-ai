"""Hologram atölyesi ve bilim laboratuvarı: arayüzdeki 3D sahneleri yöneten araçlar + molekül verisi."""
import json
import re
import urllib.parse

from ..tools import N, S, _http_get, _path, _schema

VIEWS = {"çekirdek": "core", "core": "core", "ana": "core", "dünya": "globe", "globe": "globe", "küre": "globe",
         "atölye": "lab", "lab": "lab", "hologram": "lab", "ev tasarımı": "design", "spaceplanner": "design", "bilim": "science", "science": "science", "laboratuvar": "science"}


def show_view(view):
    v = VIEWS.get(view.lower().strip(), view)
    return {"ui": "view", "view": v}


def show_panel(name, open=True):
    return {"ui": "panel", "panel": name, "open": bool(open)}


DESIGNS = ("building", "house", "car", "robot", "arm", "rover", "rocket", "bridge", "table", "drone")


def holo_design(kind, params="{}"):
    """Hazır parametrik tasarım: building (floors, width, depth), house (rooms, roof), car (type: sedan/suv/sport, color),
    robot (type: humanoid/arm/rover), rocket (stages), drone (arms), bridge (span), table."""
    k = kind.lower()
    tr = {"bina": "building", "ev": "house", "araba": "car", "araç": "car", "robot": "robot", "robot kol": "arm",
          "kol": "arm", "gezgin": "rover", "roket": "rocket", "köprü": "bridge", "masa": "table", "dron": "drone", "drone": "drone"}
    k = tr.get(k, k)
    if k not in DESIGNS:
        return f"Bilinmeyen tasarım. Seçenekler: {', '.join(DESIGNS)}. Özel model için holo_scene kullan."
    try:
        p = json.loads(params) if isinstance(params, str) else (params or {})
    except Exception:
        p = {}
    return {"ui": "holo_design", "kind": k, "params": p}


def home_design(description="", params="{}"):
    """Ev tasarımı isteğinde JARVIS içindeki eski editör yerine SpacePlanner sayfasını açar."""
    return {"ui": "spaceplanner"}


def holo_scene(title, parts):
    """Serbest 3D tasarım. parts: JSON liste; her parça
    {"name":"gövde","type":"box|sphere|cylinder|cone|torus|wedge","size":[...],"pos":[x,y,z],"rot":[derece x,y,z],"color":"#38d6ff"}"""
    try:
        pl = json.loads(parts) if isinstance(parts, str) else parts
        assert isinstance(pl, list) and pl
    except Exception:
        return "parts geçerli bir JSON liste olmalı."
    return {"ui": "holo_scene", "title": title, "count": len(pl)}


def holo_action(action, value=""):
    """explode (parçalara ayır), assemble (birleştir), rotate (döndür aç/kapat), view (front/top/side/iso), scale, export_stl, clear, wireframe"""
    return {"ui": "holo_action", "action": action, "value": value}


def holo_model(path):
    p = _path(path)
    if not p.exists():
        return f"Bulunamadı: {p}"
    if p.suffix.lower() not in (".stl", ".obj", ".glb", ".gltf"):
        return "Desteklenen: STL, OBJ, GLB, GLTF."
    return {"ui": "holo_model", "url": "/api/holo/file?path=" + urllib.parse.quote(str(p)), "ext": p.suffix.lower()[1:], "ad": p.name}


def chart3d(title, data):
    """3D çubuk grafik. data: JSON {"etiket": değer, ...} veya [["etiket", değer], ...]"""
    return {"ui": "chart3d", "title": title}


SIMS = ("solar", "galaxy", "atom", "molecule", "projectile", "pendulum", "collision", "gravity", "airflow", "circuit", "dna", "body")


def sim_show(kind, params="{}"):
    """Bilim simülasyonu: solar (güneş sistemi), galaxy (spiral/elliptical), atom (element), molecule (İngilizce ad, örn caffeine),
    projectile (açı, hız), pendulum (uzunluk), collision, gravity (n-cisim), airflow (hız, şekil: cylinder/wing),
    circuit (voltaj, dirençler, bağlantı: series/parallel), dna (dizi), body (insan vücudu)."""
    tr = {"güneş sistemi": "solar", "gezegen": "solar", "galaksi": "galaxy", "atom": "atom", "molekül": "molecule",
          "eğik atış": "projectile", "sarkaç": "pendulum", "çarpışma": "collision", "yerçekimi": "gravity",
          "hava akışı": "airflow", "devre": "circuit", "elektrik": "circuit", "dna": "dna", "vücut": "body", "insan": "body"}
    k = tr.get(kind.lower(), kind.lower())
    if k not in SIMS:
        return f"Bilinmeyen simülasyon. Seçenekler: {', '.join(SIMS)}"
    try:
        p = json.loads(params) if isinstance(params, str) else (params or {})
    except Exception:
        p = {}
    out = {"ui": "sim", "kind": k, "params": p}
    if k == "circuit":
        out["sonuç"] = circuit_solve(p.get("voltage", 12), p.get("resistors", [100, 220]), p.get("mode", "series"))
    return out


def circuit_solve(voltage=12, resistors=(100, 220), mode="series"):
    rs = [float(r) for r in (json.loads(resistors) if isinstance(resistors, str) else resistors)]
    V = float(voltage)
    if mode == "parallel":
        Rt = 1 / sum(1 / r for r in rs)
        I = V / Rt
        parts = [{"R": r, "V": round(V, 3), "I_mA": round(V / r * 1000, 2), "P_mW": round(V * V / r * 1000, 1)} for r in rs]
    else:
        Rt = sum(rs)
        I = V / Rt
        parts = [{"R": r, "V": round(I * r, 3), "I_mA": round(I * 1000, 2), "P_mW": round(I * I * r * 1000, 1)} for r in rs]
    return {"bağlantı": "paralel" if mode == "parallel" else "seri", "toplam_direnç_ohm": round(Rt, 2),
            "toplam_akım_mA": round(I * 1000, 2), "toplam_güç_mW": round(V * I * 1000, 1), "dirençler": parts}


ATOM_SYMBOL = {"H": 1, "C": 6, "N": 7, "O": 8, "F": 9, "P": 15, "S": 16, "Cl": 17, "Br": 35, "I": 53, "Na": 11, "K": 19,
               "Ca": 20, "Mg": 12, "Fe": 26, "Si": 14, "B": 5, "Li": 3, "Zn": 30, "Cu": 29}


def molecule_data(name):
    """PubChem'den 3D (yoksa 2D) yapı alır: atomlar ve bağlar."""
    q = urllib.parse.quote(name.strip())
    base = "https://pubchem.ncbi.nlm.nih.gov/rest/pug/compound/name/"
    sdf = None
    for rec in ("3d", "2d"):
        try:
            sdf = _http_get(f"{base}{q}/SDF?record_type={rec}", timeout=20)
            if "V2000" in sdf or "V3000" in sdf:
                break
        except Exception:
            sdf = None
    if not sdf:
        raise RuntimeError(f"'{name}' PubChem'de bulunamadı (İngilizce ad kullan, örn. caffeine, water, glucose).")
    return parse_sdf(sdf, name)


def parse_sdf(sdf, name=""):
    lines = sdf.splitlines()
    counts = lines[3]
    na, nb = int(counts[0:3]), int(counts[3:6])
    atoms = []
    for ln in lines[4:4 + na]:
        x, y, z = float(ln[0:10]), float(ln[10:20]), float(ln[20:30])
        atoms.append({"e": ln[31:34].strip(), "p": [round(x, 3), round(y, 3), round(z, 3)]})
    bonds = []
    for ln in lines[4 + na:4 + na + nb]:
        bonds.append([int(ln[0:3]) - 1, int(ln[3:6]) - 1, int(ln[6:9])])
    formula = {}
    for a in atoms:
        formula[a["e"]] = formula.get(a["e"], 0) + 1
    f = "".join(f"{e}{n if n > 1 else ''}" for e, n in sorted(formula.items(), key=lambda x: (x[0] != "C", x[0] != "H", x[0])))
    return {"ad": name, "formül": f, "atomlar": atoms, "bağlar": bonds}


def molecule_info(name):
    d = molecule_data(name)
    return {"ui": "sim", "kind": "molecule", "params": {"name": name}, "formül": d["formül"], "atom_sayısı": len(d["atomlar"])}


TOOLS = {
    "show_view": (show_view, _schema("Ekran modunu değiştirir: core (çekirdek/avatar), globe (3D Dünya), lab (hologram atölyesi), science (bilim laboratuvarı).",
                                     {"view": S("mod")}, ["view"]), False),
    "show_panel": (show_panel, _schema("Arayüz panelini açar/kapatır: system, tasks (görev listesi), settings, camera, gesture (el kontrolü), files, keyboard (hava klavyesi).",
                                       {"name": S("panel"), "open": {"type": "boolean"}}, ["name"]), False),
    "holo_design": (holo_design, _schema("Hologram atölyesinde hazır parametrik 3D tasarım oluşturur: building, house, car, robot, arm, rover, rocket, bridge, table, drone.",
                                         {"kind": S("tür"), "params": S('JSON, örn {"floors":12} veya {"type":"sport","color":"#ff3030"}')}, ["kind"]), False),
    "home_design": (home_design, _schema("Kullanıcı ev tasarımı veya SpacePlanner istediğinde SpacePlanner.co sayfasını JARVIS arayüzünde açar.", {"description": S("kullanıcının ev tasarımı isteği")}, ["description"]), False),
    "holo_scene": (holo_scene, _schema("Hologram atölyesinde parçalardan ÖZEL 3D model kurar (her şeyi tasarlayabilirsin: makine, mobilya, uzay gemisi...). "
                                       "Her parça: name, type (box|sphere|cylinder|cone|torus|wedge), size (box:[en,boy,derinlik], sphere:[yarıçap], cylinder/cone:[yarıçap,yükseklik], torus:[yarıçap,kalınlık]), pos [x,y,z] (metre, y yukarı, zemin 0), rot [derece], color. 6-40 parça kullan.",
                                       {"title": S("model adı"), "parts": S("JSON parça listesi")}, ["title", "parts"]), False),
    "holo_action": (holo_action, _schema("Hologram modeline eylem: explode (parçalara ayır), assemble, rotate (dönmeyi aç/kapat), view (front/top/side/iso), wireframe, export_stl (3D yazıcı için kaydet), clear.",
                                         {"action": S("eylem"), "value": S("değer")}, ["action"]), False),
    "holo_model": (holo_model, _schema("Bilgisayardaki STL/OBJ/GLB 3D modelini holografik olarak açar.", {"path": S("dosya yolu")}, ["path"]), False),
    "chart3d": (chart3d, _schema("Veriyi 3D holografik çubuk grafik olarak gösterir.", {"title": S("başlık"), "data": S('JSON {"etiket": sayı}')}, ["title", "data"]), False),
    "sim_show": (sim_show, _schema("Bilim simülasyonu açar: solar, galaxy, atom ({\"element\":\"Fe\"}), molecule ({\"name\":\"caffeine\"} İngilizce), projectile ({\"angle\":45,\"speed\":20}), "
                                   "pendulum ({\"length\":2}), collision, gravity ({\"bodies\":6}), airflow ({\"speed\":1,\"shape\":\"wing\"}), "
                                   "circuit ({\"voltage\":9,\"resistors\":[100,220],\"mode\":\"series\"}), dna ({\"sequence\":\"ATGC...\"}), body (insan vücudu).",
                                   {"kind": S("tür"), "params": S("JSON parametreler")}, ["kind"]), False),
    "molecule_info": (molecule_info, _schema("Bir molekülün yapısını PubChem'den alır ve 3D gösterir (İngilizce ad).", {"name": S("ör. caffeine, aspirin, water")}, ["name"]), False),
    "circuit_solve": (circuit_solve, _schema("Seri/paralel direnç devresini hesaplar (Ohm yasası).",
                                             {"voltage": N("volt"), "resistors": S("JSON ohm listesi"), "mode": {"type": "string", "enum": ["series", "parallel"]}}, ["resistors"]), False),
}
