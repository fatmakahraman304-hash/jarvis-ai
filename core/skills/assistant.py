"""Persistent personal projects and resumable task evidence."""
from .. import assistant
from ..config import load_settings, save_settings
from ..tools import S, _schema


def initiative_mode(enabled=True):
    save_settings({'initiative_enabled': bool(enabled)})
    return {'initiative_enabled': bool(enabled), 'scope': 'JARVIS açıkken yerel, kanıta dayalı öneriler; saat 09–22, en fazla saatte bir. Otomatik tıklama veya ücretli model çağrısı yapmaz.'}


TOOLS = {
    'task_report': (lambda status, summary, remaining='': {'status':status,'summary':summary,'remaining':remaining}, _schema('Görevin son gerçek gözlemine dayalı sonuç raporu. Tek başına çağır. finished yalnızca hedef tamamen doğrulandıysa ve kalan iş yoksa; eksik adım varsa paused, araç/erişim hatasında blocked. Yapılmamış işi tamamlandı sayma.', {'status':{'type':'string','enum':['finished','paused','blocked']},'summary':S('somut doğrulanmış sonuç'),'remaining':S('kalan işler veya boş')}, ['status','summary']), False),
    'project_memory': (assistant.project_note, _schema('Kalıcı proje hafızası. read/set/delete; project proje adı, key karar/ölçü/tercih başlığı, value doğrulanmış bilgi. Aynı anahtar güncellenir; eski kararı tekrar getirmez. Şifre/API anahtarı kaydetme.', {'project': S('proje adı'), 'action': {'type':'string','enum':['read','set','delete']}, 'key': S('bilgi başlığı'), 'value': S('güncel bilgi')}, ['project']), False),
    'task_journal': (assistant.task_journal, _schema('Gerçek araç sonuçlarından kalıcı görev günlüğü: son hedef, durum ve en son sekiz adım. Oturumdaki yarım işleri listeler. Yeniden başlatmadan sonra da okunur; running kayıtlı durumdur, canlı süreç garantisi değildir.', {'task_id': {'type':'integer'}, 'session': S('varsayılan main'), 'include_finished': {'type':'boolean'}}), False),
    'initiative_mode': (initiative_mode, _schema('Kanıta dayalı proaktif önerileri açar/kapatır; sessiz saatlerde, misafirde ve acil durdurmada önermez. Öneri tek başına eylem başlatmaz.', {'enabled': {'type':'boolean'}}, ['enabled']), False),
}
