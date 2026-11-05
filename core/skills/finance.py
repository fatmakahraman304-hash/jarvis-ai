"""Finans: altın, döviz, borsa (BIST/ABD/kripto), fiyat alarmı, gelir-gider ve bütçe takibi."""
import datetime as dt
import json
import time
import urllib.parse

from .. import memory
from ..tools import N, S, _http_get, _schema

memory.ensure("""
CREATE TABLE IF NOT EXISTS ledger(id INTEGER PRIMARY KEY AUTOINCREMENT, kind TEXT, amount REAL, category TEXT, note TEXT, day TEXT, ts REAL);
CREATE TABLE IF NOT EXISTS budgets(category TEXT PRIMARY KEY, monthly REAL);
CREATE TABLE IF NOT EXISTS price_alerts(id INTEGER PRIMARY KEY AUTOINCREMENT, symbol TEXT, op TEXT, target REAL, note TEXT, fired INTEGER DEFAULT 0, ts REAL);
""")

ALIASES = {
    "altın": "GC=F", "ons": "GC=F", "gold": "GC=F", "gümüş": "SI=F", "silver": "SI=F", "petrol": "BZ=F", "brent": "BZ=F",
    "dolar": "USDTRY=X", "usd": "USDTRY=X", "euro": "EURTRY=X", "eur": "EURTRY=X", "sterlin": "GBPTRY=X",
    "bitcoin": "BTC-USD", "btc": "BTC-USD", "ethereum": "ETH-USD", "eth": "ETH-USD",
    "bist": "XU100.IS", "bist100": "XU100.IS", "nasdaq": "^IXIC", "sp500": "^GSPC", "dow": "^DJI",
}


def _sym(s):
    s = s.strip()
    return ALIASES.get(s.lower(), s.upper())


def _quote(symbol, rng="5d"):
    url = f"https://query1.finance.yahoo.com/v8/finance/chart/{urllib.parse.quote(symbol)}?range={rng}&interval=1d"
    data = json.loads(_http_get(url))
    res = data["chart"]["result"][0]
    meta = res["meta"]
    closes = [c for c in res["indicators"]["quote"][0].get("close", []) if c is not None]
    price = meta.get("regularMarketPrice") or (closes[-1] if closes else None)
    prev = meta.get("chartPreviousClose") or (closes[-2] if len(closes) > 1 else price)
    return {"sembol": symbol, "fiyat": round(price, 4), "para": meta.get("currency"),
            "değişim_%": round((price - prev) / prev * 100, 2) if prev else None,
            "seri": [round(c, 2) for c in closes]}


def market_price(symbols="altın,dolar,euro,bist100,bitcoin"):
    """Örnek semboller: THYAO.IS, ASELS.IS (BIST), AAPL, TSLA, BTC-USD, altın, dolar."""
    out = []
    for s in str(symbols).split(","):
        if not s.strip():
            continue
        try:
            q = _quote(_sym(s))
            q.pop("seri", None)
            q["ad"] = s.strip()
            out.append(q)
        except Exception as e:
            out.append({"ad": s.strip(), "hata": str(e)[:100]})
    return out


def gold_prices():
    ons = _quote("GC=F")["fiyat"]
    usdtry = _quote("USDTRY=X")["fiyat"]
    gram = ons * usdtry / 31.1035
    return {"ons_usd": round(ons, 2), "usd_try": round(usdtry, 4), "gram_altın_tl": round(gram, 2),
            "çeyrek_tl_yaklaşık": round(gram * 1.6065, 0), "yarım_tl_yaklaşık": round(gram * 3.213, 0),
            "tam_tl_yaklaşık": round(gram * 6.426, 0),
            "not": "Ons fiyatından hesaplanan ham değer; kuyumcu alış-satış fiyatları farklıdır."}


def stock_history(symbol, period="1mo"):
    q = _quote(_sym(symbol), period)
    s = q["seri"]
    return {"sembol": q["sembol"], "son": q["fiyat"], "para": q["para"], "en_düşük": min(s) if s else None,
            "en_yüksek": max(s) if s else None, "dönem_değişim_%": round((s[-1] - s[0]) / s[0] * 100, 2) if len(s) > 1 else None,
            "kapanışlar": s[-30:]}


def price_alert(symbol, op, target, note=""):
    """op: '>' veya '<'. Fiyat hedefe gelince bildirim gönderilir."""
    if op not in (">", "<"):
        return "op '>' veya '<' olmalı."
    memory._q("INSERT INTO price_alerts(symbol,op,target,note,ts) VALUES(?,?,?,?,?)",
              (_sym(symbol), op, float(target), note, time.time()), commit=True)
    return f"Alarm kuruldu: {symbol} {op} {target}"


def list_price_alerts():
    return memory._q("SELECT id, symbol, op, target, note FROM price_alerts WHERE fired=0") or "Aktif alarm yok."


def check_alerts(notify):
    for a in memory._q("SELECT * FROM price_alerts WHERE fired=0"):
        try:
            p = _quote(a["symbol"])["fiyat"] if a["symbol"] != "GRAM" else gold_prices()["gram_altın_tl"]
        except Exception:
            continue
        if (a["op"] == ">" and p >= a["target"]) or (a["op"] == "<" and p <= a["target"]):
            memory._q("UPDATE price_alerts SET fired=1 WHERE id=?", (a["id"],), commit=True)
            notify(f"Fiyat alarmı: {a['symbol']} şu an {p} ({a['op']} {a['target']}). {a['note']}")


# ===================== bütçe =====================
def add_transaction(amount, category="genel", note="", kind="gider", day=""):
    day = day or dt.date.today().isoformat()
    memory._q("INSERT INTO ledger(kind,amount,category,note,day,ts) VALUES(?,?,?,?,?,?)",
              ("gelir" if kind.lower().startswith(("gel", "inc")) else "gider", abs(float(amount)), category.lower(), note, day, time.time()),
              commit=True)
    warn = ""
    b = memory._q("SELECT monthly FROM budgets WHERE category=?", (category.lower(),), one=True)
    if b and not kind.lower().startswith(("gel", "inc")):
        spent = memory._q("SELECT COALESCE(SUM(amount),0) s FROM ledger WHERE kind='gider' AND category=? AND substr(day,1,7)=?",
                          (category.lower(), day[:7]), one=True)["s"]
        if spent > b["monthly"]:
            warn = f" UYARI: {category} bütçesi aşıldı ({spent:.0f}/{b['monthly']:.0f})."
        elif spent > b["monthly"] * 0.8:
            warn = f" Dikkat: {category} bütçesinin %{spent / b['monthly'] * 100:.0f}'i kullanıldı."
    return f"Kaydedildi: {kind} {amount} ({category}).{warn}"


def set_budget(category, monthly):
    memory._q("INSERT OR REPLACE INTO budgets(category, monthly) VALUES(?,?)", (category.lower(), float(monthly)), commit=True)
    return f"{category} için aylık bütçe: {monthly}"


def finance_report(month=""):
    month = month or dt.date.today().isoformat()[:7]
    rows = memory._q("SELECT kind, category, SUM(amount) s FROM ledger WHERE substr(day,1,7)=? GROUP BY kind, category", (month,))
    gelir = sum(r["s"] for r in rows if r["kind"] == "gelir")
    gider = sum(r["s"] for r in rows if r["kind"] == "gider")
    budgets = {b["category"]: b["monthly"] for b in memory._q("SELECT * FROM budgets")}
    cats = {r["category"]: {"harcanan": round(r["s"], 2), "bütçe": budgets.get(r["category"])}
            for r in rows if r["kind"] == "gider"}
    return {"ay": month, "gelir": round(gelir, 2), "gider": round(gider, 2), "kalan": round(gelir - gider, 2),
            "kategoriler": dict(sorted(cats.items(), key=lambda x: -x[1]["harcanan"])),
            "son_işlemler": memory._q("SELECT day, kind, amount, category, note FROM ledger WHERE substr(day,1,7)=? ORDER BY id DESC LIMIT 10", (month,))}


def export_finance(month=""):
    from .office import create_excel
    month = month or dt.date.today().isoformat()[:7]
    rows = memory._q("SELECT day, kind, category, amount, note FROM ledger WHERE substr(day,1,7)=? ORDER BY day", (month,))
    data = [["Tarih", "Tür", "Kategori", "Tutar", "Not"]] + [[r["day"], r["kind"], r["category"], r["amount"], r["note"]] for r in rows]
    return create_excel(data, f"belgeler/Gelir_Gider_{month}.xlsx", "Gelir-Gider")


TOOLS = {
    "market_price": (market_price, _schema("Anlık piyasa fiyatı: altın, dolar, euro, BIST hisseleri (THYAO.IS), ABD hisseleri (AAPL), kripto (BTC-USD), endeksler.",
                                           {"symbols": S("virgülle semboller")}), False),
    "gold_prices": (gold_prices, _schema("Gram, çeyrek, yarım, tam altın TL ve ons fiyatı."), False),
    "stock_history": (stock_history, _schema("Bir hissenin/varlığın dönem grafiği verisi.",
                                             {"symbol": S("sembol"), "period": {"type": "string", "enum": ["5d", "1mo", "3mo", "6mo", "1y", "5y"]}}, ["symbol"]), False),
    "price_alert": (price_alert, _schema("Fiyat alarmı kurar (fiyat hedefi geçince bildirim).",
                                         {"symbol": S("sembol"), "op": {"type": "string", "enum": [">", "<"]}, "target": N("hedef"), "note": S("not")},
                                         ["symbol", "op", "target"]), False),
    "list_price_alerts": (list_price_alerts, _schema("Aktif fiyat alarmları."), False),
    "add_transaction": (add_transaction, _schema("Harcama veya gelir kaydeder.",
                                                 {"amount": N("tutar"), "category": S("market, fatura, kira, ulaşım, maaş..."),
                                                  "note": S("açıklama"), "kind": {"type": "string", "enum": ["gider", "gelir"]}, "day": S("YYYY-AA-GG")},
                                                 ["amount"]), False),
    "set_budget": (set_budget, _schema("Kategori için aylık bütçe belirler.", {"category": S("kategori"), "monthly": N("aylık tutar")}, ["category", "monthly"]), False),
    "finance_report": (finance_report, _schema("Aylık gelir-gider ve bütçe raporu.", {"month": S("YYYY-AA")}), False),
    "export_finance": (export_finance, _schema("Aylık gelir-gider tablosunu Excel'e aktarır.", {"month": S("YYYY-AA")}), False),
}
