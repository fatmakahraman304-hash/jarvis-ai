"""Blocking telemetry/provider work must not stall unrelated async requests."""
import asyncio,json,os,sys,tempfile,threading,unittest
from pathlib import Path
from unittest.mock import patch
from types import SimpleNamespace
sys.path.insert(0,str(Path(__file__).resolve().parent.parent))
os.environ['JARVIS_DATA']=tempfile.mkdtemp(prefix='jv_responsive_')
from core import server

class ResponsiveTests(unittest.IsolatedAsyncioTestCase):
 async def test_render_style_api_validates_before_queueing(self):
  from core import architecture
  async def body(style):return {'op':'render_style','args':{'style':style}}
  with patch.object(architecture,'command',return_value={'verified':True,'result':{'render_style':'design'}}) as command:
   for invalid in ['ultra',None,[],{}]:
    request=SimpleNamespace(path_params={'what':'run'},method='POST',headers={},json=lambda:body(invalid))
    self.assertEqual((await server.architecture_api(request)).status_code,400)
   command.assert_not_called()
   request=SimpleNamespace(path_params={'what':'run'},method='POST',headers={},json=lambda:body('design'))
   self.assertEqual((await server.architecture_api(request)).status_code,200)
   command.assert_called_once_with('render_style',style='design')
 async def check_worker(self,handler,target,result,request=None):
  loop=asyncio.get_running_loop();started=asyncio.Event();release=threading.Event();active=threading.Event()
  def blocking(*args,**kwargs):
   active.set();loop.call_soon_threadsafe(started.set)
   try:release.wait(2);return result
   finally:active.clear()
  with patch(target,side_effect=blocking):
   task=asyncio.create_task(handler(request))
   try:
    await asyncio.wait_for(started.wait(),3)
    self.assertTrue(active.is_set(),'Blocking work held the ASGI loop until completion')
    # A separate request handler is able to complete while discovery is waiting.
    health=await server.manifest(SimpleNamespace())
    self.assertEqual(health.status_code,200)
   finally:
    release.set()
    response=await task
  return response
 async def test_system_sampling_does_not_block_requests(self):
  response=await self.check_worker(server.system,'core.tools.system_status',{'cpu_yüzde':12})
  self.assertEqual(json.loads(response.body),{'cpu_yüzde':12})
 async def test_process_sampling_does_not_block_requests(self):
  request=SimpleNamespace(query_params={'by':'cpu'})
  response=await self.check_worker(server.processes,'core.tools.top_processes',[{'pid':1}],request)
  self.assertEqual(json.loads(response.body),[{'pid':1}])
 async def test_model_discovery_does_not_block_requests(self):
  request=SimpleNamespace(path_params={'pid':'gemini'},query_params={})
  with patch.object(server.llm,'configured',return_value=True),patch.object(server.llm,'ranked_models',return_value=['test']),patch.object(server.llm,'pick_model',return_value='test'),patch.object(server.llm,'cooling',return_value=0):
   response=await self.check_worker(server.models,'core.llm.list_models',['test'],request)
  self.assertEqual(json.loads(response.body)['models'],['test'])

if __name__=='__main__':unittest.main()
