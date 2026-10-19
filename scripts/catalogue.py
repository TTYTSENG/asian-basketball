"""Complete, filterable history and small independent reading pages.

The public projection excludes raw player/event payloads and the SQLite file.
"""
import copy
import html
import json
import re
import sqlite3
from collections import Counter, defaultdict
from pathlib import Path
from urllib.parse import quote

from advanced import metrics, observation_metrics
from engine import finalize
from editorial import ARTICLES, METHODS

ROOT=Path(__file__).resolve().parents[1]
BASE='https://ttytseng.github.io/asian-basketball'
NAMES={'tpbl':'TPBL','plg':'P. LEAGUE+','b':'B.LEAGUE','cba':'CBA'}

def esc(x):return html.escape(str(x),quote=True)

def game_path(g):
    return 'games/'+quote(str(g['league']),safe='')+'/'+quote(str(g['id']),safe='')+'.html'

def season(g):
    if g.get('season'):return str(g['season'])
    year=int(g['date'][:4]);year-=int(int(g['date'][5:7])<7)
    return f'{year}–{str(year+1)[-2:]}'

def state(g):
    if g.get('cancelled'):return '已取消'
    if g.get('postponed'):return '已延期'
    if not g.get('complete'):return '未完賽／官方待更新'
    if not g.get('players'):return '已完賽・詳細資料待補'
    if not g.get('report'):return '已有統計・逐球分析待補'
    if g['report'].get('issues'):return '已有資料・部分分析受限'
    return '已有分析'

def load_games(db,site):
    """Read the full stored schedule, not only snapshot.recent."""
    games={}
    if Path(db).exists():
        conn=sqlite3.connect(Path(db).resolve().as_uri()+'?mode=ro',uri=True)
        try:
            for league,gid,completed,payload in conn.execute('SELECT league_id,game_id,completed,payload_json FROM games'):
                g=json.loads(payload);g.update(league=league,id=str(gid),complete=bool(completed))
                games[(league,str(gid))]=g
        finally:conn.close()
    # Snapshots contain newer quality/finalization metadata. Preserve raw detail.
    for league in site.get('leagues',[]):
        for g in league.get('recent',[])+league.get('upcoming',[]):
            key=(league['id'],str(g['id']));games.setdefault(key,{}).update(copy.deepcopy(g))
    return sorted(games.values(),key=lambda g:(g['date'],g.get('time',''),g['league'],str(g['id'])),reverse=True)

def page(title,body,path,updated='',extra=''):
    root='../'*path.count('/')
    source=(ROOT/'index.html').read_text(encoding='utf8')
    settings=re.search(r'<aside class="reading-settings".*?</aside>',source,re.S)
    body=body.replace('<div class="table-wrap">','<div class="table-wrap" tabindex="0" role="region" aria-label="資料表格，可水平捲動">')
    return ('<!doctype html><html lang="zh-Hant"><head><meta charset="utf-8">'
        '<meta name="viewport" content="width=device-width,initial-scale=1">'
        f'<title>{esc(title)}｜凸肚男</title><link rel="canonical" href="{BASE}/{esc(path)}">'
        f'<link rel="stylesheet" href="{root}style.css"><link rel="stylesheet" href="{root}reading.css">'
        f'<script src="{root}a11y.js" defer></script><script src="{root}speech.js" defer></script><script src="{root}webmcp.js" defer></script>{extra}</head>'
        '<body><a class="skip" href="#main">跳至主要內容</a><header>'
        f'<div class="brand"><a href="{root}">專注亞洲籃球觀察</a></div><nav aria-label="主要導覽">'
        f'<a href="{root}history/">歷史賽事</a><a href="{root}analytics/">進階觀戰數據</a><a href="{root}research/">研究發展</a></nav></header>'
        +(settings[0] if settings else '')+f'<main id="main" tabindex="-1"><div class="intro"><h1>{esc(title)}</h1>'
        +(f'<p class="meta">資料發布時間：{esc(updated)}</p>' if updated else '')+'</div>'+body+
        f'</main><footer><p><a href="{root}">返回首頁</a> · 獨立觀察網站；請核對各頁官方來源。</p></footer></body></html>')

def save(public,path,text):
    p=public/path;p.parent.mkdir(parents=True,exist_ok=True);p.write_text(text,encoding='utf8')

def observation_html(g):
    obs=observation_metrics(g)
    fields=[('efg','eFG%'),('ts','TS%估計'),('three_attempt_pct','三分出手率'),('fta_rate','罰球出手率'),
            ('oreb_pct','進攻籃板率'),('dreb_pct','防守籃板率'),('tov_pct_est','回合失誤率估計'),
            ('off_rating_est','每百回合得分估計'),('assisted_fg_pct','助攻投籃比'),('ft_points_pct','罰球得分占比')]
    def num(x,pct=True):return f'{x:.1f}'+('%' if pct else '') if isinstance(x,(int,float)) else '未取得／不適用'
    body='<section><h2>進階觀戰數據</h2><p>'+esc(obs['method'])+'</p>'
    body+='<div class="table-wrap"><table><caption>雙方效率與出手結構</caption><thead><tr><th scope="col">指標</th>'
    body+=''.join('<th scope="col">'+esc(g[s])+'</th>' for s in ('home','away'))+'</tr></thead><tbody>'
    for key,label in fields:
        body+='<tr><th scope="row">'+label+'</th>'+''.join('<td>'+num(obs['teams'][s][key],key!='off_rating_est')+'</td>' for s in ('home','away'))+'</tr>'
    for key,label in [('paint_points','禁區得分'),('second_chance_points','二次進攻得分'),('fast_break_points','快攻得分')]:
        body+='<tr><th scope="row">'+label+'</th>'+''.join('<td>'+num(obs['teams'][s][key],False)+'</td>' for s in ('home','away'))+'</tr>'
    body+='</tbody></table></div><p>估計共同回合：'+num(obs['possessions_est'],False)+'。官方得分類別可能重疊，不相加當總得分。</p>'
    body+='<details><summary>查看計算分子與分母</summary>'
    for side in ('home','away'):
        body+='<h3>'+esc(g[side])+'</h3><p>'+esc('；'.join(k+'='+str(v) for k,v in obs['teams'][side]['source_counts'].items()))+'</p>'
    return body+'</details>'+''.join('<p class="notice">'+esc(w)+'</p>' for w in obs['warnings'])+'<p><a href="../../analytics/">閱讀指標定義與限制</a></p></section>'

def history_row(g):
    score='：'.join(str(x) for x in g.get('score',[]) if x is not None) or '—'
    return (f'<tr><td>{esc(g["date"])}</td><td>{esc(NAMES.get(g["league"],g["league"]))}</td>'
            f'<th scope="row"><a href="../{game_path(g)}">{esc(g["home"])} vs {esc(g["away"])}</a></th>'
            f'<td>{esc(score)}</td><td>{esc(state(g))}</td></tr>')

def build_catalogue(public,site,games,render):
    public=Path(public);urls=[];prepared=[];bykey={g['league']+':'+str(g['id']):g for g in games}
    for original in games:
        g=copy.deepcopy(original)
        if g.get('players'):
            g['advanced']=metrics(g);g=finalize(g,bykey)
        path=game_path(g);status=state(g)
        if g.get('complete') and g.get('players'):
            body=observation_html(g)+'<section><h2>單場觀察與資料品質</h2>'+render(g)+'</section>'
        else:
            body='<section><h2>'+esc(g['home'])+' vs '+esc(g['away'])+'</h2><p>'+esc(status)+'</p>'
            if g.get('complete'):body+='<p>官方比分：'+esc('：'.join(map(str,g.get('score',[]))))+'。詳細統計尚未取得，不產生效率或陣容結論。</p>'
            body+=f'<p><a href="{esc(g["source"])}">查看官方賽事</a></p></section>'
        body=f'<p>{esc(g["date"])} {esc(g.get("time",""))} · {esc(NAMES.get(g["league"],g["league"]))} · {esc(status)}</p><p><a href="../../history/?date={esc(g["date"])}&amp;league={esc(g["league"])}">返回這個比賽日</a></p>'+body
        save(public,path,page(g['home']+' vs '+g['away'],body,path,site.get('generatedAt','')));urls.append(BASE+'/'+path)
        prepared.append(dict(league=g['league'],id=str(g['id']),date=g['date'],time=g.get('time',''),
            season=season(g),home=g['home'],away=g['away'],score=g.get('score'),status=status,
            complete=bool(g.get('complete')),detail=bool(g.get('players')),path=path))
    save(public,'data/history.json',json.dumps(dict(generatedAt=site.get('generatedAt'),games=prepared),ensure_ascii=False))
    filters='<form id="history-filters" class="filter-form"><label>聯盟<select name="league"><option value="">全部聯盟</option>'+''.join(f'<option value="{k}">{esc(v)}</option>' for k,v in NAMES.items())+'</select></label>'
    filters+='<label>賽季<select name="season"><option value="">全部賽季</option>'+''.join(f'<option>{esc(y)}</option>' for y in sorted({g['season'] for g in prepared},reverse=True))+'</select></label>'
    filters+='<label>日期<input type="date" name="date"></label><label>球隊<input name="team" type="search" placeholder="輸入隊名"></label>'
    filters+='<label>資料狀態<select name="status"><option value="">全部</option><option value="detail">已有詳細統計</option><option value="pending">已完賽待補</option><option value="upcoming">未完賽</option></select></label><button type="reset">清除篩選</button></form>'
    body='<section><p>列出目前已保存的官方賽事，不代表已收齊全部歷年賽季。較早或資料不足場次先保留狀態，不額外回補；後續比賽持續更新。日報是當日快照，歷史賽事頁使用最近取得的官方紀錄。</p>'
    body+='<p class="meta">賽季依比賽日期以7月分界推定，供篩選使用；官方賽季或分級仍以來源為準。未完賽可能包含官方狀態待更新，請點入官網核對。</p>'+filters
    body+=f'<p id="history-count" role="status">共 {len(games)} 場已保存賽事。預設顯示最近已完賽場次；可用篩選查看未完賽。</p><div class="table-wrap"><table><caption>歷史賽事列表</caption><thead><tr><th scope="col">日期</th><th scope="col">聯盟</th><th scope="col">對戰</th><th scope="col">比分</th><th scope="col">資料狀態</th></tr></thead><tbody id="history-body">'
    body+=''.join(history_row(g) for g in games if g.get('complete'))+'</tbody></table></div><div class="pagination"><button id="history-prev" type="button" hidden>上一頁</button><span id="history-page"></span><button id="history-next" type="button" hidden>下一頁</button></div><p id="history-error" class="notice" hidden></p></section>'
    save(public,'history/index.html',page('歷史賽事',body,'history/index.html',site.get('generatedAt',''),'<script src="../history.js" defer></script>'));urls.append(BASE+'/history/')
    intro='<section><p>依官方統計讀懂比賽；公式、來源與資料限制分開說明。先閱讀方法，再從歷史賽事選擇一場看實際數據。</p><ul class="article-list">'
    for slug,title,summary,paragraphs in METHODS:
        intro+=f'<li><a href="{slug}.html">{esc(title)}</a><p>{esc(summary)}</p></li>'
        body='<section>'+''.join('<p>'+esc(p)+'</p>' for p in paragraphs)
        if slug=='lineups':body+='<p><a href="../research/lineup-rapm.html">研究延伸：L-RAPM</a></p>'
        body+='<p>定義參考：<a href="https://stats.gleague.nba.com/help/glossary">NBA G League統計字典</a>；本站估算與排除規則另於賽事頁標示。</p><p><a href="../history/">選擇比賽查看數據</a> · <a href="./">返回觀戰數據列表</a></p></section>'
        path='analytics/'+slug+'.html';save(public,path,page(title,body,path));urls.append(BASE+'/'+path)
    save(public,'analytics/index.html',page('進階觀戰數據',intro+'</ul></section>','analytics/index.html'));urls.append(BASE+'/analytics/')
    intro='<section><p>2026年10月19日研究更新。arXiv版本不代表已確認同儕審查，方法介紹也不表示本站已實作模型。本輪使用SciSpace與Consensus搜尋並回查原文；Elicit因帳戶API權限未能執行。</p><ul class="article-list">'
    for slug,title,year,authors,paper,url,summary,method,limits,application in ARTICLES:
        intro+=f'<li><a href="{slug}.html">{esc(title)}</a><p class="meta">{year} · {esc(authors)}</p><p>{esc(summary)}</p></li>'
        body=f'<section><p class="meta">{year} · {esc(authors)} · 整理日期2026年10月19日</p><p>{esc(summary)}</p><h2>研究方法與發現</h2><p>{esc(method)}</p><h2>資料需求與限制</h2><p>{esc(limits)}</p><h2>對本站與研究的用途</h2><p>{esc(application)}</p><h2>原文來源</h2><p><a href="{esc(url)}">{esc(paper)}</a></p><p>本頁為研究導讀，不是本站模型驗證結果；未下載所有資料集或完成逐篇風險偏差評讀。</p><p><a href="./">返回研究發展列表</a> · <a href="../analytics/">進階觀戰方法</a></p></section>'
        path='research/'+slug+'.html';save(public,path,page(title,body,path));urls.append(BASE+'/'+path)
    save(public,'research/index.html',page('籃球科學研究發展',intro+'</ul></section>','research/index.html'));urls.append(BASE+'/research/')
    return urls
