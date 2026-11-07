"""Never mutate a plan after observation failure or manufacture progress text."""
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parent.parent))
os.environ['JARVIS_DATA']=tempfile.mkdtemp(prefix='jv_pause_')
from core import brain,llm

def call(name):
    return {'id':name,'function':{'name':name,'arguments':'{}'}}

class PauseTests(unittest.TestCase):
    def run_agent(self,rounds,fail_at=1):
        executed=[];requests=[];observations=0;iterator=iter(rounds)
        def route(*args,**kwargs):
            requests.append(True)
            yield ('final',{'content':'Devam ediyorum.','tool_calls':[call(x) for x in next(iterator,[])]})
        def execute(name,args):
            nonlocal observations
            executed.append(name)
            if name=='browser_observe':
                observations+=1
                return 'Hata: Görüntü analizi yapılamadı. gemini/test: 429' if observations==fail_at else json.dumps({'ekran_analizi':'fresh visible plan'})
            return 'ok'
        with patch.object(brain.llm,'route',side_effect=route),patch.object(brain.tools,'execute',side_effect=execute),patch.object(brain.tools,'is_critical',return_value=False),patch.object(brain.memory,'history',return_value=[]),patch.object(brain.memory,'add_message'),patch.object(brain,'_estop',return_value=False):
            events=list(brain.chat('Chrome aç ve düğmeye tıkla',groups_override={'browser'}))
        return executed,requests,events

    def test_open_failure_prevents_all_later_draws_and_summary_model(self):
        executed,requests,events=self.run_agent([['browser_open'],['browser_click']])
        self.assertEqual(executed,['browser_open','browser_observe'])
        self.assertEqual(len(requests),1)
        self.assertEqual(events[-1]['outcome'],'paused')
        self.assertIn('429',events[-1]['text']);self.assertNotIn('Devam ediyorum',events[-1]['text'])

    def test_after_one_draw_no_second_draw_even_in_same_batch(self):
        executed,requests,events=self.run_agent([['browser_open'],['browser_click','browser_click'],['browser_click']],fail_at=2)
        self.assertEqual(executed,['browser_open','browser_observe','browser_click','browser_observe'])
        self.assertEqual(len(requests),2);self.assertEqual(events[-1]['outcome'],'paused')
        self.assertIn('otomatik tekrarlanmadı',events[-1]['text'])

    def test_failed_initial_observation_does_not_execute_requested_edit(self):
        executed,_,events=self.run_agent([['browser_click'],['browser_click']])
        self.assertEqual(executed,['browser_observe'])
        self.assertIn('Yeni çizim/fare işlemi yapılmadı',events[-1]['text'])

    def test_nested_or_empty_analysis_is_not_success(self):
        for observation in ['',{}, {'error':'quota'}, {'ekran_analizi':'Hata: quota'}, {'ekran_analizi':''}]:
            self.assertFalse(brain._observation_ready(json.dumps({'güncel_gözlem':observation})))
        self.assertTrue(brain._observation_ready(json.dumps({'güncel_gözlem':{'ekran_analizi':'visible room'}})))

    def test_approved_action_also_pauses_without_resuming_model(self):
        pid=brain._new_pending('browser_click',{'target':'1'},'jarvis','test','web',task='Oda çiz')
        with patch.object(brain.tools,'execute',side_effect=['ok','Hata: vision 429']),patch.object(brain,'chat') as resume,patch.object(brain.memory,'add_message'),patch.object(brain,'_estop',return_value=False):
            events=list(brain.resolve(pid,True))
        resume.assert_not_called();self.assertEqual(events[-1]['outcome'],'paused')

    def test_vision_skips_pinned_model_on_cooldown(self):
        seen=[]
        def stream(pid,model,*a,**kw):
            seen.append(model);yield ('text','fresh screen')
        with patch.object(llm,'VISION_ORDER',['gemini']),patch.object(llm,'configured',return_value=True),patch.object(llm,'allowed',return_value=True),patch.object(llm,'key_bad',return_value=''),patch.object(llm,'env',return_value='cooled'),patch.object(llm,'cooling',side_effect=lambda p,m:m=='cooled'),patch.object(llm,'next_model_for_tier',return_value='ready'),patch.object(llm,'stream_chat',side_effect=stream):
            self.assertEqual(llm.vision('screen',b'jpg'),'fresh screen')
        self.assertEqual(seen,['ready'])

if __name__=='__main__':unittest.main()
