"""Agent observe/act sequencing using scripted model responses and tool results."""
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parent.parent))
os.environ['JARVIS_DATA']=tempfile.mkdtemp(prefix='jv_observe_')
from core import brain

def call(name, **args):
    return {'id':name+str(args),'type':'function','function':{'name':name,'arguments':json.dumps(args)}}

class ObserveTests(unittest.TestCase):
    def run_chat(self, rounds):
        executed=[]; sent=[]
        def execute(name,args):
            executed.append(name)
            if name=='browser_observe': return json.dumps({'ekran_analizi':'fresh-'+str(executed.count(name))})
            if name=='screen_look': return 'fresh-desktop-'+str(executed.count(name))
            if name=='browser_read': return 'read-'+str(executed.count(name))
            return json.dumps({'ui':'spaceplanner'}) if name=='home_design' else 'ok'
        iterator=iter(rounds)
        def route(*args,**kwargs):
            sent.append(json.loads(json.dumps(args[1])))
            calls=next(iterator,[])
            if not calls: yield ('text','tamam')
            yield ('final',{'content':'' if calls else 'tamam','tool_calls':calls})
        with patch.object(brain.llm,'route',side_effect=route),patch.object(brain.tools,'execute',side_effect=execute),patch.object(brain.tools,'is_critical',return_value=False),patch.object(brain.memory,'history',return_value=[]),patch.object(brain.memory,'add_message'),patch.object(brain,'_estop',return_value=False):
            events=list(brain.chat('SpacePlanner aç ve ekranı analiz ederek devam et',groups_override={'browser','computer'}))
        return executed,sent,events

    def test_each_action_gets_fresh_observation_and_batch_is_deferred(self):
        executed,sent,events=self.run_chat([
            [call('browser_open',url='https://spaceplanner.co'),call('browser_click',target='old-id')],
            [call('browser_read'),call('browser_read')],
            [call('browser_click',target='7')],[]])
        self.assertEqual(executed,['browser_open','browser_observe','browser_read','browser_read','browser_click','browser_observe'])
        tools=[m['content'] for m in sent[-1] if m['role']=='tool']
        self.assertTrue(any('YAPILMADI' in t for t in tools))
        self.assertTrue(any('read-2' in t for t in tools))
        self.assertTrue(any('fresh-2' in t for t in tools))

    def test_desktop_is_observed_before_first_action_and_after_it(self):
        executed,_,_=self.run_chat([[call('mouse_move',x=5,y=6)],[call('mouse_move',x=5,y=6)],[]])
        self.assertEqual(executed,['screen_look','mouse_move','screen_look'])

    def test_browser_click_requires_initial_observation(self):
        executed,_,_=self.run_chat([[call('browser_click',target='7')],[call('browser_click',target='8')],[]])
        self.assertEqual(executed,['browser_observe','browser_click','browser_observe'])

    def test_ui_payload_survives_observation(self):
        with patch.object(brain.tools,'execute',return_value='new screenshot'):
            payload=json.loads(brain._with_observation('{"ui":"spaceplanner"}','screen_look'))
        self.assertEqual(payload['ui'],'spaceplanner')
        self.assertEqual(payload['güncel_gözlem'],'new screenshot')

    def test_pending_preserves_original_goal(self):
        pid=brain._new_pending('mouse_click',{'x':1,'y':2},'jarvis','test','web',task='SpacePlanner aç')
        try:self.assertEqual(brain._pending[pid]['task'],'SpacePlanner aç')
        finally:brain._pending.pop(pid,None)

    def test_approved_action_observes_and_resumes_goal(self):
        pid=brain._new_pending('browser_click',{'target':'7'},'jarvis','test','web',task='Oda çiz')
        notes=[];executed=[]
        def execute(name,args):
            executed.append(name)
            return 'fresh observation' if name=='browser_observe' else 'clicked'
        def chat(note,*args,**kwargs):
            notes.append(note)
            yield {'type':'done','text':'continued'}
        with patch.object(brain.tools,'execute',side_effect=execute),patch.object(brain,'chat',side_effect=chat),patch.object(brain,'_estop',return_value=False):
            list(brain.resolve(pid,True))
        self.assertEqual(executed,['browser_click','browser_observe'])
        self.assertIn('Oda çiz',notes[0]);self.assertIn('fresh observation',notes[0])

if __name__=='__main__': unittest.main()
