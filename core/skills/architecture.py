"""SweetHomeJS model operations; measured geometry, not screenshot guesses."""
import json
from .. import architecture as workspace
from ..tools import S,N,_schema

def _bounded(response,offset=0,limit=10):
    offset,limit=int(offset),int(limit)
    if offset<0 or not 1<=limit<=30:raise ValueError('offset >= 0 ve limit 1–30 gerekli.')
    result=response['result']
    if isinstance(result,list):result={'items':result}
    result=dict(result);pages={}
    for key,rows in list(result.items()):
        if not isinstance(rows,list):continue
        page=[]
        for row in rows[offset:offset+limit]:
            if len(json.dumps(page+[row],ensure_ascii=False))>4000:break
            page.append(row)
        result[key]=page
        pages[key]={'total':len(rows),'offset':offset,'returned':len(page),'more':offset+len(page)<len(rows)}
    result['pages']=pages
    # Keep valid JSON through the general tool output limit. Huge polygons can
    # be requested as a smaller page rather than returning a cut JSON string.
    answer={**response,'result':result}
    if len(json.dumps(answer,ensure_ascii=False))>7600:
        for key in pages:
            result.pop(key,None)
            pages[key].update(returned=0,more=pages[key]['total']>offset)
        result['detail_note']='İşlem sonucu geçerli; ayrıntılar büyük olduğundan atlandı. architecture_state ile limit=1 kullanarak oku.'
    return answer

def architecture_open():return _bounded(workspace.command('state'))
def architecture_state(details=False,offset=0,limit=10):return _bounded(workspace.command('state',details=bool(details)),offset,limit)
def architecture_catalog(query='',offset=0,limit=20):return _bounded(workspace.command('catalog',query=query),offset,limit)
def architecture_apply(operations):
    data=json.loads(operations) if isinstance(operations,str) else operations
    if not isinstance(data,list) or not 1<=len(data)<=400:raise ValueError('1–400 işlemden oluşan JSON listesi gerekli.')
    return _bounded(workspace.command('apply',operations=data))
def architecture_house(width=10,depth=12,bedrooms=2,bathrooms=1,name='Ev projesi',replace=False):
    return _bounded(workspace.command('apply',operations=workspace.house_operations(width,depth,bedrooms,bathrooms,name,replace)))
def architecture_history(action='undo'):
    if action not in ('undo','redo'):raise ValueError('undo veya redo gerekli')
    return _bounded(workspace.command(action))
def architecture_render(style='technical'):
    if style not in ('technical','design'):raise ValueError('technical veya design gerekli')
    return _bounded(workspace.command('render_style',style=style))
TOOLS={
 'architecture_render':(architecture_render,_schema('3D görünümü değiştirir: technical hızlı teknik çizim; design fiziksel malzeme, gölge ve ortam ışığı. design daha fazla grafik gücü kullanır. Kamera açısını korur ve gerçek çizilmiş kareyi doğrular. Bu görünüm tercihi geometriyi veya işlem geçmişini değiştirmez.',{'style':S('technical veya design')},['style']),False),
 'architecture_open':(architecture_open,_schema('JARVIS içindeki yerel SweetHomeJS 2D/3D mimari editörünü açar; mevcut projeyi korur.',{}),False),
 'architecture_state':(architecture_state,_schema('Gerçek proje modelinden duvar/oda/mobilya kimlikleri, ölçüler, alan ve ayak izi çakışma uyarılarını okur. details=true ile düzenlenecek nesneleri getir. Büyük projeler sayfalıdır; pages alanında toplam/dönen/more bulunur, offset ile sonraki sayfayı oku. Görsel API gerekmez.',{'details':{'type':'boolean'},'offset':{'type':'integer'},'limit':{'type':'integer'}}),False),
 'architecture_catalog':(architecture_catalog,_schema('Yerel gerçek 3D model kataloğunu arar; result.items içinde model kimlikleri, ölçüler ve kapı/pencere bilgisi verir. İngilizce arama veya boş sorgu kullan. pages.items.more varsa dönen sayı kadar offset artır. limit 1–30.',{'query':S('ör. bed, door, window, kitchen veya boş'),'offset':{'type':'integer'},'limit':{'type':'integer'}}),False),
 'architecture_house':(architecture_house,_schema('Ölçülü, koridorlu tek katlı ev oluşturur: duvarlar, odalar, kapılar, pencereler ve gerçek katalog mobilyaları. Ölçüler metre; 7–40m, yatak odası 1–5, banyo 1–3. Mevcut proje varsa replace=true yalnızca kullanıcı yeni proje istediğinde; önceki sürüm yedeklenir.',{'width':N('dış genişlik m'),'depth':N('dış derinlik m'),'bedrooms':N('yatak odası sayısı'),'bathrooms':N('banyo sayısı'),'name':S('proje adı'),'replace':{'type':'boolean'}}),False),
 'architecture_apply':(architecture_apply,_schema('Ölçülü mimari işlemleri tek atomik grupta uygular; hata olursa geri alır. operations JSON listesi. kind: new(name,replace), level(name,elevation,height), select_level(id veya name), wall(start:[x,y],end:[x,y],thickness,height,color), room(name,points:[[x,y]],color), furniture(catalog_id veya name,x,y,width,depth,height,elevation,angle derece,label), update(id,values:{x,y,width,depth,height,angle,name,color,floor_color,wall_color}), delete(id), dimension(start,end,offset), label(text,x,y), camera(mode:top/walk). Bütün uzunluklar metre. Önce state/catalog ile gerçek kimlikleri öğren. Sonuç modelden doğrulanır, ekran/fare gerekmez.',{'operations':S('JSON işlem listesi')},['operations']),False),
 'architecture_history':(architecture_history,_schema('Son mimari işlem grubunu geri alır veya tekrarlar; 20 işlem geçmişi.',{'action':S('undo veya redo')},['action']),False),
}
