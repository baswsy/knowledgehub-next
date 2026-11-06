"""无外部 CDN 的交互图谱：缩放、拖动节点、领域筛选与证据详情。"""
import json
import streamlit.components.v1 as components

def render_graph(data):
    payload=json.dumps(data,ensure_ascii=False).replace('<','\\u003c').replace('>','\\u003e').replace('&','\\u0026')
    html='''<!doctype html><meta charset="utf-8"><style>
body{margin:0;font:14px system-ui;color:#1e293b;background:#f8fafc}#bar{display:flex;gap:12px;align-items:center;padding:12px}button,select{border:1px solid #cbd5e1;background:white;border-radius:8px;padding:7px}canvas{width:100%;height:420px;touch-action:none;cursor:grab}#detail{padding:12px 18px;background:white;min-height:60px;border-top:1px solid #e2e8f0;white-space:pre-wrap}small{color:#64748b}</style>
<div id="bar"><select id="group"><option value="">全部领域</option></select><button id="reset">重置视图</button><small>拖动节点 · 滚轮缩放 · 点击查看出处</small></div><canvas id="c"></canvas><div id="detail">选择一个概念，查看解释与原文位置。</div>
<script>
const data=PAYLOAD, canvas=document.getElementById('c'),ctx=canvas.getContext('2d'),detail=document.getElementById('detail'),select=document.getElementById('group');
const colors=['#6366f1','#0d9488','#e08735','#b45bc4','#3b82f6'];let w,h,zoom=1,pan={x:0,y:0},drag=null,last=null,moved=false;
const groups=[...new Set(data.nodes.map(n=>n.group))];groups.forEach(g=>{let o=document.createElement('option');o.value=g;o.textContent=g;select.appendChild(o)});
const nodes=data.nodes.map((n,i)=>({...n,x:Math.cos(i/data.nodes.length*2*Math.PI)*150,y:Math.sin(i/data.nodes.length*2*Math.PI)*140})), byId=Object.fromEntries(nodes.map(n=>[n.id,n]));
function size(){w=canvas.clientWidth;h=420;canvas.width=w*devicePixelRatio;canvas.height=h*devicePixelRatio;draw()}
function draw(){ctx.setTransform(devicePixelRatio,0,0,devicePixelRatio,0,0);ctx.clearRect(0,0,w,h);ctx.translate(w/2+pan.x,h/2+pan.y);ctx.scale(zoom,zoom);
for(const e of data.edges){const a=byId[e.source],b=byId[e.target];ctx.globalAlpha=select.value&&a.group!==select.value&&b.group!==select.value?.12:1;ctx.strokeStyle='#cbd5e1';ctx.beginPath();ctx.moveTo(a.x,a.y);ctx.lineTo(b.x,b.y);ctx.stroke();ctx.fillStyle='#64748b';ctx.font='11px system-ui';ctx.fillText(e.label,(a.x+b.x)/2,(a.y+b.y)/2)}
for(const n of nodes){ctx.globalAlpha=select.value&&n.group!==select.value?.15:1;ctx.fillStyle=colors[groups.indexOf(n.group)%colors.length];ctx.beginPath();ctx.arc(n.x,n.y,18,0,7);ctx.fill();ctx.fillStyle='#1e293b';ctx.font='12px system-ui';ctx.textAlign='center';ctx.fillText(n.label,n.x,n.y+34)}ctx.globalAlpha=1}
function point(e){const r=canvas.getBoundingClientRect();return{x:(e.clientX-r.left-w/2-pan.x)/zoom,y:(e.clientY-r.top-h/2-pan.y)/zoom}}
canvas.onpointerdown=e=>{const p=point(e);drag=nodes.find(n=>Math.hypot(n.x-p.x,n.y-p.y)<24);last={x:e.clientX,y:e.clientY};moved=false;canvas.setPointerCapture(e.pointerId)};
canvas.onpointermove=e=>{if(!last)return;const p=point(e);if(Math.abs(e.clientX-last.x)+Math.abs(e.clientY-last.y)>2)moved=true;if(drag){drag.x=p.x;drag.y=p.y}else{pan.x+=e.clientX-last.x;pan.y+=e.clientY-last.y}last={x:e.clientX,y:e.clientY};draw()};
canvas.onpointerup=e=>{if(drag&&!moved){const edges=data.edges.filter(x=>x.source===drag.id||x.target===drag.id);detail.textContent=drag.label+' · '+drag.group+'\\n'+drag.summary+'\\n出处：'+drag.refs.map(r=>r.source+'#'+r.paragraph).join('、')+'\\n'+edges.map(x=>byId[x.source].label+' → '+x.label+' → '+byId[x.target].label+' ['+x.evidence.source+'#'+x.evidence.paragraph+']').join('\\n')}last=null;drag=null};
canvas.onwheel=e=>{e.preventDefault();zoom=Math.min(3,Math.max(.35,zoom*(e.deltaY>0?.9:1.1)));draw()};select.onchange=draw;document.getElementById('reset').onclick=()=>{zoom=1;pan={x:0,y:0};draw()};new ResizeObserver(size).observe(canvas);size();
</script>'''
    components.html(html.replace('PAYLOAD',payload),height=580,scrolling=True)

def graph_svg(data):
    """导出可共享的矢量图，文本按 XML 规则转义。"""
    from html import escape
    import math
    nodes=data['nodes'];positions={n['id']:(450+300*math.cos(i/len(nodes)*2*math.pi),350+240*math.sin(i/len(nodes)*2*math.pi)) for i,n in enumerate(nodes)}
    parts=['<svg xmlns="http://www.w3.org/2000/svg" width="900" height="700" viewBox="0 0 900 700"><rect width="900" height="700" fill="#f8fafc"/>']
    for e in data['edges']:
        x,y=positions[e['source']];a,b=positions[e['target']]
        parts.append(f'<line x1="{x}" y1="{y}" x2="{a}" y2="{b}" stroke="#cbd5e1"/><text x="{(x+a)/2}" y="{(y+b)/2}" font-size="11" fill="#64748b">{escape(e["label"])}</text>')
    for n in nodes:
        x,y=positions[n['id']]
        parts.append(f'<circle cx="{x}" cy="{y}" r="18" fill="#6366f1"/><text x="{x}" y="{y+35}" text-anchor="middle" font-family="sans-serif" font-size="13">{escape(n["label"])}</text>')
    return ''.join(parts)+'</svg>'
