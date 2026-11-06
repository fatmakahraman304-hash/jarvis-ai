"""Strict post-function-call protocol regressions, including provider call IDs."""
import io
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parent.parent))
os.environ['JARVIS_DATA']=tempfile.mkdtemp(prefix='jv_continuation_')
from core import brain,gemini_native,llm,tools

RAW={'role':'model','parts':[{'text':'Internal context','thought':True,'thoughtSignature':'opaque-thought'}, {'text':'Açıyorum.','thoughtSignature':'opaque-text'}, {'functionCall':{'id':'provider-call-17','name':'spaceplanner_open','args':{}},'thoughtSignature':'opaque-call'}]}
DECL=[{'type':'function','function':{'name':'spaceplanner_open','parameters':{'type':'object','properties':{}}}}]

class ContinuationTests(unittest.TestCase):
    def test_call_id_and_entire_signed_content_roundtrip(self):
        with patch('urllib.request.urlopen',return_value=io.BytesIO(json.dumps({'candidates':[{'content':RAW}]}).encode())):
            events=list(gemini_native.stream('test','gemini-3-test',[{'role':'user','content':'open'}],DECL))
        final=events[-1][1];call=final['tool_calls'][0]
        self.assertEqual(call['id'],'provider-call-17');self.assertEqual(call['gemini_call_id'],'provider-call-17')
        messages=[{'role':'user','content':'open'},brain._model_turn(final,final['tool_calls'],{'provider':'gemini','model':'gemini-3-test'}),{'role':'tool','name':'spaceplanner_open','tool_call_id':call['id'],'content':'{"page":"open"}'}]
        _,contents=gemini_native.convert(messages,model='gemini-3-test')
        self.assertEqual(contents[1]['parts'],RAW['parts'])
        response=contents[2]['parts'][0]['functionResponse'];self.assertEqual(response['id'],'provider-call-17')
        self.assertEqual(response['response'],{'page':'open'})
        self.assertNotIn('Internal context',''.join(d for k,d in events if k=='text'))

    def test_model_switch_uses_verified_result_text_not_foreign_signature(self):
        calls=[{'id':'provider-call-17','gemini_call_id':'provider-call-17','function':{'name':'spaceplanner_open','arguments':'{}'}}]
        turn=brain._model_turn({'content':'','gemini_content':RAW},calls,{'provider':'gemini','model':'model-A'})
        _,contents=gemini_native.convert([{'role':'user','content':'open'},turn,{'role':'tool','tool_call_id':calls[0]['id'],'name':'spaceplanner_open','content':'NOT EXECUTED: confirmation pending'}],model='model-B')
        text=json.dumps(contents)
        self.assertNotIn('thoughtSignature',text);self.assertNotIn('functionResponse',text)
        self.assertIn('NOT EXECUTED',text)

    def test_openai_request_does_not_receive_gemini_internal_fields(self):
        messages=[{'role':'user','content':'x'},{'role':'assistant','content':'','tool_provider':'gemini','tool_model':'model-A','gemini_content':RAW,'tool_calls':[{'id':'17','type':'function','thought_signature':'private','gemini_call_id':'17','function':{'name':'spaceplanner_open','arguments':'{}'}}]}]
        with patch.object(llm,'_key',return_value='test'),patch('urllib.request.urlopen',return_value=io.BytesIO(b'data: [DONE]\n')) as request:
            list(llm.stream_chat('openai','test',messages))
        body=json.loads(request.call_args.args[0].data)
        for word in ['gemini_content','tool_provider','tool_model','thought_signature','gemini_call_id']:self.assertNotIn(word,json.dumps(body))

    def test_long_house_command_has_focused_tools_not_all_keyword_groups(self):
        command="JARVIS SpacePlanner aç. 10 metreye 12 metre tek katlı ev tasarla. İki yatak odası, bir salon, ayrı mutfak, bir banyo, koridor, kapı, pencere ve mobilyalar olsun. Her adımda ekranı analiz et."
        full=tools.specs(tools.pick_groups(command));focused=brain._focused_specs(full,set())
        self.assertGreater(len(full),100);self.assertLess(len(focused),25)
        names={s['function']['name'] for s in focused}
        self.assertIn('spaceplanner_draw',names);self.assertIn('enable_tools',names)
        self.assertNotIn('vault_type',names)
        expanded=brain._focused_specs(tools.specs({'core','browser','computer'}),{'computer'})
        self.assertIn('mouse_click',{s['function']['name'] for s in expanded})

    def test_real_error_detail_is_preserved_and_key_is_redacted(self):
        secret='AIza_this_is_a_long_secret_key_12345'
        err=llm.ProviderError('gemini',400,json.dumps({'error':{'message':'FunctionResponse id missing '+secret}}))
        with patch.object(llm,'_key',return_value=secret):detail=llm._error_detail('gemini','model-A',err)
        self.assertIn('HTTP 400',detail);self.assertIn('FunctionResponse id missing',detail);self.assertNotIn(secret,detail)
        self.assertTrue(llm._protocol_error(err))
        self.assertFalse(llm._protocol_error(llm.ProviderError('gemini',400,'function calls unsupported')))

if __name__=='__main__':unittest.main()
