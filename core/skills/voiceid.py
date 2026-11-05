"""Ses kimliği: kullanıcıyı sesinden tanıma, birden fazla kişiyi ayırt etme.

Varsayılan yöntem: MFCC ses parmak izi + ses perdesi (numpy, internetsiz, hızlı).
'resemblyzer' kuruluysa (pip install resemblyzer) çok daha doğru sinir ağı yöntemi otomatik kullanılır.
Ses kayıtları saklanmaz; sadece sayısal parmak izi data/voiceprints.json'da tutulur.
"""
import io
import json
import struct
import wave

from ..config import DATA
from ..tools import _schema

PROFILES = DATA / "voiceprints.json"
SR = 16000

try:
    import numpy as np
except ImportError:  # pragma: no cover
    np = None

_encoder = None


def _neural():
    global _encoder
    if _encoder is None:
        try:
            from resemblyzer import VoiceEncoder  # type: ignore
            _encoder = VoiceEncoder("cpu")
        except Exception:
            _encoder = False
    return _encoder or None


# ---------------- ses okuma ----------------
def read_wav(data):
    with wave.open(io.BytesIO(data)) as w:
        sr, ch, sw, n = w.getframerate(), w.getnchannels(), w.getsampwidth(), w.getnframes()
        raw = w.readframes(n)
    if sw != 2:
        raise ValueError("16-bit WAV gerekli")
    x = np.frombuffer(raw, dtype=np.int16).astype(np.float32) / 32768.0
    if ch > 1:
        x = x.reshape(-1, ch).mean(axis=1)
    if sr != SR:  # basit yeniden örnekleme
        idx = np.linspace(0, len(x) - 1, int(len(x) * SR / sr))
        x = np.interp(idx, np.arange(len(x)), x).astype(np.float32)
    return x


def make_wav(x, sr=SR):
    buf = io.BytesIO()
    with wave.open(buf, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(sr)
        w.writeframes((np.clip(x, -1, 1) * 32767).astype(np.int16).tobytes())
    return buf.getvalue()


# ---------------- öznitelik çıkarma ----------------
def _mel_fb(n_fft=512, n_mels=32, fmin=60, fmax=7600):
    mel = lambda f: 2595 * np.log10(1 + f / 700)
    inv = lambda m: 700 * (10 ** (m / 2595) - 1)
    pts = inv(np.linspace(mel(fmin), mel(fmax), n_mels + 2))
    bins = np.floor((n_fft + 1) * pts / SR).astype(int)
    fb = np.zeros((n_mels, n_fft // 2 + 1))
    for i in range(1, n_mels + 1):
        a, b, c = bins[i - 1], bins[i], bins[i + 1]
        for k in range(a, b):
            fb[i - 1, k] = (k - a) / max(1, b - a)
        for k in range(b, c):
            fb[i - 1, k] = (c - k) / max(1, c - b)
    return fb


_FB = None


def _embed_classic(x):
    global _FB
    if _FB is None:
        _FB = _mel_fb()
    x = np.append(x[0], x[1:] - 0.97 * x[:-1])
    flen, hop = 400, 160
    if len(x) < flen * 10:
        raise ValueError("Ses çok kısa (en az 1 sn konuş).")
    n = 1 + (len(x) - flen) // hop
    idx = np.arange(flen)[None, :] + hop * np.arange(n)[:, None]
    frames = x[idx] * np.hamming(flen)
    energy = (frames ** 2).sum(axis=1)
    voiced = energy > max(np.percentile(energy, 40), 1e-6)  # sessiz kısımları at
    frames = frames[voiced]
    if len(frames) < 40:
        raise ValueError("Yeterince konuşma algılanmadı.")
    spec = np.abs(np.fft.rfft(frames, 512)) ** 2
    logmel = np.log(spec @ _FB.T + 1e-10)
    k = np.arange(32)
    dct = np.cos(np.pi / 32 * (k[None, :] + 0.5) * np.arange(1, 21)[:, None])
    mfcc = logmel @ dct.T  # (frames, 20)
    delta = np.diff(mfcc, axis=0)
    # ses perdesi (otokorelasyon), 70-400 Hz
    f0s = []
    for fr in frames[:: max(1, len(frames) // 60)]:
        ac = np.correlate(fr, fr, "full")[flen - 1:]
        lo, hi = SR // 400, SR // 70
        if ac[0] <= 0:
            continue
        p = lo + int(np.argmax(ac[lo:hi]))
        if ac[p] / ac[0] > 0.3:
            f0s.append(SR / p)
    f0 = np.median(f0s) if f0s else 150.0
    feat = np.concatenate([mfcc.mean(0), mfcc.std(0), delta.std(0),
                           [np.log(f0) * 8, np.std(np.log(f0s)) * 20 if f0s else 0]])
    return feat


def embed(wav_bytes):
    if np is None:
        raise RuntimeError("numpy gerekli (pip install numpy).")
    x = read_wav(wav_bytes)
    enc = _neural()
    if enc:
        from resemblyzer import preprocess_wav  # type: ignore
        return "neural", enc.embed_utterance(preprocess_wav(x, SR)).tolist()
    return "classic", _embed_classic(x).tolist()


# ---------------- profiller ----------------
def _load():
    try:
        return json.loads(PROFILES.read_text())
    except Exception:
        return {}


def _save(p):
    PROFILES.write_text(json.dumps(p))


def profiles():
    return {name: {"örnek": len(v["samples"]), "yöntem": v["method"], "sahip": v.get("owner", False)} for name, v in _load().items()}


def enroll(name, wav_bytes, owner=None):
    method, vec = embed(wav_bytes)
    p = _load()
    prof = p.setdefault(name, {"method": method, "samples": [], "owner": not p})
    if prof["method"] != method:
        prof.update(method=method, samples=[])
    prof["samples"].append(vec)
    prof["samples"] = prof["samples"][-12:]
    if owner is not None:
        for k in p:
            p[k]["owner"] = False
        prof["owner"] = bool(owner)
    _save(p)
    return {"ad": name, "örnek_sayısı": len(prof["samples"]), "yöntem": method}


def delete(name):
    p = _load()
    p.pop(name, None)
    _save(p)


def _dist(a, b, method, scale):
    a, b = np.asarray(a), np.asarray(b)
    if method == "neural":
        return 1 - float(a @ b / (np.linalg.norm(a) * np.linalg.norm(b) + 1e-9))
    return float(np.linalg.norm((a - b) / scale))


def identify(wav_bytes):
    p = _load()
    if not p:
        return {"known": False, "name": None, "reason": "kayıtlı ses yok", "no_profiles": True}
    method, vec = embed(wav_bytes)
    allv = [s for v in p.values() if v["method"] == method for s in v["samples"]]
    if not allv:
        return {"known": False, "name": None, "reason": "yöntem değişti, sesleri yeniden tanıt"}
    scale = np.std(np.asarray(allv), axis=0) + 0.5 if len(allv) > 2 else np.ones(len(vec))
    best, best_d, thr_best = None, 1e9, 0
    for name, v in p.items():
        if v["method"] != method or not v["samples"]:
            continue
        ds = sorted(_dist(vec, s, method, scale) for s in v["samples"])
        d = float(np.mean(ds[: min(3, len(ds))]))
        # eşik: kişinin kendi örnekleri arasındaki uzaklık
        S = v["samples"]
        intra = [_dist(S[i], S[j], method, scale) for i in range(len(S)) for j in range(i + 1, len(S))]
        thr = (0.25 if method == "neural" else (np.mean(intra) * 1.6 + 1.0 if intra else 6.0))
        if d < best_d:
            best, best_d, thr_best = name, d, thr
    known = best_d <= thr_best
    return {"known": bool(known), "name": best if known else None, "closest": best,
            "distance": round(best_d, 3), "threshold": round(float(thr_best), 3),
            "owner": bool(known and p[best].get("owner")), "method": method}


def voice_profiles():
    return profiles() or "Henüz ses tanıtılmadı. Ayarlar > SES > SESİMİ TANIT."


TOOLS = {
    "voice_profiles": (voice_profiles, _schema("JARVIS'in sesinden tanıdığı kişiler."), False),
}
