"""按 UTF-8 字节上界分配上下文，保留完整消息，避免字符截断破坏证据。"""
def build_context(history, question, byte_budget=24000):
    current={'role':'user','content':question}
    if len(question.encode('utf-8'))>byte_budget:
        raise ValueError('任务过长，请缩小资料或问题范围')
    remaining=byte_budget-len(question.encode('utf-8'))
    selected=[]
    for message in reversed(history or []):
        if message.get('role') not in ('user','assistant'):continue
        item={'role':message['role'],'content':str(message['content'])}
        size=len(item['content'].encode('utf-8'))
        if size>remaining:break
        selected.insert(0,item);remaining-=size
    return selected+[current]
