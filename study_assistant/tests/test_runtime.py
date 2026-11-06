import unittest
import tempfile
from pathlib import Path
from unittest.mock import patch
import context
import storage
import server

class RuntimeTests(unittest.TestCase):
    def test_context_keeps_current_and_contiguous_recent_history(self):
        history=[{'role':'user','content':'旧'*20},{'role':'assistant','content':'新'}]
        self.assertEqual(context.build_context(history,'问题',byte_budget=12),[history[-1],{'role':'user','content':'问题'}])
        with self.assertRaises(ValueError):context.build_context([], '长'*20, byte_budget=10)

    def test_memory_update_delete(self):
        with tempfile.TemporaryDirectory() as tmp, patch.object(storage,'BASE',Path(tmp)):
            self.assertEqual(storage.learning_memory(),'')
            storage.learning_memory('准备考试')
            self.assertEqual(storage.learning_memory(),'准备考试')
            storage.learning_memory('')
            self.assertEqual(storage.learning_memory(),'')

    def test_save_requires_authorization_and_is_idempotent(self):
        with tempfile.TemporaryDirectory() as tmp, patch.object(server,'BASE',Path(tmp)):
            with patch.dict('os.environ',{'STUDY_ALLOW_SAVE':'0'}):
                with self.assertRaises(PermissionError):server.save_study_note('标题','正文')
            self.assertFalse((Path(tmp)/'exports').exists())
            with patch.dict('os.environ',{'STUDY_ALLOW_SAVE':'1'}):
                a=server.save_study_note('标题','正文');b=server.save_study_note('标题','正文')
                self.assertEqual(a,b)
                self.assertEqual(len(list((Path(tmp)/'exports').glob('*'))),1)

if __name__=='__main__':unittest.main()

class FailureTests(unittest.IsolatedAsyncioTestCase):
    async def test_tool_failure_preserves_partial_trace(self):
        import agent
        class Client:
            async def get_tools(self):return []
        class BrokenAgent:
            async def astream(self,*args,**kwargs):
                yield {'tools':{'messages':[]}}
                raise RuntimeError('injected failure')
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);(root/'skills').mkdir();(root/'skills/study-coach.md').write_text('规则')
            with patch.object(agent,'ROOT',root), patch.object(agent,'client',return_value=Client()), patch.object(agent,'make_model',return_value=None), patch.object(agent,'create_agent',return_value=BrokenAgent()):
                with self.assertRaises(RuntimeError):await agent.run('问题')
            import json
            trace=json.loads(next((root/'runs').glob('run-*.json')).read_text())
            self.assertEqual(trace['status'],'failed')
            self.assertEqual(trace['error_type'],'RuntimeError')
            self.assertTrue(trace['events'])
