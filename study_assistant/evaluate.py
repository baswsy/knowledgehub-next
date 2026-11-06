"""离线审核运行记录；结果只衡量执行状态，不冒充答案质量评分。"""
import json
import argparse
from pathlib import Path

def evaluate(folder):
    rows=[]
    for path in sorted(Path(folder).glob('run-*.json')):
        data=json.loads(path.read_text())
        events=data.get('events',[])
        final=next((e.get('content','') for e in reversed(events) if e.get('type')=='ai' and not e.get('tool_calls')), '')
        rows.append({'file':path.name,'status':data.get('status','legacy'),
                     'elapsed_seconds':data.get('elapsed_seconds'),
                     'tool_calls':sum(len(e.get('tool_calls',[])) for e in events),
                     'has_final_answer':bool(final),
                     'citation_review':'人工检查引用是否支持结论',
                     'answer_review':'待人工评分'})
    return rows

if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--runs',default=str(Path(__file__).parent/'runs'))
    args=parser.parse_args();print(json.dumps(evaluate(args.runs),ensure_ascii=False,indent=2))
