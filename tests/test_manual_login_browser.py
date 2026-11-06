"""Real CDP Chrome session handoff using a local login fixture, no real account."""
import os
import subprocess
import sys
import tempfile
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parent.parent))
os.environ['JARVIS_DATA']=tempfile.mkdtemp(prefix='jv_cdp_')
from core import chrome_session,tools
from core.skills import browser
from playwright.sync_api import sync_playwright
old=dict(browser._state)
real_popen=subprocess.Popen

def start():
    pw=sync_playwright().start()
    exe=os.environ.get('JARVIS_TEST_CHROMIUM') or pw.chromium.executable_path
    def launch(args,**kw):return real_popen([*args,'--no-sandbox'],**kw)
    with patch.object(chrome_session,'executable',return_value=exe),patch.object(chrome_session.subprocess,'Popen',side_effect=launch),patch.dict(os.environ,{'JARVIS_BROWSER_HEADLESS':'1'}):
        b,ctx,process=chrome_session.launch(pw,Path(tempfile.mkdtemp(prefix='jv_profile_')))
    p=ctx.new_page()
    p.route('https://spaceplanner.co/**',lambda r:r.fulfill(content_type='text/html',body='''
      <h1>Plan fixture</h1><canvas width=500 height=300></canvas>
      <form onsubmit="event.preventDefault();localStorage.setItem('signed-in','yes');this.reset();this.remove()">
        <input type=email><input type=password><button>Log in</button></form>
      <script>window.plan='existing-geometry';</script>'''))
    p.goto('https://spaceplanner.co/editor')
    browser._state.update(ctx=ctx,page=p,pw=pw,browser=b,process=process,manual_capable=True,manual=False)
    return True

def manual_user():
    p=browser._state['page']
    p.locator('[type=email]').fill('fixture@example.invalid')
    p.locator('[type=password]').fill('local-fixture-only')
    p.get_by_role('button',name='Log in').click()

def verify():
    p=browser._state['page']
    return p.evaluate("({plan:window.plan,auth:localStorage.getItem('signed-in')})")

def close():
    try:
        browser._state['browser'].new_browser_cdp_session().send('Browser.close')
    except Exception:pass
    browser._state['pw'].stop()
    process=browser._state['process']
    try:process.wait(timeout=5)
    except subprocess.TimeoutExpired:process.terminate()

try:
    browser._call(start)
    before=browser.spaceplanner_frame();assert before['active']
    assert browser.spaceplanner_manual('start')['manual']
    assert 'image' not in browser.spaceplanner_frame()
    assert 'duraklatıldı' in tools.execute('browser_read',{})
    assert 'duraklatıldı' in tools.execute('screen_look',{})
    browser._call(manual_user)
    assert not browser.spaceplanner_manual('finish')['manual']
    assert browser._call(verify)=={'plan':'existing-geometry','auth':'yes'}
    after=browser.spaceplanner_frame();assert after['active']
    assert 'local-fixture-only' not in str(after)
    print('Real Chrome CDP: manual login, masked frames, paused tools, same plan and authenticated session retained.')
finally:
    if browser._state.get('process'):browser._call(close)
    browser._state.clear();browser._state.update(old)
