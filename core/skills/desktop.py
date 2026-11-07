"""Windows UI Automation + fresh, hit-tested mouse targeting; no password values."""
import hashlib
import json
import subprocess
import time
import unicodedata
from ..config import ROOT,load_settings
from ..tools import S,_schema
from . import computer

def _norm(text):
    text=''.join(c for c in unicodedata.normalize('NFKD',str(text).casefold()) if not unicodedata.combining(c)).replace('ı','i')
    return ' '.join(text.split())

def _tree():
    computer._need_win()
    computer.U32.GetForegroundWindow.restype=computer.wintypes.HWND
    window=computer.U32.GetForegroundWindow()
    if not window:raise RuntimeError('Etkin Windows penceresi bulunamadı.')
    result=subprocess.run(['powershell.exe','-NoProfile','-NonInteractive','-ExecutionPolicy','Bypass','-File',str(ROOT/'core/uia_tree.ps1'),'-WindowHandle',str(window)],capture_output=True,timeout=7,encoding='utf-8',errors='replace',creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
    if result.returncode:raise RuntimeError('Windows erişilebilirlik bilgisi alınamadı; görsel ekran analizi kullan.')
    try:tree=json.loads(result.stdout.lstrip('\ufeff'))
    except ValueError:raise RuntimeError('Windows erişilebilirlik yanıtı okunamadı.')
    elements=tree.get('elements') or []
    if not isinstance(elements,list):elements=[elements]
    tree['elements']=[e for e in elements if e.get('name') and e.get('enabled') and len(e.get('rect',[]))==4]
    tree['snapshot']=hashlib.sha256(json.dumps(tree,sort_keys=True).encode()).hexdigest()[:16]
    tree['captured_at']=time.time()
    return tree

def desktop_inspect():
    tree=_tree()
    return {**tree,'source':'windows-uia','verification':'accessibility','ekran_analizi':f"Windows erişilebilirlik gözlemi: {tree['title']}; {len(tree['elements'])} etkin öğe. Bu, piksel görüntüsü analizi değildir.",'not':'Ad/rol/automation_id ile hedef seç. Şifre alanları ve alan değerleri okunmaz.'}

def _resolve(tree,target,role='',automation_id=''):
    key=_norm(target)
    candidates=[e for e in tree['elements'] if (not role or _norm(e['role'])==_norm(role)) and (not automation_id or e.get('automation_id')==automation_id)]
    exact=[e for e in candidates if _norm(e['name'])==key]
    candidates=exact or [e for e in candidates if key and key in _norm(e['name'])]
    if len(candidates)!=1:
        raise ValueError('Hedef bulunamadı veya belirsiz. desktop_inspect ile tam ad/rol/automation_id seç. Eşleşmeler: '+json.dumps([{'name':e['name'],'role':e['role'],'automation_id':e.get('automation_id')} for e in candidates[:8]],ensure_ascii=False))
    e=candidates[0];x,y,w,h=map(float,e['rect'])
    if not all(__import__('math').isfinite(n) for n in (x,y,w,h)) or w<=0 or h<=0:raise ValueError('Geçersiz hedef sınırı')
    return e,round(x+w/2),round(y+h/2)

def desktop_target(target,role='',automation_id=''):
    tree=_tree();e,x,y=_resolve(tree,target,role,automation_id)
    return {'target':e,'x':x,'y':y,'snapshot':tree['snapshot'],'source':'windows-uia','not':'Tıklamak için desktop_click_target kullan; hedef işlemden hemen önce yeniden bulunur.'}

def desktop_click_target(target,role='',automation_id='',double=False):
    with computer._input_lock:
        computer._check_stop()
        tree=_tree();e,x,y=_resolve(tree,target,role,automation_id)
        if computer.U32.GetForegroundWindow()!=int(tree['window']):raise RuntimeError('Etkin pencere değişti; işlem yapılmadı.')
        # Verify no other top-level window covers the observed target.
        computer.U32.WindowFromPoint.argtypes=[computer.wintypes.POINT]
        computer.U32.WindowFromPoint.restype=computer.wintypes.HWND
        computer.U32.GetAncestor.argtypes=[computer.wintypes.HWND,computer.ctypes.c_uint]
        computer.U32.GetAncestor.restype=computer.wintypes.HWND
        hit=computer.U32.WindowFromPoint(computer.wintypes.POINT(x,y))
        root=computer.U32.GetAncestor(hit,2) if hit else 0
        if int(root or 0)!=int(tree['window']):raise RuntimeError('Hedef başka pencerenin altında; işlem yapılmadı.')
        result=computer.mouse_click(x,y,double=bool(double))
        return {'action':result,'target':e['name'],'source':'windows-uia','snapshot':tree['snapshot']}

def _critical(args):
    from .browser import RISKY,SENSITIVE_UI
    if not load_settings().get('semantic_desktop_auto',True):return True
    try:
        tree=_tree();element,_,_=_resolve(tree,args.get('target',''),args.get('role',''),args.get('automation_id',''))
        label=element['name']+' '+tree.get('title','')
        return bool(RISKY.search(label) or SENSITIVE_UI.search(label))
    except Exception:
        return True

TOOLS={
 'desktop_inspect':(desktop_inspect,_schema('Etkin Windows penceresindeki gerçek düğme/metin/alan adlarını ve sınırlarını UI Automation ile okur. Görsel API kotası gerekmez; şifre/değer okumaz. Canvas/görüntü içeriği için screen_look gerekir.',{}),False),
 'desktop_target':(desktop_target,_schema('Windows erişilebilirliğinden tek ve kesin hedef bulur; ad/rol/automation_id ile belirsizliği azalt. Negatif monitör koordinatlarını korur.',{'target':S('görünen tam ad'),'role':S('Button, MenuItem vb.'),'automation_id':S('varsa AutomationId')},['target']),False),
 'desktop_click_target':(desktop_click_target,_schema('Hedefi tıklamadan hemen önce Windows erişilebilirliğinden tekrar bulur; pencere odağı ve üstünü örten pencere kontrol edilir, acil durdurma korunur. Belirsiz hedefe basmaz.',{'target':S('tam görünen ad'),'role':S('Button vb.'),'automation_id':S('varsa AutomationId'),'double':{'type':'boolean'}},['target']),_critical),
}
