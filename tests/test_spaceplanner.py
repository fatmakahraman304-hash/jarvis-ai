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

    def test_routing(self):
        for text in ['SpacePlanner aç', 'ev tasarımı', '4 metre oda çiz', 'kapı ekle']:
            self.assertIn('browser', tools.pick_groups(text))
        self.assertIn('spaceplanner_draw', tools.TOOLS)

if __name__=='__main__': unittest.main()
