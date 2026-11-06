"""Real Chromium fixture: close ad overlay, observe new state, continue original task.
Requires: python -m playwright install chromium
"""
import os
import sys
import tempfile
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parent.parent))
os.environ['JARVIS_DATA']=tempfile.mkdtemp(prefix='jv_browser_observe_')
from core import tools
from core.skills import browser, control
from playwright.sync_api import sync_playwright

with sync_playwright() as pw:
    b=pw.chromium.launch(headless=True, **({'executable_path':os.environ['JARVIS_TEST_CHROMIUM']} if os.environ.get('JARVIS_TEST_CHROMIUM') else {}))
    try:
        p=b.new_page(viewport={'width':1000,'height':700})
        p.route('https://app.spaceplanner.co/**',lambda r:r.fulfill(content_type='text/html',body='''
          <button id="draw" onclick="this.textContent='Drawing ready'">Draw room</button>
          <div role="dialog" id="advert" style="position:fixed;inset:0;background:white;z-index:10">
          Advertisement <button onclick="document.querySelector('#advert').remove()">Skip ad</button></div>'''))
        p.goto('https://app.spaceplanner.co/editor')
        images=[]
        def vision(question,img,mime):
            images.append(img)
            assert p.locator('#advert').count()==0
            return 'Editor visible; Draw room button is ready.'
        with patch.object(browser,'_call',side_effect=lambda f,*a,**kw:f(*a)),patch.object(browser,'_page',return_value=p),patch.object(browser,'_ctx',return_value=p.context),patch('core.llm.vision',side_effect=vision):
            result=browser.browser_observe()
            assert result['kapatılanlar']==['Skip ad']
            assert images[0].startswith(b'\xff\xd8')
            browser.browser_click('Draw room')
            assert p.locator('#draw').inner_text()=='Drawing ready'
            assert browser.browser_observe()['kapatılanlar']==[]
            p.evaluate("""() => {document.body.insertAdjacentHTML('beforeend','<input type="file" aria-label="Upload plan"><a href="/file.txt">Download file</a>')}""")
            source=Path(tempfile.mkdtemp())/'plan.txt';source.write_text('plan fixture')
            browser.browser_upload('Upload plan',str(source))
            assert p.get_by_label('Upload plan').evaluate('e=>e.files[0].name')=='plan.txt'
            p.route('**/file.txt',lambda r:r.fulfill(body='download fixture',headers={'Content-Type':'text/plain','Content-Disposition':'attachment; filename="fixture.txt"'}))
            saved=browser.browser_download('Download file')
            assert Path(saved['path']).read_text()=='download fixture'
            p.evaluate("""() => {document.body.insertAdjacentHTML('beforeend','<div role="dialog" id="payment" style="position:fixed;inset:0;background:white;z-index:20">Payment credit card<button>Close</button></div>')}""")
            assert browser._dismiss_overlays(p)==[]
            assert p.locator('#payment').count()==1
            p.locator('#payment').evaluate('(e)=>e.remove()')
            p.evaluate("""() => {document.body.insertAdjacentHTML('beforeend','<div role="dialog" id="stopad" style="position:fixed;inset:0;background:white;z-index:20">Advertisement<button>Close</button></div>')}""")
            control.ESTOP.set()
            try: assert browser._dismiss_overlays(p)==[]
            finally:control.ESTOP.clear()
        print('Chromium overlay dismissal, fresh screenshot, task continuation, protected dialogs and emergency stop: OK')
    finally:b.close()
