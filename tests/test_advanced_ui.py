"""Real Chromium UI test for local plans, revisions, preferences and feature status."""
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
data=Path(tempfile.mkdtemp(prefix='jv_adv_ui_'))
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
            p.evaluate("JV.openPanel('settings')");p.click('.s-tabs button[data-tab="advanced"]')
            p.wait_for_function("document.querySelector('#plan-kind').options.length > 0")
            p.select_option('#adv-theme','light');p.wait_for_function("document.documentElement.dataset.theme === 'light'")
            p.select_option('#adv-length','short');p.wait_for_function("JV.settings.response_length === 'short'")
            p.click('#plan-add-room');p.wait_for_function("document.querySelectorAll('#plan-preview polygon').length === 1")
            p.click('#plan-save');p.wait_for_function("document.querySelector('#plan-id').value.length > 0")
            pid=p.input_value('#plan-id')
            first=p.request.post(base+'/api/architecture',data={'action':'load','project_id':pid}).json()
            assert first['revision']==1
            p.click('#plan-add-item');p.wait_for_function("document.querySelectorAll('#plan-preview rect').length === 1")
            p.click('#plan-save');p.wait_for_function("document.querySelector('#adv-result').textContent.includes('sürüm 2')")
            p.fill('#plan-revision','1');p.click('#plan-load');p.wait_for_function("document.querySelectorAll('#plan-preview rect').length === 0")
            assert p.request.post(base+'/api/architecture',data={'action':'history','project_id':pid}).json()==[1,2]
            p.click('#plan-export');p.wait_for_selector('#adv-result a')
            exported=p.request.get(p.locator('#adv-result a').get_attribute('href')).text()
            assert '<rect' not in exported,'export must use the opened historical revision'
            p.click('#adv-status');p.wait_for_function("document.querySelector('#adv-result').textContent.includes('SLAM')")
            assert 'Donanım/ortam gerekli' in p.text_content('#adv-result')
            assert not errors,errors
            print('Advanced UI: light theme, profile, local plan, furniture, immutable revisions and truthful status passed.')
        finally:b.close()
finally:
    server.terminate()
    try:server.wait(timeout=10)
    except subprocess.TimeoutExpired:server.kill();server.wait()
    log.close()
