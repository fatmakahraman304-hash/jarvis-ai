import io,json,os,sys,tempfile,threading,time,unittest,zipfile
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent.parent))
os.environ['JARVIS_DATA']=tempfile.mkdtemp(prefix='jv_arch_')
from core import architecture as a,tools,brain
class WorkspaceTests(unittest.TestCase):
 def test_model_operations_have_complete_room_door_window_layout(self):
  ops=a.house_operations(10,12,2,1)
  self.assertEqual(len([o for o in ops if o['kind']=='room']),6)
  self.assertGreaterEqual(len([o for o in ops if o['kind']=='wall']),9)
  self.assertEqual(len([o for o in ops if o.get('name')=='window']),5)
  self.assertEqual(len([o for o in ops if o.get('name')=='door']),6)
  self.assertTrue(any(o.get('name')=='Koridor' for o in ops))
 def test_compact_house_counts_corridor_as_a_room(self):
  ops=a.house_operations(8,9,1,1)
  self.assertEqual(len([o for o in ops if o['kind']=='room']),5)
 def test_impossible_or_nonfinite_dimensions_rejected(self):
  for width in [float('nan'),float('inf'),-2,4]:
   with self.assertRaises(ValueError):a.house_operations(width,12)
  for count in [1.5,float('nan'),float('inf')]:
   with self.assertRaises(ValueError):a.house_operations(10,12,count,1)
 def test_tool_catalog_pagination_remains_valid_json_under_output_limit(self):
  from unittest.mock import patch
  from core.skills import architecture as skill
  rows=[{'id':str(i),'name':'Bed '+str(i),'model':True} for i in range(90)]
  with patch.object(skill.workspace,'command',return_value={'ui':'architecture','verified':True,'result':rows}):
   first=skill.architecture_catalog();second=skill.architecture_catalog(offset=20)
  self.assertEqual(len(first['result']['items']),20)
  self.assertEqual(second['result']['items'][0]['id'],'20')
  self.assertEqual(first['result']['pages']['items']['total'],90)
  self.assertLess(len(json.dumps(first,ensure_ascii=False)),8000)
 def test_ack_requires_owner_and_returns_real_editor_result(self):
  result=[]
  t=threading.Thread(target=lambda:result.append(a.command('state')));t.start()
  for _ in range(100):
   job=a.claim('test-client-123').get('job')
   if job:break
   time.sleep(.01)
  with self.assertRaises(ValueError):a.acknowledge('different-client',job['id'],{'counts':{}})
  a.acknowledge('test-client-123',job['id'],{'counts':{'walls':4}});t.join(2)
  self.assertEqual(result[0]['result']['counts']['walls'],4)
 def test_version_conflict_does_not_overwrite_and_previous_project_kept(self):
  b=io.BytesIO()
  with zipfile.ZipFile(b,'w')as z:z.writestr('Home.xml','<home version="7500"/>')
  payload=b.getvalue();before=a.project_info()['revision']
  a.save_project(payload,before,{'counts':{}})
  with self.assertRaises(ValueError):a.save_project(payload,before,{})
  a.save_project(payload,before+1,{})
  self.assertTrue((a.STORE/'history'/f'r{before+1:06}.sh3d').exists())
 def test_history_is_bounded_and_revision_cannot_traverse_files(self):
  b=io.BytesIO()
  with zipfile.ZipFile(b,'w') as z:z.writestr('Home.xml','<home version="7500"/>')
  before=a.project_info()['revision']
  a.save_project(b.getvalue(),before,{})
  a.save_project(b.getvalue(),before+1,{})
  rows=a.project_history()
  self.assertLessEqual(len(rows),50)
  self.assertEqual(rows[0]['revision'],before+1)
  self.assertEqual(a.project_version(before+1).read_bytes(),b.getvalue())
  for bad in ['../current','1/../../current','-1','0',True,'1.5',9999999]:
   with self.assertRaises(ValueError):a.project_version(bad)
 def test_room_words_do_not_hijack_camera_or_smart_home_requests(self):
  for text in ['Mutfak ışığını aç','Salondaki kameraya bak','Kapıyı kilitle','Chrome penceresini aç']:
   self.assertFalse(brain._architecture_requested(text),text)
  for text in ['10 metreye 12 metre ev tasarla','Üst kat ekle','Salona pencere ekle','Mimari editörü aç']:
   self.assertTrue(brain._architecture_requested(text),text)
 def test_editor_package_is_local_and_source_available(self):
  self.assertTrue((a.assets()/'index.html').exists())
  self.assertTrue((a.ROOT/'vendor/designer-source.zip').exists())
 def test_cutaway_patch_and_corresponding_source_are_reproducible(self):
  from core.designer_patch import BUNDLE_PATCHES, SOURCE_PATCHES, patch_source, replace_once
  target=a.assets()
  code=next((target/'assets').glob('index-*.js')).read_text()
  for old,new in BUNDLE_PATCHES:
   self.assertNotIn(old,code)
   self.assertIn(new,code)
  with zipfile.ZipFile(target/'jarvis-source.zip') as source:
   for path,patches in SOURCE_PATCHES.items():
    content=source.read(path).decode()
    for old,new in patches:
     self.assertNotIn(old,content)
     self.assertIn(new,content)
    self.assertEqual(patch_source(path,content),content)
  with self.assertRaises(RuntimeError):replace_once('unexpected','old','new')
 def test_architecture_group_has_native_tools_no_retired_integration(self):
  names={s['function']['name'] for s in tools.specs({'architecture'})}
  self.assertIn('architecture_house',names);self.assertIn('architecture_apply',names)
  self.assertFalse(any('space'+'planner' in n for n in tools.TOOLS))
 def test_render_tool_rejects_unknown_style_before_dispatch(self):
  from core.skills.architecture import architecture_render
  from unittest.mock import patch
  with patch.object(a,'command',return_value={'verified':True,'result':{'render_style':'design'}}) as dispatch:
   self.assertEqual(architecture_render('design')['result']['render_style'],'design')
   dispatch.assert_called_once_with('render_style',style='design')
   with self.assertRaises(ValueError):architecture_render('ultra')
   self.assertEqual(dispatch.call_count,1)
 def test_production_icon_method_reuses_buffer_and_copies_exact_pixels(self):
  import subprocess
  bundle=next((a.assets()/'assets').glob('index-*.js')).read_text()
  subprocess.run(['node',str(a.ROOT/'tests/test_designer_icon.js')],input=bundle,text=True,encoding='utf-8',check=True)
if __name__=='__main__':unittest.main()
