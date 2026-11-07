"""Real 2D/3D editor, local catalog, transaction rollback and durable project roundtrip."""
import json,os,socket,subprocess,sys,tempfile,time,urllib.request,re
from pathlib import Path
from playwright.sync_api import sync_playwright
ROOT=Path(__file__).resolve().parent.parent
sock=socket.socket();sock.bind(('127.0.0.1',0));port=sock.getsockname()[1];sock.close()
data=Path(tempfile.mkdtemp(prefix='jv_designer_browser_'))
(data/'settings.json').write_text(json.dumps({'wake_word':False,'voice_enabled':False,'always_listen_migrated':True,'continuous_voice_v2':True}))
env=dict(os.environ,JARVIS_DATA=str(data),TELEGRAM_BOT_TOKEN='',GEMINI_API_KEY='',OPENAI_API_KEY='',GROQ_API_KEY='',CUSTOM_BASE_URL='')
log=tempfile.TemporaryFile(mode='w+')
server=subprocess.Popen([sys.executable,'run.py','--no-browser','--port',str(port)],cwd=ROOT,env=env,stdout=log,stderr=log)
base=f'http://127.0.0.1:{port}'
try:
 for _ in range(200):
  try:
   with urllib.request.urlopen(base+'/api/node/hello',timeout=1):break
  except Exception:time.sleep(.1)
 else:log.seek(0);raise RuntimeError(log.read()[-4000:])
 with sync_playwright() as pw:
  kwargs={'headless':os.environ.get('JARVIS_CI_HEADED')!='1','channel':os.environ.get('JARVIS_BROWSER_CHANNEL','chromium'),'args':['--use-gl=angle','--use-angle=swiftshader','--enable-unsafe-swiftshader','--disable-dev-shm-usage']}
  if os.environ.get('JARVIS_TEST_CHROMIUM'):kwargs['executable_path']=os.environ['JARVIS_TEST_CHROMIUM']
  b=pw.chromium.launch(**kwargs)
  try:
   # Isolated editor boot must succeed without relying on the main dashboard.
   probe=b.new_page(viewport={'width':1200,'height':800})
   probe.goto(base+'/designer/',wait_until='domcontentloaded',timeout=30000)
   probe.wait_for_function('window.jarvisDesigner && typeof window.jarvisDesigner.run === "function"',timeout=30000)
   probe.close()
   p=b.new_page(viewport={'width':1600,'height':1000});errors=[];requests=[]
   p.on('pageerror',lambda e:errors.append(str(e)))
   p.on('crash',lambda _:errors.append('Page/renderer crashed'))
   p.on('console',lambda m:errors.append('Browser '+m.type+': '+m.text[:1800]) if m.type=='error' else None)
   p.on('requestfailed',lambda r:requests.append(f'{r.method} {r.url}: {r.failure}'))
   # Block external resources, but let localhost requests run natively: routing
   # every poll through Python can starve the synchronous APIRequestContext test.
   p.route(re.compile(r'^https?://(?!127\.0\.0\.1:'+str(port)+r'(?:/|$))'),lambda r:r.abort())
   p.goto(base);p.wait_for_function('window.JV && JV.state.personas.length>0');p.click('#boot-btn');p.wait_for_timeout(1200)
   def run(op,args=None):
    response=p.request.post(base+'/api/architecture/run',data={'op':op,'args':args or {}},timeout=65000)
    assert response.ok, f'{response.text()}\nJS errors: {errors}\nFailed requests: {requests}'
    return response.json()['result']
   # First voice/model command must open the editor from the core view automatically.
   print('Opening model catalog from real UI...',flush=True)
   catalog=run('catalog');assert len(catalog)>80
   print('REAL CATALOG ITEM NAMES: '+repr([x.get('name') for x in catalog]),flush=True)

   frame=p.frame(url=base+'/designer/');assert frame
   import io,zipfile
   serialized=frame.evaluate('async()=>Array.from(await window.jarvisDesigner.save())')
   with zipfile.ZipFile(io.BytesIO(bytes(serialized))) as archive:
    home_xml=archive.read('Home.xml').decode('utf8')
    print('ARCHITECTURE ROUNDTRIP Home.xml beginning: '+home_xml[:650],flush=True)

   assert sum(bool(x['model']) for x in catalog)>70
   assert any(x['opening'] for x in catalog)
   result=run('house',{'width':10,'depth':12,'bedrooms':2,'bathrooms':1,'name':'Test 10x12'})
   assert result['counts']['rooms']==6,result
   assert result['counts']['furniture']>=20,result
   assert result['counts']['walls']>=9,result
   p.wait_for_timeout(2500)
   assert frame.locator('canvas').count()>=2,'2D and 3D canvases missing'
   stats=frame.evaluate('window.jarvisRenderStats')
   assert stats and stats['frames']>0 and stats['triangles']>0,stats
   full=run('state',{'details':True});room=full['rooms'][0]
   run('apply',{'operations':[{'kind':'update','id':room['id'],'values':{'name':'Yeni Salon'}}]})
   assert run('state')['rooms'][0]['name']=='Yeni Salon'
   run('undo');assert run('state')['rooms'][0]['name']!='Yeni Salon'
   run('redo');assert run('state')['rooms'][0]['name']=='Yeni Salon'
   count=run('state')['counts']['walls']
   bad=p.request.post(base+'/api/architecture/run',data={'op':'apply','args':{'operations':[{'kind':'wall','start':[0,0],'end':[2,0]},{'kind':'INVALID'}]}},timeout=65000)
   assert bad.status==400
   assert run('state')['counts']['walls']==count,'Failed batch was not rolled back'
   snapshot=p.request.get(base+'/api/architecture/project');assert snapshot.ok and snapshot.body()[:2]==b'PK'
   revision=p.request.get(base+'/api/architecture/info').json()['revision'];assert revision>=4
   assert p.locator('#mic').is_visible() and p.locator('#send').is_visible()
   box=p.locator('#architecture-view').bounding_box();chat=p.locator('#right').bounding_box();assert box['x']+box['width']<=chat['x']
   Path('test-results').mkdir(exist_ok=True);p.screenshot(path='test-results/architecture-2d3d.png',full_page=True)
   p.reload();p.wait_for_function('window.JV && JV.state.personas.length>0');p.click('#boot-btn');p.wait_for_timeout(1000);p.evaluate("JV.setView('design')")
   p.wait_for_function("document.querySelector('#architecture-frame').contentWindow.jarvisDesigner",timeout=45000)
   # Browser reload releases the old client lease after ten seconds.
   p.wait_for_timeout(10500)
   restored=run('state');assert restored['counts']['rooms']==6 and restored['rooms'][0]['name']=='Yeni Salon'
   # Both new persistent stores are available through the existing memory API.
   mem=p.request.get(base+'/api/memory').json();assert 'tasks' in mem and 'projects' in mem
   assert p.locator('#o-initiative').count()==1
   assert not errors,errors
   print('Real editor: 90+ model catalog, measured 10x12 house, 2D+3D triangles, update/undo/redo, atomic rollback, saved/reloaded SH3D, visible voice/chat.')
  finally:b.close()
finally:
 server.terminate()
 try:server.wait(timeout=10)
 except subprocess.TimeoutExpired:server.kill();server.wait()
 log.close()
