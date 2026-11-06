"""Regressions for the screenshot: prose tool markers must never act or finish a task."""
import io
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parent.parent))
os.environ['JARVIS_DATA']=tempfile.mkdtemp(prefix='jv_tool_exec_')
from core import brain,llm,gemini_native

TOOLS=[{'type':'function','function':{'name':'spaceplanner_open','parameters':{'type':'object','properties':{}}}}]
def call(name,**args):return {'id':name,'type':'function','function':{'name':name,'arguments':json.dumps(args)}}

class ExecutionTests(unittest.TestCase):
    def run_brain(self,rounds,text='JARVIS, SpacePlanner aç ve bir oda çiz',history=None,failure=None):
        executed=[];requests=[];iterator=iter(rounds)
        def route(*args,**kwargs):
            requests.append((args,kwargs));row=next(iterator,{'content':'İşlem sonucu alındı.'})
            if row.get('content'):yield ('text',row['content'])
            yield ('final',{'content':row.get('content',''),'tool_calls':row.get('calls',[])})
        def execute(name,args):
            executed.append(name)
            if name==failure:return "Hata: Playwright bulunamadı"
            return json.dumps({'ekran_analizi':'Oda çizimi görünür.'}) if name=='browser_observe' else 'ok'
        with patch.object(brain.llm,'route',side_effect=route),patch.object(brain.tools,'execute',side_effect=execute),patch.object(brain.tools,'is_critical',return_value=False),patch.object(brain.memory,'history',return_value=history or []),patch.object(brain.memory,'add_message'),patch.object(brain,'_estop',return_value=False):
            events=list(brain.chat(text,groups_override={'browser','computer'}))
        return executed,requests,events

    def test_screenshot_markers_are_repaired_not_executed(self):
        executed,requests,events=self.run_brain([
            {'content':'Efendim başlıyorum.[spaceplanner_open] [browser_look]'},
            {'calls':[call('spaceplanner_open')]},
            {'calls':[call('spaceplanner_draw',points=[{'x':100,'y':100},{'x':500,'y':400}],size='400x300')]},
            {'calls':[call('task_report',status='finished',summary='Oda çizimi ekranda doğrulandı.',remaining='')]}])
        self.assertEqual(executed,['spaceplanner_open','browser_observe','spaceplanner_draw','browser_observe'])
        text=''.join(e.get('text','') for e in events if e['type']=='token')
        self.assertNotIn('[spaceplanner_open]',text);self.assertNotIn('başlıyorum',text)
        self.assertTrue(requests[0][1]['require_tools']);self.assertTrue(requests[1][1]['require_tools'])
        self.assertEqual([s['function']['name'] for s in requests[0][0][2]],['spaceplanner_open'])

    def test_persistent_fake_calls_block_with_clear_error(self):
        rows=[{'content':'[spaceplanner_open] [browser_look]'}]*3
        executed,_,events=self.run_brain(rows)
        self.assertEqual(executed,[])
        self.assertEqual(events[-1]['outcome'],'blocked')
        self.assertIn('tamamlanmadı',events[-1]['text'])
        self.assertFalse(any('[spaceplanner_open]' in e.get('text','') for e in events if e['type']=='token'))

    def test_future_promise_after_open_must_continue(self):
        executed,_,_=self.run_brain([{'calls':[call('spaceplanner_open')]},{'content':'Şimdi çizmeye başlıyorum.'},{'calls':[call('spaceplanner_draw',points=[{'x':1,'y':1},{'x':2,'y':2}])]},{'calls':[call('task_report',status='finished',summary='Sonuç doğrulandı.',remaining='')]}])
        self.assertIn('spaceplanner_draw',executed)

    def test_actual_tool_failure_remains_blocked(self):
        executed,_,events=self.run_brain([{'calls':[call('spaceplanner_open')]},{'calls':[call('task_report',status='blocked',summary='Tarayıcı açılamadı. Playwright gerekli.',remaining='Ev çizilmedi.')]}],failure='spaceplanner_open')
        self.assertEqual(events[-1]['outcome'],'blocked')
        self.assertIn('Playwright',events[-1]['text'])

    def test_every_design_turn_requires_real_call_and_report(self):
        _,requests,events=self.run_brain([
            {'calls':[call('spaceplanner_open')]},
            {'calls':[call('browser_click',target='start')]},
            {'calls':[call('spaceplanner_draw',points=[{'x':1,'y':1},{'x':2,'y':2}])]},
            {'calls':[call('task_report',status='paused',summary='Bir oda çizildi.',remaining='Diğer odalar ve mobilyalar.')]}
        ])
        self.assertTrue(all(k.get('require_tools') for _,k in requests))
        self.assertIn('task_report',{s['function']['name'] for s in requests[1][0][2]})
        self.assertEqual(events[-1]['outcome'],'paused')
        self.assertIn('Diğer odalar',events[-1]['text'])

    def test_start_button_is_not_drawing_completion(self):
        executed,_,events=self.run_brain([
            {'calls':[call('spaceplanner_open')]},
            {'calls':[call('browser_click',target='start')]},
            {'calls':[call('task_report',status='finished',summary='Ev bitti.',remaining='')]},
            {'calls':[call('task_report',status='blocked',summary='Çizim tuvali yüklenmedi.',remaining='Ev çizilmedi.')]}
        ])
        self.assertNotIn('spaceplanner_draw',executed)
        self.assertEqual(events[-1]['outcome'],'blocked')
        self.assertNotIn('Ev bitti.',events[-1]['text'])
        self.assertIn('tuvali yüklenmedi',events[-1]['text'])

    def test_successful_action_resets_consecutive_prose_repairs(self):
        executed,_,events=self.run_brain([
            {'content':'[spaceplanner_open]'},
            {'content':'Açıyorum.'},
            {'calls':[call('spaceplanner_open')]},
            {'content':'Çizeceğim.'},
            {'calls':[call('spaceplanner_draw',points=[{'x':1,'y':1},{'x':2,'y':2}])]},
            {'calls':[call('task_report',status='finished',summary='Oda ekranda doğrulandı.',remaining='')]}
        ])
        self.assertIn('spaceplanner_draw',executed)
        self.assertEqual(events[-1]['outcome'],'finished')

    def test_command_example_is_not_forced_to_execute(self):
        executed,requests,events=self.run_brain([{'content':'Örnek: [spaceplanner_open]'}],text='SpacePlanner aç komutunu örnek olarak açıkla')
        self.assertFalse(executed);self.assertNotIn('require_tools',requests[0][1])

    def test_continue_retains_action_contract(self):
        executed,requests,_=self.run_brain([{'calls':[call('browser_read')]},{'calls':[call('spaceplanner_draw',points=[{'x':1,'y':1},{'x':2,'y':2}])]},{'calls':[call('task_report',status='finished',summary='Sonuç doğrulandı.',remaining='')]}],text='devam et',history=[{'role':'user','content':'SpacePlanner aç ve oda çiz'}])
        self.assertTrue(requests[0][1]['require_tools']);self.assertIn('spaceplanner_draw',executed)

    def test_shortcut_and_typo_route(self):
        self.assertTrue(brain._ui_action_requested('ev tasarımı',{'browser'}))
        self.assertTrue(brain._spaceplanner_start('Spacelanner aç'))
        self.assertFalse(brain._ui_action_requested('SpacePlanner açma',{'browser'}))

    def test_gemini_required_sets_any_on_wire(self):
        response=io.BytesIO(json.dumps({'candidates':[{'content':{'parts':[{'functionCall':{'name':'spaceplanner_open','args':{}},'thoughtSignature':'signed'}]}}]}).encode())
        with patch('urllib.request.urlopen',return_value=response) as request:
            events=list(gemini_native.stream('key','gemini-3-test',[{'role':'user','content':'open'}],TOOLS,tool_choice='required'))
        payload=json.loads(request.call_args.args[0].data)
        self.assertEqual(payload['toolConfig']['functionCallingConfig']['mode'],'ANY')
        self.assertEqual(events[-1][1]['tool_calls'][0]['thought_signature'],'signed')

    def route_fixture(self,stream):
        from contextlib import ExitStack
        stack=ExitStack()
        patches=[patch.object(llm,'configured',side_effect=lambda p:p=='gemini'),patch.object(llm,'allowed',return_value=True),patch.object(llm,'key_bad',return_value=''),patch.object(llm,'only_gemini',return_value=True),patch.object(llm,'pick_model_for_tier',return_value='bad'),patch.object(llm,'ranked_models_for_tier',return_value=['bad','good']),patch.object(llm,'next_model_for_tier',side_effect=lambda p,m,u,t:'good' if m=='bad' else ''),patch.object(llm,'report_bad_key',return_value=False),patch.object(llm,'stream_chat',side_effect=stream)]
        for p in patches:stack.enter_context(p)
        return stack

    def test_unsupported_tools_never_downgrade_to_text_only(self):
        seen=[]
        def stream(pid,model,messages,tools=None,**kwargs):
            seen.append((model,tools,kwargs))
            if model=='bad':raise llm.ProviderError(pid,400,'function calls unsupported')
            yield ('final',{'content':'','tool_calls':[call('spaceplanner_open')]})
        with self.route_fixture(stream):events=list(llm.route(['gemini'],[],TOOLS,tier='smart',require_tools=True))
        self.assertEqual(len(seen),2);self.assertTrue(all(x[1] and x[2]['tool_choice']=='required' for x in seen))
        self.assertTrue(events[-1][1]['tool_calls'])

    def test_required_prose_is_rejected_not_streamed(self):
        def stream(*args,**kwargs):
            yield ('text','Başlıyorum [spaceplanner_open]')
            yield ('final',{'content':'Başlıyorum [spaceplanner_open]','tool_calls':[]})
        with self.route_fixture(stream):events=list(llm.route(['gemini'],[],TOOLS,tier='smart',require_tools=True))
        self.assertFalse(any(k=='text' for k,d in events));self.assertEqual(events[-1][0],'error')

if __name__=='__main__':unittest.main()
