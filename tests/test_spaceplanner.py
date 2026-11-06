"""SpacePlanner routing, drawing and protected controls without network/model calls."""
import os
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
os.environ['JARVIS_DATA'] = tempfile.mkdtemp(prefix='jv_planner_')
from core import tools
from core.skills import browser, holo

ORIGINAL_CTX=browser._ctx

class PlannerTests(unittest.TestCase):
    def setUp(self):
        self.page = Mock(url='https://spaceplanner.co/editor')
        self.page.is_closed.return_value = False
        self.ctx = SimpleNamespace(pages=[self.page], new_page=Mock())
        self.patches = [patch.object(browser, '_call', side_effect=lambda fn,*a,**kw:fn(*a)),
                        patch.object(browser, '_ctx', return_value=self.ctx),
                        patch.object(browser, '_page', return_value=self.page),
                        patch.object(browser, '_read', return_value={'adres':self.page.url})]
        for p in self.patches: p.start(); self.addCleanup(p.stop)
        self.old = dict(browser._state)
        browser._state['page'] = self.page
        self.addCleanup(lambda: browser._state.update(self.old))

    def test_reuse_preserves_plan(self):
        self.assertEqual(holo.home_design('4x3 oda')['sayfa']['adres'],self.page.url)
        self.page.goto.assert_not_called(); self.ctx.new_page.assert_not_called()
        self.page.bring_to_front.assert_called_once()

    def test_live_frame_does_not_launch_or_reload_and_blocks_other_tabs(self):
        browser._state['ctx']=self.ctx
        self.page.screenshot.return_value=b'jpeg'
        frame=browser.spaceplanner_frame()
        self.assertTrue(frame['active']);self.assertTrue(frame['image'].startswith('data:image/jpeg;base64,'))
        self.page.goto.assert_not_called();self.ctx.new_page.assert_not_called()
        self.page.url='https://example.com/private'
        self.assertFalse(browser.spaceplanner_frame()['active'])
        self.assertEqual(self.page.screenshot.call_count,1)
        browser._state['ctx']=None
        self.assertFalse(browser.spaceplanner_frame()['active'])

    def test_open_marks_embedded_and_returns_ui(self):
        result=browser.spaceplanner_open()
        self.assertTrue(browser._state['embedded'])
        self.assertEqual(result['ui'],'spaceplanner')

    def test_embedded_launch_requires_regular_chrome_without_edge_fallback(self):
        from playwright import sync_api
        from core import chrome_session
        original=dict(browser._state)
        try:
            browser._state.update(ctx=None,page=None,pw=None,embedded=True)
            with patch.object(browser,'_ctx',wraps=ORIGINAL_CTX),patch.object(sync_api,'sync_playwright'),patch.object(chrome_session,'launch',side_effect=RuntimeError('Chrome missing')) as launch:
                with patch.dict(os.environ,{'JARVIS_BROWSER_HEADLESS':''}):
                    with self.assertRaisesRegex(RuntimeError,'Chrome missing'):
                        browser._ctx()
                launch.assert_called_once()
        finally:
            browser._state.clear();browser._state.update(original)

    def test_precise_room_drag(self):
        browser.spaceplanner_draw([{'x':200,'y':200},{'x':500,'y':400}],size='400x300')
        self.page.mouse.down.assert_called_once(); self.page.mouse.up.assert_called_once()
        self.page.keyboard.type.assert_called_once_with('400x300')
        self.page.keyboard.press.assert_called_once_with('Enter')

    def test_release_mouse_on_failure(self):
        self.page.keyboard.type.side_effect=RuntimeError('typing failed')
        with self.assertRaises(RuntimeError):
            browser.spaceplanner_draw([{'x':200,'y':200},{'x':500,'y':400}],size='400x300')
        self.page.mouse.up.assert_called_once()

    def test_reject_noncanvas_and_other_sites(self):
        self.page.evaluate.return_value=False
        with self.assertRaises(ValueError): browser.spaceplanner_draw([{'x':1,'y':1}],action='click')
        self.page.url='https://spaceplanner.co.evil.example/editor'
        with self.assertRaises(ValueError): browser.spaceplanner_draw([{'x':1,'y':1}],action='click')
        self.page.mouse.click.assert_not_called()

    def test_controls_require_approval(self):
        with patch.object(browser, '_label_of', return_value='Export PDF'):
            self.assertTrue(browser._click_crit({'target':'10'}))
        with patch.object(browser, '_label_of', return_value='Room'):
            self.assertFalse(browser._click_crit({'target':'10'}))
        self.assertTrue(browser._fill_crit({'field':'10','value':'x','submit':True}))

    def test_frame_endpoint_is_not_cached_and_requires_remote_token(self):
        from starlette.testclient import TestClient
        from core import server
        with patch.object(browser,'spaceplanner_frame',return_value={'active':False}) as frame:
            with TestClient(server.app) as client:
                response=client.get('/api/spaceplanner/frame')
                self.assertEqual(response.status_code,200)
                self.assertEqual(response.headers['cache-control'],'no-store')
            frame.reset_mock()
            with patch.object(server,'TOKEN','test-secret'),TestClient(server.app,client=('198.51.100.2',1234)) as remote:
                self.assertEqual(remote.get('/api/spaceplanner/frame').status_code,401)
            frame.assert_not_called()

    def test_windows_app_uses_chrome_and_never_default_browser(self):
        import run
        with patch.object(run.sys,'platform','win32'),patch.object(run.time,'sleep'),patch.object(run.shutil,'which',return_value='C:/Chrome/chrome.exe'),patch.object(Path,'is_file',return_value=True),patch.object(run.subprocess,'Popen') as launch,patch.object(run.webbrowser,'open') as fallback:
            run.open_window('http://127.0.0.1:8765')
            self.assertEqual(launch.call_args.args[0][0],'C:/Chrome/chrome.exe')
            self.assertIn('--app=http://127.0.0.1:8765',launch.call_args.args[0])
            self.assertNotIn('shell',launch.call_args.kwargs)
            fallback.assert_not_called()
        with patch.object(run.sys,'platform','win32'),patch.object(run.time,'sleep'),patch.object(run.shutil,'which',return_value=None),patch.object(Path,'is_file',return_value=False),patch.object(run.webbrowser,'open') as fallback,patch('builtins.print'):
            run.open_window('http://127.0.0.1:8765')
            fallback.assert_not_called()

    def test_routing(self):
        for text in ['SpacePlanner aç', 'ev tasarımı', '4 metre oda çiz', 'kapı ekle']:
            self.assertIn('browser', tools.pick_groups(text))
        self.assertIn('spaceplanner_draw', tools.TOOLS)

if __name__=='__main__': unittest.main()
