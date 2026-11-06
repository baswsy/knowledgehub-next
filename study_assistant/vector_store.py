"""持久化 Chroma + 本地中文嵌入；按内容哈希更新索引。"""
from pathlib import Path
import hashlib
import threading
import chromadb
from fastembed import TextEmbedding

BASE = Path(__file__).parent
LOCK = threading.Lock()
_model = None

def model():
    global _model
    if _model is None:
        _model = TextEmbedding('BAAI/bge-small-zh-v1.5', cache_dir=str(BASE / 'data/models'))
    return _model

def collection():
    return chromadb.PersistentClient(path=str(BASE / 'data/chroma')).get_or_create_collection(
        'course_bge_zh_v1', embedding_function=None, metadata={'hnsw:space':'cosine'})

def sync(c):
    records = []
    for path in sorted((BASE / 'materials').glob('*.md')):
        for number, paragraph in enumerate(path.read_text(encoding='utf-8').split('\n\n'), 1):
            for offset in range(0, len(paragraph), 450):
                text = paragraph[offset:offset+500].strip()
                if text:
                    key = hashlib.sha256(f'{path.name}:{number}:{offset}:{text}'.encode()).hexdigest()
                    records.append((key, text, {'source':path.name, 'paragraph':number, 'offset':offset}))
    current = set(c.get()['ids'])
    wanted = {r[0] for r in records}
    new = [r for r in records if r[0] not in current]
    for start in range(0, len(new), 64):
        batch = new[start:start+64]
        vectors = [v.tolist() for v in model().embed([r[1] for r in batch])]
        c.upsert(ids=[r[0] for r in batch], documents=[r[1] for r in batch],
                 metadatas=[r[2] for r in batch], embeddings=vectors)
    if current-wanted:
        c.delete(ids=list(current-wanted))
    return c.count()

def search(query, source='', sources=None):
    if not query.strip():
        return []
    with LOCK:
        c = collection()
        if not sync(c):
            return []
        vector = next(model().query_embed(query)).tolist()
        if sources and source and source not in sources:
            return []
        args = {'where':{'source':source}} if source else ({'where':{'source':{'$in':sources}}} if sources else {})
        result = c.query(query_embeddings=[vector], n_results=min(5,c.count()), **args)
        return [dict(meta, text=text, distance=round(distance,4))
                for meta,text,distance in zip(result['metadatas'][0],result['documents'][0],result['distances'][0])]
