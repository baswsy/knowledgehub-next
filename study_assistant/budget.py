"""每轮模型预算。无对应分词器时用UTF-8字节作保守代理，不标记为实际Token。"""
import json
import os
from dataclasses import dataclass, asdict
from langchain.agents.middleware import wrap_model_call
from langchain.agents.middleware.types import ModelResponse
from langchain_core.messages import AIMessage, SystemMessage
from langchain_core.utils.function_calling import convert_to_openai_tool

@dataclass
class Limits:
    context: int = 32000
    output: int = 1500
    margin: int = 2000
    calls: int = 6
    total: int = 100000
    input_price: float | None = None
    output_price: float | None = None
    cost: float | None = None

    @classmethod
    def from_env(cls):
        keys={'context':'CONTEXT','output':'OUTPUT','margin':'MARGIN','calls':'CALLS','total':'TOTAL'}
        values={k:int(os.getenv('STUDY_BUDGET_'+v,str(getattr(cls(),k)))) for k,v in keys.items()}
        for k,v in {'input_price':'INPUT_PRICE','output_price':'OUTPUT_PRICE','cost':'COST'}.items():
            raw=os.getenv('STUDY_BUDGET_'+v)
            values[k]=float(raw) if raw else None
        result=cls(**values)
        if min(result.context,result.output,result.calls,result.total)<=0 or result.margin<0:raise ValueError('预算配置必须为正数')
        if result.context<=result.output+result.margin:raise ValueError('上下文预算不足')
        if any(x is not None and x<0 for x in (result.input_price,result.output_price,result.cost)):raise ValueError('价格和费用不可为负')
        if result.cost is not None and (result.input_price is None or result.output_price is None):raise ValueError('费用上限需要同时配置输入和输出单价')
        return result

class Budget:
    def __init__(self, limits=None, emit=lambda e:None):
        self.limits=limits or Limits.from_env();self.emit=emit
        self.calls=0;self.tokens=0;self.cost=0.;self.estimated=False;self.stopped=False

    def snapshot(self):
        return dict(limits=asdict(self.limits),calls=self.calls,accounted_tokens=self.tokens,
                    cost=self.cost if self.limits.input_price is not None and self.limits.output_price is not None else None,
                    has_estimates=self.estimated,stopped=self.stopped,
                    counting='UTF-8 bytes plus framing allowance; not exact tokenizer')

    def count(self,messages,system,tools):
        payload=[m.model_dump(mode='json') for m in messages]
        schema=[convert_to_openai_tool(t) for t in tools]
        return len(json.dumps({'messages':payload,'system':system.content if system else '', 'tools':schema},ensure_ascii=False,default=str).encode('utf-8'))+512

    def price(self,inp,out):
        l=self.limits
        if l.input_price is None or l.output_price is None:return None
        return (inp*l.input_price+out*l.output_price)/1_000_000

    def middleware(self):
        @wrap_model_call
        async def guard(request,handler):
            l=self.limits;messages=list(request.messages);tools=list(request.tools);system=request.system_message
            # Remove whole earlier user turns, keeping current question and all tool-call/result pairs intact.
            while self.count(messages,system,tools)>l.context-l.output-l.margin:
                users=[i for i,m in enumerate(messages) if m.type=='human']
                if len(users)<2:break
                messages=messages[users[1]:]
            inp=self.count(messages,system,tools)
            closing=self.calls>=l.calls-1 or self.tokens+2*(inp+l.output)>l.total
            if l.cost is not None:
                closing |= self.cost + 2 * (self.price(inp,l.output) or 0) > l.cost
            if closing:
                tools=[]
                system=SystemMessage(content=(system.content if system else '')+'\n预算即将耗尽。停止调用工具，用已有证据总结已完成内容、引用和未完成项。')
                inp=self.count(messages,system,tools)
            projected=self.price(inp,l.output)
            reason=None
            if inp+l.output+l.margin>l.context:reason='上下文容量不足，请缩小资料或问题范围'
            elif self.calls>=l.calls:reason='模型调用次数已达上限'
            elif self.tokens+inp+l.output>l.total:reason='任务累计Token预算不足'
            elif l.cost is not None and self.cost+(projected or 0)>l.cost:reason='任务费用预算不足'
            if reason:
                self.stopped=True;self.emit({'stage':'budget_stopped','reason':reason,'budget':self.snapshot()})
                return ModelResponse(result=[AIMessage(content=f'本次任务已停止：{reason}。已收到的工具证据保留在执行记录中；尚未完成综合分析。可缩小任务范围后继续。')])
            self.calls+=1
            self.emit({'stage':'budget_before_call','input_estimate':inp,'closing':closing,'budget':self.snapshot()})
            try:
                response=await handler(request.override(messages=messages,tools=tools,system_message=system,
                    model_settings={**request.model_settings,'max_tokens':l.output}))
            except BaseException:
                # Transport failure may still be billed. Reserve the entire attempted request.
                self.tokens+=inp+l.output;self.cost+=projected or 0;self.estimated=True
                self.emit({'stage':'budget_failed_call','budget':self.snapshot()});raise
            usages=[m.usage_metadata for m in response.result if getattr(m,'usage_metadata',None)]
            actual_in=sum(u['input_tokens'] for u in usages) if usages else inp
            actual_out=sum(u['output_tokens'] for u in usages) if usages else l.output
            self.tokens+=actual_in+actual_out
            # Full input rate is a conservative estimate when cache discounts exist.
            self.cost+=self.price(actual_in,actual_out) or 0
            self.estimated |= not bool(usages)
            if closing:
                response.result=[AIMessage(content=m.content or '本次预算内未生成总结，请查看执行记录并缩小任务。',usage_metadata=getattr(m,'usage_metadata',None)) if isinstance(m,AIMessage) else m for m in response.result]
            self.emit({'stage':'budget_after_call','usage_source':'provider' if usages else 'estimate','budget':self.snapshot()})
            return response
        return guard
