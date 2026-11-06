"""Manual Google/SpacePlanner handoff without account credentials or model access."""
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch
sys.path.insert(0,str(Path(__file__).resolve().parent.parent))
os.environ['JARVIS_DATA']=tempfile.mkdtemp(prefix='jv_manual_')
from core import brain, chrome_session, tools
from core.skills import browser

class ManualTests(unittest.TestCase):
    def setUp(self):
        self.old=dict(browser._state)
        self.page=Mock(url='https://spaceplanner.co/editor')
        self.page.is_closed.return_value=False
        self.page.evaluate.return_value=False
        self.ctx=Mock(pages=[self.page])
        browser._state.update(ctx=self.ctx,page=self.page,manual_capable=True,manual=False)
        self.worker=patch.object(browser,'_call',side_effect=lambda f,*a,**kw:f(*a));self.worker.start()
    def tearDown(self):
        self.worker.stop();browser._state.clear();browser._state.update(self.old)

    def test_handoff_masks_frames_blocks_all_tools_and_returns_same_plan(self):
        with patch.object(browser,'_window_state') as window:
            self.assertTrue(browser.spaceplanner_manual('start')['manual'])
            frame=browser.spaceplanner_frame()
            self.assertNotIn('image',frame);self.assertTrue(frame['manual'])
            with self.assertRaisesRegex(RuntimeError,'elle kullanımda'):browser._ctx()
            self.assertIn('duraklatıldı',tools.execute('screen_look',{}))
            self.assertIn('duraklatıldı',tools.execute('browser_close',{}))
            self.page.screenshot.assert_not_called()
            self.assertFalse(browser.spaceplanner_manual('finish')['manual'])
            self.assertIs(browser._state['page'],self.page)
            self.page.goto.assert_not_called();self.ctx.new_page.assert_not_called()
            self.assertEqual([c.args[1] for c in window.call_args_list],['normal','minimized'])

    def test_google_popup_must_be_finished_before_automation_resumes(self):
        popup=Mock(url='https://accounts.google.com/signin');popup.is_closed.return_value=False
        self.ctx.pages=[self.page,popup]
        browser._state['manual']=True
        with patch.object(browser,'_window_state'),self.assertRaisesRegex(RuntimeError,'Google giriş penceresi'):
            browser.spaceplanner_manual('finish')
        self.assertTrue(browser.manual_active());self.page.screenshot.assert_not_called()

    def test_filled_password_form_cannot_be_given_to_model(self):
        browser._state['manual']=True
        self.page.evaluate.return_value=True
        with patch.object(browser,'_window_state'),self.assertRaisesRegex(RuntimeError,'şifre alanı'):
            browser.spaceplanner_manual('finish')
        self.assertTrue(browser.manual_active());self.page.screenshot.assert_not_called()

    def test_failure_to_show_does_not_leave_manual_lock(self):
        with patch.object(browser,'_window_state',side_effect=RuntimeError('window gone')):
            with self.assertRaisesRegex(RuntimeError,'window gone'):browser.spaceplanner_manual('start')
        self.assertFalse(browser.manual_active());self.assertFalse(browser._manual_lock.locked())

    def test_brain_pauses_before_model_request(self):
        browser._state['manual']=True
        with patch.object(brain.llm,'route') as route,patch.object(brain.memory,'history',return_value=[]),patch.object(brain.memory,'add_message'):
            events=list(brain.chat('SpacePlanner aç ve oda çiz',groups_override={'browser'}))
        self.assertEqual(events[-1]['outcome'],'paused');route.assert_not_called()

    def test_control_endpoint_only_accepts_same_origin_json(self):
        from starlette.testclient import TestClient
        from core import server
        with TestClient(server.app) as client,patch.object(browser,'spaceplanner_manual',return_value={'manual':True}) as manual:
            self.assertEqual(client.post('/api/spaceplanner/manual',json={'action':'start'},headers={'Origin':'https://other.example'}).status_code,403)
            self.assertEqual(client.post('/api/spaceplanner/manual',data={'action':'start'}).status_code,415)
            manual.assert_not_called()
            response=client.post('/api/spaceplanner/manual',json={'action':'start'})
            self.assertEqual(response.status_code,200);self.assertEqual(response.headers['cache-control'],'no-store')
            manual.assert_called_once_with('start')

    def test_normal_chrome_has_dedicated_profile_and_loopback_debugging(self):
        pw=Mock();pw.chromium.connect_over_cdp.return_value.contexts=[self.ctx]
        process=Mock();process.poll.return_value=None
        response=Mock();response.__enter__=Mock(return_value=Mock(status=200));response.__exit__=Mock(return_value=False)
        opener=Mock();opener.open.return_value=response
        with patch.object(chrome_session,'executable',return_value='/chrome'),patch.object(chrome_session.subprocess,'Popen',return_value=process) as launch,patch.object(chrome_session.urllib.request,'build_opener',return_value=opener),patch.dict(os.environ,{'JARVIS_BROWSER_HEADLESS':''}):
            chrome_session.launch(pw,Path(tempfile.mkdtemp()))
        args=launch.call_args.args[0]
        self.assertIn('--remote-debugging-address=127.0.0.1',args)
        self.assertTrue(any(s.startswith('--user-data-dir=') for s in args))
        self.assertNotIn('--enable-automation',args);self.assertNotIn('--headless=new',args)
        self.assertTrue(pw.chromium.connect_over_cdp.call_args.args[0].startswith('http://127.0.0.1:'))
        chrome_session._processes.remove(process)

if __name__=='__main__':unittest.main()
