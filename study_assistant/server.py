"""本地学习 MCP：向量检索、资料导航和学习笔记归档。"""
from pathlib import Path
import hashlib
import os
import json
from mcp.server.fastmcp import FastMCP
from vector_store import search

mcp = FastMCP('course-library')
BASE = Path(__file__).parent
ROOT = BASE / 'materials'
SCOPE = json.loads(os.getenv('STUDY_SOURCE_SCOPE', '[]'))

@mcp.tool()
def list_materials() -> list[dict]:
    """列出已上传资料的 source 标识、标题和段落数量，整理大纲前先调用。"""
    return [{'source':p.name, 'title':p.read_text().split('\n')[0].lstrip('# '),
             'paragraphs':len(p.read_text().split('\n\n'))} for p in sorted(ROOT.glob('*.md')) if not SCOPE or p.name in SCOPE]

@mcp.tool()
def search_materials(query: str, source: str = '') -> list[dict]:
    """中文语义向量检索。可按 source 限定资料；返回原文、段落和余弦距离，距离不是可信度。"""
    return search(query, source, SCOPE)

@mcp.tool()
def read_material(source: str, start_paragraph: int = 1, count: int = 3) -> dict:
    """按检索返回的 source 读取原文段落，核对引用或阅读上下文；一次最多五段。"""
    if Path(source).name != source or not source.endswith('.md'):
        raise ValueError('无效资料标识')
    if SCOPE and source not in SCOPE:
        raise ValueError('资料不在当前选择范围内')
    path = ROOT / source
    if not path.is_file():
        raise ValueError('资料不存在')
    if start_paragraph < 1 or not 1 <= count <= 5:
        raise ValueError('段落从1开始，count为1到5')
    parts = path.read_text().split('\n\n')
    return {'source':source, 'paragraphs':[{'paragraph':i+1,'text':parts[i][:5000]}
            for i in range(start_paragraph-1,min(len(parts),start_paragraph-1+count))]}

@mcp.tool()
def save_study_note(title: str, content: str) -> dict:
    """仅当用户明确要求保存时调用。将学习笔记存到本机 exports，不修改课程资料。"""
    if os.getenv('STUDY_ALLOW_SAVE') != '1':
        raise PermissionError('本次任务未授权保存笔记')
    if not title.strip() or not content.strip() or len(content)>50000:
        raise ValueError('标题正文不能为空，正文最多50000字符')
    folder = BASE / 'exports'
    folder.mkdir(exist_ok=True)
    key = hashlib.sha256((title+'\n'+content).encode()).hexdigest()[:20]
    path = folder / f'study-{key}.md'
    path.write_text('# '+title+'\n\n'+content, encoding='utf-8')
    return {'saved':True,'file':path.name}

if __name__ == '__main__':
    mcp.run(transport='stdio')
