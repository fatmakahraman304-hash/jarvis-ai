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
        b=pw.chromium.launch(headless=True)
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
            assert not errors,errors
            print('Removed local planner; existing settings and SpacePlanner launch view passed.')
        finally:b.close()
finally:
    server.terminate()
    try:server.wait(timeout=10)
    except subprocess.TimeoutExpired:server.kill();server.wait()
    log.close()
