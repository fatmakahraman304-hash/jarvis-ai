"""Real Chromium pointer/keyboard contract on a local SpacePlanner-shaped canvas.

Run after: pip install playwright; python -m playwright install chromium
This checks browser input, not the external site's availability or model accuracy.
"""
import os
import sys
import tempfile
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
os.environ['JARVIS_DATA'] = tempfile.mkdtemp(prefix='jv_canvas_')
from core import tools
from core.skills import browser
from playwright.sync_api import sync_playwright

with sync_playwright() as pw:
    kwargs = {'headless': True}
    if os.environ.get('JARVIS_TEST_CHROMIUM'):
        kwargs['executable_path'] = os.environ['JARVIS_TEST_CHROMIUM']
    b = pw.chromium.launch(**kwargs)
    try:
        p = b.new_page(viewport={'width': 1000, 'height': 700})
        p.route('https://app.spaceplanner.co/**', lambda r: r.fulfill(content_type='text/html', body='''
          <button>Export</button>
          <canvas width="800" height="500" style="position:absolute;left:100px;top:100px"></canvas>
          <script>window.events=[];
          for(const e of ['mousedown','mousemove','mouseup','keydown'])
            addEventListener(e,x=>events.push({type:e,x:x.clientX,y:x.clientY,key:x.key}));</script>'''))
        p.goto('https://app.spaceplanner.co/editor')
        with patch.object(browser, '_call', side_effect=lambda f,*a,**kw:f(*a)), patch.object(browser, '_page', return_value=p):
            browser.spaceplanner_draw([{'x':200,'y':200},{'x':500,'y':400}],size='400x300')
            events = p.evaluate('events')
            assert sum(e['type']=='mousedown' for e in events)==1
            assert sum(e['type']=='mouseup' for e in events)==1
            assert ''.join(e.get('key','') for e in events if e['type']=='keydown')=='400x300Enter'
            assert events[-1]['type']=='mouseup'
            try:
                browser.spaceplanner_draw([{'x':20,'y':20}],action='click')
            except ValueError:
                pass
            else:
                raise AssertionError('non-canvas click accepted')
        print('Real Chromium canvas drag, exact input and boundary checks passed.')
    finally:
        b.close()
