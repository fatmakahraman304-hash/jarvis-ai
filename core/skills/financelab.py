"""Finans laboratuvarı: canlı portföy takibi (kâr/zarar, dağılım), strateji geri testi (al-tut, SMA kesişimi, RSI) gerçek geçmiş fiyatlarla,
risk ölçüleri (oynaklık, maksimum düşüş, Sharpe, beta), Monte Carlo yatırım/emeklilik simülasyonu, kredi ve bileşik faiz hesapları.
Yatırım tavsiyesi değildir; hesaplar geçmiş veriye ve varsayımlara dayanır."""
import json
import math
import random
import time
import urllib.parse

from .. import memory
from ..tools import S, _http_get, _schema
from .finance import _quote, _sym

memory.ensure("""
CREATE TABLE IF NOT EXISTS portfolio(id INTEGER PRIMARY KEY AUTOINCREMENT, symbol TEXT, name TEXT, qty REAL, cost REAL, currency TEXT, added REAL);
""")
GROUP = "finance"
NOTE = "Bilgi amaçlıdır, yatırım tavsiyesi değildir. Geçmiş getiri geleceği garanti etmez."


def _history(symbol, rng="5y"):
    url = f"https://query1.finance.yahoo.com/v8/finance/chart/{urllib.parse.quote(symbol)}?range={rng}&interval=1d"
    res = json.loads(_http_get(url, timeout=20))["chart"]["result"][0]
    ts, cl = res.get("timestamp") or [], res["indicators"]["quote"][0].get("close") or []
    pts = [(t, c) for t, c in zip(ts, cl) if c is not None]
    if len(pts) < 30:
        raise RuntimeError(f"{symbol} için yeterli geçmiş veri yok.")
    return [time.strftime("%Y-%m-%d", time.gmtime(t)) for t, _ in pts], [c for _, c in pts], res["meta"].get("currency", "")


# ---------------- metrikler ----------------

def _returns(px):
    return [px[i] / px[i - 1] - 1 for i in range(1, len(px))]


def _maxdd(eq):
    peak, dd = eq[0], 0.0
    for v in eq:
        peak = max(peak, v)
        dd = min(dd, v / peak - 1)
    return dd


def _stats(eq, days_per_year=252, rf=0.0):
    r = _returns(eq)
    if not r:
        return {}
    years = len(r) / days_per_year
    cagr = (eq[-1] / eq[0]) ** (1 / years) - 1 if years > 0 and eq[0] > 0 else 0
    mu = sum(r) / len(r)
    sd = math.sqrt(sum((x - mu) ** 2 for x in r) / max(1, len(r) - 1))
    sharpe = (mu * days_per_year - rf) / (sd * math.sqrt(days_per_year)) if sd > 0 else 0
    return {"toplam_getiri_%": round((eq[-1] / eq[0] - 1) * 100, 2), "yıllık_getiri_%": round(cagr * 100, 2),
            "yıllık_oynaklık_%": round(sd * math.sqrt(days_per_year) * 100, 2), "maks_düşüş_%": round(_maxdd(eq) * 100, 2), "sharpe": round(sharpe, 2)}


def _sma(px, n):
    out, s = [None] * len(px), 0.0
    for i, v in enumerate(px):
        s += v
        if i >= n:
            s -= px[i - n]
        if i >= n - 1:
            out[i] = s / n
    return out


def _rsi(px, n=14):
    out = [None] * len(px)
    g = l = 0.0
    for i in range(1, len(px)):
        d = px[i] - px[i - 1]
        up, dn = max(d, 0), max(-d, 0)
        if i <= n:
            g += up / n
            l += dn / n
            if i == n:
                out[i] = 100 - 100 / (1 + g / l) if l else 100
        else:
            g = (g * (n - 1) + up) / n
            l = (l * (n - 1) + dn) / n
            out[i] = 100 - 100 / (1 + g / l) if l else 100
    return out


def run_backtest(px, strategy="sma", short=50, long=200, fee=0.001):
    """Saf hesap: sinyal günün kapanışında oluşur, ertesi gün pozisyona girilir (ileriye bakma hatası yok). Her işlemde komisyon."""
    n = len(px)
    pos = [0] * n
    if strategy in ("sma", "sma_cross"):
        a, b = _sma(px, int(short)), _sma(px, int(long))
        for i in range(n):
            pos[i] = 1 if (a[i] is not None and b[i] is not None and a[i] > b[i]) else 0
    elif strategy == "rsi":
        r = _rsi(px)
        state = 0
        for i in range(n):
            if r[i] is not None:
                if r[i] < 30:
                    state = 1
                elif r[i] > 70:
                    state = 0
            pos[i] = state
    else:  # al-tut
        pos = [1] * n
    eq, trades, cur = [1.0], 0, 0
    for i in range(1, n):
        held = pos[i - 1]
        if held != cur:
            trades += 1
            eq[-1] *= (1 - fee)
            cur = held
        eq.append(eq[-1] * (px[i] / px[i - 1] if held else 1.0))
    return eq, trades, sum(pos) / n


def backtest(symbol, strategy="sma", period="5y", short=50, long=200):
    """Stratejiyi gerçek geçmiş fiyatlarla dener ve al-tut ile karşılaştırır."""
    sym = _sym(symbol)
    dates, px, cur = _history(sym, period)
    eq, trades, exposure = run_backtest(px, strategy, short, long)
    bh = [p / px[0] for p in px]
    st, bs = _stats(eq), _stats(bh)
    step = max(1, len(px) // 300)
    return {"ui": "finlab", "tab": "backtest", "sembol": sym, "para": cur, "strateji": {"sma": f"SMA {short}/{long} kesişimi", "rsi": "RSI 30/70", "hold": "Al-tut"}.get(strategy, strategy),
            "dönem": f"{dates[0]} → {dates[-1]}", "strateji_sonuç": {**st, "işlem_sayısı": trades, "piyasada_kalma_%": round(exposure * 100)},
            "al_tut_sonuç": bs, "seri": {"tarih": dates[::step], "strateji": [round(x, 4) for x in eq[::step]], "al_tut": [round(x, 4) for x in bh[::step]]}, "not": NOTE}


def risk_metrics(symbol, benchmark="", period="2y"):
    sym = _sym(symbol)
    bm = _sym(benchmark) if benchmark else ("XU100.IS" if sym.endswith(".IS") else "^GSPC")
    d1, p1, cur = _history(sym, period)
    out = {"sembol": sym, "para": cur, **_stats(p1)}
    try:
        d2, p2, _ = _history(bm, period)
        m2 = dict(zip(d2, p2))
        common = [(a, m2[d]) for d, a in zip(d1, p1) if d in m2]
        ra, rb = _returns([c[0] for c in common]), _returns([c[1] for c in common])
        ma, mb = sum(ra) / len(ra), sum(rb) / len(rb)
        cov = sum((x - ma) * (y - mb) for x, y in zip(ra, rb)) / (len(ra) - 1)
        var = sum((y - mb) ** 2 for y in rb) / (len(rb) - 1)
        sa = math.sqrt(sum((x - ma) ** 2 for x in ra) / (len(ra) - 1))
        sb = math.sqrt(var)
        out.update({"karşılaştırma": bm, "beta": round(cov / var, 2) if var else None, "korelasyon": round(cov / (sa * sb), 2) if sa and sb else None})
    except Exception as e:
        out["karşılaştırma"] = f"{bm} alınamadı: {str(e)[:60]}"
    # günlük %95 riske maruz değer (tarihsel)
    r = sorted(_returns(p1))
    out["günlük_VaR95_%"] = round(-r[int(len(r) * 0.05)] * 100, 2)
    out["not"] = NOTE
    return out


# ---------------- portföy ----------------

def portfolio_add(symbol, quantity, buy_price=0, name=""):
    sym = _sym(symbol)
    try:
        q = _quote(sym)
        cur = q["para"]
        bp = float(buy_price) or q["fiyat"]
    except Exception as e:
        if not float(buy_price or 0):
            return f"Fiyat alınamadı ({e}); alış fiyatını da belirt."
        cur, bp = "", float(buy_price)
    memory._q("INSERT INTO portfolio(symbol,name,qty,cost,currency,added) VALUES(?,?,?,?,?,?)", (sym, name or symbol, float(quantity), bp, cur, time.time()), commit=True)
    return {"eklendi": sym, "adet": float(quantity), "alış": bp, "para": cur}


def portfolio_remove(symbol):
    sym = _sym(symbol)
    memory._q("DELETE FROM portfolio WHERE symbol=?", (sym,), commit=True)
    return f"Portföyden çıkarıldı: {sym}"


def portfolio_show():
    rows = memory._q("SELECT symbol, name, SUM(qty) qty, SUM(qty*cost)/SUM(qty) cost, currency FROM portfolio GROUP BY symbol")
    if not rows:
        return "Portföy boş. 'Portföye 10 adet THYAO ekle' gibi söyle."
    fx = {}
    try:
        fx["USD"] = _quote("USDTRY=X")["fiyat"]
        fx["EUR"] = _quote("EURTRY=X")["fiyat"]
    except Exception:
        pass
    items, tot_v, tot_c = [], 0.0, 0.0
    for r in rows:
        try:
            q = _quote(r["symbol"])
            p, ch = q["fiyat"], q["değişim_%"]
        except Exception:
            p, ch = None, None
        cur = r["currency"] or ""
        k = 1.0 if cur in ("TRY", "") else fx.get(cur)
        v = (p or 0) * r["qty"]
        c = r["cost"] * r["qty"]
        item = {"sembol": r["symbol"], "ad": r["name"], "adet": r["qty"], "maliyet": round(r["cost"], 4), "fiyat": p, "para": cur, "günlük_%": ch,
                "değer": round(v, 2), "kâr_zarar": round(v - c, 2), "kâr_zarar_%": round((v / c - 1) * 100, 2) if c and p else None}
        if k:
            item["değer_TL"] = round(v * k, 2)
            tot_v += v * k
            tot_c += c * k
        items.append(item)
    for it in items:
        it["pay_%"] = round(it.get("değer_TL", 0) / tot_v * 100, 1) if tot_v else None
    return {"ui": "finlab", "tab": "portfolio", "varlıklar": items, "toplam_TL": round(tot_v, 2), "maliyet_TL": round(tot_c, 2),
            "kâr_zarar_TL": round(tot_v - tot_c, 2), "kâr_zarar_%": round((tot_v / tot_c - 1) * 100, 2) if tot_c else None, "not": NOTE}


# ---------------- simülasyon ve hesaplar ----------------

def monte_carlo(initial=100000, monthly=5000, years=20, annual_return=10, volatility=18, inflation=0, goal=0, sims=2000, seed=0):
    """Aylık katkılı yatırımın olası gelecekleri: log-normal aylık getiriler, yüzdelik dilimler, hedefe ulaşma olasılığı.
    inflation verilirse sonuçlar bugünkü paraya çevrilir (reel)."""
    rng = random.Random(int(seed) or None)
    m = int(float(years) * 12)
    mu, sd = float(annual_return) / 100, float(volatility) / 100
    mm, ms = math.log(1 + mu) / 12 - (sd ** 2) / 24, sd / math.sqrt(12)
    inf_m = (1 + float(inflation) / 100) ** (1 / 12)
    paths_y = []
    finals = []
    for _ in range(int(min(int(sims), 20000))):
        v, yearly = float(initial), []
        for k in range(1, m + 1):
            v = v * math.exp(rng.gauss(mm, ms)) + float(monthly)
            if k % 12 == 0:
                yearly.append(v / (inf_m ** k))
        finals.append(v / (inf_m ** m))
        paths_y.append(yearly)
    pct = lambda arr, p: sorted(arr)[min(len(arr) - 1, int(p * len(arr)))]  # noqa: E731
    years_n = len(paths_y[0])
    bands = {f"p{int(p * 100)}": [round(pct([pp[y] for pp in paths_y], p)) for y in range(years_n)] for p in (0.1, 0.25, 0.5, 0.75, 0.9)}
    invested = float(initial) + float(monthly) * m
    out = {"ui": "finlab", "tab": "montecarlo", "yıl": years_n, "yatırılan_toplam": round(invested), "medyan_son": round(pct(finals, 0.5)),
           "kötü_senaryo_p10": round(pct(finals, 0.1)), "iyi_senaryo_p90": round(pct(finals, 0.9)), "bantlar": bands,
           "varsayım": f"yıllık %{annual_return} beklenen getiri, %{volatility} oynaklık" + (f", %{inflation} enflasyon (reel)" if float(inflation) else ""),
           "simülasyon": len(finals), "not": NOTE}
    if float(goal):
        out["hedef"] = float(goal)
        out["hedefe_ulaşma_olasılığı_%"] = round(100 * sum(1 for f in finals if f >= float(goal)) / len(finals), 1)
    return out


def loan_calc(principal, annual_rate, months, extra_monthly=0):
    """Eşit taksitli kredi: aylık taksit, toplam faiz, yıllık özet amortisman tablosu. Faiz yıllık % (aylık = yıllık/12)."""
    P, r, n = float(principal), float(annual_rate) / 100 / 12, int(months)
    pay = P / n if r == 0 else P * r / (1 - (1 + r) ** -n)
    bal, total_int, rows, k = P, 0.0, [], 0
    year = {"faiz": 0.0, "anapara": 0.0}
    while bal > 0.005 and k < n * 2:
        k += 1
        it = bal * r
        pr = min(bal, pay - it + float(extra_monthly))
        bal -= pr
        total_int += it
        year["faiz"] += it
        year["anapara"] += pr
        if k % 12 == 0 or bal <= 0.005:
            rows.append({"yıl": math.ceil(k / 12), "ödenen_faiz": round(year["faiz"], 2), "ödenen_anapara": round(year["anapara"], 2), "kalan": round(max(bal, 0), 2)})
            year = {"faiz": 0.0, "anapara": 0.0}
    return {"aylık_taksit": round(pay + float(extra_monthly), 2), "toplam_faiz": round(total_int, 2), "toplam_ödeme": round(P + total_int, 2),
            "taksit_sayısı": k, "yıllık_özet": rows, "formül": "taksit = P·r / (1 − (1+r)^−n)"}


def compound_growth(principal, annual_rate, years, monthly_add=0, inflation=0):
    P, r, n = float(principal), float(annual_rate) / 100 / 12, int(float(years) * 12)
    v, out = P, []
    for k in range(1, n + 1):
        v = v * (1 + r) + float(monthly_add)
        if k % 12 == 0:
            real = v / ((1 + float(inflation) / 100) ** (k / 12))
            out.append({"yıl": k // 12, "değer": round(v, 2), "reel_değer": round(real, 2)})
    invested = P + float(monthly_add) * n
    return {"son_değer": round(v, 2), "yatırılan": round(invested, 2), "kazanç": round(v - invested, 2), "yıllar": out}


TOOLS = {
    "portfolio_add": (portfolio_add, _schema("Portföye varlık ekler (hisse, altın, döviz, kripto). Alış fiyatı verilmezse güncel fiyat.",
                                             {"symbol": S("THYAO.IS, AAPL, altın, bitcoin…"), "quantity": {"type": "number"}, "buy_price": {"type": "number"}, "name": S("ad")}, ["symbol", "quantity"]), False),
    "portfolio_remove": (portfolio_remove, _schema("Portföyden varlık çıkarır.", {"symbol": S("sembol")}, ["symbol"]), True),
    "portfolio_show": (portfolio_show, _schema("Portföyün canlı değeri, kâr/zarar ve dağılımı (TL'ye çevrilmiş).", {}), False),
    "backtest": (backtest, _schema("Bir yatırım stratejisini gerçek geçmiş fiyatlarla dener: sma (hareketli ortalama kesişimi), rsi, hold (al-tut).",
                                   {"symbol": S("sembol"), "strategy": S("sma/rsi/hold"), "period": S("1y/2y/5y/10y/max"), "short": {"type": "integer"}, "long": {"type": "integer"}}, ["symbol"]), False),
    "risk_metrics": (risk_metrics, _schema("Risk ölçüleri: oynaklık, maksimum düşüş, Sharpe, beta, korelasyon, VaR.", {"symbol": S("sembol"), "benchmark": S("karşılaştırma endeksi"), "period": S("1y/2y/5y")}, ["symbol"]), False),
    "monte_carlo": (monte_carlo, _schema("Monte Carlo yatırım/emeklilik simülasyonu: olası sonuç aralıkları ve hedefe ulaşma olasılığı.",
                                         {"initial": {"type": "number"}, "monthly": {"type": "number"}, "years": {"type": "number"}, "annual_return": {"type": "number", "description": "% beklenen yıllık getiri"},
                                          "volatility": {"type": "number", "description": "% yıllık oynaklık"}, "inflation": {"type": "number"}, "goal": {"type": "number"}}), False),
    "loan_calc": (loan_calc, _schema("Kredi hesabı: aylık taksit, toplam faiz, amortisman.", {"principal": {"type": "number"}, "annual_rate": {"type": "number", "description": "% yıllık"},
                                                                                            "months": {"type": "integer"}, "extra_monthly": {"type": "number"}}, ["principal", "annual_rate", "months"]), False),
    "compound_growth": (compound_growth, _schema("Bileşik faiz/birikim hesabı (aylık ekleme ve enflasyon dahil).", {"principal": {"type": "number"}, "annual_rate": {"type": "number"},
                                                                                                                  "years": {"type": "number"}, "monthly_add": {"type": "number"}, "inflation": {"type": "number"}}, ["principal", "annual_rate", "years"]), False),
}
