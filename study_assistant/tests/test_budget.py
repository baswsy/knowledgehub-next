import unittest
from types import SimpleNamespace
from langchain_core.messages import HumanMessage,AIMessage,SystemMessage,ToolMessage
from langchain.agents.middleware.types import ModelResponse
from budget import Budget,Limits
class Request(SimpleNamespace):
    def override(self,**kwargs):return Request(**{**vars(self),**kwargs})
class BudgetTests(unittest.IsolatedAsyncioTestCase):
    def request(self,messages=None):return Request(messages=messages or [HumanMessage('问题')],tools=[],system_message=SystemMessage('规则'),model_settings={})
    async def test_usage_and_output_cap(self):
        b=Budget(Limits());r=self.request()
        async def handler(req):
            self.assertEqual(req.model_settings['max_tokens'],1500)
            return ModelResponse([AIMessage('答案',usage_metadata={'input_tokens':100,'output_tokens':20,'total_tokens':120})])
        await b.middleware().awrap_model_call(r,handler)
        self.assertEqual(b.tokens,120);self.assertEqual(b.calls,1)
    async def test_no_spend_over_limit(self):
        b=Budget(Limits(total=1))
        async def handler(req):self.fail('must not call provider')
        response=await b.middleware().awrap_model_call(self.request(),handler)
        self.assertTrue(b.stopped);self.assertIn('停止',response.result[0].content)
    async def test_closing_removes_tools(self):
        b=Budget(Limits(calls=1))
        async def handler(req):
            self.assertEqual(req.tools,[]);self.assertIn('预算即将耗尽',req.system_message.content)
            return ModelResponse([AIMessage('总结')])
        await b.middleware().awrap_model_call(self.request(),handler)
        self.assertTrue(b.estimated)
    async def test_compaction_preserves_tool_pairs(self):
        b=Budget(Limits(context=4000,output=200,margin=100))
        messages=[HumanMessage('旧'*3000),AIMessage('旧答'),HumanMessage('新问题'),AIMessage('',tool_calls=[{'id':'a','name':'read','args':{}}]),ToolMessage('证据',tool_call_id='a')]
        async def handler(req):
            self.assertEqual(len(req.messages),3);self.assertEqual(req.messages[-1].tool_call_id,'a')
            return ModelResponse([AIMessage('答案')])
        await b.middleware().awrap_model_call(self.request(messages),handler)
    async def test_cost_blocks_call(self):
        b=Budget(Limits(input_price=1,output_price=2,cost=0.000001))
        async def handler(req):self.fail('cost exceeded')
        await b.middleware().awrap_model_call(self.request(),handler)
        self.assertTrue(b.stopped)
