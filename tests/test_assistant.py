"""Durable project decisions, task continuation, live reads and bounded initiative."""
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import time
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
os.environ['JARVIS_DATA'] = tempfile.mkdtemp(prefix='jv_assistant_')
from core import assistant as a, brain, memory
from core.skills import control


class AssistantTests(unittest.TestCase):
    def setUp(self):
        for table in ('project_notes','assistant_tasks','task_evidence','initiative_sent','messages','actions'):
            memory._q('DELETE FROM ' + table, commit=True)
        control.ESTOP.clear()

    def test_project_change_replaces_old_decision_and_survives_new_process(self):
        a.project_note('Ev', 'set', 'Mutfak', 'Açık mutfak')
        a.project_note('Ev', 'set', 'Mutfak', 'Ayrı mutfak')
        self.assertEqual(len(a.project_note('Ev')), 1)
        self.assertEqual(a.context('MUTFAK')[0]['value'], 'Ayrı mutfak')
        output = subprocess.check_output([sys.executable, '-c',
            "from core.assistant import project_note;print(project_note('Ev')[0]['value'])"], cwd=ROOT, encoding='utf-8')
        self.assertEqual(output.strip(), 'Ayrı mutfak')
        a.project_note('Ev', 'delete', 'Mutfak')
        self.assertEqual(a.context('mutfak'), [])

    def test_task_evidence_and_session_isolation(self):
        ident = a.start_task('private', 'Salon duvarını çiz')
        a.checkpoint(ident, 'architecture_apply', '{"verified":true}', True)
        a.finish_task(ident, 'paused', 'Kapı henüz eklenmedi')
        self.assertIsNone(a.resume_context('main'))
        row = a.resume_context('private')
        self.assertEqual(row['summary'], 'Kapı henüz eklenmedi')
        self.assertEqual(row['evidence'][0]['tool'], 'architecture_apply')
        self.assertEqual(row['status'], 'paused')

    def test_continue_restores_goal_and_uses_new_architecture_state(self):
        ident = a.start_task('test', '10 metreye 12 metre ev tasarla')
        a.finish_task(ident, 'paused', 'Kapı eksik')
        rounds = iter([
            {'content':'', 'tool_calls':[{'id':'1','function':{'name':'architecture_state','arguments':'{}'}}]},
            {'content':'', 'tool_calls':[{'id':'report','function':{'name':'task_report','arguments':json.dumps({'status':'paused','summary':'Projeyi okudum.','remaining':'Kapı eksik'})}}]},
        ])
        sent = []
        def route(*args, **kwargs):
            sent.append(args[1]); yield 'final', next(rounds)
        with patch.object(brain.llm,'route',side_effect=route), patch.object(brain.tools,'execute',return_value='{"verified":true,"result":{"counts":{"rooms":6}}}'), patch.object(brain,'_estop',return_value=False):
            events = list(brain.chat('devam et',session='test'))
        self.assertTrue(any('Kapı eksik' in m['content'] for m in sent[0]))
        self.assertTrue(any(e.get('name') == 'architecture_state' for e in events))
        self.assertEqual(events[-1]['outcome'], 'paused')
        self.assertEqual(a.resume_context('test')['status'], 'paused')

    def test_live_model_and_semantic_reads_are_never_cached(self):
        for name in ('architecture_state','architecture_apply','desktop_inspect','desktop_target','project_memory','task_journal','screen_region'):
            self.assertIn(name, brain._LIVE_TOOLS)
        self.assertIn('assistant',brain.GUEST_BLOCKED)

    def test_initiative_quiet_hours_guest_recent_activity_stop_and_restart_dedup(self):
        now = time.time()
        ident = a.start_task('main','Ev planı')
        a.finish_task(ident,'paused','Pencere eksik')
        memory._q('UPDATE assistant_tasks SET updated=? WHERE id=?',(now-900,ident),commit=True)
        notices=[]
        def notify(*args):notices.append(args)
        with patch.object(a,'load_settings',return_value={'initiative_enabled':True}), patch.object(a.time,'localtime',return_value=time.struct_time((2026,11,7,12,0,0,5,311,-1))):
            control.ESTOP.set(); a.tick(notify,now); self.assertFalse(notices)
            control.ESTOP.clear()
            memory.add_message('main','user','merhaba')
            a.tick(notify,now); self.assertFalse(notices)
            memory._q('DELETE FROM messages',commit=True)
            a.tick(notify,now); self.assertEqual(len(notices),1)
            a.tick(notify,now+3601); self.assertEqual(len(notices),1)
        memory._q('DELETE FROM initiative_sent',commit=True)
        with patch.object(a,'load_settings',return_value={'guest_mode':True}):a.tick(notify,now)
        self.assertEqual(len(notices),1)
        with patch.object(a,'load_settings',return_value={'initiative_enabled':False}):a.tick(notify,now)
        self.assertEqual(len(notices),1)

    def test_old_related_fact_is_retrieved_beyond_last_sixty(self):
        memory.add_fact('Mutfak ayrı olacak', 'proje')
        for n in range(80):memory.add_fact(f'İlgisiz kayıt {n}')
        prompt=brain._system_prompt({'prompt':'Test'},'web','mutfak')
        self.assertIn('Mutfak ayrı olacak',prompt)


if __name__ == '__main__':unittest.main()
