"""独立网页使用的单工作区HTTP API；模型密钥始终保留在服务端。"""
import os
import hmac
import asyncio
from pathlib import Path
from fastapi import FastAPI,Header,HTTPException,UploadFile,File
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel,Field
import storage as store
from agent import run

app=FastAPI(title='知学 KnowledgeHub API')
origins=[s.strip() for s in os.getenv('STUDY_WEB_ORIGINS','http://127.0.0.1:8080,http://localhost:8080').split(',') if s.strip()]
app.add_middleware(CORSMiddleware,allow_origins=origins,allow_methods=['GET','POST','DELETE'],allow_headers=['Content-Type','Authorization'])

def authorize(authorization):
    secret=os.getenv('STUDY_ACCESS_PASSWORD','')
    if not secret:raise HTTPException(503,'请在服务端配置 STUDY_ACCESS_PASSWORD')
    if not hmac.compare_digest((authorization or '').encode(),('Bearer '+secret).encode()):raise HTTPException(401,'访问口令不正确')

@app.get('/health')
def health():return {'status':'ok','version':'2.0'}

@app.get('/api/workspace')
def workspace(authorization:str|None=Header(default=None)):
    authorize(authorization)
    return {'notes':store.notes(),'favorites':store.favorites(),'memory':store.learning_memory(),
            'graphs':store.artifacts('graph'),'outlines':store.artifacts('outline')}

class Note(BaseModel):
    title:str=Field(min_length=1,max_length=200)
    content:str=Field(min_length=1,max_length=1000000)
    source:str|None=None

@app.post('/api/notes')
def note(body:Note,authorization:str|None=Header(default=None)):
    authorize(authorization);return {'source':store.write_note(body.title,body.content,source=body.source)}

@app.delete('/api/notes/{source}')
def delete(source:str,authorization:str|None=Header(default=None)):
    authorize(authorization);store.delete_note(source);return {'ok':True}

class Chat(BaseModel):
    question:str=Field(min_length=1,max_length=20000)
    sources:list[str]=Field(default_factory=list,max_length=100)
    session:str=Field(default='web',max_length=100)
    allow_save:bool=False
    deep:bool=False

@app.post('/api/chat')
async def chat(body:Chat,authorization:str|None=Header(default=None)):
    authorize(authorization)
    result=await run(body.question,history=store.messages(body.session),sources=body.sources,
                     allow_save=body.allow_save,deep=body.deep,memory=store.learning_memory())
    final=next((e['content'] for e in reversed(result['events']) if e.get('type')=='ai' and not e.get('tool_calls')),None)
    if not final:raise HTTPException(502,'模型未返回最终答案')
    store.add_message(body.session,'user',body.question);store.add_message(body.session,'assistant',str(final))
    return {'answer':final,'trace':result}

class Memory(BaseModel):
    content:str=Field(max_length=2000)
@app.post('/api/memory')
def memory(body:Memory,authorization:str|None=Header(default=None)):
    authorize(authorization);store.learning_memory(body.content);return {'ok':True}

class Generate(BaseModel):
    kind:str
    sources:list[str]=Field(min_length=1,max_length=100)
@app.post('/api/generate')
async def generate(body:Generate,authorization:str|None=Header(default=None)):
    authorize(authorization)
    if body.kind not in ('graph','outline'):raise HTTPException(400,'无效成果类型')
    from knowledge import generate as build
    return await asyncio.to_thread(build,body.kind,body.sources)

class Favorite(BaseModel):
    title:str=Field(min_length=1,max_length=200)
    url:str=Field(max_length=2000)
    description:str=Field(default='',max_length=5000)
    platform:str='B站'
@app.post('/api/favorites')
def favorite(body:Favorite,authorization:str|None=Header(default=None)):
    authorize(authorization);return {'count':store.save_favorites([body.model_dump()])}

@app.delete('/api/favorites/{key}')
def delete_favorite(key:str,authorization:str|None=Header(default=None)):
    authorize(authorization);store.remove_favorite(key);return {'ok':True}

class Video(BaseModel):
    url:str=Field(max_length=2000)
    title:str=Field(min_length=1,max_length=200)
@app.post('/api/video')
async def video(body:Video,authorization:str|None=Header(default=None)):
    authorize(authorization)
    import hashlib
    from video_content import fetch_subtitle
    transcript=await asyncio.to_thread(fetch_subtitle,body.url)
    source='transcript-'+hashlib.sha256(body.url.encode()).hexdigest()[:16]+'.md'
    store.write_note(body.title+' 字幕',transcript,'视频字幕',source=source)
    return {'source':source}

@app.post('/api/upload')
async def upload(file:UploadFile=File(),authorization:str|None=Header(default=None)):
    authorize(authorization)
    from ingestion import save_material,MAX_BYTES
    data=await file.read(MAX_BYTES+1)
    if len(data)>MAX_BYTES:raise HTTPException(413,'文件最多10MB')
    path=await asyncio.to_thread(save_material,file.filename or 'upload.txt',data,Path(__file__).parent/'materials')
    return {'source':path.name}

from fastapi import Form
@app.post('/api/subtitle')
async def subtitle(url:str=Form(),title:str=Form(),file:UploadFile=File(),authorization:str|None=Header(default=None)):
    authorize(authorization)
    import hashlib
    from video_content import parse_subtitle,render,MAX_BYTES
    data=await file.read(MAX_BYTES+1)
    text=render(parse_subtitle(file.filename or 'subtitle.srt',data),url,'用户上传字幕')
    source='transcript-'+hashlib.sha256(url.encode()).hexdigest()[:16]+'.md'
    store.write_note(title+' 字幕',text,'视频字幕',source=source)
    return {'source':source}

@app.exception_handler(ValueError)
async def invalid_request(request, exc):
    return JSONResponse(status_code=400,content={'detail':str(exc)})

@app.exception_handler(Exception)
async def unavailable(request, exc):
    return JSONResponse(status_code=500,content={'detail':'任务未完成，请检查服务端运行日志或稍后重试。'})
