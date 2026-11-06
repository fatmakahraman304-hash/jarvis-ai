"""Dijital ikiz ve biyoloji: bilgisayarın canlı 3D ikizi (CPU çekirdekleri, RAM, disk, ağ, GPU, fanlar), Home Assistant'tan evin 3D ikizi
(odalar, ışıklar, sensörler; tıklayınca aç/kapat), RCSB PDB'den gerçek protein yapıları (atom koordinatları) ve hücre modeli."""
import json
import re
import shutil
import subprocess
import sys
import time
import urllib.error
import urllib.parse
import urllib.request

from ..config import DATA, env
from ..tools import S, _schema

UA = {"User-Agent": "JARVIS/3.0"}
_prev = {"t": 0, "disk": None, "net": None}
_tcache = {"t": 0, "v": {}}


# ---------------- bilgisayar ikizi ----------------

def _gpu():
    if not shutil.which("nvidia-smi"):
        return None
    try:
        r = subprocess.run(["nvidia-smi", "--query-gpu=name,utilization.gpu,memory.used,memory.total,temperature.gpu,fan.speed,power.draw",
                            "--format=csv,noheader,nounits"], capture_output=True, text=True, timeout=4)
        if r.returncode:
            return None
        v = [x.strip() for x in r.stdout.splitlines()[0].split(",")]
        num = lambda x: float(x) if re.match(r"^[\d.]+$", x) else None  # noqa: E731
        return {"ad": v[0], "kullanım": num(v[1]), "vram_kullanılan_mb": num(v[2]), "vram_toplam_mb": num(v[3]), "sıcaklık": num(v[4]),
                "fan": num(v[5]), "güç_w": num(v[6])}
    except Exception:
        return None


def _temps():
    import psutil
    out = {}
    try:
        for k, arr in (psutil.sensors_temperatures() or {}).items():
            for t in arr:
                if t.current:
                    out[f"{k}:{t.label or len(out)}"] = round(t.current, 1)
    except Exception:
        pass
    if not out and sys.platform.startswith("win"):
        if time.time() - _tcache["t"] < (30 if _tcache["v"] else 300):  # PowerShell yavaş: sonucu önbellekle
            return _tcache["v"]
        try:  # ACPI termal bölge (her bilgisayarda yok; yönetici izni gerekebilir)
            r = subprocess.run(["powershell", "-NoProfile", "-Command",
                                "Get-CimInstance -Namespace root/wmi -ClassName MSAcpi_ThermalZoneTemperature | % { [math]::Round($_.CurrentTemperature/10-273.15,1) }"],
                               capture_output=True, text=True, timeout=5)
            for i, line in enumerate(r.stdout.split()):
                out[f"ACPI:{i}"] = float(line.replace(",", "."))
        except Exception:
            pass
        _tcache.update({"t": time.time(), "v": out})
    return out


def pc_twin_data():
    import psutil
    now = time.time()
    dio, nio = psutil.disk_io_counters(), psutil.net_io_counters()
    dt = now - _prev["t"] if _prev["t"] else 0
    rates = {"disk_okuma_mbs": 0.0, "disk_yazma_mbs": 0.0, "ağ_indirme_mbs": 0.0, "ağ_yükleme_mbs": 0.0}
    if dt > 0 and _prev["disk"] and dio:
        rates["disk_okuma_mbs"] = round((dio.read_bytes - _prev["disk"].read_bytes) / dt / 1e6, 2)
        rates["disk_yazma_mbs"] = round((dio.write_bytes - _prev["disk"].write_bytes) / dt / 1e6, 2)
    if dt > 0 and _prev["net"]:
        rates["ağ_indirme_mbs"] = round((nio.bytes_recv - _prev["net"].bytes_recv) / dt / 1e6, 3)
        rates["ağ_yükleme_mbs"] = round((nio.bytes_sent - _prev["net"].bytes_sent) / dt / 1e6, 3)
    _prev.update({"t": now, "disk": dio, "net": nio})
    vm = psutil.virtual_memory()
    freq = psutil.cpu_freq()
    disks = []
    for p in psutil.disk_partitions(all=False)[:6]:
        try:
            u = psutil.disk_usage(p.mountpoint)
            disks.append({"ad": p.device or p.mountpoint, "yüzde": u.percent, "boş_gb": round(u.free / 1e9, 1), "toplam_gb": round(u.total / 1e9, 1)})
        except Exception:
            pass
    bat = None
    try:
        b = psutil.sensors_battery()
        if b:
            bat = {"yüzde": round(b.percent), "şarjda": b.power_plugged}
    except Exception:
        pass
    procs = []
    for p in psutil.process_iter(["name", "cpu_percent", "memory_info"]):
        try:
            procs.append((p.info["cpu_percent"] or 0, p.info["memory_info"].rss if p.info["memory_info"] else 0, p.info["name"]))
        except Exception:
            pass
    top = sorted(procs, key=lambda x: -x[1])[:5]
    fans = []
    try:
        for k, arr in (psutil.sensors_fans() or {}).items():
            fans += [{"ad": f"{k}:{f.label}", "rpm": f.current} for f in arr]
    except Exception:
        pass
    return {"çekirdekler": psutil.cpu_percent(percpu=True), "cpu": psutil.cpu_percent(), "frekans_mhz": round(freq.current) if freq else None,
            "ram_yüzde": vm.percent, "ram_gb": round(vm.used / 1e9, 1), "ram_toplam_gb": round(vm.total / 1e9, 1), "diskler": disks, **rates,
            "gpu": _gpu(), "sıcaklıklar": _temps(), "fanlar": fans, "pil": bat, "en_çok_ram": [{"ad": n, "mb": round(m / 1e6)} for _, m, n in top],
            "zaman": now}


# ---------------- ev ikizi (Home Assistant) ----------------

def home_twin_data():
    if not (env("HA_URL") and env("HA_TOKEN")):
        return {"bağlı": False, "not": "Evin dijital ikizi için Home Assistant gerekli: .env'ye HA_URL ve HA_TOKEN ekle. Odalar ve cihazlar oradan otomatik gelir."}
    from .smarthome import _ha
    tmpl = ("{% set ns = namespace(out=[]) %}{% for a in areas() %}{% set ns.out = ns.out + [{'ad': area_name(a), 'cihazlar': area_entities(a)}] %}{% endfor %}"
            "{{ ns.out | tojson }}")
    try:
        res = _ha("template", "POST", {"template": tmpl})
        areas = res if isinstance(res, list) else json.loads(res)
    except Exception:
        areas = []
    states = {s["entity_id"]: s for s in _ha("states")}
    keep = ("light.", "switch.", "sensor.", "binary_sensor.", "climate.", "cover.", "fan.", "lock.", "media_player.", "camera.")
    rooms, used = [], set()
    for a in areas:
        devs = []
        for e in a.get("cihazlar", []):
            st = states.get(e)
            if st and e.startswith(keep):
                used.add(e)
                at = st.get("attributes", {})
                devs.append({"id": e, "ad": at.get("friendly_name", e), "durum": st["state"], "birim": at.get("unit_of_measurement", ""),
                             "parlaklık": at.get("brightness"), "cihaz_sınıfı": at.get("device_class", "")})
        if devs:
            rooms.append({"ad": a["ad"], "cihazlar": devs[:30]})
    rest = [{"id": e, "ad": s.get("attributes", {}).get("friendly_name", e), "durum": s["state"], "birim": s.get("attributes", {}).get("unit_of_measurement", ""),
             "cihaz_sınıfı": s.get("attributes", {}).get("device_class", "")} for e, s in states.items() if e.startswith(keep) and e not in used]
    if rest:
        rooms.append({"ad": "Odasız cihazlar", "cihazlar": rest[:30]})
    return {"bağlı": True, "odalar": rooms, "zaman": time.time()}


def home_toggle(entity_id):
    from .smarthome import _ha
    dom = entity_id.split(".")[0]
    if dom not in ("light", "switch", "fan", "cover", "lock", "media_player", "climate"):
        return "Bu cihaz aç/kapat desteklemiyor."
    svc = {"cover": "toggle", "lock": "unlock"}.get(dom, "toggle")
    _ha(f"services/{dom}/{svc}", "POST", {"entity_id": entity_id})
    return {"değişti": entity_id}


# ---------------- protein (RCSB PDB) ----------------

def _get(url, data=None, timeout=25):
    req = urllib.request.Request(url, data=data, headers={**UA, **({"Content-Type": "application/json"} if data else {})})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read() if r.status != 204 else b""


KNOWN = {"hemoglobin": "4HHB", "hemoglobin (insan)": "4HHB", "insülin": "4INS", "insulin": "4INS", "miyoglobin": "1MBN", "myoglobin": "1MBN",
         "crambin": "1CRN", "gfp": "1EMA", "yeşil floresan protein": "1EMA", "lizozim": "1LYZ", "lysozyme": "1LYZ", "dna": "1BNA",
         "antikor": "1IGT", "antibody": "1IGT", "kollajen": "1BKV", "collagen": "1BKV", "spike": "6VXX", "koronavirüs spike": "6VXX",
         "atp sentaz": "5ARA", "ubikitin": "1UBQ", "ubiquitin": "1UBQ", "hiv proteaz": "1HVR", "kafein reseptörü": "3EML", "rubisco": "8RUC",
         "keratin": "6EC0", "aktin": "1ATN", "miyozin": "2MYS", "p53": "1TUP", "kas proteini": "2MYS", "insan serum albümini": "1AO6", "albümin": "1AO6"}


def protein_search(query):
    q = (query or "").strip()
    if re.fullmatch(r"\d[A-Za-z0-9]{3}", q):
        return [q.upper()]
    if q.lower() in KNOWN:
        return [KNOWN[q.lower()]]
    body = json.dumps({"query": {"type": "terminal", "service": "full_text", "parameters": {"value": q}}, "return_type": "entry",
                       "request_options": {"paginate": {"start": 0, "rows": 5}}}).encode()
    raw = _get("https://search.rcsb.org/rcsbsearch/v2/query", body)
    return [x["identifier"] for x in (json.loads(raw).get("result_set") or [])] if raw else []


def parse_pdb(text, max_atoms=60000):
    atoms, helices, sheets = [], [], []
    for ln in text.splitlines():
        rec = ln[:6].strip()
        if rec in ("ATOM", "HETATM") and len(ln) >= 54:
            try:
                el = (ln[76:78].strip() if len(ln) >= 78 else "") or re.sub(r"\d", "", ln[12:16].strip())[:1]
                atoms.append({"het": rec == "HETATM", "name": ln[12:16].strip(), "res": ln[17:20].strip(), "chain": ln[21].strip() or "A",
                              "seq": int(ln[22:26]), "x": float(ln[30:38]), "y": float(ln[38:46]), "z": float(ln[46:54]), "el": el.upper()})
            except ValueError:
                continue
        elif rec == "HELIX":
            try:
                helices.append((ln[19].strip() or "A", int(ln[21:25]), int(ln[33:37])))
            except ValueError:
                pass
        elif rec == "SHEET":
            try:
                sheets.append((ln[21].strip() or "A", int(ln[22:26]), int(ln[33:37])))
            except ValueError:
                pass
        elif rec == "ENDMDL":
            break  # NMR: yalnızca ilk model
        if len(atoms) >= max_atoms:
            break
    return atoms, helices, sheets


def parse_cif(text, max_atoms=60000):
    """mmCIF _atom_site döngüsü (yeni/büyük girişler PDB biçiminde yayımlanmaz)."""
    lines = text.splitlines()
    atoms, cols, i = [], [], 0
    while i < len(lines):
        if lines[i].startswith("_atom_site."):
            while i < len(lines) and lines[i].startswith("_atom_site."):
                cols.append(lines[i].split(".", 1)[1].strip())
                i += 1
            ix = {c: k for k, c in enumerate(cols)}
            model0 = None
            while i < len(lines) and lines[i] and not lines[i].startswith(("#", "_", "loop_")):
                f = lines[i].split()
                i += 1
                if len(f) < len(cols):
                    continue
                mdl = f[ix["pdbx_PDB_model_num"]] if "pdbx_PDB_model_num" in ix else "1"
                model0 = model0 or mdl
                if mdl != model0:
                    continue
                try:
                    atoms.append({"het": f[ix["group_PDB"]] == "HETATM", "name": f[ix["label_atom_id"]].strip('"'), "res": f[ix["label_comp_id"]],
                                  "chain": f[ix.get("auth_asym_id", ix["label_asym_id"])], "seq": int(f[ix.get("auth_seq_id", ix["label_seq_id"])]) if f[ix.get("auth_seq_id", ix["label_seq_id"])] not in (".", "?") else 0,
                                  "x": float(f[ix["Cartn_x"]]), "y": float(f[ix["Cartn_y"]]), "z": float(f[ix["Cartn_z"]]), "el": f[ix["type_symbol"]].upper()})
                except (KeyError, ValueError):
                    continue
                if len(atoms) >= max_atoms:
                    break
            break
        i += 1
    return atoms, [], []


def protein_data(query):
    ids = protein_search(query)
    if not ids:
        raise RuntimeError(f"'{query}' için protein bulunamadı (İngilizce ad ya da 4 haneli PDB kodu dene).")
    pid = ids[0].upper()
    cache = DATA / "pdb"
    cache.mkdir(exist_ok=True)
    f = cache / f"{pid}.txt"
    if f.exists():
        text = f.read_text(encoding="utf-8")
    else:
        try:
            text = _get(f"https://files.rcsb.org/download/{pid}.pdb").decode("utf-8", "ignore")
        except urllib.error.HTTPError:
            text = _get(f"https://files.rcsb.org/download/{pid}.cif").decode("utf-8", "ignore")
        f.write_text(text, encoding="utf-8")
    atoms, helices, sheets = parse_pdb(text) if "\nATOM  " in text or text.startswith(("HEADER", "ATOM")) else parse_cif(text)
    if not atoms:
        raise RuntimeError("Yapı dosyasında atom bulunamadı.")
    info = {"kod": pid, "başlık": "", "yöntem": "", "çözünürlük_Å": None, "organizma": "", "tanım": ""}
    try:
        e = json.loads(_get(f"https://data.rcsb.org/rest/v1/core/entry/{pid}", timeout=12))
        info.update({"başlık": e.get("struct", {}).get("title", ""), "yöntem": (e.get("exptl") or [{}])[0].get("method", ""),
                     "çözünürlük_Å": (e.get("rcsb_entry_info", {}).get("resolution_combined") or [None])[0],
                     "yayın": e.get("rcsb_accession_info", {}).get("initial_release_date", "")[:10]})
        pe = json.loads(_get(f"https://data.rcsb.org/rest/v1/core/polymer_entity/{pid}/1", timeout=12))
        info["organizma"] = ((pe.get("rcsb_entity_source_organism") or [{}])[0]).get("scientific_name", "")
        info["tanım"] = pe.get("rcsb_polymer_entity", {}).get("pdbx_description", "")
    except Exception:
        m = re.search(r"^TITLE\s+(.*)$", text, re.M)
        info["başlık"] = m.group(1).strip() if m else ""
    chains = sorted({a["chain"] for a in atoms})
    residues = len({(a["chain"], a["seq"]) for a in atoms if not a["het"]})
    ligands = sorted({a["res"] for a in atoms if a["het"] and a["res"] not in ("HOH", "WAT")})
    return {"info": {**info, "zincir": len(chains), "kalıntı": residues, "atom": len(atoms), "ligandlar": ligands[:12], "diğer_eşleşmeler": ids[1:5]},
            "atoms": [[a["x"], a["y"], a["z"], a["el"], a["chain"], a["seq"], a["name"], a["res"], 1 if a["het"] else 0] for a in atoms],
            "helices": helices, "sheets": sheets}


# ---------------- araçlar ----------------

def digital_twin(kind="pc"):
    k = (kind or "pc").lower()
    k = "home" if k in ("ev", "home", "house", "evim") else "pc"
    return {"ui": "twin", "kind": k, "not": "Canlı veriler her 2 saniyede güncellenir." if k == "pc" else home_twin_data().get("not", "Ev ikizi Home Assistant'tan canlı.")}


def protein_show(name, style="cartoon"):
    try:
        d = protein_data(name)
    except Exception as e:
        return f"Protein yüklenemedi: {e}"
    return {"ui": "bio", "kind": "protein", "query": d["info"]["kod"], "style": style, "bilgi": d["info"]}


def cell_show(kind="hayvan"):
    k = {"hayvan": "animal", "animal": "animal", "bitki": "plant", "plant": "plant", "bakteri": "bacteria", "bacteria": "bacteria"}.get((kind or "").lower(), "animal")
    return {"ui": "bio", "kind": "cell", "cell": k}


def vr_mode(view="", mode="vr"):
    """3D dünyalardan birini VR gözlükte ya da AR'de (telefon kamerası üstünde) açar."""
    v = {"dünya": "globe", "küre": "globe", "atölye": "lab", "bilim": "science", "uzay": "space", "ikiz": "twin", "biyoloji": "bio", "hücre": "bio",
         "protein": "bio", "grafik": "graph"}.get((view or "").lower(), view or "")
    m = "ar" if (mode or "").lower() in ("ar", "artırılmış") else "vr"
    return {"ui": "xr", "view": v, "mode": m, "not": ("VR için: Quest/Pico tarayıcısında ya da SteamVR/Windows Mixed Reality ile Chrome/Edge'de JARVIS'i "
                                                      "'python run.py --lan --https' ile başlatıp https:// adresinden aç. AR için ARCore'lu Android telefonda Chrome. "
                                                      "Ekrandaki düğmeye dokununca başlar; kumanda tetiği ile nesne seçilir.")}


TOOLS = {
    "vr_mode": (vr_mode, _schema("3D dünyayı (küre, uzay, atölye, bilim, ikiz, biyoloji) VR gözlükte ya da AR'de açar (WebXR).",
                                 {"view": S("dünya"), "mode": S("vr / ar")}), False),
    "digital_twin": (digital_twin, _schema("Dijital ikiz: bilgisayarın (pc) canlı 3D modeli (çekirdekler, RAM, disk, ağ, GPU, sıcaklık) ya da evin (ev) Home Assistant'tan 3D ikizi.",
                                           {"kind": S("pc / ev")}), False),
    "protein_show": (protein_show, _schema("Gerçek protein yapısını RCSB PDB'den indirip 3D gösterir (hemoglobin, insülin, spike, GFP… ya da 4 haneli PDB kodu).",
                                           {"name": S("protein adı (İngilizce daha iyi) ya da PDB kodu"), "style": S("cartoon / atoms")}, ["name"]), False),
    "cell_show": (cell_show, _schema("3D hücre modeli: organeller, görevleri (hayvan, bitki, bakteri).", {"kind": S("hayvan/bitki/bakteri")}), False),
}
