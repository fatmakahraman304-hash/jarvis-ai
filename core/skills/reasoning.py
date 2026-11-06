"""Explicit multi-provider comparison and personal response-length preferences."""
import concurrent.futures
from .. import llm, memory
from ..config import load_settings, save_settings
from ..tools import S, _schema


def model_compare(question, providers='gemini,openai,anthropic,ollama'):
    selected=list(dict.fromkeys(p.strip() for p in providers.split(',') if p.strip()))[:4]
    if len(selected)<2:raise ValueError('Karşılaştırma için en az iki sağlayıcı seç.')
    if not question.strip() or len(question)>12000:raise ValueError('1–12000 karakter soru gerekli.')
    def answer(pid):
        if pid not in llm.PROVIDERS or not llm.allowed(pid) or not llm.configured(pid):return {'provider':pid,'error':'Sağlayıcı bağlı değil veya ayarlarda devre dışı.'}
        model=llm.pick_model(pid)
        if not model:return {'provider':pid,'error':'Model bulunamadı.'}
        out=''
        try:
            for kind,data in llm.stream_chat(pid,model,[{'role':'user','content':question}],timeout=25):
                if kind=='text':out+=data
            return {'provider':pid,'model':model,'answer':out[:10000]}
        except Exception as e:return {'provider':pid,'error':type(e).__name__}
    with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:results=list(pool.map(answer,selected))
    return {'responses':results,'instruction':'Cevapların ortak ve çelişen iddialarını tabloyla karşılaştır. Model mutabakatı doğruluk kanıtı değildir; doğrulanmayan iddiaları belirt.'}


def response_profile(length='normal'):
    if length not in ('short','normal','detailed'):raise ValueError('short/normal/detailed kullan.')
    save_settings({'response_length':length});return {'response_length':length}


def macro_suggestions(min_count=3):
    from collections import Counter
    import json
    minimum=max(2,min(int(min_count),20));safe={'open_app','browser_open','window_control','screen_look','runtime_diagnostics'}
    rows=[r for r in reversed(memory.recent_actions(500)) if r.get('ok') and r.get('tool') in safe]
    pairs=Counter()
    for a,b in zip(rows,rows[1:]):
        if b['ts']-a['ts']>120:continue
        pairs[(a['tool'],a['args'],b['tool'],b['args'])]+=1
    return [{'count':n,'steps':[{'tool':a,'args':json.loads(x)},{'tool':b,'args':json.loads(y)}]} for (a,x,b,y),n in pairs.most_common(10) if n>=minimum]


TOOLS={
 'model_compare':(model_compare,_schema('Aynı soruyu en fazla dört bağlı ve izinli modele ayrı ayrı sorar. Yanıtları ve model kimliklerini döndürür; mutabakat doğruluk garantisi değildir. Ücretli API kullanabilir.',{'question':S('soru'),'providers':S('virgülle sağlayıcı kimlikleri')},['question']),True),
 'response_profile':(response_profile,_schema('Kalıcı kullanıcı cevap uzunluğu tercihi: short/normal/detailed.',{'length':{'type':'string','enum':['short','normal','detailed']}},['length']),False),
 'macro_suggestions':(macro_suggestions,_schema('Son başarılı eylemlerde iki dakikalık tekrar eden güvenli iki adımlı işleri bulup makro önerir; kendiliğinden etkinleştirmez.',{'min_count':{'type':'integer'}}),False),
}
