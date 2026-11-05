"""Gmail + Google Takvim. Ek kütüphane gerektirmez (OAuth ve REST urllib ile).

Kurulum (bir kez, ~5 dk) README'de ve Ayarlar > Google ekranında anlatılıyor:
GOOGLE_CLIENT_ID / GOOGLE_CLIENT_SECRET  (Google Cloud > Masaüstü uygulaması OAuth istemcisi)
"""
import base64
import datetime as dt
import hashlib
import html
import json
import re
import secrets
import time
import urllib.error
import urllib.parse
import urllib.request
from email.message import EmailMessage
from email.utils import parseaddr

from ..config import DATA, env
from ..tools import N, S, _schema

TOKEN_FILE = DATA / "google_token.json"
SCOPES = [
    "openid", "email",
    "https://www.googleapis.com/auth/gmail.modify",
    "https://www.googleapis.com/auth/calendar",
]
AUTH_URL = "https://accounts.google.com/o/oauth2/v2/auth"
TOKEN_URL = "https://oauth2.googleapis.com/token"
GMAIL = "https://gmail.googleapis.com/gmail/v1/users/me"
CAL = "https://www.googleapis.com/calendar/v3"

_pending_auth = {}


class GoogleError(Exception):
    pass


# ======================= OAuth =======================
def configured():
    return bool(env("GOOGLE_CLIENT_ID") and env("GOOGLE_CLIENT_SECRET"))


def connected():
    return TOKEN_FILE.exists()


def account():
    try:
        return json.loads(TOKEN_FILE.read_text()).get("email", "")
    except Exception:
        return ""


def auth_url(redirect_uri):
    verifier = secrets.token_urlsafe(48)
    challenge = base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest()).rstrip(b"=").decode()
    state = secrets.token_urlsafe(16)
    _pending_auth[state] = {"verifier": verifier, "redirect": redirect_uri, "ts": time.time()}
    q = {
        "client_id": env("GOOGLE_CLIENT_ID"), "redirect_uri": redirect_uri, "response_type": "code",
        "scope": " ".join(SCOPES), "access_type": "offline", "prompt": "consent",
        "code_challenge": challenge, "code_challenge_method": "S256", "state": state,
    }
    return AUTH_URL + "?" + urllib.parse.urlencode(q)


def _post_form(url, data):
    req = urllib.request.Request(url, data=urllib.parse.urlencode(data).encode(),
                                 headers={"Content-Type": "application/x-www-form-urlencoded"})
    try:
        with urllib.request.urlopen(req, timeout=20) as r:
            return json.loads(r.read())
    except urllib.error.HTTPError as e:
        raise GoogleError(f"Google token hatası {e.code}: {e.read().decode('utf-8', 'ignore')[:300]}")


def finish_auth(state, code):
    p = _pending_auth.pop(state, None)
    if not p:
        raise GoogleError("Geçersiz veya süresi geçmiş oturum, tekrar bağlan.")
    tok = _post_form(TOKEN_URL, {
        "code": code, "client_id": env("GOOGLE_CLIENT_ID"), "client_secret": env("GOOGLE_CLIENT_SECRET"),
        "redirect_uri": p["redirect"], "grant_type": "authorization_code", "code_verifier": p["verifier"],
    })
    tok["expires_at"] = time.time() + tok.get("expires_in", 3600) - 60
    try:
        payload = tok.get("id_token", "").split(".")[1]
        payload += "=" * (-len(payload) % 4)
        tok["email"] = json.loads(base64.urlsafe_b64decode(payload)).get("email", "")
    except Exception:
        tok["email"] = ""
    TOKEN_FILE.write_text(json.dumps(tok))
    return tok["email"]


def disconnect():
    if TOKEN_FILE.exists():
        TOKEN_FILE.unlink()


def _access_token():
    if not TOKEN_FILE.exists():
        raise GoogleError("Google hesabı bağlı değil. Ayarlar > Google > 'Google'a bağlan' ile bağla.")
    tok = json.loads(TOKEN_FILE.read_text())
    if time.time() > tok.get("expires_at", 0):
        if not tok.get("refresh_token"):
            raise GoogleError("Google oturumu süresi doldu, Ayarlar'dan tekrar bağlan.")
        new = _post_form(TOKEN_URL, {
            "client_id": env("GOOGLE_CLIENT_ID"), "client_secret": env("GOOGLE_CLIENT_SECRET"),
            "refresh_token": tok["refresh_token"], "grant_type": "refresh_token",
        })
        tok["access_token"] = new["access_token"]
        tok["expires_at"] = time.time() + new.get("expires_in", 3600) - 60
        TOKEN_FILE.write_text(json.dumps(tok))
    return tok["access_token"]


def api(method, url, params=None, body=None):
    if params:
        url += "?" + urllib.parse.urlencode(params, doseq=True)
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(url, data=data, method=method, headers={
        "Authorization": f"Bearer {_access_token()}", "Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=25) as r:
            raw = r.read()
            return json.loads(raw) if raw else {}
    except urllib.error.HTTPError as e:
        txt = e.read().decode("utf-8", "ignore")
        if e.code == 403 and "has not been used" in txt:
            raise GoogleError("Google Cloud'da Gmail API ve Google Calendar API'yi etkinleştirmen gerekiyor.")
        raise GoogleError(f"Google API {e.code}: {txt[:300]}")


# ======================= Gmail yardımcıları =======================
def _b64d(s):
    return base64.urlsafe_b64decode(s + "=" * (-len(s) % 4)).decode("utf-8", "ignore")


def _headers(msg):
    return {h["name"].lower(): h["value"] for h in msg.get("payload", {}).get("headers", [])}


def _body(payload):
    plain, htm = [], []

    def walk(p):
        mt = p.get("mimeType", "")
        data = p.get("body", {}).get("data")
        if data and mt == "text/plain":
            plain.append(_b64d(data))
        elif data and mt == "text/html":
            htm.append(_b64d(data))
        for c in p.get("parts", []) or []:
            walk(c)
    walk(payload)
    if plain:
        return "\n".join(plain)
    t = "\n".join(htm)
    t = re.sub(r"(?is)<(script|style).*?</\1>", " ", t)
    t = re.sub(r"(?i)<br\s*/?>|</p>|</div>", "\n", t)
    return re.sub(r"[ \t]+", " ", html.unescape(re.sub(r"<[^>]+>", " ", t))).strip()


def _attachments(payload):
    out = []

    def walk(p):
        if p.get("filename"):
            out.append(f"{p['filename']} ({p.get('body', {}).get('size', 0)//1024} KB)")
        for c in p.get("parts", []) or []:
            walk(c)
    walk(payload)
    return out


def _summary(m):
    h = _headers(m)
    labels = m.get("labelIds", [])
    return {"id": m["id"], "kimden": h.get("from", ""), "konu": h.get("subject", "(konusuz)"),
            "tarih": h.get("date", ""), "özet": html.unescape(m.get("snippet", "")),
            "okunmamış": "UNREAD" in labels, "önemli": "IMPORTANT" in labels, "yıldızlı": "STARRED" in labels}


# ======================= Gmail araçları =======================
def gmail_search(query="in:inbox", max_results=10):
    ids = api("GET", f"{GMAIL}/messages", {"q": query, "maxResults": min(int(max_results), 30)}).get("messages", [])
    if not ids:
        return f"'{query}' için e-posta yok."
    out = []
    for i in ids:
        m = api("GET", f"{GMAIL}/messages/{i['id']}", {"format": "metadata",
                                                       "metadataHeaders": ["From", "Subject", "Date"]})
        out.append(_summary(m))
    return out


def gmail_read(message_id, mark_read=True):
    m = api("GET", f"{GMAIL}/messages/{message_id}", {"format": "full"})
    h = _headers(m)
    if mark_read and "UNREAD" in m.get("labelIds", []):
        api("POST", f"{GMAIL}/messages/{message_id}/modify", body={"removeLabelIds": ["UNREAD"]})
    body = _body(m.get("payload", {}))
    return {"id": m["id"], "konu_id": m.get("threadId"), "kimden": h.get("from"), "kime": h.get("to"),
            "cc": h.get("cc", ""), "konu": h.get("subject"), "tarih": h.get("date"),
            "ekler": _attachments(m.get("payload", {})), "içerik": body[:6000]}


def gmail_thread(thread_id):
    t = api("GET", f"{GMAIL}/threads/{thread_id}", {"format": "full"})
    msgs = []
    for m in t.get("messages", []):
        h = _headers(m)
        msgs.append({"kimden": h.get("from"), "tarih": h.get("date"), "içerik": _body(m.get("payload", {}))[:2000]})
    return msgs


def _build(to, subject, body, cc="", bcc="", reply_to_id=""):
    msg = EmailMessage()
    msg["To"] = to
    if cc:
        msg["Cc"] = cc
    if bcc:
        msg["Bcc"] = bcc
    thread_id = None
    if reply_to_id:
        orig = api("GET", f"{GMAIL}/messages/{reply_to_id}", {"format": "metadata",
                   "metadataHeaders": ["Subject", "Message-ID", "References", "From", "Reply-To"]})
        oh = _headers(orig)
        thread_id = orig.get("threadId")
        mid = oh.get("message-id", "")
        if mid:
            msg["In-Reply-To"] = mid
            msg["References"] = (oh.get("references", "") + " " + mid).strip()
        if not subject:
            s = oh.get("subject", "")
            subject = s if s.lower().startswith(("re:", "ynt:")) else "Re: " + s
        if not to:
            msg.replace_header("To", oh.get("reply-to") or oh.get("from", ""))
    msg["Subject"] = subject or "(konusuz)"
    msg.set_content(body)
    raw = base64.urlsafe_b64encode(msg.as_bytes()).decode()
    out = {"raw": raw}
    if thread_id:
        out["threadId"] = thread_id
    return out


def gmail_send(to, subject, body, cc="", bcc="", reply_to_id=""):
    r = api("POST", f"{GMAIL}/messages/send", body=_build(to, subject, body, cc, bcc, reply_to_id))
    return f"Gönderildi (id {r.get('id')})."


def gmail_reply(message_id, body):
    r = api("POST", f"{GMAIL}/messages/send", body=_build("", "", body, reply_to_id=message_id))
    return f"Yanıt gönderildi (id {r.get('id')})."


def gmail_draft(to, subject, body, cc="", reply_to_id=""):
    r = api("POST", f"{GMAIL}/drafts", body={"message": _build(to, subject, body, cc, "", reply_to_id)})
    return f"Taslak oluşturuldu (taslak id {r.get('id')}). Gmail'de Taslaklar'da."


def gmail_send_draft(draft_id):
    r = api("POST", f"{GMAIL}/drafts/send", body={"id": draft_id})
    return f"Taslak gönderildi (id {r.get('id')})."


def _label_id(name, create=True):
    labels = api("GET", f"{GMAIL}/labels").get("labels", [])
    for lb in labels:
        if lb["name"].lower() == name.lower() or lb["id"] == name.upper():
            return lb["id"]
    if not create:
        return None
    return api("POST", f"{GMAIL}/labels", body={"name": name, "labelListVisibility": "labelShow",
                                                 "messageListVisibility": "show"})["id"]


ACTIONS = {
    "okundu": ([], ["UNREAD"]), "mark_read": ([], ["UNREAD"]),
    "okunmadı": (["UNREAD"], []), "mark_unread": (["UNREAD"], []),
    "arşivle": ([], ["INBOX"]), "archive": ([], ["INBOX"]),
    "gelen_kutusuna": (["INBOX"], []), "unarchive": (["INBOX"], []),
    "yıldızla": (["STARRED"], []), "star": (["STARRED"], []),
    "yıldızı_kaldır": ([], ["STARRED"]), "unstar": ([], ["STARRED"]),
    "önemli": (["IMPORTANT"], []), "important": (["IMPORTANT"], []),
    "önemsiz": ([], ["IMPORTANT"]), "not_important": ([], ["IMPORTANT"]),
    "spam": (["SPAM"], ["INBOX"]), "spam_değil": (["INBOX"], ["SPAM"]), "not_spam": (["INBOX"], ["SPAM"]),
}


def gmail_modify(message_ids, action, label=""):
    ids = [x.strip() for x in str(message_ids).replace(";", ",").split(",") if x.strip()]
    if action in ("trash", "çöp"):
        for i in ids:
            api("POST", f"{GMAIL}/messages/{i}/trash")
        return f"{len(ids)} e-posta çöp kutusuna taşındı (30 gün içinde geri alınabilir)."
    if action in ("untrash", "çöpten_çıkar"):
        for i in ids:
            api("POST", f"{GMAIL}/messages/{i}/untrash")
        return f"{len(ids)} e-posta çöpten çıkarıldı."
    if action in ("label_add", "etiket_ekle", "label_remove", "etiket_kaldır"):
        lid = _label_id(label, create=action in ("label_add", "etiket_ekle"))
        if not lid:
            return f"'{label}' etiketi yok."
        add, rem = ([lid], []) if action in ("label_add", "etiket_ekle") else ([], [lid])
    elif action in ACTIONS:
        add, rem = ACTIONS[action]
    else:
        return "Geçersiz eylem. Geçerli: " + ", ".join(list(ACTIONS) + ["trash", "untrash", "label_add", "label_remove"])
    api("POST", f"{GMAIL}/messages/batchModify", body={"ids": ids, "addLabelIds": add, "removeLabelIds": rem})
    return f"{len(ids)} e-postaya '{action}' uygulandı."


def gmail_labels():
    return [{"ad": lb["name"], "id": lb["id"]} for lb in api("GET", f"{GMAIL}/labels").get("labels", [])]


def gmail_stats():
    out = {}
    for name, lid in (("gelen_kutusu", "INBOX"), ("okunmamış", "UNREAD"), ("önemli", "IMPORTANT"), ("spam", "SPAM")):
        lb = api("GET", f"{GMAIL}/labels/{lid}")
        out[name] = {"toplam": lb.get("messagesTotal"), "okunmamış": lb.get("messagesUnread")}
    out["hesap"] = account()
    return out


def gmail_attachment_save(message_id, filename=""):
    from ..tools import _path
    m = api("GET", f"{GMAIL}/messages/{message_id}", {"format": "full"})
    saved = []
    dst = _path("indirilenler")

    def walk(p):
        if p.get("filename") and p.get("body", {}).get("attachmentId"):
            if filename and filename.lower() not in p["filename"].lower():
                return
            a = api("GET", f"{GMAIL}/messages/{message_id}/attachments/{p['body']['attachmentId']}")
            raw = base64.urlsafe_b64decode(a["data"] + "=" * (-len(a["data"]) % 4))
            path = dst / re.sub(r'[\\/:*?"<>|]', "_", p["filename"])
            path.write_bytes(raw)
            saved.append(str(path))
        for c in p.get("parts", []) or []:
            walk(c)
    walk(m.get("payload", {}))
    return saved or "Ek bulunamadı."


# ======================= Takvim =======================
def _tz():
    return dt.datetime.now().astimezone().tzinfo


def _parse_time(s):
    s = str(s).strip().replace("T", " ")
    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M", "%d.%m.%Y %H:%M", "%d.%m.%Y", "%Y-%m-%d"):
        try:
            d = dt.datetime.strptime(s[:19] if "%S" in fmt else s[:16] if "%H" in fmt else s[:10], fmt)
            return d.replace(tzinfo=_tz()), "%H" not in fmt
        except ValueError:
            continue
    try:
        d = dt.datetime.fromisoformat(s)
        return (d if d.tzinfo else d.replace(tzinfo=_tz())), False
    except ValueError:
        raise GoogleError(f"Tarih anlaşılamadı: {s} (örnek: 2026-11-05 14:30)")


def _fmt_event(e):
    st = e.get("start", {})
    en = e.get("end", {})
    return {"id": e.get("id"), "başlık": e.get("summary", "(başlıksız)"),
            "başlangıç": st.get("dateTime", st.get("date")), "bitiş": en.get("dateTime", en.get("date")),
            "yer": e.get("location", ""), "açıklama": (e.get("description") or "")[:300],
            "katılımcılar": [a.get("email") for a in e.get("attendees", [])],
            "toplantı_linki": e.get("hangoutLink", "")}


def calendar_events(days=7, query="", start=""):
    t0 = _parse_time(start)[0] if start else dt.datetime.now(_tz())
    t1 = t0 + dt.timedelta(days=float(days))
    params = {"timeMin": t0.isoformat(), "timeMax": t1.isoformat(), "singleEvents": "true",
              "orderBy": "startTime", "maxResults": 50}
    if query:
        params["q"] = query
    items = api("GET", f"{CAL}/calendars/primary/events", params).get("items", [])
    return [_fmt_event(e) for e in items] or "Bu aralıkta etkinlik yok."


def calendar_create(title, start, end="", duration_minutes=60, description="", location="", attendees="",
                    reminder_minutes=15, meet_link=False):
    s, all_day = _parse_time(start)
    body = {"summary": title, "description": description, "location": location,
            "reminders": {"useDefault": False, "overrides": [{"method": "popup", "minutes": int(reminder_minutes)}]}}
    if all_day:
        e_date = (_parse_time(end)[0] if end else s + dt.timedelta(days=1)).date()
        body["start"] = {"date": s.date().isoformat()}
        body["end"] = {"date": e_date.isoformat()}
    else:
        e = _parse_time(end)[0] if end else s + dt.timedelta(minutes=float(duration_minutes))
        body["start"] = {"dateTime": s.isoformat()}
        body["end"] = {"dateTime": e.isoformat()}
    if attendees:
        body["attendees"] = [{"email": a.strip()} for a in attendees.split(",") if a.strip()]
    params = {"sendUpdates": "all" if attendees else "none"}
    if meet_link:
        body["conferenceData"] = {"createRequest": {"requestId": secrets.token_hex(8)}}
        params["conferenceDataVersion"] = 1
    r = api("POST", f"{CAL}/calendars/primary/events", params, body)
    return {"oluşturuldu": _fmt_event(r)}


def calendar_update(event_id, title="", start="", end="", description="", location=""):
    body = {}
    if title:
        body["summary"] = title
    if description:
        body["description"] = description
    if location:
        body["location"] = location
    if start:
        s, all_day = _parse_time(start)
        if all_day:
            body["start"] = {"date": s.date().isoformat()}
        else:
            old = api("GET", f"{CAL}/calendars/primary/events/{event_id}")
            try:
                dur = (dt.datetime.fromisoformat(old["end"]["dateTime"]) - dt.datetime.fromisoformat(old["start"]["dateTime"]))
            except Exception:
                dur = dt.timedelta(hours=1)
            body["start"] = {"dateTime": s.isoformat()}
            if not end:
                body["end"] = {"dateTime": (s + dur).isoformat()}
    if end:
        e, all_day = _parse_time(end)
        body["end"] = {"date": e.date().isoformat()} if all_day else {"dateTime": e.isoformat()}
    r = api("PATCH", f"{CAL}/calendars/primary/events/{event_id}", {"sendUpdates": "all"}, body)
    return {"güncellendi": _fmt_event(r)}


def calendar_delete(event_id):
    api("DELETE", f"{CAL}/calendars/primary/events/{event_id}", {"sendUpdates": "all"})
    return "Etkinlik silindi."


def calendar_free_slots(date, start_hour=9, end_hour=18, min_minutes=30):
    d, _ = _parse_time(date)
    t0 = d.replace(hour=int(start_hour), minute=0)
    t1 = d.replace(hour=int(end_hour), minute=0)
    fb = api("POST", f"{CAL}/freeBusy", body={"timeMin": t0.isoformat(), "timeMax": t1.isoformat(),
                                              "items": [{"id": "primary"}]})
    busy = [(dt.datetime.fromisoformat(b["start"].replace("Z", "+00:00")).astimezone(_tz()),
             dt.datetime.fromisoformat(b["end"].replace("Z", "+00:00")).astimezone(_tz()))
            for b in fb["calendars"]["primary"].get("busy", [])]
    free, cur = [], t0
    for bs, be in sorted(busy):
        if (bs - cur).total_seconds() >= int(min_minutes) * 60:
            free.append(f"{cur:%H:%M}-{bs:%H:%M}")
        cur = max(cur, be)
    if (t1 - cur).total_seconds() >= int(min_minutes) * 60:
        free.append(f"{cur:%H:%M}-{t1:%H:%M}")
    return free or "Bu gün boş zaman yok."


# ======================= Arka plan izleyiciler (sunucudan çağrılır) =======================
_seen_mail = set()
_seen_events = set()
_last_mail_check = [0.0]


def watch_tick(notify):
    """Önemli yeni e-postaları ve yaklaşan toplantıları bildirir. notify(metin) çağırır."""
    if not connected():
        return
    from ..config import load_settings
    s = load_settings()
    now = time.time()
    if s.get("email_watch", True) and now - _last_mail_check[0] > 120:
        first = _last_mail_check[0] == 0
        _last_mail_check[0] = now
        try:
            ids = api("GET", f"{GMAIL}/messages", {"q": "is:unread is:important in:inbox newer_than:1d",
                                                    "maxResults": 10}).get("messages", [])
            for i in ids:
                if i["id"] in _seen_mail:
                    continue
                _seen_mail.add(i["id"])
                if first:
                    continue  # açılışta eski okunmamışları tek tek okumayalım
                m = _summary(api("GET", f"{GMAIL}/messages/{i['id']}", {"format": "metadata",
                                                                         "metadataHeaders": ["From", "Subject"]}))
                who = parseaddr(m["kimden"])[0] or parseaddr(m["kimden"])[1]
                notify(f"Önemli yeni e-posta: {who} — {m['konu']}")
        except Exception as e:
            print("[gmail izleme]", e)
    if s.get("meeting_alerts", True):
        try:
            t0 = dt.datetime.now(_tz())
            items = api("GET", f"{CAL}/calendars/primary/events", {
                "timeMin": t0.isoformat(), "timeMax": (t0 + dt.timedelta(minutes=11)).isoformat(),
                "singleEvents": "true", "orderBy": "startTime"}).get("items", [])
            for e in items:
                if e["id"] in _seen_events or "dateTime" not in e.get("start", {}):
                    continue
                _seen_events.add(e["id"])
                st = dt.datetime.fromisoformat(e["start"]["dateTime"])
                mins = max(0, int((st - t0).total_seconds() // 60))
                notify(f"{mins} dakika sonra toplantı: {e.get('summary', '')}")
        except Exception as e:
            print("[takvim izleme]", e)


# ======================= kayıt =======================
def _crit_send(a):
    return True


TOOLS = {
    "gmail_search": (gmail_search, _schema(
        "Gmail'de e-posta arar/listeler. Gmail arama sözdizimi: 'is:unread', 'from:ali', 'subject:fatura', "
        "'newer_than:2d', 'has:attachment', 'in:inbox', 'is:important', 'category:promotions'.",
        {"query": S("Gmail arama sorgusu"), "max_results": N("en fazla (30)")}), False),
    "gmail_read": (gmail_read, _schema("Bir e-postanın tamamını okur (okundu işaretler).",
                                       {"message_id": S("e-posta id"), "mark_read": {"type": "boolean"}}, ["message_id"]), False),
    "gmail_thread": (gmail_thread, _schema("Bir yazışmanın (konu) tüm mesajlarını okur.",
                                           {"thread_id": S("konu id")}, ["thread_id"]), False),
    "gmail_send": (gmail_send, _schema("Yeni e-posta GÖNDERİR (kullanıcı onayı gerekir).",
                                       {"to": S("alıcı(lar), virgülle"), "subject": S("konu"), "body": S("metin"),
                                        "cc": S("cc"), "bcc": S("bcc"), "reply_to_id": S("yanıtlanan e-posta id")},
                                       ["to", "subject", "body"]), _crit_send),
    "gmail_reply": (gmail_reply, _schema("Bir e-postaya aynı konu içinde yanıt GÖNDERİR (onay gerekir).",
                                         {"message_id": S("yanıtlanacak e-posta id"), "body": S("yanıt metni")},
                                         ["message_id", "body"]), True),
    "gmail_draft": (gmail_draft, _schema("E-posta TASLAĞI hazırlar (göndermez). Yanıt taslağı için reply_to_id ver.",
                                         {"to": S("alıcı"), "subject": S("konu"), "body": S("metin"), "cc": S("cc"),
                                          "reply_to_id": S("yanıtlanan e-posta id")}, ["to", "subject", "body"]), False),
    "gmail_send_draft": (gmail_send_draft, _schema("Hazır bir taslağı gönderir (onay gerekir).",
                                                   {"draft_id": S("taslak id")}, ["draft_id"]), True),
    "gmail_modify": (gmail_modify, _schema(
        "E-postaları düzenler: okundu/okunmadı, arşivle, yıldızla, önemli, spam, spam_değil, trash (çöp), "
        "untrash, label_add/label_remove (etiket adıyla; yoksa oluşturur). Birden fazla id virgülle.",
        {"message_ids": S("id(ler)"), "action": S("eylem"), "label": S("etiket adı")}, ["message_ids", "action"]),
        lambda a: a.get("action") in ("trash", "çöp", "spam")),
    "gmail_labels": (gmail_labels, _schema("Gmail etiketlerini listeler."), False),
    "gmail_stats": (gmail_stats, _schema("Gelen kutusu, okunmamış, önemli, spam sayıları."), False),
    "gmail_attachment_save": (gmail_attachment_save, _schema("E-posta eklerini İndirilenler'e kaydeder.",
                                                             {"message_id": S("id"), "filename": S("sadece bu ek")},
                                                             ["message_id"]), False),
    "calendar_events": (calendar_events, _schema("Google Takvim etkinliklerini listeler.",
                                                 {"days": N("kaç gün"), "query": S("arama"), "start": S("başlangıç tarihi")}), False),
    "calendar_create": (calendar_create, _schema(
        "Takvime etkinlik/randevu ekler. Tarih biçimi 'YYYY-AA-GG SS:DD'. Katılımcı eklenirse davet gider (onay gerekir).",
        {"title": S("başlık"), "start": S("başlangıç"), "end": S("bitiş"), "duration_minutes": N("süre dk"),
         "description": S("açıklama"), "location": S("yer"), "attendees": S("e-postalar, virgülle"),
         "reminder_minutes": N("kaç dk önce hatırlat"), "meet_link": {"type": "boolean", "description": "Google Meet linki"}},
        ["title", "start"]), lambda a: bool(a.get("attendees"))),
    "calendar_update": (calendar_update, _schema("Etkinliği değiştirir (saat, başlık, yer).",
                                                 {"event_id": S("id"), "title": S("başlık"), "start": S("yeni başlangıç"),
                                                  "end": S("yeni bitiş"), "description": S("açıklama"), "location": S("yer")},
                                                 ["event_id"]), False),
    "calendar_delete": (calendar_delete, _schema("Etkinliği siler (onay gerekir).", {"event_id": S("id")}, ["event_id"]), True),
    "calendar_free_slots": (calendar_free_slots, _schema("Bir gündeki boş zaman aralıkları.",
                                                         {"date": S("tarih"), "start_hour": N("başlangıç saati"),
                                                          "end_hour": N("bitiş saati"), "min_minutes": N("en az dk")},
                                                         ["date"]), False),
}
