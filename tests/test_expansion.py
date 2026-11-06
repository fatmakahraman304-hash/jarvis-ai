"""Focused tests for the v4.6.36 feature package; no paid services or hardware."""
import io
import json
import os
import sqlite3
import sys
import tempfile
import types
import unittest
import urllib.error
import wave
from pathlib import Path
from unittest.mock import Mock,patch
sys.path.insert(0,str(Path(__file__).resolve().parent.parent))
os.environ['JARVIS_DATA']=tempfile.mkdtemp(prefix='jv_expansion_')
from core import tools,llm,offline_stt
from core.skills import architecture as a, engineering as e, integrations as i, operations as o, reasoning as r, media


def doc():return {'units':'m','rooms':[{'id':'salon','name':'Salon','points':[[0,0],[4,0],[4,3],[0,3]]}],'furniture':[]}

class ExpansionTests(unittest.TestCase):
    def test_symbolic_roots_and_residuals(self):
        result=e.math_solve('x^2=4')
        self.assertEqual({x['x'] for x in result['solutions']},{'2','-2'})
        self.assertTrue(all(x==['0'] for x in result['residuals']))
        result=e.math_solve('x+y=5;x-y=1','x,y')
        self.assertEqual(result['solutions'],[{'x':'3','y':'2'}])
    def test_math_rejects_code(self):
        for text in ["__import__('os').system('echo x')",'x.__class__','[x for x in range(2)]']:
            with self.assertRaises((ValueError,SyntaxError)):e.math_solve(text)
    def test_numeric_result_check(self):
        self.assertTrue(e.math_verify('x^2','{"x":3}','9')['verified'])
        self.assertFalse(e.math_verify('x^2','{"x":3}','8')['verified'])
    def test_linear_optimization(self):
        result=e.linear_optimize({'c':[-1,-1],'A_ub':[[1,1],[1,0],[0,1]],'b_ub':[4,2,3]})
        self.assertTrue(result['success']);self.assertAlmostEqual(result['objective'],-4)
    def test_area_and_cost(self):
        result=a.analyze_plan(doc(),{'floor_m2':100})
        self.assertEqual(result['quantities']['floor_m2'],12)
        self.assertEqual(result['total_cost'],1200)
    def test_collisions_and_outside(self):
        d=doc();d['furniture']=[{'id':'s','kind':'sofa','room':'salon','x':0,'y':0},{'id':'t','kind':'table','room':'salon','x':1,'y':0},{'id':'b','kind':'bed_double','room':'salon','x':3.5,'y':2}]
        result=a.analyze_plan(d);self.assertIn(['s','t'],result['collisions']);self.assertIn('b',result['outside_room'])
    def test_polygon_validation(self):
        d=doc();d['rooms'][0]['points']=[[0,0],[4,3],[4,0],[0,3]]
        with self.assertRaises(ValueError):a.validate(d)
        with self.assertRaises(ValueError):a.plan_project('load','../outside')
    def test_revision_history_and_exports(self):
        d=doc();first=a.plan_project('save','test',d);d['rooms'][0]['name']='Changed';second=a.plan_project('save','test',d)
        self.assertEqual((first['revision'],second['revision']),(1,2));self.assertEqual(a.plan_project('load','test',revision=1)['document']['rooms'][0]['name'],'Salon')
        for format in ['svg','json','dxf','obj']:
            path=Path(a.plan_export('test',format)['path']);self.assertTrue(path.is_file());self.assertGreater(path.stat().st_size,10)
        old_export=Path(a.plan_export('test','json',revision=1)['path'])
        self.assertEqual(json.loads(old_export.read_text())['rooms'][0]['name'],'Salon')
        self.assertEqual(a.plan_project('history','test'),[1,2])
    def test_alternatives_preserve_area(self):
        result=a.plan_alternatives(8,6,3)
        for d in result['alternatives']:self.assertAlmostEqual(a.analyze_plan(d)['quantities']['floor_m2'],48)
    def test_database_read_only_and_quoted_table(self):
        path=Path(tempfile.mkdtemp())/'test.db'
        with sqlite3.connect(path) as db:db.execute('CREATE TABLE "odd table"(id INTEGER)');db.execute('INSERT INTO "odd table" VALUES (7)')
        self.assertEqual(o.database_inspect(str(path),'odd table')['rows'],[[7]])
        with self.assertRaises(ValueError):o.database_inspect(str(path),'odd table; DROP TABLE x')
    def test_source_audit_reports_without_source_code(self):
        path=Path(tempfile.mkdtemp())/'sample.py';path.write_text('eval(user_input)\n')
        result=o.source_audit(str(path));self.assertEqual(result['findings'][0]['line'],1);self.assertNotIn('user_input',json.dumps(result))
    def test_energy_arithmetic(self):
        result=o.energy_analysis([{'timestamp':0,'watts':1000},{'timestamp':3600,'watts':1000}],2)
        self.assertEqual(result['kwh'],1);self.assertEqual(result['cost'],2)
    def test_docker_argv_and_approval(self):
        with patch.object(i,'_run',return_value='started') as run:self.assertEqual(i.docker_manage('start','my-container'),'started');run.assert_called_with(['docker','start','my-container'])
        with self.assertRaises(ValueError):i.docker_manage('start','x;whoami')
        self.assertTrue(tools.is_critical('docker_manage',{'action':'stop'}));self.assertFalse(tools.is_critical('docker_manage',{'action':'list'}))
        self.assertTrue(tools.is_critical('mqtt_message',{'action':'publish'}))
    def test_provider_registration_and_headers(self):
        self.assertEqual(llm.PROVIDERS['openai']['key_env'],'OPENAI_API_KEY');self.assertEqual(llm.PROVIDERS['anthropic']['key_env'],'ANTHROPIC_API_KEY')
        with patch.object(llm,'_key',return_value='test-key'):
            self.assertEqual(llm._headers('anthropic')['x-api-key'],'test-key')
    def test_provider_stream_request_contract(self):
        for pid in ['openai','anthropic']:
            data=b'data: {"choices":[{"delta":{"content":"hello"}}]}\n\ndata: [DONE]\n'
            with patch.object(llm,'_key',return_value='test'),patch('urllib.request.urlopen',return_value=io.BytesIO(data)) as request:
                result=list(llm.stream_chat(pid,'test-model',[{'role':'user','content':'hi'}]))
            self.assertIn(('text','hello'),result)
            req=request.call_args.args[0]
            self.assertTrue(req.full_url.endswith('/chat/completions'))
            self.assertNotIn('temperature',json.loads(req.data))
    def test_model_comparison_keeps_provider_identity(self):
        def stream(pid,*args,**kwargs):yield ('text',pid+' answer')
        with patch.object(llm,'allowed',return_value=True),patch.object(llm,'configured',return_value=True),patch.object(llm,'pick_model',return_value='model'),patch.object(llm,'stream_chat',side_effect=stream):
            result=r.model_compare('test','gemini,openai')
        self.assertEqual([x['provider'] for x in result['responses']],['gemini','openai'])
    def test_offline_mode_never_falls_back_to_cloud(self):
        with patch('core.config.load_settings',return_value={'stt_engine':'vosk'}),patch.object(offline_stt,'transcribe',side_effect=RuntimeError('missing model')),patch.object(media,'transcribe_gemini') as cloud:
            with self.assertRaises(RuntimeError):media.transcribe_bytes(b'wav',mime='audio/wav')
            cloud.assert_not_called()
    def test_offline_wav_contract(self):
        folder=Path(tempfile.mkdtemp());(folder/'am').mkdir();data=io.BytesIO()
        with wave.open(data,'wb') as w:w.setnchannels(1);w.setsampwidth(2);w.setframerate(16000);w.writeframes(b'\0\0'*4000)
        fake=Mock();fake.KaldiRecognizer.return_value.AcceptWaveform.return_value=False;fake.KaldiRecognizer.return_value.FinalResult.return_value='{"text":"jarvis merhaba"}'
        with patch.dict(sys.modules,{'vosk':fake}),patch.object(offline_stt,'env',return_value=str(folder)):
            self.assertEqual(offline_stt.transcribe(data.getvalue()),'jarvis merhaba')
    def test_feature_tools_registered(self):
        for name in ['math_solve','linear_optimize','analyze_plan','plan_project','model_compare','browser_upload','browser_download','mqtt_message','database_inspect','runtime_diagnostics']:
            self.assertIn(name,tools.TOOLS)
    def test_architecture_api_roundtrip(self):
        from starlette.testclient import TestClient
        from core.server import app
        client=TestClient(app)
        try:
            saved=client.post('/api/architecture',json={'action':'save','project_id':'api_test','document':doc()})
            self.assertEqual(saved.status_code,200)
            loaded=client.post('/api/architecture',json={'action':'load','project_id':'api_test'}).json()
            self.assertEqual(loaded['revision'],1)
            self.assertEqual(client.post('/api/architecture',json=[]).status_code,400)
            status=client.get('/api/features').json()
            self.assertEqual(status['actual_listed_count'],len(status['features']))
            self.assertTrue(any(x['status']=='pending' for x in status['features']))
        finally:client.close()
    def test_mqtt_publish_waits_for_ack(self):
        seen=[]
        class Client:
            def __init__(self,*args):pass
            def connect(self,host,port,keepalive):seen.append(('connect',host,port))
            def loop_start(self):self.on_connect(self,None,None,0,None)
            def publish(self,topic,payload,qos,retain):
                seen.append(('publish',topic,payload,qos,retain));self.on_publish(self,None,1,types.SimpleNamespace(is_failure=False),None)
            def disconnect(self):seen.append(('disconnect',))
            def loop_stop(self):pass
        paho=types.ModuleType('paho');mqtt=types.ModuleType('paho.mqtt');client=types.ModuleType('paho.mqtt.client')
        client.Client=Client;client.CallbackAPIVersion=types.SimpleNamespace(VERSION2=2);paho.mqtt=mqtt;mqtt.client=client
        modules={'paho':paho,'paho.mqtt':mqtt,'paho.mqtt.client':client}
        values={'MQTT_HOST':'localhost','MQTT_PORT':'1883'}
        with patch.dict(sys.modules,modules),patch.object(i,'env',side_effect=lambda k,d='':values.get(k,d)):
            self.assertTrue(i.mqtt_message('publish','test/topic','hello')['published'])
        self.assertIn(('publish','test/topic','hello',1,False),seen);self.assertIn(('disconnect',),seen)
    def test_real_process_diagnostics(self):
        self.assertGreater(i.runtime_diagnostics()['current']['rss_bytes'],0)
    def test_update_network_retry_is_bounded(self):
        from core import updater
        with patch('urllib.request.urlopen',side_effect=[urllib.error.URLError('network'),io.BytesIO(b'zip')]) as request,patch.object(updater.time,'sleep'),patch.object(updater,'_log'):
            self.assertEqual(updater._get('https://example.invalid'),'zip'.encode());self.assertEqual(request.call_count,2)
        error=urllib.error.HTTPError('url',404,'missing',{},io.BytesIO())
        with patch('urllib.request.urlopen',side_effect=error) as request:
            with self.assertRaises(urllib.error.HTTPError):updater._get('https://example.invalid')
            self.assertEqual(request.call_count,1)
    def test_update_package_retry_only_for_transient_errors(self):
        from core import updater
        bad=types.SimpleNamespace(returncode=1,stderr='connection reset',stdout='')
        good=types.SimpleNamespace(returncode=0,stderr='',stdout='')
        with patch.object(updater.subprocess,'run',side_effect=[bad,good]) as run,patch.object(updater.time,'sleep'),patch.object(updater,'_log'):
            updater._pip(['package'],[]);self.assertEqual(run.call_count,2);self.assertEqual(run.call_args.kwargs['timeout'],180)
        bad.stderr='No matching distribution found'
        with patch.object(updater.subprocess,'run',return_value=bad) as run:
            with self.assertRaises(RuntimeError):updater._pip(['package'],[])
            self.assertEqual(run.call_count,1)

if __name__=='__main__':unittest.main()
