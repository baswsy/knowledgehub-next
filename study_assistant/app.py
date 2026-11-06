import asyncio
import os
import hmac
import json
import uuid
from pathlib import Path
import streamlit as st
from agent import run
from ingestion import save_material
import storage as store

ROOT=Path(__file__).parent
st.set_page_config(page_title='知学 KnowledgeHub',page_icon='📚',layout='wide',initial_sidebar_state='expanded')
# The current workspace is shared single-user storage, so require a deployment password.
if os.getenv('STUDY_DEPLOYED') == '1':
    expected = os.getenv('STUDY_ACCESS_PASSWORD', '')
    if not expected:
        st.error('网站尚未配置访问密码，请设置 STUDY_ACCESS_PASSWORD。')
        st.stop()
    if not st.session_state.get('authenticated'):
        with st.form('login'):
            supplied = st.text_input('网站访问密码', type='password')
            submitted = st.form_submit_button('进入知学')
        if submitted and hmac.compare_digest(supplied.encode(), expected.encode()):
            st.session_state.authenticated = True
            st.rerun()
        elif submitted:
            st.error('密码不正确')
        st.stop()
st.markdown('''<style>
.stApp{background:#f6f8fc;color:#17233c}.block-container{padding-top:2rem;max-width:1440px;padding-bottom:3rem}
[data-testid="stSidebar"]{background:#eef2f9;border-right:1px solid #e1e7f0}
h1{font-size:2.1rem!important;letter-spacing:-.04em}h2{font-size:1.4rem!important}
[data-testid="stMetric"]{background:white;border:1px solid #e5eaf3;border-radius:14px;padding:14px 20px}
[data-testid="stChatMessage"]{background:white;border:1px solid #e5eaf3;border-radius:14px;margin-bottom:12px}
.stButton>button{border-radius:9px}.stTextArea textarea{line-height:1.7}
@media(max-width:700px){.block-container{padding:1rem}h1{font-size:1.6rem!important}}
</style>''',unsafe_allow_html=True)
all_notes=store.notes()
with st.sidebar:
    st.title('📚 知学')
    st.caption('KNOWLEDGE HUB · 本地学习工作台')
    page=st.radio('工作区',['学习对话','资料与笔记','知识大纲','知识图谱','视频收藏','学习记录'],label_visibility='collapsed')
    st.divider()
    st.caption(f'{len(all_notes)} 份资料 · {len(store.favorites())} 条收藏')
    st.caption('DeepSeek Flash · LangChain\n\n本地中文向量检索 · MCP')
    with st.expander('连接与索引'):
        from dotenv import dotenv_values
        config={**dotenv_values(ROOT/'.env'), **os.environ}
        st.caption('模型密钥：'+('已配置' if config.get('DEEPSEEK_API_KEY') or config.get('OPENAI_API_KEY') else '未配置'))
        if st.button('更新向量索引'):
            try:
                from vector_store import collection,sync,LOCK
                with st.spinner('同步资料索引…'):
                    with LOCK: count=sync(collection())
                st.success(f'已索引 {count} 个片段')
            except Exception as exc: st.error(str(exc))
    st.caption('资料与笔记保存在本机。AI 功能会将所用资料发送到配置的模型接口。')


def title(name,description):
    st.title(name);st.caption(description)

def choose_sources(key):
    selected=st.multiselect('选择学习资料',options=[n['source'] for n in all_notes],
        default=[n['source'] for n in all_notes],format_func=lambda s:next(n['title'] for n in all_notes if n['source']==s),key=key)
    return [n for n in all_notes if n['source'] in selected]

def refs(items):
    return ' · '.join(f"[{r['source']}#{r['paragraph']}]" for r in items)

def outline_item(item,depth=0):
    with st.expander(item['title'],expanded=depth==0):
        st.write(item['summary']);st.caption(refs(item['refs']))
        for child in item.get('children',[]): outline_item(child,depth+1)

def final_text(result):
    for e in reversed(result['events']):
        if e.get('type')=='ai' and not e.get('tool_calls'): return e['content'] if isinstance(e['content'],str) else json.dumps(e['content'],ensure_ascii=False)
    raise ValueError('模型没有生成最终回答')

if page=='学习对话':
    title('让资料成为你的知识','理解一个概念，连接已有笔记，再用练习检验掌握程度。')
    cols=st.columns(3)
    for col,label,value in zip(cols,['学习资料','知识成果','视频收藏'],[len(all_notes),len(store.artifacts('graph'))+len(store.artifacts('outline')),len(store.favorites())]): col.metric(label,value)
    st.write('')
    if 'chat_session' not in st.session_state: st.session_state.chat_session=uuid.uuid4().hex
    left,right=st.columns([4,1])
    with left: mode=st.selectbox('学习方式',['理解知识点','制定复习计划','深度研究','分析视频收藏'])
    with right:
        st.write('')
        if st.button('＋ 新对话',use_container_width=True):
            st.session_state.chat_session=uuid.uuid4().hex;st.rerun()
    selected=st.multiselect('限定资料（留空使用全部）',[n['source'] for n in all_notes],format_func=lambda s:next(n['title'] for n in all_notes if n['source']==s))
    allow_save=st.checkbox('允许本次任务保存学习笔记',value=False)
    with st.expander('学习记忆与偏好'):
        memory_text=st.text_area('学习目标与偏好（可编辑或清空）',value=store.learning_memory(),max_chars=2000)
        if st.button('保存学习记忆'):
            store.learning_memory(memory_text)
            st.success('已更新学习记忆')
    session=st.session_state.chat_session
    history=store.messages(session)
    if not history:
        st.info('试试：对比 RAG 与 Agent 的区别，给我一个30分钟学习计划。')
    for m in history:
        with st.chat_message(m['role']):st.markdown(m['content'])
    question=st.chat_input('输入你的学习问题…')
    if question:
        with st.chat_message('user'):st.write(question)
        try:
            task=f'任务类型：{mode}。用户需求：{question}'
            if selected:task+='\n仅使用这些资料（检索时逐个source限定）：'+','.join(selected)
            if mode=='分析视频收藏':
                task+='\n以下仅为视频标题和简介，不是视频正文；只推测主题与观看顺序，不声称提取视频知识：\n'+json.dumps(store.favorites(),ensure_ascii=False)[:24000]
            events=[]
            with st.chat_message('assistant'):
                with st.status('正在检索与整理…',expanded=False) as status:
                    def emit(event):
                        events.append(event)
                        if event.get('tool_calls'):st.write('调用：'+', '.join(t['name'] for t in event['tool_calls']))
                        elif event.get('type')=='tool':st.caption('已收到工具结果')
                    result=asyncio.run(run(task,emit,history=history,deep=mode=='深度研究',sources=selected,allow_save=allow_save,memory=store.learning_memory()))
                    answer=final_text(result)
                    status.update(label=f"已完成 · {result['elapsed_seconds']} 秒",state='complete')
                st.markdown(answer)
            store.add_message(session,'user',question);store.add_message(session,'assistant',answer)
            if result.get('budget'):
                budget_info=result['budget']
                st.caption(f"模型调用 {budget_info['calls']} 次 · 累计记账 {budget_info['accounted_tokens']} Token · 费用 {budget_info['cost'] if budget_info['cost'] is not None else '未配置单价'}")
            st.session_state.last_trace=result
            st.session_state.trace_session=session
        except Exception as exc:st.error(f'本次任务未完成：{exc}')
    if history or question:
        current=store.messages(session)
        text='\n\n'.join(('## 我\n' if m['role']=='user' else '## 知学\n')+m['content'] for m in current)
        st.download_button('导出本次学习对话',text,'学习对话.md')
    if st.session_state.get('last_trace') and st.session_state.get('trace_session')==session:
        with st.expander('查看 Agent 与 MCP 执行记录'):
            st.json(st.session_state.last_trace)
            st.download_button('下载执行记录',json.dumps(st.session_state.last_trace,ensure_ascii=False,indent=2),'trace.json')

elif page=='资料与笔记':
    title('你的个人资料库','上传课程资料，记录想法，用标签把碎片知识连接起来。')
    library,upload,new=st.tabs(['我的资料','上传文件','新建笔记'])
    with upload:
        files=st.file_uploader('拖入学习资料',type=['pdf','docx','txt','md','json','csv'],accept_multiple_files=True)
        auto=st.checkbox('导入后用 AI 提取标签与摘要（需要联网）',value=False)
        st.caption('每份最多10 MB。PDF支持文字版，扫描版需先OCR。JSON/CSV按文本资料导入。')
        if st.button('导入到资料库',type='primary',disabled=not files):
            for f in files:
                try:
                    p=save_material(f.name,f.getvalue(),ROOT/'materials')
                    if auto:
                        from knowledge import analyze
                        note=next(n for n in store.notes() if n['source']==p.name)
                        try:
                            a=analyze(note);store.metadata(p.name,a.domain,a.tags,a.summary)
                        except Exception as exc:st.warning(f'{f.name} 已保存，但AI整理未完成：{exc}')
                    st.success(f'{f.name} 已导入')
                except Exception as exc:st.error(f'{f.name}：{exc}')
            st.button('刷新资料列表',on_click=lambda:None)
    with new:
        with st.form('new_note',clear_on_submit=True):
            nt=st.text_input('笔记标题');nc=st.text_area('笔记正文',height=220)
            nd=st.text_input('知识领域',value='未分类');ng=st.text_input('标签，用逗号分隔')
            if st.form_submit_button('创建笔记',type='primary'):
                try:store.write_note(nt,nc,nd,[t.strip() for t in ng.replace('，',',').split(',') if t.strip()]);st.success('笔记已保存');st.rerun()
                except Exception as exc:st.error(str(exc))
    with library:
        search_col,filter_col=st.columns([3,1])
        query=search_col.text_input('搜索标题、正文或标签',placeholder='输入关键词…')
        domain=filter_col.selectbox('领域',['全部']+sorted({n['domain'] for n in all_notes}))
        filtered=[n for n in all_notes if (domain=='全部' or n['domain']==domain) and query.lower() in (n['title']+n['content']+' '.join(n['tags'])).lower()]
        if not filtered:st.info('暂无匹配资料，可以上传文件或新建笔记。')
        else:
            list_col,detail_col=st.columns([1,2.2])
            with list_col:
                source=st.radio('资料列表',[n['source'] for n in filtered],format_func=lambda s:next(n['title'] for n in filtered if n['source']==s))
            note=next(n for n in filtered if n['source']==source)
            with detail_col:
                st.subheader(note['title']);st.caption(note['domain']+' · '+' · '.join('#'+t for t in note['tags']))
                if note['summary']:st.info(note['summary'])
                preview,edit=st.tabs(['阅读原文','编辑笔记'])
                with preview:
                    st.markdown(note['content'])
                    st.download_button('导出 Markdown',note['content'],note['source'])
                    if st.button('AI 整理标签与摘要'):
                        try:
                            from knowledge import analyze
                            with st.spinner('整理笔记…'):a=analyze(note)
                            store.metadata(source,a.domain,a.tags,a.summary);st.rerun()
                        except Exception as exc:st.error(str(exc))
                with edit:
                    with st.form('edit_'+source):
                        t=st.text_input('标题',note['title']);body=st.text_area('正文',note['content'].split('\n\n',1)[-1],height=280)
                        d=st.text_input('领域',note['domain']);tags=st.text_input('标签',','.join(note['tags']))
                        if st.form_submit_button('保存修改'):
                            try:store.write_note(t,body,d,[x.strip() for x in tags.replace('，',',').split(',') if x.strip()],source);st.rerun()
                            except Exception as exc:st.error(str(exc))
                    if st.checkbox('确认将此资料移入本地回收目录',key='del_'+source):
                        if st.button('移除资料',type='secondary'):store.delete_note(source);st.rerun()

elif page in ['知识大纲','知识图谱']:
    kind='graph' if page=='知识图谱' else 'outline'
    title(page,'从选中的资料中提取知识结构，每个知识点都保留原文出处。')
    selected=choose_sources('sources_'+kind)
    if st.button('生成'+page,type='primary',disabled=not selected):
        try:
            from knowledge import generate
            with st.spinner('阅读资料并构建知识结构…'):payload=generate(kind,selected)
            st.success('已生成并保存到本机')
        except Exception as exc:st.error(f'生成未完成：{exc}')
    saved=store.artifacts(kind)
    if not saved:st.info('选择资料后生成第一份知识成果。无需重复生成，历史版本会自动保存。')
    else:
        item=st.selectbox('历史版本',saved,format_func=lambda x:__import__('datetime').datetime.fromtimestamp(x['created']).strftime('%m-%d %H:%M')+' · '+x['title'])
        payload=item['payload'];data=payload['data']
        if payload.get('truncated'):st.warning('资料超过本次上下文容量，本结果仅覆盖部分原文。请缩小资料范围后生成。')
        stale=set(payload['sources'])-{n['source'] for n in all_notes}
        if stale:st.warning('部分来源已移除，历史结果仍保留，请重新生成以更新引用。')
        if kind=='graph':
            from graph_view import render_graph,graph_svg
            render_graph(data)
            st.download_button('导出 SVG 图谱',graph_svg(data),'知识图谱.svg',mime='image/svg+xml')
            with st.expander('概念与关系证据'):
                for n in data['nodes']:st.write(n['label']+'：'+n['summary']);st.caption(refs(n['refs']))
        else:
            for node in data['items']:outline_item(node)
        st.download_button('导出 JSON',json.dumps(payload,ensure_ascii=False,indent=2),kind+'.json')
        if kind=='outline':
            def lines(items,depth=0):
                return '\n'.join('#'*(depth+1)+' '+i['title']+'\n'+i['summary']+'\n'+refs(i['refs'])+'\n'+lines(i.get('children',[]),depth+1) for i in items)
            st.download_button('导出 Markdown 大纲',lines(data['items']),'知识大纲.md')

elif page=='视频收藏':
    title('把收藏变成学习清单','整理视频标题与简介，建立观看顺序；视频知识需要字幕或笔记支持。')
    local,public=st.tabs(['导入 JSON / CSV','B站公开收藏夹'])
    with local:
        st.caption('CSV字段：title,url,author,description,platform。也支持含 bvid、upper、intro 的B站JSON。')
        f=st.file_uploader('上传收藏列表',type=['json','csv'])
        st.download_button('下载 CSV 模板','title,url,author,description,platform\n示例视频,https://www.bilibili.com/,作者,这里填写简介,B站\n','收藏模板.csv')
        if st.button('导入收藏',disabled=f is None):
            try:
                from favorites import parse_favorites
                rows=parse_favorites(f.name,f.getvalue());count=store.save_favorites(rows)
                st.success(f'已保存 {count} 条有效收藏；相同链接自动去重')
            except Exception as exc:st.error(str(exc))
    with public:
        st.caption('只读取公开元数据，不登录。平台可能限制请求；失败时可使用文件导入。每次最多200条。')
        uid=st.text_input('B站 UID');folder=st.text_input('收藏夹名称')
        if st.button('读取公开收藏夹',disabled=not(uid and folder)):
            try:
                from favorites import fetch_public_bilibili
                with st.spinner('读取公开列表…'):rows=fetch_public_bilibili(uid,folder)
                st.success(f'已保存 {store.save_favorites(rows)} 条收藏')
            except Exception as exc:st.error(str(exc))
    rows=store.favorites()
    q=st.text_input('搜索收藏')
    for row in rows:
        if q.lower() not in (row['title']+row['description']).lower():continue
        with st.container(border=True):
            st.subheader(row['title']);st.caption(row['platform']+' · '+row['author']);st.write(row['description'])
            c1,c2,c3=st.columns(3)
            c1.link_button('打开视频',row['url'])
            if c2.button('加入资料库',key='video_'+row['id']):
                store.write_note(row['title'],'【视频元数据，并非视频正文】\n\n来源：'+row['url']+'\n\n简介：'+row['description'],'视频收藏',[row['platform']],source='video-'+row['id'][:16]+'.md');st.success('已加入资料库，可用于主题整理')
            if c3.button('移除收藏',key='remove_'+row['id']):store.remove_favorite(row['id']);st.rerun()
            with st.expander('读取视频字幕与总结'):
                st.caption('先读取可公开获取的字幕，或上传SRT/VTT/B站字幕JSON；总结覆盖字幕语言内容，不包含画面。')
                subtitle=st.file_uploader('字幕文件',type=['srt','vtt','json'],key='subtitle_'+row['id'])
                transcript_key='transcript_'+row['id']
                if st.button('读取字幕 / 导入字幕',key='read_sub_'+row['id']):
                    try:
                        from video_content import fetch_subtitle,parse_subtitle,render
                        with st.spinner('读取字幕…'):
                            transcript=render(parse_subtitle(subtitle.name,subtitle.getvalue()),row['url'],'用户上传字幕') if subtitle else fetch_subtitle(row['url'])
                            source='transcript-'+row['id'][:16]+'.md'
                            store.write_note(row['title']+' 字幕',transcript,'视频字幕',[row['platform']],source=source)
                            st.session_state[transcript_key]=source
                        st.success('字幕已加入资料库，可在学习对话中检索和核对')
                    except Exception as exc:st.error(f'字幕读取未完成：{exc}')
                source=st.session_state.get(transcript_key)
                if source and st.button('基于字幕生成总结',key='summarize_'+row['id']):
                    try:
                        with st.spinner('检索字幕并生成总结…'):
                            result=asyncio.run(run('请读取这份视频字幕，按主题总结核心观点、关键例子与学习行动，引用原文和时间戳。明确说明本次读取范围，不将未读字幕或画面内容当作已知。',sources=[source]))
                        st.markdown(final_text(result))
                        store.save_artifact('video_summary',row['title'],{'source':source,'url':row['url'],'answer':final_text(result),'budget':result.get('budget')})
                    except Exception as exc:st.error(f'总结未完成：{exc}')

    if rows:st.download_button('导出全部收藏',json.dumps(rows,ensure_ascii=False,indent=2),'收藏.json')

else:
    title('学习记录','回到之前的对话，查看学习成果和本机归档。')
    for s in store.sessions():
        if st.button(s['title'][:70],key=s['session']):
            st.session_state.chat_session=s['session'];st.session_state['pending_session']=True
            st.info('已选中对话，请从左侧进入“学习对话”继续。')
    folder=ROOT/'exports'
    for p in sorted(folder.glob('*.md')) if folder.exists() else []:
        with st.expander(p.name):
            st.markdown(p.read_text());st.download_button('下载笔记',p.read_text(),p.name,key=p.name)
