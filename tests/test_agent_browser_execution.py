"""Real browser + native Gemini HTTP fixture: prose markers cannot replace opening a page."""
import json
import os
import sys
import tempfile
import threading
from http.server import BaseHTTPRequestHandler,ThreadingHTTPServer
from pathlib import Path
from unittest.mock import patch
from contextlib import ExitStack
sys.path.insert(0,str(Path(__file__).resolve().parent.parent))
os.environ['JARVIS_DATA']=tempfile.mkdtemp(prefix='jv_agent_browser_')
from core import brain,llm,gemini_native
from core.skills import browser
from playwright.sync_api import sync_playwright
seen=[];attempts=0
class Gemini(BaseHTTPRequestHandler):
    def log_message(self,*args):pass
    def do_POST(self):
        global attempts
        body=json.loads(self.rfile.read(int(self.headers['Content-Length'])));seen.append(body)
        answered=any('functionResponse' in part for turn in body['contents'] for part in turn['parts'])
        if body.get('tools') and not answered:
            attempts+=1
            if attempts==1:parts=[{'text':'Başlıyorum.[spaceplanner_open] [browser_look]'}]
            else:parts=[{'functionCall':{'name':'spaceplanner_open','args':{}},'thoughtSignature':'SIGNED'}]
        else:parts=[{'text':'SpacePlanner editörü gerçek tarayıcıda açık.'}]
        self.send_response(200);self.end_headers();self.wfile.write(json.dumps({'candidates':[{'content':{'role':'model','parts':parts}}]}).encode())
server=ThreadingHTTPServer(('127.0.0.1',0),Gemini);threading.Thread(target=server.serve_forever,daemon=True).start()
old=dict(browser._state)
def start_browser():
    pw=sync_playwright().start();b=pw.chromium.launch(headless=True);ctx=b.new_context();page=ctx.new_page()
    ctx.route('https://spaceplanner.co/**',lambda r:r.fulfill(content_type='text/html',body='<title>SpacePlanner fixture</title><h1>Editor ready</h1><button>Start Drawing</button>'))
    browser._state.update(ctx=ctx,page=page,pw=pw)
    browser._state['test_browser']=b
    return True

def close_browser():
    b=browser._state.pop('test_browser',None)
    if b:b.close()
    if browser._state['pw']:browser._state['pw'].stop()

try:
    browser._call(start_browser)
    with ExitStack() as stack:
        for p in [patch.object(gemini_native,'ROOT',f'http://127.0.0.1:{server.server_port}/v1beta'),patch.object(llm,'configured',side_effect=lambda pid:pid=='gemini'),patch.object(llm,'allowed',return_value=True),patch.object(llm,'_key',return_value='test-key'),patch.object(llm,'key_bad',return_value=''),patch.object(llm,'report_bad_key',return_value=False),patch.object(llm,'pick_model_for_tier',return_value='gemini-test-a'),patch.object(llm,'ranked_models_for_tier',return_value=['gemini-test-a','gemini-test-b']),patch.object(llm,'next_model_for_tier',side_effect=lambda pid,m,u,t:'gemini-test-b' if m.endswith('-a') else '')]:stack.enter_context(p)
        events=list(brain.chat('JARVIS, SpacePlanner aç',groups_override={'browser'}))
    active=browser._call(lambda:{'url':browser._state['page'].url,'buttons':browser._state['page'].get_by_role('button',name='Start Drawing').count()})
    assert active['url']=='https://spaceplanner.co/'
    assert active['buttons']==1
    assert any(e['type']=='tool' and e['name']=='spaceplanner_open' and e['status']=='done' for e in events)
    assert all('[spaceplanner_open]' not in e.get('text','') for e in events if e['type']=='token')
    assert seen[0]['toolConfig']['functionCallingConfig']['mode']=='ANY'
    assert seen[1]['toolConfig']['functionCallingConfig']['mode']=='ANY'
    assert any('inline_data' in part for req in seen for turn in req['contents'] for part in turn['parts'])
    assert events[-1]['outcome']=='finished'
    print('Native HTTP + real Chromium: rejected fake bracket reply, opened actual controlled page and analyzed screenshot.')
finally:
    try:browser._call(close_browser)
    finally:browser._state.clear();browser._state.update(old);server.shutdown();server.server_close()
