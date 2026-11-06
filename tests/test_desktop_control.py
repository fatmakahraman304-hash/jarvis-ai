"""Desktop input and vision coordinate regressions; never touches the real mouse."""
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
os.environ['JARVIS_DATA'] = tempfile.mkdtemp(prefix='jv_desktop_')
from core import tools
from core.skills import computer, control

class DesktopTests(unittest.TestCase):
    def setUp(self):
        self.u32 = Mock()
        self.u32.GetSystemMetrics.side_effect = {76:-1920,77:0,78:3840,79:1080}.get
        self.u32.SetCursorPos.return_value = 1
        def cursor(ptr):
            ptr._obj.x, ptr._obj.y = 0, 0
            return 1
        self.u32.GetCursorPos.side_effect = cursor
        self.patches = [patch.object(computer,'IS_WIN',True),patch.object(computer,'U32',self.u32,create=True),patch.object(computer.time,'sleep')]
        for p in self.patches: p.start(); self.addCleanup(p.stop)
        control.ESTOP.clear(); self.addCleanup(control.ESTOP.clear)

    def test_snapshot_resize_and_negative_origin(self):
        from PIL import Image
        with patch('PIL.ImageGrab.grab',return_value=Image.new('RGB',(3840,2160))):
            img,meta=computer._grab(with_meta=True)
        self.assertTrue(img.startswith(b'\xff\xd8'))
        self.assertEqual(meta,{'scale':2.4,'ox':-1920,'oy':0,'w':1600,'h':900})

    def test_find_uses_own_snapshot(self):
        meta={'w':1600,'h':900,'scale':2.4,'ox':-1920,'oy':0}
        def answer(*args):
            computer._last_shot.update(scale=1,ox=1000,oy=1000)
            return json.dumps({'bulundu':True,'x':400,'y':200})
        with patch.object(computer,'_grab',return_value=(b'image',meta)),patch.object(computer.llm,'vision',side_effect=answer):
            result=computer.screen_find('Başlat')
        self.assertEqual((result['x'],result['y']),(-960,480))

    def test_find_rejects_invalid_model_coordinates(self):
        meta={'w':1600,'h':900,'scale':2.4,'ox':-1920,'oy':0}
        for data in [{'bulundu':True,'x':1700,'y':1},{'bulundu':True,'x':float('nan'),'y':1},{'bulundu':True},{'x':20,'y':20}]:
            with patch.object(computer,'_grab',return_value=(b'image',meta)),patch.object(computer.llm,'vision',return_value=json.dumps(data)):
                self.assertIsInstance(computer.screen_find('x'),str)

    def test_smooth_move_and_bounds(self):
        computer.mouse_move(-100,200,duration=.1)
        self.assertEqual(self.u32.SetCursorPos.call_count,6)
        self.u32.SetCursorPos.assert_called_with(-100,200)
        with self.assertRaises(ValueError): computer.mouse_move(3000,200)
        with self.assertRaises(ValueError): computer.mouse_move(0,0,duration=float('nan'))

    def test_drag_releases_on_stop(self):
        def move(*args):
            if args != (0,0):
                control.ESTOP.set()
            return 1
        self.u32.SetCursorPos.side_effect=move
        with self.assertRaises(RuntimeError): computer.mouse_drag(0,0,100,100)
        flags=[call.args[0] for call in self.u32.mouse_event.call_args_list]
        self.assertEqual(flags,[0x0002,0x0004])

    def test_click_buttons_and_emergency_stop(self):
        computer.mouse_click(0,0,button='middle',double=True)
        self.assertEqual([c.args[0] for c in self.u32.mouse_event.call_args_list],[0x20,0x40,0x20,0x40])
        self.u32.mouse_event.reset_mock(); control.ESTOP.set()
        with self.assertRaises(RuntimeError): computer.mouse_click(0,0)
        self.u32.mouse_event.assert_not_called()

    def test_routing_and_confirmation(self):
        self.assertIn('computer',tools.pick_groups('mosue hareket etsin'))
        self.assertIn('mouse_drag',tools.TOOLS)
        self.assertEqual(computer.screen_info()['x'],-1920)
        with patch.object(computer,'load_settings',return_value={'auto_control':False}):
            self.assertTrue(tools.is_critical('mouse_drag',{}))
        with patch.object(computer,'load_settings',return_value={'auto_control':True}):
            self.assertFalse(tools.is_critical('mouse_drag',{}))

if __name__=='__main__': unittest.main()
