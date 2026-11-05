"""Müzik ve ritim üretimi: müzik teorisine dayalı besteci (ton/dizi, akor yürüyüşleri, akor tonlarına dayanan melodi, motif tekrarı ve
varyasyon, bas hatları, türüne göre davul kalıpları ve swing). Çıktı: standart MIDI dosyası (her DAW'da açılır) + tarayıcıda çalınan/
WAV olarak indirilen sentezlenmiş ses. Tamamen yerel, internet ve API anahtarı gerekmez."""
import json
import random
import re
import struct
import time

from ..tools import HOME, S, _schema

NOTE = {"c": 0, "c#": 1, "db": 1, "d": 2, "d#": 3, "eb": 3, "e": 4, "f": 5, "f#": 6, "gb": 6, "g": 7, "g#": 8, "ab": 8, "a": 9, "a#": 10, "bb": 10, "b": 11,
        "do": 0, "re": 2, "mi": 4, "fa": 5, "sol": 7, "la": 9, "si": 11}
SCALES = {"major": [0, 2, 4, 5, 7, 9, 11], "minor": [0, 2, 3, 5, 7, 8, 10], "dorian": [0, 2, 3, 5, 7, 9, 10], "mixolydian": [0, 2, 4, 5, 7, 9, 10],
          "harmonic_minor": [0, 2, 3, 5, 7, 8, 11]}
NAMES = ["C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B"]

# tür → (tempo aralığı, dizi, akor yürüyüşleri (derece, 0 tabanlı), çalgılar, davul, swing, melodi yoğunluğu)
STYLES = {
    "lofi": {"bpm": (70, 88), "scale": "dorian", "prog": [[1, 4, 0, 3], [0, 5, 3, 4], [3, 2, 1, 4]], "inst": {"chords": "epiano", "bass": "bass", "lead": "bell"},
             "drums": "boombap", "swing": 0.58, "density": 0.45, "sevenths": True},
    "sinematik": {"bpm": (68, 92), "scale": "minor", "prog": [[0, 5, 2, 6], [0, 3, 5, 4], [5, 3, 0, 4]], "inst": {"chords": "strings", "bass": "cello", "lead": "brass"},
                  "drums": "epic", "swing": 0.5, "density": 0.35, "sevenths": False},
    "elektronik": {"bpm": (118, 128), "scale": "minor", "prog": [[0, 5, 2, 6], [5, 3, 0, 4], [0, 3, 4, 3]], "inst": {"chords": "pad", "bass": "synthbass", "lead": "lead"},
                   "drums": "house", "swing": 0.5, "density": 0.7, "sevenths": False},
    "piyano": {"bpm": (66, 84), "scale": "major", "prog": [[0, 4, 5, 3], [0, 5, 3, 4], [3, 0, 4, 5]], "inst": {"chords": "piano", "bass": "piano", "lead": "piano"},
               "drums": None, "swing": 0.5, "density": 0.55, "sevenths": False},
    "ambient": {"bpm": (60, 72), "scale": "major", "prog": [[0, 3, 5, 3], [0, 4, 3, 0], [5, 3, 0, 4]], "inst": {"chords": "pad", "bass": "pad", "lead": "bell"},
                "drums": None, "swing": 0.5, "density": 0.2, "sevenths": True},
    "hiphop": {"bpm": (84, 96), "scale": "minor", "prog": [[0, 0, 5, 4], [0, 3, 0, 4], [0, 5, 3, 4]], "inst": {"chords": "epiano", "bass": "synthbass", "lead": "bell"},
               "drums": "trap", "swing": 0.55, "density": 0.4, "sevenths": True},
    "caz": {"bpm": (110, 140), "scale": "major", "prog": [[1, 4, 0, 0], [5, 1, 4, 0], [2, 5, 1, 4]], "inst": {"chords": "epiano", "bass": "upright", "lead": "sax"},
            "drums": "jazz", "swing": 0.66, "density": 0.6, "sevenths": True},
    "rock": {"bpm": (110, 140), "scale": "mixolydian", "prog": [[0, 6, 3, 0], [0, 3, 4, 3], [5, 3, 0, 4]], "inst": {"chords": "guitar", "bass": "bass", "lead": "lead"},
             "drums": "rock", "swing": 0.5, "density": 0.6, "sevenths": False},
}
STYLE_ALIAS = {"lo-fi": "lofi", "chill": "lofi", "epik": "sinematik", "film": "sinematik", "cinematic": "sinematik", "edm": "elektronik", "house": "elektronik",
               "techno": "elektronik", "piano": "piyano", "rahatlatıcı": "ambient", "uyku": "ambient", "meditasyon": "ambient", "rap": "hiphop", "trap": "hiphop",
               "jazz": "caz", "rock": "rock", "neşeli": "piyano", "hüzünlü": "piyano"}
MOOD = {"neşeli": "major", "mutlu": "major", "enerjik": None, "hüzünlü": "minor", "üzgün": "minor", "karanlık": "harmonic_minor", "gizemli": "harmonic_minor",
        "sakin": None, "romantik": "major", "epik": "minor"}
GM = {"piano": 0, "epiano": 4, "bell": 11, "guitar": 29, "bass": 33, "upright": 32, "synthbass": 38, "strings": 48, "cello": 42, "brass": 61, "sax": 65,
      "lead": 81, "pad": 89}
DR = {"kick": 36, "snare": 38, "rim": 37, "clap": 39, "hat": 42, "ohat": 46, "crash": 49, "ride": 51, "tom": 45}

# 16'lık ızgarada davul kalıpları (1 ölçü)
PATTERNS = {
    "boombap": {"kick": "x.........x.x...", "snare": "....x.......x...", "hat": "x.x.x.x.x.x.x.x."},
    "house": {"kick": "x...x...x...x...", "clap": "....x.......x...", "hat": "..x...x...x...x.", "ohat": "..x...x...x...x."},
    "trap": {"kick": "x......x..x.....", "snare": "........x.......", "hat": "xxxxxxxxxxxxxxxx"},
    "rock": {"kick": "x.......x.x.....", "snare": "....x.......x...", "hat": "x.x.x.x.x.x.x.x."},
    "jazz": {"ride": "x..xx..xx..xx..x", "kick": "x.......x.......", "hat": "....x.......x..."},
    "epic": {"kick": "x.......x..x....", "tom": "......x.....x.x.", "snare": "............x..."},
}


def _key(key):
    k = (key or "").strip().lower().replace("♯", "#").replace("♭", "b")
    m = re.match(r"(do|re|mi|fa|sol|la|si|[a-g][#b]?)\s*(minör|minor|m|majör|major|maj)?$", k)
    if not m:
        return None, None
    return NOTE[m.group(1)], ("minor" if m.group(2) in ("minör", "minor", "m") else "major" if m.group(2) else None)


def _chord_name(root, sc, d):
    r = sc[d % 7]
    third = (sc[(d + 2) % 7] - r) % 12
    fifth = (sc[(d + 4) % 7] - r) % 12
    q = "m" if third == 3 and fifth == 7 else "°" if third == 3 and fifth == 6 else "+" if fifth == 8 else ""
    return NAMES[(root + r) % 12] + q


def compose(style="lofi", mood="", bpm=0, bars=16, key="", seed=0, parts="all"):
    rnd = random.Random(int(seed) or random.randint(1, 10 ** 9))
    st = STYLE_ALIAS.get(style.lower(), style.lower())
    if st not in STYLES:
        st = "lofi"
    cfg = STYLES[st]
    root, kscale = _key(key)
    root = root if root is not None else rnd.choice([0, 2, 5, 7, 9])
    scale_name = kscale or MOOD.get((mood or "").lower()) or cfg["scale"]
    if (mood or "").lower() == "hüzünlü" and scale_name == "dorian":
        scale_name = "minor"
    sc = SCALES[scale_name]
    tempo = int(bpm) or rnd.randint(*cfg["bpm"])
    bars = max(4, min(int(bars or 16), 64))
    bars -= bars % 4
    prog = rnd.choice(cfg["prog"])
    deg = lambda d, octv=0: 48 + root + sc[d % 7] + 12 * (d // 7) + 12 * octv  # noqa: E731
    chords, bass, lead, drums = [], [], [], []
    swing = cfg["swing"]

    def sw(step):  # 16'lık adım → vuruş; swing: vuruş içindeki ikinci 8'lik geciktirilir (0.5 = düz, 0.66 = üçleme swing)
        b, r = divmod(int(step), 4)
        return b + {0: 0.0, 1: swing / 2, 2: swing, 3: swing + (1 - swing) / 2}[r]

    # melodi motifi (2 ölçülük) — A A' B A yapısı
    def motif():
        notes, t = [], 0.0
        while t < 8:
            dur = rnd.choice([0.5, 0.5, 1, 1, 1.5, 2] if cfg["density"] < 0.5 else [0.25, 0.5, 0.5, 0.5, 1, 1])
            if rnd.random() < cfg["density"] + 0.25:
                notes.append([t, min(dur, 8 - t), rnd.choice([0, 2, 4, 4, 7, 2, 1, 3, 5])])
            t += dur
        return notes
    A, B = motif(), motif()
    for b in range(bars):
        d = prog[b % 4]
        t0 = b * 4
        # akorlar: 3'lü (+7'li) yakın konum, ritim türe göre
        tones = [deg(d), deg(d + 2), deg(d + 4)] + ([deg(d + 6)] if cfg["sevenths"] else [])
        tones = [n + 12 if n < 55 else n for n in tones]
        if st in ("elektronik",):
            hits = [(0, 0.5), (1.5, 0.5), (2.5, 0.5), (3.5, 0.5)]
        elif st in ("rock",):
            hits = [(0, 1.5), (1.5, 1), (2.5, 1.5)]
        elif st in ("caz",):
            hits = [(0, 1), (2.66, 1)]
        else:
            hits = [(0, 4)]
        for (h, ln) in hits:
            for n in tones:
                chords.append([t0 + h, ln, n, 70])
        # bas
        r = deg(d) - 12
        if st == "caz":  # yürüyen bas
            walk = [r, deg(d + 2) - 12, deg(d + 4) - 12, deg(prog[(b + 1) % 4]) - 13]
            bass += [[t0 + i, 1, n, 85] for i, n in enumerate(walk)]
        elif st == "elektronik":
            bass += [[t0 + i * 0.5 + 0.5, 0.4, r, 95] for i in range(0, 8, 2)]
        elif st == "hiphop":
            bass += [[t0, 1.5, r, 100], [t0 + 1.75, 0.5, r, 90], [t0 + 2.5, 1.5, r + 12 if rnd.random() < 0.3 else r, 95]]
        elif st in ("ambient", "piyano", "sinematik"):
            bass += [[t0, 4, r, 75]]
        else:
            bass += [[t0, 1.5, r, 95], [t0 + 2, 1, r, 85], [t0 + 3, 0.75, deg(d + 4) - 12, 80]]
        # davullar
        if cfg["drums"]:
            pat = PATTERNS[cfg["drums"]]
            fill = (b % 8 == 7)
            for inst, line in pat.items():
                for step, ch in enumerate(line):
                    if ch == "x":
                        v = 110 if inst in ("kick", "snare", "clap") else (70 if step % 4 else 90)
                        if inst == "hat" and cfg["drums"] == "trap" and fill and step > 8:
                            drums.append([t0 + sw(step) + 0.125, inst, v - 20])  # trap hi-hat ruloları
                        drums.append([t0 + sw(step), inst, v])
            if fill:
                for step in (12, 13, 14, 15):
                    drums.append([t0 + sw(step), "snare" if cfg["drums"] != "epic" else "tom", 80 + step])
            if b % 8 == 0:
                drums.append([t0, "crash", 100])
    # melodi: bölüm yapısı (ilk 4 ölçü sessiz giriş seçenekli), akor tonlarına çekim
    sect = bars // 4
    for s in range(sect):
        if s == 0 and bars >= 16 and st not in ("piyano",):
            continue  # giriş: melodi yok
        mt = [A, A, B, A][s % 4]
        varied = s % 4 == 1
        for half in (0, 1):
            t0 = s * 16 + half * 8
            for (t, dur, step) in mt:
                if t0 + t >= bars * 4:
                    continue
                d = prog[int((t0 + t) // 4) % 4]
                stp = step + (rnd.choice([-1, 1]) if varied and rnd.random() < 0.35 else 0)
                n = deg(d + stp, 1)
                if (t % 1 == 0) and stp not in (0, 2, 4, 7):
                    n = deg(d + rnd.choice([0, 2, 4]), 1)  # güçlü vuruşta akor tonu
                while n > 96:
                    n -= 12
                while n < 55:
                    n += 12
                lead.append([t0 + (sw(int(t * 4)) if (t * 4) % 1 == 0 else t), dur * 0.95, n, 88 if t % 1 == 0 else 74])
    tracks = []
    if parts in ("all", "music"):
        tracks += [{"name": "Akorlar", "instrument": cfg["inst"]["chords"], "notes": chords}, {"name": "Bas", "instrument": cfg["inst"]["bass"], "notes": bass},
                   {"name": "Melodi", "instrument": cfg["inst"]["lead"], "notes": lead}]
    song = {"title": f"{st.capitalize()} · {NAMES[root]} {'minör' if 'minor' in scale_name else scale_name if scale_name != 'major' else 'majör'} · {tempo} BPM",
            "style": st, "bpm": tempo, "key": NAMES[root], "scale": scale_name, "bars": bars, "swing": swing, "tracks": tracks,
            "drums": drums if parts in ("all", "drums") else [], "lofi": st == "lofi", "reverb": 0.45 if st in ("ambient", "sinematik", "piyano") else 0.2,
            "progression": [_chord_name(root, sc, d) for d in prog]}
    return song


# ---------------- standart MIDI dosyası ----------------

def _vlq(n):
    out = [n & 0x7F]
    n >>= 7
    while n:
        out.insert(0, (n & 0x7F) | 0x80)
        n >>= 7
    return bytes(out)


def to_midi(song, tpq=480):
    def track(events, name):
        events.sort(key=lambda e: (e[0], e[1]))
        data, last = b"\x00\xff\x03" + _vlq(len(name.encode())) + name.encode(), 0
        for tick, _, msg in events:
            data += _vlq(tick - last) + msg
            last = tick
        data += b"\x00\xff\x2f\x00"
        return b"MTrk" + struct.pack(">I", len(data)) + data
    us = int(60_000_000 / song["bpm"])
    tempo = b"MTrk" + struct.pack(">I", 19) + b"\x00\xff\x51\x03" + us.to_bytes(3, "big") + b"\x00\xff\x58\x04\x04\x02\x18\x08" + b"\x00\xff\x2f\x00"
    chunks = [tempo]
    for ch, tr in enumerate(song["tracks"]):
        ev = [(0, 0, bytes([0xC0 | ch, GM.get(tr["instrument"], 0)]))]
        for t, d, n, v in tr["notes"]:
            a, b = int(round(t * tpq)), int(round((t + d) * tpq))
            ev.append((a, 1, bytes([0x90 | ch, n & 127, v & 127])))
            ev.append((max(a + 1, b), 0, bytes([0x80 | ch, n & 127, 0])))
        chunks.append(track(ev, tr["name"]))
    if song["drums"]:
        ev = []
        for t, inst, v in song["drums"]:
            a = int(round(t * tpq))
            ev.append((a, 1, bytes([0x99, DR[inst], min(127, v)])))
            ev.append((a + tpq // 8, 0, bytes([0x89, DR[inst], 0])))
        chunks.append(track(ev, "Davul"))
    return b"MThd" + struct.pack(">IHHH", 6, 1, len(chunks), tpq) + b"".join(chunks)


def music_compose(style="lofi", mood="", bpm=0, bars=16, key="", seed=0, parts="all"):
    """Müzik besteler: MIDI kaydeder ve ekranda çalar (WAV indirilebilir)."""
    song = compose(style, mood, bpm, bars, key, seed, parts)
    out = HOME / "Music" / "JARVIS Müzik"
    out.mkdir(parents=True, exist_ok=True)
    f = out / f"{time.strftime('%Y%m%d_%H%M%S')}_{song['style']}_{song['key']}_{song['bpm']}bpm.mid"
    f.write_bytes(to_midi(song))
    song["midi"] = str(f)
    return {"ui": "music", "song": song, "midi": str(f), "başlık": song["title"], "akorlar": " – ".join(song["progression"]),
            "süre_sn": round(song["bars"] * 4 * 60 / song["bpm"], 1), "not": "MIDI dosyasını FL Studio, Ableton, GarageBand, MuseScore gibi programlarda açabilirsin."}


def drum_beat(style="hiphop", bpm=0, bars=8):
    """Sadece ritim (davul) üretir: hiphop/trap, house, rock, caz, lofi (boom-bap), sinematik."""
    return music_compose(style, "", bpm, bars, "", 0, "drums")


TOOLS = {
    "music_compose": (music_compose, _schema("Müzik besteler ve çalar (lofi, sinematik, elektronik, piyano, ambient, hiphop, caz, rock); MIDI dosyası + WAV indirme.",
                                             {"style": S("tür"), "mood": S("neşeli/hüzünlü/karanlık/sakin/epik"), "bpm": {"type": "integer"}, "bars": {"type": "integer", "description": "ölçü (4-64)"},
                                              "key": S("ton (ör. A minör, Do, F#)"), "seed": {"type": "integer"}}), False),
    "drum_beat": (drum_beat, _schema("Davul ritmi üretir ve çalar (hiphop, trap, house, rock, caz, lofi).", {"style": S("tür"), "bpm": {"type": "integer"}, "bars": {"type": "integer"}}), False),
}
