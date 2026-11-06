"""Browser regression: no local plan UI; existing settings and SpacePlanner remain."""
import json
import os
import socket
import subprocess
import sys
import tempfile
import time
import urllib.request
from pathlib import Path
from playwright.sync_api import sync_playwright
ROOT=Path(__file__).resolve().parent.parent
sock=socket.socket();sock.bind(('127.0.0.1',0));port=sock.getsockname()[1];sock.close()
data=Path(tempfile.mkdtemp(prefix='jv_sp_ui_'))
(data/'settings.json').write_text(json.dumps({'wake_word':False,'voice_enabled':False,'always_listen_migrated':True,'continuous_voice_v2':True}))
env=dict(os.environ,JARVIS_DATA=str(data),TELEGRAM_BOT_TOKEN='',GEMINI_API_KEY='',OPENAI_API_KEY='',ANTHROPIC_API_KEY='',GROQ_API_KEY='',CUSTOM_BASE_URL='')
log=tempfile.TemporaryFile(mode='w+')
server=subprocess.Popen([sys.executable,'run.py','--no-browser','--port',str(port)],cwd=ROOT,env=env,stdout=log,stderr=log)
base=f'http://127.0.0.1:{port}'
try:
    for _ in range(150):
        try:
            with urllib.request.urlopen(base+'/api/node/hello',timeout=1):break
        except Exception:time.sleep(.1)
    else:log.seek(0);raise RuntimeError(log.read()[-3000:])
    with sync_playwright() as pw:
        b=pw.chromium.launch(headless=True, **({'executable_path':os.environ['JARVIS_TEST_CHROMIUM']} if os.environ.get('JARVIS_TEST_CHROMIUM') else {}))
        try:
            p=b.new_page(viewport={'width':1360,'height':1000});errors=[];p.on('pageerror',lambda e:errors.append(str(e)))
            p.route('**/*',lambda r:r.continue_() if r.request.url.startswith(base) else r.abort())
            p.goto(base);p.wait_for_function('window.JV && JV.state.personas.length > 0');p.click('#boot-btn');p.wait_for_timeout(1600)
            assert p.locator('[data-tab="advanced"]').count()==0
            assert p.locator('#plan-preview').count()==0
            assert p.request.post(base+'/api/architecture',data={'action':'list'}).status==404
            assert p.request.get(base+'/static/advanced.js').status==404
            p.evaluate("JV.openPanel('settings')");p.click('.s-tabs button[data-tab="voice"]')
            p.select_option('#pref-theme','light');p.wait_for_function("document.documentElement.dataset.theme === 'light'")
            p.select_option('#pref-length','short');p.wait_for_function("JV.settings.response_length === 'short'")
            p.click('#s-close')
            p.evaluate("JV.uiCommand('home_design', {}, JSON.stringify({ui:'spaceplanner'}))")
            p.wait_for_selector('#spaceplanner-open',state='visible')
            assert p.evaluate('JV.getView()')=='design'
            assert p.url.startswith(base)
            assert p.locator('#spaceplanner-view iframe').count()==0
            image=p.screenshot(type='jpeg')
            import base64
            frame={'active':True,'message':'Chrome · canlı görünüm','image':'data:image/jpeg;base64,'+base64.b64encode(image).decode()}
            p.route('**/api/spaceplanner/frame',lambda r:r.fulfill(content_type='application/json',body=json.dumps(frame)))
            p.wait_for_selector('#spaceplanner-frame[src^="data:image/jpeg"]',state='visible')
            p.wait_for_function("document.querySelector('#spaceplanner-frame').naturalWidth > 0")
            assert p.locator('.spaceplanner-launch').is_hidden()
            panel=p.locator('#spaceplanner-view').bounding_box();chat=p.locator('#right').bounding_box()
            assert panel['x']+panel['width'] <= chat['x']
            assert p.locator('#mic').is_visible() and p.locator('#send').is_visible()

            def sse(events):return ''.join('data: '+json.dumps(e)+'\n\n' for e in events)
            response={'body':sse([{'type':'token','text':'Önceki kısmi yanıt.'},{'type':'error','text':'Gerçek araç çağrısı oluşmadı.'},{'type':'done','text':'Gerçek araç çağrısı oluşmadı.','outcome':'blocked'}])}
            p.route('**/api/chat',lambda r:r.fulfill(content_type='text/event-stream',body=response['body']))
            p.evaluate("JV.sendCommand('SpacePlanner aç')")
            assert p.locator('#task-state').get_attribute('data-state')=='blocked'
            assert 'Gerçek araç çağrısı oluşmadı.' in p.locator('#log').inner_text()
            response['body']=sse([{'type':'token','text':'Kesik yanıt'}])
            p.evaluate("JV.sendCommand('SpacePlanner aç')")
            assert p.locator('#task-state').get_attribute('data-state')=='blocked'
            assert 'tamamlanmadan kesildi' in p.locator('#log').inner_text()
            response['body']=sse([{'type':'tool','name':'browser_observe','status':'running'}, {'type':'tool','name':'browser_observe','status':'done','result':'<script>untrusted</script> gözlem sonucu'}, {'type':'done','text':'Gözlem alındı.','outcome':'finished'}])
            p.evaluate("JV.sendCommand('SpacePlanner analiz et')")
            assert 'SONUÇ ALINDI' in p.locator('#log').inner_text()
            assert '<script>untrusted</script>' in p.locator('.tool-result').last.text_content()
            assert p.locator('.tool-result script').count()==0
            response['body']=sse([{'type':'token','text':'SpacePlanner açık.'},{'type':'done','text':'SpacePlanner açık.','outcome':'finished'}])
            p.evaluate("JV.sendCommand('SpacePlanner aç')")
            assert p.locator('#task-state').get_attribute('data-state')=='finished'
            assert not errors,errors
            print('Removed local planner; existing settings and SpacePlanner launch view passed.')
        finally:b.close()
finally:
    server.terminate()
    try:server.wait(timeout=10)
    except subprocess.TimeoutExpired:server.kill();server.wait()
    log.close()
