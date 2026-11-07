import os,sys,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parent.parent));os.environ['JARVIS_DATA']=tempfile.mkdtemp()
from core.skills import desktop
from core import brain
class TargetTests(unittest.TestCase):
 def tree(self):return {'window':3,'title':'Settings','elements':[{'name':'İleri','role':'Button','automation_id':'next','enabled':True,'rect':[-400,100,100,40]},{'name':'İleri','role':'MenuItem','automation_id':'menu','enabled':True,'rect':[50,20,80,30]}]}
 def test_ambiguity_prevents_click_and_role_resolves_negative_monitor(self):
  with self.assertRaises(ValueError):desktop._resolve(self.tree(),'İleri')
  e,x,y=desktop._resolve(self.tree(),'ileri','Button')
  self.assertEqual((x,y),(-350,120));self.assertEqual(e['automation_id'],'next')
 def test_missing_target_is_not_guessed(self):
  with self.assertRaises(ValueError):desktop._resolve(self.tree(),'Delete')
 def test_nonfinite_geometry_rejected(self):
  tree=self.tree();tree['elements'][0]['rect'][0]=float('nan')
  with self.assertRaises(ValueError):desktop._resolve(tree,'İleri','Button')
 def test_inspection_preserves_source_and_does_not_claim_pixel_vision(self):
  t=self.tree();t.update(snapshot='one',captured_at=0)
  with patch.object(desktop,'_tree',return_value=t):result=desktop.desktop_inspect()
  self.assertEqual(result['source'],'windows-uia')
  self.assertIn('piksel görüntüsü analizi değildir',result['ekran_analizi'])
  self.assertEqual(brain._observer_for('desktop_click_target'),'desktop_inspect')
 def test_sensitive_target_still_classified_from_real_control(self):
  tree=self.tree();tree['elements'][0]['name']='Delete project'
  with patch.object(desktop,'_tree',return_value=tree),patch.object(desktop,'load_settings',return_value={'semantic_desktop_auto':True}):
   self.assertTrue(desktop._critical({'target':'Delete project','role':'Button'}))
if __name__=='__main__':unittest.main()
