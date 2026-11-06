"""单用户本地 SQLite 存储。资料正文继续保存在 materials 供 MCP 使用。"""
import json
import sqlite3
import uuid
import time
from pathlib import Path
from contextlib import contextmanager

BASE = Path(__file__).parent

@contextmanager
def db():
    (BASE / 'data').mkdir(exist_ok=True)
    conn = sqlite3.connect(BASE / 'data/workspace.sqlite', timeout=20)
    conn.row_factory = sqlite3.Row
    conn.executescript('''
    CREATE TABLE IF NOT EXISTS metadata(source TEXT PRIMARY KEY, domain TEXT, tags TEXT, summary TEXT);
    CREATE TABLE IF NOT EXISTS artifacts(id TEXT PRIMARY KEY, kind TEXT, title TEXT, payload TEXT, created REAL);
    CREATE TABLE IF NOT EXISTS messages(id INTEGER PRIMARY KEY, session TEXT, role TEXT, content TEXT);
    CREATE TABLE IF NOT EXISTS favorites(id TEXT PRIMARY KEY, title TEXT, url TEXT, author TEXT, description TEXT, platform TEXT);
    ''')
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()

def notes():
    with db() as c:
        meta = {r['source']:dict(r) for r in c.execute('SELECT * FROM metadata')}
    result=[]
    for p in sorted((BASE/'materials').glob('*.md'), key=lambda p:p.stat().st_mtime, reverse=True):
        text=p.read_text(encoding='utf-8')
        m=meta.get(p.name,{})
        result.append(dict(source=p.name,title=text.split('\n')[0].lstrip('# ') or p.stem,
                           content=text,domain=m.get('domain') or '未分类',tags=json.loads(m.get('tags') or '[]'),
                           summary=m.get('summary') or '',updated=p.stat().st_mtime))
    return result

def metadata(source,domain,tags,summary=''):
    with db() as c:
        c.execute('INSERT OR REPLACE INTO metadata VALUES(?,?,?,?)',(source,domain,json.dumps(tags,ensure_ascii=False),summary))

def write_note(title,content,domain='未分类',tags=None,source=None):
    if not title.strip() or not content.strip(): raise ValueError('标题和正文不能为空')
    if len(content)>1_000_000: raise ValueError('正文过长')
    source=source or f'note-{uuid.uuid4().hex[:16]}.md'
    if Path(source).name!=source or not source.endswith('.md'): raise ValueError('无效资料标识')
    folder=BASE/'materials'; folder.mkdir(exist_ok=True)
    (folder/source).write_text('# '+title.strip()+'\n\n'+content,encoding='utf-8')
    metadata(source,domain,tags or [])
    return source

def delete_note(source):
    if Path(source).name!=source or not source.endswith('.md'): raise ValueError('无效资料标识')
    # 移到回收目录，避免误删后无法找回。
    p=BASE/'materials'/source
    trash=BASE/'data/trash';trash.mkdir(parents=True,exist_ok=True)
    if p.exists(): p.rename(trash/(str(time.time_ns())+'-'+source))
    with db() as c: c.execute('DELETE FROM metadata WHERE source=?',(source,))

def save_artifact(kind,title,payload):
    key=uuid.uuid4().hex
    with db() as c: c.execute('INSERT INTO artifacts VALUES(?,?,?,?,?)',(key,kind,title,json.dumps(payload,ensure_ascii=False),time.time()))
    return key

def artifacts(kind):
    with db() as c:
        return [dict(r, payload=json.loads(r['payload'])) for r in c.execute('SELECT * FROM artifacts WHERE kind=? ORDER BY created DESC',(kind,))]

def messages(session):
    with db() as c: return [dict(r) for r in c.execute('SELECT role,content FROM messages WHERE session=? ORDER BY id',(session,))]

def add_message(session,role,content):
    with db() as c: c.execute('INSERT INTO messages(session,role,content) VALUES(?,?,?)',(session,role,content))

def sessions():
    with db() as c:
        return [dict(r) for r in c.execute("SELECT session, MIN(content) AS title, MAX(id) AS recent FROM messages WHERE role='user' GROUP BY session ORDER BY recent DESC")]

def favorites():
    with db() as c: return [dict(r) for r in c.execute('SELECT * FROM favorites ORDER BY rowid DESC')]

def save_favorites(rows):
    import hashlib
    count=0
    with db() as c:
        for row in rows:
            title=str(row.get('title') or '').strip();url=str(row.get('url') or '').strip()
            if not title or not url.startswith(('https://','http://')): continue
            key=hashlib.sha256(url.encode()).hexdigest()
            c.execute('INSERT OR REPLACE INTO favorites VALUES(?,?,?,?,?,?)',(key,title,url,str(row.get('author') or ''),str(row.get('description') or '')[:5000],str(row.get('platform') or '其他')))
            count+=1
    return count

def remove_favorite(key):
    with db() as c: c.execute('DELETE FROM favorites WHERE id=?',(key,))


def learning_memory(content=None):
    """仅保存用户手动确认的偏好和目标；空字符串清除记忆。"""
    with db() as c:
        c.execute('CREATE TABLE IF NOT EXISTS learning_memory(id INTEGER PRIMARY KEY, content TEXT)')
        if content is not None:
            if len(content)>2000:raise ValueError('学习记忆最多2000字符')
            c.execute('INSERT OR REPLACE INTO learning_memory VALUES(1,?)',(content,))
        row=c.execute('SELECT content FROM learning_memory WHERE id=1').fetchone()
        return row['content'] if row else ''
