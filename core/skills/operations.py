"""Bounded local inspection, energy arithmetic and public GitHub polling helpers."""
import ast
import contextlib
import json
import math
import re
import sqlite3
import threading
import urllib.parse
import urllib.request
from pathlib import Path
from ..config import DATA
from ..tools import S, _schema, _path

_watch_lock=threading.Lock()

def database_inspect(path,table='',limit=50):
    p=_path(path).resolve()
    if not p.is_file():raise ValueError('Veritabanı dosyası bulunamadı.')
    with contextlib.closing(sqlite3.connect(p.as_uri()+'?mode=ro',uri=True,timeout=3)) as db:
        db.execute('PRAGMA query_only=ON')
        tables=[x[0] for x in db.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")]
        if not table:return {'tables':tables,'mode':'read-only SQLite'}
        if table not in tables:raise ValueError('Tablo bulunamadı.')
        quoted='"'+table.replace('"','""')+'"';cur=db.execute(f'SELECT * FROM {quoted} LIMIT ?', (max(1,min(int(limit),200)),))
        return {'columns':[x[0] for x in cur.description],'rows':[[v if not isinstance(v,bytes) else f'<{len(v)} binary bytes>' for v in row] for row in cur], 'mode':'read-only'}


def source_audit(path):
    root=_path(path).resolve()
    if not root.exists():raise ValueError("Kaynak yolu bulunamadı.")
    files=[root] if root.is_file() else (p for p in root.rglob('*.py') if not any(x in {'.git','.venv','venv','node_modules'} for x in p.relative_to(root).parts))
    findings=[];checked=0
    for p in files:
        if checked>=1000:break
        if p.suffix!='.py' or p.stat().st_size>1_000_000:continue
        checked+=1
        try:tree=ast.parse(p.read_text(encoding='utf-8'))
        except (UnicodeError,SyntaxError):continue
        for node in ast.walk(tree):
            if not isinstance(node,ast.Call):continue
            name=ast.unparse(node.func)
            reason=''
            if name in {'eval','exec','pickle.loads','pickle.load','os.system'}:reason='Girdi doğrulaması ve güven sınırı incelenmeli: '+name
            if name.startswith('subprocess.') and any(k.arg=='shell' and isinstance(k.value,ast.Constant) and k.value.value is True for k in node.keywords):reason='shell=True komut enjeksiyonu açısından incelenmeli.'
            if reason and len(findings)<200:findings.append({'file':str(p),'line':node.lineno,'review':reason})
    return {'files_checked':checked,'findings':findings,'scope':'Sezgisel Python kaynak taraması; bağımlılık/CVE veya kapsamlı güvenlik açığı taraması değildir.'}


def energy_analysis(readings,price_per_kwh=0):
    rows=json.loads(readings) if isinstance(readings,str) else readings
    if not isinstance(rows,list) or not 2<=len(rows)<=10000:raise ValueError('En az iki zaman/güç örneği gerekli.')
    vals=[]
    for row in rows:
        t,w=float(row['timestamp']),float(row['watts'])
        if not math.isfinite(t) or not math.isfinite(w) or w<0:raise ValueError('Sonlu zaman ve pozitif/0 güç gerekli.')
        vals.append((t,w))
    vals.sort();seconds=vals[-1][0]-vals[0][0]
    if seconds<=0 or any(a[0]==b[0] for a,b in zip(vals,vals[1:])):raise ValueError('Zamanlar benzersiz olmalı.')
    price=float(price_per_kwh)
    if not math.isfinite(price) or price<0:raise ValueError('Geçersiz fiyat.')
    kwh=sum((b[0]-a[0])*(a[1]+b[1])/2 for a,b in zip(vals,vals[1:]))/3_600_000
    return {'kwh':kwh,'duration_hours':seconds/3600,'average_watts':kwh*3_600_000/seconds,'peak_watts':max(w for _,w in vals),'cost':kwh*price,
            'scope':'Unix saniyesi ve Watt örnekleri arasında doğrusal değişim varsayılır; cihazdan veri toplamaz, örnek boşlukları hata yaratabilir.'}


def repository_watch(repo,action='check',interval_minutes=60):
    if not re.fullmatch(r'[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+',repo):raise ValueError('owner/repo gerekli.')
    if action=='schedule':
        from .automation import schedule_task
        minutes=max(5,min(float(interval_minutes),10080))
        return schedule_task(f'repository_watch aracıyla {repo} deposunu check yap; değişiklik varsa commit bağlantısını ve kısa özetini bildir. Yoksa değişiklik yok de.',kind='interval',every_minutes=minutes)
    if action!='check':raise ValueError('check/schedule kullan.')
    req=urllib.request.Request(f'https://api.github.com/repos/{repo}/commits?per_page=1',headers={'User-Agent':'JARVIS-Personal-AI','Accept':'application/vnd.github+json'})
    with urllib.request.urlopen(req,timeout=10) as response:data=json.load(response)
    if not data:raise ValueError('Commit bulunamadı.')
    latest=data[0];sha=latest['sha'];path=DATA/'repository_watch.json'
    with _watch_lock:
        old=json.loads(path.read_text()) if path.exists() else {};previous=old.get(repo);old[repo]=sha
        tmp=path.with_suffix('.tmp');tmp.write_text(json.dumps(old),encoding='utf-8');tmp.replace(path)
    return {'repo':repo,'changed':previous is not None and previous!=sha,'first_check':previous is None,'previous':previous,'sha':sha,'url':latest['html_url'],'message':latest['commit']['message'][:1000],
            'scope':'Herkese açık depoları JARVIS açıkken aralıklı kontrol eder; özel depo/webhook tabanlı gerçek zamanlı izleme değildir.'}


TOOLS={
 'database_inspect':(database_inspect,_schema('Yerel SQLite veritabanını salt okunur açar; tabloları veya sınırlı satırları gösterir. Yazma/yönetim paneli değildir.',{'path':S('SQLite dosyası'),'table':S('isteğe bağlı tablo'),'limit':{'type':'integer'}},['path']),False),
 'source_audit':(source_audit,_schema('Python kodunda eval/exec/pickle/os.system/shell=True inceleme noktalarını arar. Kapsamlı zafiyet/CVE tarayıcısı değildir.',{'path':S('proje/dosya')},['path']),False),
 'energy_analysis':(energy_analysis,_schema('Watt/zaman serisini kWh ve maliyete dönüştürür. readings JSON listesi: timestamp Unix saniyesi, watts. Sensör bağlantısını ayrıca kurmak gerekir.',{'readings':S('ölçümler JSON'),'price_per_kwh':{'type':'number'}},['readings']),False),
 'repository_watch':(repository_watch,_schema('Herkese açık GitHub depo commit değişikliğini kontrol eder veya uygulama açıkken periyodik görev oluşturur. check/schedule.',{'repo':S('owner/repo'),'action':S('check/schedule'),'interval_minutes':{'type':'number'}},['repo']),False),
}
