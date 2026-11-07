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
   p=b.new_page(viewport={'width':1600,'height':1000});errors=[];requests=[];measurements=[]
   p.on('pageerror',lambda e:errors.append(str(e)))
   p.on('crash',lambda _:errors.append('Page/renderer crashed'))
   p.on('console',lambda m:errors.append('Browser '+m.type+': '+m.text[:1800]) if m.type=='error' else None)
   p.on('requestfailed',lambda r:requests.append(f'{r.method} {r.url}: {r.failure}'))
   # Block external resources, but let localhost requests run natively: routing
   # every poll through Python can starve the synchronous APIRequestContext test.
   p.route(re.compile(r'^https?://(?!127\.0\.0\.1:'+str(port)+r'(?:/|$))'),lambda r:r.abort())
   p.goto(base);p.wait_for_function('window.JV && JV.state.personas.length>0');p.click('#boot-btn');p.wait_for_timeout(1200)
   def run(op,args=None):
    started=time.perf_counter()
    response=p.request.post(base+'/api/architecture/run',data={'op':op,'args':args or {}},timeout=65000)
    assert response.ok, f'{response.text()}\nJS errors: {errors}\nFailed requests: {requests}'
    measurements.append({'operation':op,'elapsed_ms':round((time.perf_counter()-started)*1000,2)})
    print('Architecture command:',measurements[-1],flush=True)
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
   profiler=p.context.new_cdp_session(p);profiler.send('Profiler.enable');profiler.send('Profiler.start')
   profile_saved=[]
   def save_profile():
    if profile_saved:return
    profile=profiler.send('Profiler.stop')['profile']
    nodes={n['id']:n['callFrame'] for n in profile['nodes']};totals={}
    for ident,delta in zip(profile.get('samples',[]),profile.get('timeDeltas',[])):
     name=nodes[ident].get('functionName') or '(anonymous)';totals[name]=totals.get(name,0)+delta/1000
    Path('test-results').mkdir(exist_ok=True)
    Path('test-results/architecture-cpu.json').write_text(json.dumps(sorted(totals.items(),key=lambda item:item[1],reverse=True)[:80],indent=2))
    profile_saved.append(True)

   # End-to-end studio workflow: preset -> dimensions -> visible button -> real SH3D geometry.
   p.locator('#studio-preset').select_option('compact')
   assert p.locator('#studio-width').input_value()=='8'
   assert p.locator('#studio-depth').input_value()=='9'
   p.locator('#studio-house').click()
   p.wait_for_function("document.getElementById('studio-metrics').textContent.includes('5 oda') || document.getElementById('architecture-status').textContent.startsWith('Tasarım hatası:')",timeout=90000)
   studio_state=run('state')
   assert studio_state['counts']['rooms']==5,studio_state
   assert studio_state['counts']['furniture']>=12,studio_state
   assert 'Tasarım uygulandı' in p.locator('#architecture-status').inner_text()
   p.locator('#architecture-expand').click()
   assert p.locator('#architecture-expand').get_attribute('aria-pressed')=='true'
   p.keyboard.press('Escape')
   assert p.locator('#architecture-expand').get_attribute('aria-pressed')=='false'
   result=run('house',{'width':10,'depth':12,'bedrooms':2,'bathrooms':1,'name':'Test 10x12','replace':True})
   assert result['counts']['rooms']==6,result
   assert result['counts']['furniture']>=20,result
   assert result['counts']['walls']>=9,result
   frame.evaluate('window.__testIconRenderer=window.__planView.pipeline.getIconCache().getRenderer().renderer')
   # Real WebGL: a larger shared buffer must preserve every output pixel for
   # an icon with the same dimensions, rather than scaling/cropping its image.
   icon_evidence=frame.evaluate('''async()=>{
    const icon=window.__planView.pipeline.getIconCache().getRenderer(),renderer=icon.renderer;
    const piece=window.__homeController.getHome().getFurniture().find(p=>p.getModel()&&!p.isDoorOrWindow());
    const pixels=c=>Array.from(c.getContext('2d').getImageData(0,0,c.width,c.height).data);
    renderer.setSize(64,32,false);
    await icon.renderTopView(piece,64,32);
    const expected=pixels(await icon.renderTopView(piece,64,32));
    await icon.renderTopView(piece,256,256);
    const before=[renderer.domElement.width,renderer.domElement.height];
    const actual=pixels(await icon.renderTopView(piece,64,32));
    const after=[renderer.domElement.width,renderer.domElement.height];
    return {before,after,same:expected.every((value,i)=>value===actual[i]),
      opaque:actual.filter((_,i)=>i%4===3).every(value=>value===255),
      colored:actual.filter((value,i)=>i%4!==3&&value<240).length};
   }''')
   assert icon_evidence['before']==icon_evidence['after']==[256,256],icon_evidence
   assert icon_evidence['same'] and icon_evidence['opaque'] and icon_evidence['colored']>0,icon_evidence
   print('Real icon buffer/pixel verification:',icon_evidence,flush=True)
   assert frame.evaluate('window.__homeController.getHome().getRooms().every(room=>!room.isCeilingVisible())'), 'Ceilings obscure the furnished interior'
   p.wait_for_timeout(2500)
   assert frame.locator('canvas').count()>=2,'2D and 3D canvases missing'
   stats=frame.evaluate('window.jarvisRenderStats')
   assert stats and stats['frames']>0 and stats['triangles']>0,stats
   assert isinstance(stats.get('resizes'),int),stats
   frame.wait_for_function('(before)=>window.jarvisRenderStats.frames>before+5',arg=stats['frames'],timeout=15000)
   steady=frame.evaluate('window.jarvisRenderStats')
   assert steady['resizes']==stats['resizes'],('Stable frames reallocated the drawing buffer',stats,steady)
   full=run('state',{'details':True});room=full['rooms'][0]
   run('apply',{'operations':[{'kind':'update','id':room['id'],'values':{'name':'Yeni Salon'}}]})
   assert run('state')['rooms'][0]['name']=='Yeni Salon'
   run('undo');assert frame.evaluate('window.__testIconRenderer===window.__planView.pipeline.getIconCache().getRenderer().renderer');assert run('state')['rooms'][0]['name']!='Yeni Salon'
   run('redo');assert frame.evaluate('window.__testIconRenderer===window.__planView.pipeline.getIconCache().getRenderer().renderer');assert run('state')['rooms'][0]['name']=='Yeni Salon'
   p.locator('#studio-inspect').click()
   p.wait_for_function("document.querySelector('#studio-object').options.length>1")
   editable=run('state',{'details':True})['furniture'][0]
   p.locator('#studio-object').select_option(editable['id'])
   p.locator('#studio-properties input[name="name"]').fill('Ölçülü test mobilyası')
   p.locator('#studio-properties input[name="x"]').fill('2.75')
   p.locator('#studio-properties input[name="angle"]').fill('45')
   assert p.locator('#studio-properties').evaluate('(form)=>form.checkValidity()'),p.locator('#studio-properties input').evaluate_all('(inputs)=>inputs.map(i=>({name:i.name,value:i.value,valid:i.validity.valid}))')
   p.locator('#studio-properties button').click()
   p.wait_for_function("()=>{const f=document.querySelector('#architecture-frame').contentWindow.jarvisDesigner.state(true).furniture;return f.some(item=>item.name==='Ölçülü test mobilyası'&&Math.abs(item.x-2.75)<.001)}",timeout=65000)
   p.wait_for_function("document.querySelector('#studio-house').disabled===false",timeout=65000)
   changed=next(f for f in run('state',{'details':True})['furniture'] if f['id']==editable['id'])
   assert changed['name']=='Ölçülü test mobilyası' and abs(changed['x']-2.75)<.001 and abs(changed['angle']-45)<.001,changed
   p.locator('#studio-inspect').click()
   for selector,mode in [('#studio-walk','walk'),('#studio-top','top')]:
    p.locator(selector).click()
    p.wait_for_function("document.querySelector('#studio-house').disabled===false",timeout=65000)
    assert run('state')['view_3d']==mode
   with p.expect_download() as exported:p.locator('#studio-svg').click()
   svg=Path(exported.value.path()).read_text()
   assert '<svg' in svg and 'Ölçülü test mobilyası' in svg and 'rotate(45' in svg,svg[:1000]
   save_profile()
   count=run('state')['counts']['walls']
   bad=p.request.post(base+'/api/architecture/run',data={'op':'apply','args':{'operations':[{'kind':'wall','start':[0,0],'end':[2,0]},{'kind':'INVALID'}]}},timeout=65000)
   assert bad.status==400
   assert run('state')['counts']['walls']==count,'Failed batch was not rolled back'
   snapshot=p.request.get(base+'/api/architecture/project');assert snapshot.ok and snapshot.body()[:2]==b'PK'
   revision=p.request.get(base+'/api/architecture/info').json()['revision'];assert revision>=4
   assert p.locator('#mic').is_visible() and p.locator('#send').is_visible()
   box=p.locator('#architecture-view').bounding_box();chat=p.locator('#right').bounding_box();assert box['x']+box['width']<=chat['x']
   Path('test-results').mkdir(exist_ok=True);p.screenshot(path='test-results/architecture-2d3d.png',full_page=True)
   p.click('#studio-fit');p.wait_for_function("document.querySelector('#architecture-status').textContent.includes('sığdırıldı')")
   for width,height in [(1920,1080),(2560,1440),(3840,2160)]:
    p.set_viewport_size({'width':width,'height':height})
    p.wait_for_function("""()=>{
     const win=document.querySelector('#architecture-frame').contentWindow,v=win.__planView?.getViewport(),canvas=win.document.querySelector('.sh-plan canvas');if(!v||!canvas)return false;
     if(Math.abs(canvas.clientWidth-canvas.parentElement.clientWidth)>2)return false;
     const b=v.getPlanBounds(),x0=v.convertXModelToPixel(b.minX),x1=v.convertXModelToPixel(b.maxX),y0=v.convertYModelToPixel(b.minY),y1=v.convertYModelToPixel(b.maxY);
     return x0>=20&&y0>=20&&x1<=canvas.clientWidth-20&&y1<=canvas.clientHeight-20&&Math.max((x1-x0)/canvas.clientWidth,(y1-y0)/canvas.clientHeight)>.65&&Math.abs((x0+x1)/2-canvas.clientWidth/2)<5;
    }""",timeout=15000)
    assert p.locator('#studio-house').is_visible() and p.locator('#studio-svg').is_visible()
    assert p.locator('#architecture-frame').bounding_box()['height']>300
    p.screenshot(path=f'test-results/studio-{width}x{height}.png')
   # Manual camera navigation must survive resize; explicit fit re-enables follow.
   scene=frame.locator('[data-testid="view3d"]').bounding_box()
   p.mouse.move(scene['x']+scene['width']/2,scene['y']+scene['height']/2);p.mouse.down()
   p.mouse.move(scene['x']+scene['width']/2+60,scene['y']+scene['height']/2+30,steps=5);p.mouse.up()
   manual=frame.evaluate('window.__homeController.getHome().getObserverCamera().getYaw()')
   p.set_viewport_size({'width':1600,'height':1000});p.wait_for_timeout(500)
   assert abs(frame.evaluate('window.__homeController.getHome().getObserverCamera().getYaw()')-manual)<.0001
   p.click('#studio-fit');p.wait_for_function("document.querySelector('#architecture-status').textContent.includes('sığdırıldı')")
   # The quality control must change native materials/lighting, preserve the
   # camera and geometry, and survive a browser reload + revision replacement.
   before_style=frame.evaluate('''()=>{
    const h=window.__homeController.getHome(),c=h.getObserverCamera();
    return {pose:[c.getX(),c.getY(),c.getZ(),c.getYaw(),c.getPitch(),c.getFieldOfView()],observer:h.getCamera()===c,state:window.jarvisDesigner.state(true)};
   }''')
   assert p.locator('#studio-render-style').bounding_box()['width']>=150,'Quality label is truncated'
   p.locator('#studio-render-style').select_option('design')
   p.wait_for_function("document.querySelector('#studio-render-style').disabled===false",timeout=90000)
   assert 'görünümü çizildi' in p.locator('#architecture-status').inner_text()
   quality=frame.evaluate('''()=>{
    const h=window.__homeController.getHome(),c=h.getObserverCamera(),root=window.__homeScene.getRoot();let physical=0;
    root.traverse(o=>{for(const m of (Array.isArray(o.material)?o.material:[o.material]))if(m?.isMeshPhysicalMaterial)physical++;});
    return {stats:window.jarvisRenderStats,physical,scene:root.isScene,environment:!!root.environment?.isTexture,
      pose:[c.getX(),c.getY(),c.getZ(),c.getYaw(),c.getPitch(),c.getFieldOfView()],observer:h.getCamera()===c,state:window.jarvisDesigner.state(true)};
   }''')
   assert quality['stats']['style']=='design' and quality['stats']['frames']>0 and quality['stats']['shadows'] and quality['stats']['ao'],quality
   assert quality['physical']>0 and quality['scene'] and quality['environment'],quality
   assert quality['pose']==before_style['pose'] and quality['observer']==before_style['observer'],(before_style['pose'],quality['pose'],before_style['observer'],quality['observer'])
   for key in ['counts','walls','rooms','furniture','levels']:assert quality['state'][key]==before_style['state'][key],key
   p.screenshot(path='test-results/studio-material-light.png')
   print('Native material/light view:',{key:quality[key] for key in ['stats','physical','scene','environment']},flush=True)
   Path('test-results/architecture-stages-before-reload.json').write_text(json.dumps(p.evaluate('JV.architecture.timings'),indent=2))
   p.reload();p.wait_for_function('window.JV && JV.state.personas.length>0');p.click('#boot-btn');p.wait_for_timeout(1000);p.evaluate("JV.setView('design')")
   p.wait_for_function("document.querySelector('#architecture-frame').contentWindow.jarvisDesigner",timeout=45000)
   # Browser reload releases the old client lease after ten seconds.
   p.wait_for_timeout(10500)
   restored=run('state');assert restored['counts']['rooms']==6 and restored['rooms'][0]['name']=='Yeni Salon'
   frame=p.frame(url=base+'/designer/');assert frame
   frame.wait_for_function("window.jarvisRenderStats?.style==='design'&&window.jarvisRenderStats.frames>0",timeout=65000)
   assert restored['render_style']=='design'
   # Restore a previous version through the visible controls. The replaced
   # current project must remain recoverable as a newly retained snapshot.
   versions=p.request.get(base+'/api/architecture/history').json()
   assert versions
   p.click('#studio-history-refresh')
   p.wait_for_function("document.querySelector('#studio-history').options.length>1")
   p.click('#studio-history')
   p.keyboard.press('Home');p.keyboard.press('ArrowDown');p.keyboard.press('Enter')
   target=int(p.evaluate("document.querySelector('#studio-history').value"))
   assert any(row['revision']==target for row in p.request.get(base+'/api/architecture/history').json())
   prior_revision=p.request.get(base+'/api/architecture/info').json()['revision']
   p.once('dialog',lambda dialog:dialog.accept())
   p.locator('#studio-restore').click()
   p.wait_for_function("document.querySelector('#studio-house').disabled===false",timeout=65000)
   assert p.request.get(base+'/api/architecture/info').json()['revision']>prior_revision
   assert any(row['revision']>=prior_revision for row in p.request.get(base+'/api/architecture/history').json())
   frame.wait_for_function("window.jarvisRenderStats?.style==='design'&&window.jarvisRenderStats.frames>0",timeout=65000)
   assert frame.evaluate("window.__preferences.getView3DStyle()")=='design'
   # Return to the fast mode through the model-facing command as well.
   fast=run('render_style',{'style':'technical'})
   assert fast['render_style']=='technical' and not fast['shadows'] and not fast['ambient_occlusion']
   # Both new persistent stores are available through the existing memory API.
   mem=p.request.get(base+'/api/memory').json();assert 'tasks' in mem and 'projects' in mem
   assert p.locator('#o-initiative').count()==1
   # Only expected errors from the deliberately rejected transaction and
   # the intentionally offline external-resource route may be ignored.
   unexpected=[e for e in errors if not (
    e=='Browser error: Failed to load resource: net::ERR_FAILED' or
    (e.startswith('Browser error: [architecture] command failed: apply ') and
     'Unsupported architecture operation: INVALID' in e) or
    e=='Browser error: Failed to load resource: the server responded with a status of 400 (Bad Request)'
   )]
   Path('test-results/architecture-stages.json').write_text(json.dumps(p.evaluate('JV.architecture.timings'),indent=2))
   Path('test-results/architecture-timings.json').write_text(json.dumps({'environment':'Linux Chromium; software WebGL, no live model/voice','measurements':measurements},indent=2))
   assert not unexpected,unexpected
   print('Real editor: catalog, measured house, 2D+3D geometry, inspector, cameras, SVG, undo/redo, atomic rollback and durable SH3D.')
  except BaseException:
   if 'profiler' in locals():
    try:save_profile()
    except Exception:pass
   Path('test-results').mkdir(exist_ok=True)
   if 'measurements' in locals():Path('test-results/architecture-timings.json').write_text(json.dumps(measurements,indent=2))
   if 'p' in locals():
    try:Path('test-results/architecture-stages-failure.json').write_text(json.dumps(p.evaluate('JV.architecture.timings'),indent=2))
    except Exception:pass
    try:print('History debug:',p.evaluate('({html:document.querySelector("#studio-history")?.outerHTML,buttons:document.querySelector("#architecture-tools")?.textContent})'),flush=True)
    except Exception:pass
    try:print('Studio failure state:',p.evaluate('({status:document.querySelector("#architecture-status")?.textContent,object:document.querySelector("#studio-object-status")?.textContent})'),flush=True)
    except Exception:pass
    try:p.screenshot(path='test-results/architecture-failure.png',full_page=True,timeout=10000)
    except Exception as error:print('Could not capture failure screenshot:',error,flush=True)
    try:Path('test-results/browser-errors.json').write_text(json.dumps({'errors':errors,'failed_requests':requests},ensure_ascii=False,indent=2))
    except Exception:pass
   raise
  finally:b.close()
finally:
 server.terminate()
 try:server.wait(timeout=10)
 except subprocess.TimeoutExpired:server.kill();server.wait()
 log.seek(0)
 Path('test-results').mkdir(exist_ok=True)
 Path('test-results/architecture-server.log').write_text(log.read()[-16000:])
 log.close()
