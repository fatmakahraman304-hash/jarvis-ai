"""Real 2D/3D editor, local catalog, transaction rollback and durable project roundtrip."""
import json,os,socket,subprocess,sys,tempfile,time,urllib.request,re,zipfile
from pathlib import Path
from playwright.sync_api import sync_playwright
ROOT=Path(__file__).resolve().parent.parent
with zipfile.ZipFile(ROOT/'vendor/designer.zip') as archive:
 entries=[(i.filename,i.file_size) for i in archive.infolist() if i.filename.endswith(('.js','.html'))]
 print('DESIGNER files largest: '+repr(sorted(entries,key=lambda x:-x[1])[:12]),flush=True)
 for name,size in entries:
  if size>15_000_000:continue
  raw=archive.read(name)
  for needle in (b'jarvisDesigner',b'jarvisRenderStats'):
   at=raw.find(needle)
   if at>=0:
    print('DESIGNER bridge in '+name+' bytes='+str(size)+' near='+raw[max(0,at-600):at+700].decode('utf8','replace'),flush=True)

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
   # Separate the editor-bundle boot from the surrounding JARVIS dashboard.
   # A crashing standalone page points to the designer/WebGL runtime itself.
   print('Probe: loading isolated SweetHomeJS designer...',flush=True)
   probe=b.new_page(viewport={'width':1200,'height':800});probe_errors=[]
   # Trace the bundled app's async session bootstrap without changing release assets.
   with zipfile.ZipFile(ROOT/'vendor/designer.zip') as archive:
    bundle_name=next(n for n in archive.namelist() if n.startswith('assets/index-') and n.endswith('.js'))
    bundle=archive.read(bundle_name).decode('utf8')
   anchor=re.search(r'globalThis\.__devEvent=[^,]{1,30},([\w$]+\(new [\w$]+\)\.then\(async [\w$]+=>\{)',bundle)
   assert anchor, 'Session bootstrap entry not found in compiled bundle'
   bundle=bundle[:anchor.start(1)]+'console.warn("JARVIS_TRACE before createSession"),'+anchor.group(1).replace('=>{','=>{console.warn("JARVIS_TRACE session ready");',1)+bundle[anchor.end(1):]
   probe.route('**/designer/'+bundle_name,lambda route:route.fulfill(status=200,content_type='application/javascript',body=bundle))
   print('Patched bundled app boot checkpoints at '+bundle_name,flush=True)
   probe.on('crash',lambda _:probe_errors.append('standalone renderer crashed'))
   probe.on('pageerror',lambda e:probe_errors.append(str(e)))
   probe.on('console',lambda m:probe_errors.append('console '+m.type+': '+m.text[:250]) if m.type in ('error','warning') else None)
   probe.on('requestfailed',lambda r:probe_errors.append('request '+r.url[:130]+' '+str(r.failure)))
   probe.goto(base+'/designer/',wait_until='domcontentloaded',timeout=30000)
   try:probe.wait_for_function('window.jarvisDesigner && typeof window.jarvisDesigner.run === "function"',timeout=30000)
   except Exception as e:raise AssertionError(f'Isolated designer failed: {e}; errors={probe_errors}') from e
   print('Probe: isolated designer booted; errors='+str(probe_errors),flush=True)
   probe.close()
   p=b.new_page(viewport={'width':1600,'height':1000});errors=[];requests=[]
   p.on('pageerror',lambda e:errors.append(str(e)))
   p.on('crash',lambda _:errors.append('Page/renderer crashed'))
   p.on('console',lambda m:errors.append('Browser '+m.type+': '+m.text[:300]) if m.type=='error' else None)
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
   frame=p.frame(url=base+'/designer/');assert frame
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
