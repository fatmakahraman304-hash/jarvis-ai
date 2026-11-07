"""Real tool calls and bounded recovery; native architecture uses acknowledged state."""
import io,json,os,sys,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parent.parent));os.environ['JARVIS_DATA']=tempfile.mkdtemp()
from core import brain,llm,gemini_native
TOOLS=[{'type':'function','function':{'name':'browser_open','parameters':{'type':'object','properties':{}}}}]
def call(name,**args):return {'id':name,'type':'function','function':{'name':name,'arguments':json.dumps(args)}}
class ExecutionTests(unittest.TestCase):
    def test_architecture_native_call_is_used_without_screen_or_browser(self):
        requests=[];executed=[];rounds=iter([{'content':'','tool_calls':[call('architecture_house',width=10,depth=12)]},{'content':'','tool_calls':[call('task_report',status='finished',summary='Altı oda bölgesi, kapılar ve mobilyalar modelde doğrulandı.',remaining='')]}])
        def route(*args,**kw):
            requests.append((args,kw));result=next(rounds);yield ('final',result)
        def execute(name,args):
            executed.append(name);return json.dumps({'ui':'architecture','verified':True,'result':{'counts':{'rooms':6}}})
        with patch.object(llm,'route',side_effect=route),patch.object(brain.tools,'execute',side_effect=execute),patch.object(brain.memory,'history',return_value=[]),patch.object(brain.memory,'add_message'),patch.object(brain,'_estop',return_value=False):
            events=list(brain.chat('10 metreye 12 metre ev tasarla'))
        self.assertEqual(executed,['architecture_house']);self.assertEqual(events[-1]['outcome'],'finished')
        self.assertTrue(requests[0][1]['require_tools'])
        self.assertIn('architecture_house',{s['function']['name'] for s in requests[0][0][2]})
        self.assertLessEqual(len(requests[0][0][2]),24)

    def test_native_gemini_keeps_provider_id_and_signed_parts(self):
        raw={'role':'model','parts':[{'functionCall':{'id':'provider-17','name':'browser_open','args':{}},'thoughtSignature':'signed'}]}
        with patch('urllib.request.urlopen',return_value=io.BytesIO(json.dumps({'candidates':[{'content':raw}]}).encode())):
            events=list(gemini_native.stream('test','gemini-3-test',[{'role':'user','content':'open'}],TOOLS,tool_choice='required'))
        final=events[-1][1];calls=final['tool_calls'];turn=brain._model_turn(final,calls,{'provider':'gemini','model':'gemini-3-test'})
        _,content=gemini_native.convert([{'role':'user','content':'open'},turn,{'role':'tool','tool_call_id':calls[0]['id'],'name':'browser_open','content':'ok'}],model='gemini-3-test')
        self.assertEqual(content[1]['parts'],raw['parts']);self.assertEqual(content[2]['parts'][0]['functionResponse']['id'],'provider-17')

    def route_fixture(self,stream):
        from contextlib import ExitStack
        stack=ExitStack()
        patches=[patch.dict(llm._cooldown, {}, clear=True),patch.object(llm,'configured',side_effect=lambda p:p=='gemini'),patch.object(llm,'allowed',return_value=True),patch.object(llm,'key_bad',return_value=''),patch.object(llm,'only_gemini',return_value=True),patch.object(llm,'pick_model_for_tier',return_value='bad'),patch.object(llm,'ranked_models_for_tier',return_value=['bad','good']),patch.object(llm,'next_model_for_tier',side_effect=lambda p,m,u,t:'good' if m=='bad' else ''),patch.object(llm,'report_bad_key',return_value=False),patch.object(llm,'stream_chat',side_effect=stream)]
        for p in patches:stack.enter_context(p)
        return stack

    def test_unsupported_tools_never_downgrade_to_text_only(self):
        seen=[]
        def stream(pid,model,messages,tools=None,**kwargs):
            seen.append((model,tools,kwargs))
            if model=='bad':raise llm.ProviderError(pid,400,'function calls unsupported')
            yield ('final',{'content':'','tool_calls':[call('browser_open')]})
        with self.route_fixture(stream):events=list(llm.route(['gemini'],[],TOOLS,tier='smart',require_tools=True))
        self.assertEqual(len(seen),2);self.assertTrue(all(x[1] and x[2]['tool_choice']=='required' for x in seen))
        self.assertTrue(events[-1][1]['tool_calls'])

    def test_required_prose_is_rejected_not_streamed(self):
        def stream(*args,**kwargs):
            yield ('text','Başlıyorum [browser_open]')
            yield ('final',{'content':'Başlıyorum [browser_open]','tool_calls':[]})
        with self.route_fixture(stream):events=list(llm.route(['gemini'],[],TOOLS,tier='smart',require_tools=True))
        self.assertFalse(any(k=='text' for k,d in events));self.assertEqual(events[-1][0],'error')

if __name__=='__main__':unittest.main()
