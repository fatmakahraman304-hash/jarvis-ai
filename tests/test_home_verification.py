"""Device ambiguity and service acknowledgment must not masquerade as state verification."""
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parent.parent))
os.environ['JARVIS_DATA']=tempfile.mkdtemp()
from core.skills import smarthome as h


class HomeTests(unittest.TestCase):
    def state(self, ident='light.oda', name='Oda ışığı', state='off'):
        return {'entity_id':ident,'state':state,'attributes':{'friendly_name':name}}

    def test_duplicate_name_never_controls_arbitrary_first_device(self):
        devices=[self.state(),self.state('light.oda2')]
        with patch.object(h,'_ha',return_value=devices) as ha:
            with self.assertRaises(ValueError):h.home_control('oda ışığı','on')
        self.assertFalse(any(c.args[0].startswith('services/') for c in ha.call_args_list))

    def test_service_acknowledgment_is_followed_by_device_state(self):
        def api(path,method='GET',body=None):
            if path=='states':return [self.state()]
            if path.startswith('services/'):return []
            return self.state(state='on')
        with patch.object(h,'_ha',side_effect=api):result=h.home_control('light.oda','on')
        self.assertTrue(result['verified'])

    def test_failed_state_change_is_reported_unverified_without_retrying_command(self):
        def api(path,method='GET',body=None):return [self.state()] if path=='states' else self.state()
        with patch.object(h,'_ha',side_effect=api) as ha,patch.object(h.time,'sleep'):
            result=h.home_control('light.oda','on')
        self.assertFalse(result['verified']);self.assertTrue(result['command_sent'])
        self.assertEqual(sum(c.args[0].startswith('services/') for c in ha.call_args_list),1)

    def test_offline_and_nonfinite_values_do_not_send_commands(self):
        with patch.object(h,'_ha',return_value=[self.state(state='unavailable')]):
            with self.assertRaises(RuntimeError):h.home_control('light.oda','on')
        for value in ('nan','inf','-1','101'):
            with patch.object(h,'_ha',return_value=[self.state()]) as ha:
                with self.assertRaises(ValueError):h.home_control('light.oda','brightness',value)
                self.assertFalse(any(c.args[0].startswith('services/') for c in ha.call_args_list))


if __name__=='__main__':unittest.main()
