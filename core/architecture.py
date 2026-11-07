"""Local SweetHomeJS session, acknowledged commands and versioned SH3D projects."""
import hashlib
import io
import json
import math
from pathlib import Path
import secrets
import threading
import time
import zipfile
from .config import DATA, ROOT

_LOCK=threading.RLock()
_JOBS={}
_OWNER={'id':'','time':0}
STORE=DATA/'architecture'
STORE.mkdir(exist_ok=True)
PROJECT=STORE/'current.sh3d'
REPORT=STORE/'report.json'
MAX_PROJECT=24*1024*1024


# The shipped GPL SweetHomeJS build has a catalog aliasing bug: each category
# is iterated and then appended to itself through FurnitureCatalog.add(). The
# array grows forever, exhausting the browser heap before the editor opens.
# We preserve the verified original archive and patch its extracted JS only;
# this source-available patch also applies to already-extracted installations.
_BAD_CATALOG_INIT = 'for(const t of e.getCategories())for(const n of t.getFurniture())i.getFurnitureCatalog().add(t,n)'
_GOOD_CATALOG_INIT = 'for(const t of e.getCategories())i.getFurnitureCatalog().getCategories().push(t)'


def _fix_designer_catalog(target):
    bundles = list((target / 'assets').glob('index-*.js'))
    patched = 0
    for bundle in bundles:
        code = bundle.read_text(encoding='utf-8')
        if _BAD_CATALOG_INIT in code:
            if code.count(_BAD_CATALOG_INIT) != 1:
                raise RuntimeError('Multiple catalog initializers in designer bundle')
            tmp = bundle.with_suffix('.js.tmp')
            tmp.write_text(code.replace(_BAD_CATALOG_INIT, _GOOD_CATALOG_INIT), encoding='utf-8')
            tmp.replace(bundle)
            patched += 1
        elif _GOOD_CATALOG_INIT in code:
            patched += 1
    if patched != 1:
        raise RuntimeError('Designer catalog initialization patch could not be verified')


def assets():
    manifest=json.loads((ROOT/'vendor/designer.json').read_text())
    archive=ROOT/'vendor/designer.zip'
    if hashlib.sha256(archive.read_bytes()).hexdigest()!=manifest['sha256']:
        raise RuntimeError('Mimari editör paketi doğrulanamadı.')
    target=DATA/'vendor'/(manifest['sha256'][:16]+'-studio5')
    if not (target/'index.html').exists():
        target.mkdir(parents=True,exist_ok=True)
        with zipfile.ZipFile(archive) as z:
            if sum(i.file_size for i in z.infolist())>100*1024*1024:raise ValueError('Editor package too large')
            for i in z.infolist():
                p=(target/i.filename).resolve()
                if not p.is_relative_to(target.resolve()):raise ValueError('Unsafe editor path')
            z.extractall(target)
    # Legacy prebuilt archives need the runtime patch; a rebuilt source archive
    # has the fix and stable XML constructor names baked into the JavaScript.
    if manifest.get('catalog_fix') != 'shared-categories-source':
        _fix_designer_catalog(target)
    from .designer_patch import patch_bundle, corresponding_source
    if manifest.get('cutaway_fix') != 'studio-v5':
        patch_bundle(target)
    source=ROOT/'vendor/designer-source.zip'
    if hashlib.sha256(source.read_bytes()).hexdigest()!=manifest['source_sha256']:
        raise RuntimeError('Mimari editör kaynak paketi doğrulanamadı.')
    corresponding_source(source,target/'jarvis-source.zip')
    return target


def command(op, **args):
    key=secrets.token_hex(16)
    job={'id':key,'command':{'op':op,**args},'event':threading.Event(),'expires':time.monotonic()+55,'state':'queued'}
    with _LOCK:_JOBS[key]=job
    if not job['event'].wait(55):
        with _LOCK:
            job['state']='expired'
            _JOBS.pop(key,None)
        raise RuntimeError('Mimari editör yanıt vermedi. JARVIS arayüzünü açık tutup MİMARİ bölümünü aç; işlem tamamlanmış sayılmadı.')
    with _LOCK:_JOBS.pop(key,None)
    if job.get('error'):raise RuntimeError(job['error'])
    return {'ui':'architecture','verified':True,'result':job['result']}


def claim(client):
    now=time.monotonic()
    if not isinstance(client,str) or not 8<=len(client)<=80:raise ValueError('Invalid client')
    with _LOCK:
        if _OWNER['id'] and _OWNER['id']!=client and now-_OWNER['time']<10:
            return {'busy':True}
        _OWNER.update(id=client,time=now)
        for k,j in list(_JOBS.items()):
            if j['expires']<now:
                if j['state']=='queued':_JOBS.pop(k,None)
                continue
            if j['state']=='queued':
                j.update(state='running',client=client)
                return {'job':{'id':j['id'],'command':j['command']}}
        return {'job':None}


def acknowledge(client,key,result=None,error=None):
    with _LOCK:
        job=_JOBS.get(key)
        if not job or job['state']!='running' or job.get('client')!=client or job['expires']<time.monotonic():
            raise ValueError('Stale or invalid command acknowledgement')
        job.update(result=result,error=str(error)[:1000] if error else None,state='done')
        job['event'].set()


def save_project(data, revision, report):
    if not 1<=len(data)<=MAX_PROJECT:raise ValueError('Project size invalid')
    with zipfile.ZipFile(io.BytesIO(data)) as z:
        if 'Home.xml' not in z.namelist():raise ValueError('SH3D Home.xml missing')
        if sum(i.file_size for i in z.infolist())>80*1024*1024:raise ValueError('Project contents too large')
    with _LOCK:
        old=json.loads(REPORT.read_text()) if REPORT.exists() else {'revision':0}
        if revision!=old['revision']:raise ValueError('Proje başka oturumda değişti; son sürümü yükle.')
        history=STORE/'history';history.mkdir(exist_ok=True)
        if PROJECT.exists():
            (history/f"r{old['revision']:06}.sh3d").write_bytes(PROJECT.read_bytes())
        tmp=STORE/'current.tmp';tmp.write_bytes(data);tmp.replace(PROJECT)
        current={'revision':revision+1,'saved_at':time.time(),'sha256':hashlib.sha256(data).hexdigest(),'report':report}
        temp=STORE/'report.tmp';temp.write_text(json.dumps(current,ensure_ascii=False));temp.replace(REPORT)
        for oldfile in sorted(history.glob('*.sh3d'))[:-50]:oldfile.unlink()
        return current


def project_info():
    return json.loads(REPORT.read_text()) if REPORT.exists() else {'revision':0,'report':None}


def project_history():
    """Bounded local snapshots, newest first; never expose arbitrary paths."""
    with _LOCK:
        return [{'revision': int(p.stem[1:]), 'bytes': p.stat().st_size,
                 'saved_at': p.stat().st_mtime}
                for p in sorted((STORE / 'history').glob('r[0-9]*.sh3d'), reverse=True)
                if p.stem[1:].isdigit()][:50]


def project_version(revision):
    if isinstance(revision, bool) or not str(revision).isdigit() or int(revision) < 1:
        raise ValueError('Geçersiz proje sürümü.')
    path = STORE / 'history' / f'r{int(revision):06}.sh3d'
    if not path.is_file():
        raise ValueError('Kayıtlı proje sürümü bulunamadı.')
    return path


def house_operations(width=10,depth=12,bedrooms=2,bathrooms=1,name='Ev projesi',replace=False):
    width,depth=float(width),float(depth)
    if not all(math.isfinite(x) and 7<=x<=40 for x in (width,depth)):raise ValueError('Ev ölçüleri 7–40 metre olmalı.')
    if not all(math.isfinite(float(x)) and float(x).is_integer() for x in (bedrooms,bathrooms)):
        raise ValueError('Oda ve banyo sayıları tam sayı olmalı.')
    if not 1<=int(bedrooms)<=5 or not 1<=int(bathrooms)<=3:raise ValueError('1–5 yatak odası, 1–3 banyo desteklenir.')
    ops=[{'kind':'new','name':name,'replace':bool(replace)},{'kind':'level','name':'Zemin kat','elevation':0,'height':2.8}]
    wall=lambda a,b,t=.14:ops.append({'kind':'wall','start':a,'end':b,'thickness':t,'height':2.8,'color':'#e9e5df'})
    # Dimensions refer to exterior wall faces; all following coordinates are metres.
    corners=[[.1,.1],[width-.1,.1],[width-.1,depth-.1],[.1,depth-.1]]
    for a,b in zip(corners,corners[1:]+corners[:1]):wall(a,b,.2)
    hall=1.3;left=(width-hall)/2;right=left+hall
    wall([left,.2],[left,depth-.2]);wall([right,.2],[right,depth-.2])
    names=[('Salon','living'),('Mutfak','kitchen')]+[(f'Yatak odası {n+1}','bedroom') for n in range(int(bedrooms))]+[(f'Banyo {n+1}','bath') for n in range(int(bathrooms))]
    wings=[names[::2],names[1::2]]
    for side,rooms in enumerate(wings):
        x0,x1=(.2,left-.07) if side==0 else (right+.07,width-.2)
        span=(depth-.4)/len(rooms)
        if span<2.5 or x1-x0<2.5:raise ValueError('Oda sayısı bu dış ölçülere sığmıyor; ölçüyü büyüt.')
        for i,(label,kind) in enumerate(rooms):
            y0=.2+i*span+(0 if i==0 else .07);y1=.2+(i+1)*span-(0 if i==len(rooms)-1 else .07)
            if i:wall([.2 if side==0 else right,.2+i*span],[left if side==0 else width-.2,.2+i*span])
            ops.append({'kind':'room','name':label,'points':[[x0,y0],[x1,y0],[x1,y1],[x0,y1]],'color':'#dbc9aa' if kind!='bath' else '#cfdee2'})
            # Model catalog IDs are resolved from English queries by the editor.
            doorx=left if side==0 else right
            ops.append({'kind':'furniture','name':'door','x':doorx,'y':(y0+y1)/2,'width':.86,'depth':.14,'height':2.1,'angle':90})
            ops.append({'kind':'furniture','name':'window','x':.1 if side==0 else width-.1,'y':(y0+y1)/2,'width':1.2,'depth':.2,'height':1.2,'elevation':.9,'angle':90})
            cx=(x0+x1)/2;cy=(y0+y1)/2
            if kind=='bedroom':
                ops.extend([{'kind':'furniture','name':'Double bed','x':cx,'y':cy,'width':1.58,'depth':2.08,'height':.7},{'kind':'furniture','name':'Wardrobe','x':x0+.5,'y':y0+.4,'width':.9,'depth':.6,'height':2}])
            elif kind=='living':
                ops.extend([{'kind':'furniture','name':'Sofa','x':cx,'y':y0+.65,'width':2.1,'depth':.9,'height':.8},{'kind':'furniture','name':'Square table','x':cx,'y':cy+.3,'width':1,'depth':.6,'height':.4}])
            elif kind=='kitchen':
                for idx,item in enumerate(['Sink','Cooker','Fridge']):ops.append({'kind':'furniture','name':item,'x':x0+.55+idx*.8,'y':y0+.4,'width':.7,'depth':.6})
                ops.append({'kind':'furniture','name':'Round table','x':cx,'y':cy+.5,'width':1.2,'depth':.8})
            else:
                ops.extend([{'kind':'furniture','name':'Toilet unit','x':x0+.5,'y':y0+.6,'width':.4,'depth':.65},{'kind':'furniture','name':'Washbasin','x':x1-.55,'y':y0+.4,'width':.6,'depth':.5},{'kind':'furniture','name':'Shower','x':cx,'y':y1-.6,'width':.9,'depth':.9}])
    ops.extend([{'kind':'room','name':'Koridor','points':[[left+.07,.2],[right-.07,.2],[right-.07,depth-.2],[left+.07,depth-.2]],'color':'#d9cdbb'}, {'kind':'furniture','name':'door','x':width/2,'y':depth-.1,'width':.95,'depth':.2,'height':2.1}, {'kind':'dimension','start':[0,0],'end':[width,0],'offset':-.5},{'kind':'dimension','start':[0,0],'end':[0,depth],'offset':-.5}])
    return ops
