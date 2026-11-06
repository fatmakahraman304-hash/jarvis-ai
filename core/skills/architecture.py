"""Local metric floor-plan data, geometry checks, revision history and vector export.
This is a schematic planning engine, not certified CAD or a structural solver.
"""
import html
import json
import math
import re
import threading
import uuid
from pathlib import Path
from ..config import DATA
from ..tools import S, _schema

_lock=threading.RLock()
CATALOG={
 'sofa':{'width':2.1,'depth':.9,'height':.85},'bed_double':{'width':1.6,'depth':2,'height':.6},
 'bed_single':{'width':.9,'depth':2,'height':.6},'table':{'width':1.4,'depth':.8,'height':.75},
 'chair':{'width':.5,'depth':.5,'height':.85},'wardrobe':{'width':1.8,'depth':.6,'height':2.2},
 'kitchen_counter':{'width':1.2,'depth':.6,'height':.9},'sink':{'width':.6,'depth':.6,'height':.9},
 'toilet':{'width':.4,'depth':.7,'height':.8},'shower':{'width':.9,'depth':.9,'height':2.1},
 'fridge':{'width':.6,'depth':.65,'height':1.8},'stairs':{'width':1,'depth':3,'height':2.8}}
MATERIALS={'paint':{'unit':'m2'},'tile':{'unit':'m2'},'parquet':{'unit':'m2'},'wall':{'unit':'m2'}}


def _num(x,minimum=-10000,maximum=10000):
    x=float(x)
    if not math.isfinite(x) or not minimum<=x<=maximum:raise ValueError('Geçersiz ölçü.')
    return x


def _slug(value):
    if not re.fullmatch(r'[a-zA-Z0-9_-]{1,64}',str(value)):raise ValueError('Geçersiz proje kimliği.')
    return str(value)


def _points(room):
    pts=room['points']
    if not isinstance(pts,list) or not 3<=len(pts)<=64:raise ValueError('Oda 3–64 köşe içermeli.')
    pts=[(_num(p[0]),_num(p[1])) for p in pts if isinstance(p,(list,tuple)) and len(p)==2]
    if len(pts)!=len(room['points']) or len(set(pts))!=len(pts):raise ValueError('Geçersiz veya yinelenen köşe.')
    # Non-adjacent segment crossing, including collinear contacts.
    def orient(a,b,c):return (b[0]-a[0])*(c[1]-a[1])-(b[1]-a[1])*(c[0]-a[0])
    def on(a,b,c):return min(a[0],b[0])<=c[0]<=max(a[0],b[0]) and min(a[1],b[1])<=c[1]<=max(a[1],b[1])
    def cross(a,b,c,d):
        o=[orient(a,b,c),orient(a,b,d),orient(c,d,a),orient(c,d,b)]
        return (o[0]*o[1]<0 and o[2]*o[3]<0) or any(abs(v)<1e-10 and on(u,w,z) for v,u,w,z in [(o[0],a,b,c),(o[1],a,b,d),(o[2],c,d,a),(o[3],c,d,b)])
    n=len(pts)
    for i in range(n):
        for j in range(i+1,n):
            if j==i+1 or (i==0 and j==n-1):continue
            if cross(pts[i],pts[(i+1)%n],pts[j],pts[(j+1)%n]):raise ValueError('Oda sınırı kendiyle kesişiyor.')
    if area(pts)<.01:raise ValueError('Oda alanı çok küçük.')
    return pts


def area(points):
    return abs(sum(a[0]*b[1]-b[0]*a[1] for a,b in zip(points,points[1:]+points[:1])))/2


def _inside(point,poly):
    x,y=point;inside=False
    for (ax,ay),(bx,by) in zip(poly,poly[1:]+poly[:1]):
        if abs((bx-ax)*(y-ay)-(by-ay)*(x-ax))<1e-9 and min(ax,bx)<=x<=max(ax,bx) and min(ay,by)<=y<=max(ay,by):return True
        if (ay>y)!=(by>y) and x<(bx-ax)*(y-ay)/(by-ay)+ax:inside=not inside
    return inside


def validate(document):
    d=json.loads(document) if isinstance(document,str) else json.loads(json.dumps(document))
    if not isinstance(d,dict) or d.get('units','m')!='m':raise ValueError('Proje birimi metre olmalı.')
    rooms=d.get('rooms',[]);items=d.get('furniture',[])
    if not isinstance(rooms,list) or not 1<=len(rooms)<=100 or not isinstance(items,list) or len(items)>300:raise ValueError('1–100 oda, en fazla 300 mobilya.')
    ids=set()
    for room in rooms:
        rid=_slug(room['id'])
        if rid in ids:raise ValueError('Oda kimliği yineleniyor.')
        ids.add(rid);room['points']=[list(p) for p in _points(room)]
        room['floor']=int(_num(room.get('floor',0),-5,100))
        room['height']=_num(room.get('height',2.8),.5,20)
        room['wall_thickness']=_num(room.get('wall_thickness',.2),.05,2)
    fids=set()
    for item in items:
        fid=_slug(item['id'])
        if fid in fids:raise ValueError('Mobilya kimliği yineleniyor.')
        fids.add(fid)
        if item.get('room') not in ids or item.get('kind') not in CATALOG:raise ValueError('Mobilya oda/tür bilgisi geçersiz.')
        for k in ['x','y']:item[k]=_num(item[k])
        item['rotation']=int(item.get('rotation',0))%360
        if item['rotation'] not in (0,90,180,270):raise ValueError('Bu sürüm 90 derece mobilya dönüşlerini destekler.')
    d['units']='m';d['rooms']=rooms;d['furniture']=items
    return d


def _box(item):
    c=CATALOG[item['kind']];w,h=c['width'],c['depth']
    if item['rotation'] in (90,270):w,h=h,w
    return item['x'],item['y'],item['x']+w,item['y']+h


def analyze_plan(document, prices='{}'):
    d=validate(document);prices=json.loads(prices) if isinstance(prices,str) else prices
    out=[];total=0;wall_area=0;collisions=[];outside=[]
    for room in d['rooms']:
        pts=room['points'];a=area(pts);perimeter=sum(math.dist(p,q) for p,q in zip(pts,pts[1:]+pts[:1]));total+=a;wall_area+=perimeter*room['height']
        out.append({'id':room['id'],'area_m2':round(a,4),'perimeter_m':round(perimeter,4),'floor':room['floor']})
    byid={r['id']:r for r in d['rooms']}
    for i,a in enumerate(d['furniture']):
        box=_box(a);corners=[(box[0],box[1]),(box[2],box[1]),(box[2],box[3]),(box[0],box[3])]
        if not all(_inside(p,byid[a['room']]['points']) for p in corners):outside.append(a['id'])
        for b in d['furniture'][i+1:]:
            if byid[a['room']]['floor']!=byid[b['room']]['floor']:continue
            q=_box(b)
            if min(box[2],q[2])-max(box[0],q[0])>1e-6 and min(box[3],q[3])-max(box[1],q[1])>1e-6:collisions.append([a['id'],b['id']])
    quantities={'floor_m2':round(total,4),'gross_wall_faces_m2':round(wall_area,4)}
    costs={k:round(v*_num(prices[k],0,1e9),2) for k,v in quantities.items() if k in prices}
    return {'rooms':out,'quantities':quantities,'costs':costs,'total_cost':round(sum(costs.values()),2),'collisions':collisions,'outside_room':outside,
            'limits':['Alanlar oda poligonları toplamıdır; örtüşen odalar toplamdan düşülmez.','Duvar metrajı brüttür; kapı/pencere ve ortak duvar düşümleri yok.','Mobilya kontrolü 2D eksen hizalı kutudur; taşıyıcı/tesisat projesi değildir.']}


def plan_project(action='list',project_id='',document='{}',revision=0):
    root=DATA/'architecture';root.mkdir(exist_ok=True)
    with _lock:
        if action=='catalog':return {'furniture':CATALOG,'materials':MATERIALS,'units':'m'}
        if action=='list':return sorted(p.name for p in root.iterdir() if p.is_dir())
        pid=_slug(project_id or uuid.uuid4().hex[:12]);folder=root/pid
        if action=='save':
            d=validate(document);folder.mkdir(exist_ok=True)
            revisions=sorted(int(p.stem) for p in folder.glob('*.json') if p.stem.isdigit())
            rev=(revisions[-1]+1) if revisions else 1
            path=folder/f'{rev:06d}.json'
            with path.open('x',encoding='utf-8') as f:json.dump(d,f,ensure_ascii=False,indent=2)
            return {'project_id':pid,'revision':rev,'path':str(path)}
        files=sorted(folder.glob('*.json'))
        if not files:raise ValueError('Proje bulunamadı.')
        if action=='history':return [int(p.stem) for p in files]
        if action=='load':
            path=folder/f'{int(revision):06d}.json' if int(revision)>0 else files[-1]
            return {'project_id':pid,'revision':int(path.stem),'document':json.loads(path.read_text(encoding='utf-8'))}
        raise ValueError('İşlem list/catalog/save/load/history olmalı.')


def plan_export(project_id,format='svg',revision=0):
    record=plan_project('load',project_id,revision=revision);d=validate(record['document'])
    if format not in ('svg','json','dxf','obj'):raise ValueError('Desteklenen: svg/json/dxf/obj. DWG/GLB/PDF bu araçta yok.')
    folder=DATA/'architecture_exports';folder.mkdir(exist_ok=True)
    target=folder/f'{_slug(project_id)}-r{record["revision"]}-{uuid.uuid4().hex[:6]}.{format}'
    if format=='json':text=json.dumps(d,ensure_ascii=False,indent=2)
    elif format=='svg':
        pts=[p for r in d['rooms'] for p in r['points']];x=min(p[0] for p in pts)-1;y=min(p[1] for p in pts)-1;w=max(p[0] for p in pts)-x+1;h=max(p[1] for p in pts)-y+1
        shapes=[]
        for r in d['rooms']:
            label=html.escape(str(r.get('name',r['id'])))
            shapes.append(f'<polygon points="{" ".join(f"{p[0]},{p[1]}" for p in r["points"])}" fill="#eef7ff" stroke="#123" stroke-width=".08"/>')
            p=r['points'][0];shapes.append(f'<text x="{p[0]+.15}" y="{p[1]+.45}" font-size=".25">{label} ({area(r["points"]):.2f} m², kat {r["floor"]})</text>')
        for item in d['furniture']:
            a,b,c,e=_box(item);shapes.append(f'<rect x="{a}" y="{b}" width="{c-a}" height="{e-b}" fill="#b7dccd" stroke="#245" stroke-width=".03"/>')
        text=f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="{x} {y} {w} {h}">'+''.join(shapes)+'</svg>'
    elif format=='dxf':
        lines=['0','SECTION','2','HEADER','9','$INSUNITS','70','6','0','ENDSEC','0','SECTION','2','ENTITIES']
        for r in d['rooms']:
            lines+=['0','LWPOLYLINE','8',f'FLOOR_{r["floor"]}','90',str(len(r['points'])),'70','1']
            for x,y in r['points']:lines+=['10',str(x),'20',str(-y)]
        text='\n'.join(lines+['0','ENDSEC','0','EOF'])+'\n'
    else:
        lines=['# schematic room wall surfaces, metres; no door/window cutouts'];offset=0
        for r in d['rooms']:
            for a,b in zip(r['points'],r['points'][1:]+r['points'][:1]):
                z=r['floor']*r['height'];top=z+r['height']
                for x,y,h in [(a[0],a[1],z),(b[0],b[1],z),(b[0],b[1],top),(a[0],a[1],top)]:lines.append(f'v {x} {h} {-y}')
                lines.append(f'f {offset+1} {offset+2} {offset+3} {offset+4}');offset+=4
        text='\n'.join(lines)+'\n'
    target.write_text(text,encoding='utf-8');return {'path':str(target),'format':format,'revision':record['revision']}


def plan_alternatives(width,depth,room_count=3):
    w,h=_num(width,1,1000),_num(depth,1,1000);n=int(room_count)
    if not 1<=n<=20:raise ValueError('1–20 oda.')
    variants=[]
    for axis in ['x','y']:
        rooms=[]
        for i in range(n):
            x,y=(i*w/n,0) if axis=='x' else (0,i*h/n);rw,rh=(w/n,h) if axis=='x' else (w,h/n)
            rooms.append({'id':f'room_{i+1}','points':[[x,y],[x+rw,y],[x+rw,y+rh],[x,y+rh]]})
        variants.append(validate({'units':'m','rooms':rooms}))
    return {'alternatives':variants,'scope':'Eşit bölmeli iki şematik alternatif; koridor, yönetmelik ve taşıyıcı sistem çözülmez.'}


TOOLS={
 'plan_project':(plan_project,_schema('Yerel ölçülü proje kaydı ve değişmez sürümler. action list/catalog/save/load/history. Oda poligonları metre; furniture kind catalog ile öğrenilir.',{'action':S('işlem'),'project_id':S('proje kimliği'),'document':S('rooms ve furniture içeren JSON'),'revision':{'type':'integer'}}),False),
 'analyze_plan':(analyze_plan,_schema('Oda alanı, çevre, brüt duvar metrajı, birim fiyatlı maliyet ve 2D mobilya çakışma kontrolü. Profesyonel mimari doğrulama değildir.',{'document':S('proje JSON'),'prices':S('floor_m2 ve gross_wall_faces_m2 birim fiyat JSON')},['document']),False),
 'plan_export':(plan_export,_schema('Yerel projeyi SVG, JSON, DXF oda çizgileri veya basit OBJ duvar yüzeyleri olarak yeni dosyaya aktarır. DWG/PDF/GLB yok.',{'project_id':S('kimlik'),'format':{'type':'string','enum':['svg','json','dxf','obj']},'revision':{'type':'integer'}},['project_id']),False),
 'plan_alternatives':(plan_alternatives,_schema('Verilen dikdörtgeni eşit odalara bölen iki şematik yerleşim üretir.',{'width':{'type':'number'},'depth':{'type':'number'},'room_count':{'type':'integer'}},['width','depth']),False),
}
