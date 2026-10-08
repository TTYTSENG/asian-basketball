"""Publish crawlable snapshots alongside the existing interactive website.

Only public site/report JSON is consumed. Run after update.py at every deployment.
"""
import json,re,html,shutil
from pathlib import Path
from urllib.parse import urlparse
from xml.sax.saxutils import escape

ROOT=Path(__file__).resolve().parents[1]
BASE='https://ttytseng.github.io/asian-basketball'
NAME='專注亞洲籃球觀察'
AUTHOR={'@type':'Person','@id':BASE+'/#author','name':'凸肚男','email':'tzesmann@gmail.com','url':BASE+'/#about'}
def e(x):return html.escape(str(x),quote=True)
def link(label,url):
    if urlparse(str(url)).scheme!='https':return e(label)
    return f'<a href="{e(url)}">{e(label)}</a>'
def table(title,headers,rows):
    return '<div class="table-wrap"><table><caption>'+e(title)+'</caption><thead><tr>'+''.join('<th scope="col">'+e(h)+'</th>' for h in headers)+'</tr></thead><tbody>'+''.join('<tr>'+''.join(('<th scope="row">'+c+'</th>') if i==0 else '<td>'+c+'</td>' for i,c in enumerate(row))+'</tr>' for row in rows)+'</tbody></table></div>'
def sources(g):return '<p>'+link('引用：官方賽事紀錄',g.get('source',''))+(' · '+link('官方逐球資料',g['pbpSource']) if g.get('pbpSource') else '')+'</p>'
def analysis(g,level=4):
    h='h'+str(level);sub='h'+str(min(level+1,6))
    out=f'<article class="report"><{h}>{e(g["date"])} {e(g["home"])} vs {e(g["away"])}</{h}><p>比分（主：客）：{e("：".join(map(str,g["score"])))}</p>'
    for title,text in g.get('analysis',[]):out+=f'<{sub}>{e(title)}</{sub}><p>{e(text)}</p>'
    if g.get('keyPlayers'):
        out+=table('第四節最後五分鐘關鍵球員',['球員','得分','助攻','抄截','阻攻','失誤'],[[e(p['name']),e(p['points']),e(p['assists']),e(p['steals']),e(p['blocks']),e(p['turnovers']) if p.get('turnovers_valid') else '需核對'] for p in g['keyPlayers']])
    for x in g.get('lineups',[]):
        out+=f'<p>{e(x.get("kind",x.get("label","五人組合")))} · {e(x.get("team",""))}：{e("、".join(x["names"]))}；淨得分 {e(x.get("net","—"))}，共同 {float(x.get("seconds",0))/60:.1f} 分鐘。</p>'
        out+=table('組合球員近三場（含本場）',['球員','近三場出賽紀錄'],[[e(p['name']),'<br>'.join(e(f'{v["date"]}：{v["points"]} 分、{v["turnovers"]} 失誤、投籃 {v["fgm"]}/{v["fga"]}') for v in p.get('history',[])) or '歷史不足'] for p in x.get('players',[])])
    for p in g.get('playerChanges',[]):out+=f'<p>{e(p["name"])}：本場 {e(p["points"])} 分；前三場平均 {float(p["average"]):.1f} 分。差異 {float(p["delta"]):+.1f} 分；本場上場 {float(p["minutes"]):.1f} 分鐘。上場時間與對手均可能影響結果。</p>'
    a=g.get('advanced')
    if a:
        ato=a.get('ato',{});out+=f'<{sub}>ATO 暫停後進攻與防守</{sub}><p>共 {e(ato.get("total",0))} 次暫停；排除 {e(ato.get("excluded",0))} 個不完整回合。得分為本站進攻成功口徑，不能單憑此判定戰術效果。</p>'
        def rate(n,total):return f'{100*n/total:.1f}%（{n}/{total}）' if total else '無樣本'
        out+=table('ATO 統計',['球隊','進攻得分成功率','防守阻止得分成功率','得分／失誤'],[[e(g[x['side']]),rate(x['attack_success'],x['attack_n']),rate(x['defense_success'],x['defense_n']),e(f'{x["points"]}／{x["turnovers"]}')] for x in ato.get('summary',[])])
        out+=f'<{sub}>USG% 使用率與基本指標</{sub}><p>{e(a.get("benchmark_method",""))} 使用率為 box-score 估計，並非效率；短時間出賽估計可能大幅波動。</p>'
        def number(n):return f'{n:.1f}' if isinstance(n,(int,float)) else '資料不足'
        out+=table('個人使用率與組織指標',['球員／球隊','分鐘','USG%','EFF','助攻／失誤'],[[e(p['name']+'／'+g[p['side']]),f'{p["seconds"]/60:.1f}',number(p.get('usg')),number(p.get('eff')),e(f'{p.get("assists","—")}／{p.get("turnovers","—")}')] for p in a.get('players',[])])
    if g.get('quality'):out+='<p class="meta">'+e(g['quality'])+'</p>'
    return out+sources(g)+'</article>'
def games(data):
    out=''
    for league in data['leagues']:
        out+='<article class="league-block"><h3>'+e(league['name'])+'</h3>'+link('官方賽程與數據',league['source'])
        if league.get('error'):out+='<p class="notice">'+e(league['error'])+'</p>'
        if league.get('lastSuccess'):out+='<p>來源最後成功擷取：<time datetime="'+e(league['lastSuccess'])+'">'+e(league['lastSuccess'])+'</time></p>'
        out+=table('未來七天賽程',['臺北時間','對戰','來源'],[[e(g['date']+' '+g.get('time','')),e(g['away']+' 作客 '+g['home']),link('官方賽事',g['source'])] for g in league.get('upcoming',[])]) if league.get('upcoming') else '<p>未來七天沒有已取得的官方賽程。</p>'
        out+=table('最近五場賽後統計',['日期／對戰','比分（主：客）','來源'],[[e(g['date']+' '+g['home']+' vs '+g['away']),e('：'.join(map(str,g['score']))),link('官方紀錄',g['source'])] for g in league.get('recent',[])]) if league.get('recent') else '<p>目前沒有取得可驗證的完賽紀錄。</p>'
        out+='</article>'
    return out
def analyses(data):return ''.join('<section><h3>'+e(l['name'])+'</h3>'+(''.join(analysis(g) for g in l.get('recent',[])[:3]) or '<p>尚未取得可驗證的完賽分析。</p>')+'</section>' for l in data['leagues'])
def guides(data):return ''.join('<article class="guide"><h3>'+e(g['name'])+'</h3><p>'+e(g['description'])+'</p><ul>'+''.join('<li>'+link(x['label'],x['url'])+'</li>' for x in g['links'])+'</ul>'+('<p>球隊：'+e('、'.join(g['teams']))+'</p>' if g.get('teams') else '')+'</article>' for g in data['guides'])
def news(data):return ''.join('<article><h4>'+e(n['name'])+'</h4><ul>'+''.join('<li>'+link(x['title'],x['url'])+(' · '+e(x['date']) if x.get('date') else '')+'</li>' for x in n['items'])+'</ul>'+link('官方新聞入口',n['source'])+'</article>' for n in data['news'])
def meta(url,title,desc,graph):return f'<link rel="canonical" href="{e(url)}"><meta property="og:title" content="{e(title)}"><meta property="og:description" content="{e(desc)}"><meta property="og:url" content="{e(url)}"><meta property="og:type" content="website"><meta property="og:locale" content="zh_TW"><meta name="author" content="凸肚男"><script type="application/ld+json">'+json.dumps({'@context':'https://schema.org','@graph':graph},ensure_ascii=False).replace('<','\\u003c')+'</script><link rel="alternate" type="application/rss+xml" title="籃球日報" href="'+BASE+'/feed.xml">'
def write(public,path,text):
    if path.endswith('.html') and 'webmcp.js' not in text:
        script='../webmcp.js' if path.startswith('reports/') else './webmcp.js'
        text=text.replace('</head>','<script src="'+script+'" defer></script></head>')
    p=public/path;p.parent.mkdir(parents=True,exist_ok=True);p.write_text(text,encoding='utf8')
def build(public):
    data=json.loads((ROOT/'data/site.json').read_text(encoding='utf8'));public.mkdir(exist_ok=True)
    for name in ['index.html','basketball-analytics-handbook.html','app.js','reports.js','advanced.js','speech.js','a11y.js','style.css','reading.css','webmcp.js']:shutil.copy2(ROOT/name,public/name)
    shutil.copytree(ROOT/'downloads',public/'downloads',dirs_exist_ok=True)
    (public/'data/reports').mkdir(parents=True,exist_ok=True);shutil.copy2(ROOT/'data/site.json',public/'data/site.json')
    reports=sorted((ROOT/'data/reports').glob('*.json'))
    for p in reports:shutil.copy2(p,public/'data/reports'/p.name)
    text=(ROOT/'index.html').read_text(encoding='utf8')
    for id,body in [('game-content',games(data)),('analysis-content',analyses(data)),('news-content',news(data)),('league-content',guides(data))]:text=re.sub(r'<div id="'+id+r'">.*?</div>',lambda m:'<div id="'+id+'">'+body+'</div>',text,count=1,flags=re.S)
    text=text.replace('此網站的賽程與分析需要 JavaScript。你仍可使用以下官方來源連結查看資料。','此頁已包含最近發布的賽程與分析。開啟 JavaScript 可重新讀取最新資料；仍請核對各聯盟官網。')
    text=text.replace('</head>',meta(BASE+'/',NAME+'｜凸肚男','官方賽程、賽後數據與每日分析。',[AUTHOR,{'@type':'WebSite','name':NAME,'url':BASE+'/','inLanguage':'zh-Hant','publisher':{'@id':AUTHOR['@id']}},{'@type':'WebPage','name':NAME,'url':BASE+'/','dateModified':data['generatedAt'],'author':{'@id':AUTHOR['@id']}}])+'</head>')
    text=text.replace('id="updated">','id="updated">靜態資料發布時間：'+e(data['generatedAt'])+' · ')
    text=text.replace('</main>','<section><h2>日期日報與資料來源</h2><p><a href="reports/">依日期閱讀完整日報</a> · <a href="feed.xml">RSS 訂閱</a></p></section></main>')
    text=text.replace('</main>','<section><h2>AI 賽事資料查詢</h2><p data-webmcp-status>在支援網站工具的 AI 瀏覽器中，可查聯盟賽程、指定日期日報及比賽分析。回傳結果包含官方來源與資料時間。</p></section></main>')
    write(public,'index.html',text)
    rows=[];urls=[BASE+'/',BASE+'/basketball-analytics-handbook.html',BASE+'/reports/'];items=[]
    for p in reports:
        d=json.loads(p.read_text(encoding='utf8'));url=BASE+'/reports/'+p.stem+'.html';title=p.stem+' 亞洲籃球日報';desc='依官方公開資料整理的賽程、賽後統計與分析；包含來源與資料限制。'
        rows.append('<li>'+link(title,url)+'</li>');urls.append(url);items.append((title,url,desc))
        page=f'<!doctype html><html lang="zh-Hant"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>{e(title)}｜凸肚男</title><meta name="description" content="{desc}"><link rel="stylesheet" href="../style.css"><link rel="stylesheet" href="../reading.css">'+meta(url,title,desc,[AUTHOR,{'@type':'Article','headline':title,'dateModified':d['generatedAt'],'author':{'@id':AUTHOR['@id']},'publisher':{'@id':AUTHOR['@id']},'mainEntityOfPage':url,'inLanguage':'zh-Hant'}])+f'</head><body><a class="skip" href="#main">跳至主要內容</a><header><a href="../">專注亞洲籃球觀察</a></header><main id="main" style="max-width:1100px;margin:auto;padding:24px"><h1>{e(title)}</h1><p>作者：凸肚男 · 資料發布時間：<time datetime="{e(d["generatedAt"])}">{e(d["generatedAt"])}</time></p><p>所有時間為臺北時間。統計方法與資料限制見<a href="../#analysis">首頁說明</a>；來源失敗時可能保留之前成功擷取資料。</p><section><h2>賽程與賽後統計</h2>{games(d)}</section><section><h2>進階賽後分析</h2>{analyses(d)}</section><section><h2>官方賽事新聞</h2>{news(d)}</section><p><a href="./">其他日期日報</a></p></main></body></html>'
        write(public,'reports/'+p.stem+'.html',page)
    write(public,'reports/index.html','<!doctype html><html lang="zh-Hant"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>亞洲籃球日報目錄</title><link rel="stylesheet" href="../style.css"><link rel="canonical" href="'+BASE+'/reports/"></head><body><main style="max-width:900px;margin:auto;padding:24px"><h1>亞洲籃球日報目錄</h1><p><a href="../">返回首頁</a></p><ul>'+''.join(reversed(rows))+'</ul></main></body></html>')
    handbook=(public/'basketball-analytics-handbook.html').read_text(encoding='utf8');handbook=handbook.replace('</head>',meta(BASE+'/basketball-analytics-handbook.html','籃球空間表現分析與演算模型','進階術語與數學定義手冊。',[AUTHOR,{'@type':'Article','headline':'籃球空間表現分析與演算模型：進階術語與數學定義手冊','author':{'@id':AUTHOR['@id']},'mainEntityOfPage':BASE+'/basketball-analytics-handbook.html','inLanguage':'zh-Hant'}])+'</head>');write(public,'basketball-analytics-handbook.html',handbook)
    write(public,'sitemap.xml','<?xml version="1.0" encoding="UTF-8"?><urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">'+''.join('<url><loc>'+escape(url)+'</loc></url>' for url in urls)+'</urlset>')
    write(public,'feed.xml','<?xml version="1.0" encoding="UTF-8"?><rss version="2.0"><channel><title>凸肚男的亞洲籃球日報</title><link>'+BASE+'/</link><description>官方資料、賽後統計與分析</description>'+''.join('<item><title>'+escape(t)+'</title><link>'+u+'</link><guid>'+u+'</guid><description>'+escape(d)+'</description></item>' for t,u,d in reversed(items))+'</channel></rss>')
    write(public,'llms.txt','# 專注亞洲籃球觀察\n\n> 凸肚男依官方公開資料整理亞洲籃球賽程、統計及分析。不是官方聯盟網站；資料有擷取時間及限制。\n\n## 公開內容\n- [首頁]('+BASE+'/)\n- [日期日報]('+BASE+'/reports/)\n- [籃球術語與數學定義手冊]('+BASE+'/basketball-analytics-handbook.html)\n')
    write(public,'.nojekyll','')
    print('Built public HTML snapshots and',len(reports),'date reports; private database excluded.')
if __name__=='__main__':build(ROOT/'public')
