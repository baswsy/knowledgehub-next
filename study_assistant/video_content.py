"""读取B站可公开获取的字幕或用户上传的字幕；不下载音视频。"""
import json
import re
import math
from urllib.parse import urlparse,parse_qs
import httpx

MAX_BYTES=5*1024*1024

def identify(url):
    parsed=urlparse(url)
    if parsed.scheme!='https' or parsed.hostname not in ('www.bilibili.com','bilibili.com'):
        raise ValueError('请输入完整的 https://www.bilibili.com/video/BV… 链接')
    match=re.fullmatch(r'/video/(BV[A-Za-z0-9]{10})/?',parsed.path)
    if not match:raise ValueError('仅支持BV视频链接，请先打开短链接获取完整地址')
    try:page=int(parse_qs(parsed.query).get('p',['1'])[0])
    except ValueError:raise ValueError('分P编号无效')
    if page<1:raise ValueError('分P编号必须大于0')
    return match.group(1),page

def timestamp(seconds):
    seconds=int(seconds);return f'{seconds//3600:02d}:{seconds%3600//60:02d}:{seconds%60:02d}'

def parse_subtitle(name,data):
    if len(data)>MAX_BYTES:raise ValueError('字幕最多5MB')
    text=data.decode('utf-8-sig');segments=[]
    if name.lower().endswith('.json'):
        obj=json.loads(text);body=obj.get('body',[]) if isinstance(obj,dict) else obj
        if not isinstance(body,list):raise ValueError('字幕JSON需包含body数组')
        for item in body:
            if not isinstance(item,dict):continue
            start=float(item.get('from',0));end=float(item.get('to',start));content=str(item.get('content','')).strip()
            if not math.isfinite(start) or not math.isfinite(end) or start<0 or end<start:raise ValueError('字幕时间无效')
            if content:segments.append((start,end,content))
    else:
        pattern=r'(?m)^(\d{1,2}:\d{2}(?::\d{2})?[,.]\d{3})\s*-->\s*(\d{1,2}:\d{2}(?::\d{2})?[,.]\d{3})[^\n]*\n(.*?)(?=\n\s*\n|\Z)'
        def sec(t):
            parts=t.replace(',','.').split(':');value=0
            for part in parts:value=value*60+float(part)
            return value
        for m in re.finditer(pattern,text,re.S):
            start,end=sec(m[1]),sec(m[2])
            if end<start:raise ValueError('字幕结束时间早于开始时间')
            content=re.sub(r'<[^>]+>','',m[3]).strip()
            if content:segments.append((start,end,content))
    if not segments:raise ValueError('未提取到字幕，支持SRT、VTT或B站body格式JSON')
    return sorted(segments,key=lambda s:s[0])

def render(segments,url,origin):
    identify(url)
    return f'来源：{url}\n\n内容来源：{origin}。仅涵盖字幕中的语言信息。\n\n'+'\n\n'.join(f'[{timestamp(a)}–{timestamp(b)}] {text}' for a,b,text in segments)

def fetch_subtitle(url):
    bvid,page=identify(url)
    headers={'User-Agent':'Mozilla/5.0','Referer':'https://www.bilibili.com/'}
    with httpx.Client(timeout=20,headers=headers,follow_redirects=False) as client:
        def read_json(address,params=None):
            with client.stream('GET',address,params=params) as response:
                response.raise_for_status();chunks=[];size=0
                for chunk in response.iter_bytes():
                    size+=len(chunk)
                    if size>MAX_BYTES:raise ValueError('字幕响应超过5MB')
                    chunks.append(chunk)
            return json.loads(b''.join(chunks))
        def api(path,params):
            obj=read_json('https://api.bilibili.com'+path,params)
            if obj.get('code')!=0:raise ValueError('平台未允许读取字幕，请上传字幕文件')
            return obj.get('data') or {}
        info=api('/x/web-interface/view',{'bvid':bvid});pages=info.get('pages') or []
        if page>len(pages):raise ValueError('分P不存在')
        cid=pages[page-1]['cid']
        player=api('/x/player/v2',{'bvid':bvid,'cid':cid})
        tracks=(player.get('subtitle') or {}).get('subtitles') or []
        tracks=[t for t in tracks if t.get('subtitle_url')]
        if not tracks:raise ValueError('未获取到公开字幕；可上传字幕文件。登录或音频转写尚未接入。')
        tracks.sort(key=lambda t:not str(t.get('lan','')).startswith(('zh','ai-zh')))
        track=tracks[0];address=track['subtitle_url']
        if address.startswith('//'):address='https:'+address
        parsed=urlparse(address)
        if parsed.scheme!='https' or not parsed.hostname or not parsed.hostname.endswith('.hdslb.com') or parsed.port not in (None,443):
            raise ValueError('字幕地址不在允许的B站字幕域内')
        obj=read_json(address)
        segments=parse_subtitle('subtitle.json',json.dumps(obj).encode())
    canonical=f'https://www.bilibili.com/video/{bvid}/?p={page}'
    return render(segments,canonical,'B站字幕 · '+str(track.get('lan_doc','未知语言')))
