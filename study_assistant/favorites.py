"""视频收藏元数据导入：不下载或声称理解视频正文。"""
import csv
import io
import json
import httpx

def parse_favorites(name,data):
    if len(data)>10*1024*1024: raise ValueError('文件不能超过10 MB')
    text=data.decode('utf-8-sig')
    if name.lower().endswith('.csv'):
        rows=list(csv.DictReader(io.StringIO(text)))
    else:
        obj=json.loads(text)
        if isinstance(obj,dict):
            obj=obj.get('data',obj)
            rows=obj.get('medias',obj.get('videos',obj.get('items',[]))) if isinstance(obj,dict) else obj
        else: rows=obj
    if not isinstance(rows,list): raise ValueError('需要视频数组或包含 medias/videos/items 的 JSON')
    output=[]
    for r in rows[:1000]:
        if not isinstance(r,dict): continue
        bvid=r.get('bvid','')
        author=r.get('author') or r.get('upper') or ''
        if isinstance(author,dict): author=author.get('name','')
        output.append({'title':r.get('title') or r.get('标题'),
                       'url':r.get('url') or r.get('链接') or (f'https://www.bilibili.com/video/{bvid}' if bvid else ''),
                       'author':author,'description':r.get('description') or r.get('intro') or '',
                       'platform':r.get('platform') or ('B站' if bvid else '其他')})
    return output

def fetch_public_bilibili(uid,folder_name):
    if not uid.isdigit() or not folder_name.strip(): raise ValueError('请输入数字 UID 和收藏夹名称')
    headers={'User-Agent':'Mozilla/5.0','Referer':'https://www.bilibili.com/'}
    def get(client,url,params):
        response=client.get(url,params=params);response.raise_for_status();body=response.json()
        if body.get('code')!=0: raise ValueError('平台未允许读取公开收藏夹：'+str(body.get('message','未知错误')))
        return body.get('data') or {}
    with httpx.Client(timeout=20,headers=headers) as client:
        data=get(client,'https://api.bilibili.com/x/v3/fav/folder/created/list-all',{'up_mid':uid})
        folders=[f for f in data.get('list') or [] if folder_name in f.get('title','')]
        if len(folders)!=1: raise ValueError('未找到唯一收藏夹，请输入完整名称；也可使用文件导入')
        rows=[]
        for page in range(1,11):
            data=get(client,'https://api.bilibili.com/x/v3/fav/resource/list',{'media_id':folders[0]['id'],'pn':page,'ps':20,'platform':'web'})
            rows.extend(data.get('medias') or [])
            if not data.get('has_more'): break
    return parse_favorites('videos.json',json.dumps(rows).encode())
