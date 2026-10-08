"""Official public sources only. Parsers fail closed when layouts change."""
import json,re,time,hashlib,os
from pathlib import Path
from datetime import datetime,timedelta,timezone
from urllib.parse import urljoin,urlparse
from collections import Counter
from curl_cffi import requests
from bs4 import BeautifulSoup
from adapters import tpbl_adapter as tp,bleague_adapter as bl,pleague_adapter as pl
from engine import analyze
from advanced import metrics

TZ=timezone(timedelta(hours=8));CACHE=Path(os.environ.get('BASKETBALL_CACHE','.cache/http'))
def get(url):
    CACHE.mkdir(parents=True,exist_ok=True);path=CACHE/(hashlib.sha256(url.encode()).hexdigest()+'.txt')
    if path.exists() and time.time()-path.stat().st_mtime<1800:return path.read_text(encoding='utf8')
    error=None
    for attempt in range(3):
        try:
            response=requests.get(url,impersonate='chrome',timeout=35,headers={'Accept':'text/html,application/json','Accept-Language':'zh-TW,ja;q=0.8,en;q=0.7'})
            response.raise_for_status();text=response.text
            if not text.strip():raise ValueError('empty response')
            path.write_text(text,encoding='utf8');return text
        except Exception as exc:error=exc;time.sleep(attempt+1)
    raise RuntimeError(f'{url}: {error}')
def js(url):return json.loads(get(url))
def integer(v):return int(v or 0)
def optional_stat(p,field):
    played=secs(p.get('time_on_court',p.get('mins',p.get('PlayTime'))))
    value=p.get(field)
    return None if played>0 and value in (None,'') else integer(value)
def secs(v):
    if str(v).upper() in ('DNP','DNP-CD','','NONE'):return 0
    if isinstance(v,(int,float)):return v
    if ':' in str(v):a,b=str(v).split(':');return int(a)*60+int(b)
    return integer(v)
def player(pid,name,pts,fgm,fga,tov,seconds,**rest):return dict(id=str(pid),name=name,points=integer(pts),fgm=integer(fgm),fga=integer(fga),turnovers=integer(tov),seconds=secs(seconds),**rest)
def totals(players):return {s:{k:sum(p[k] for p in ps) if all(p.get(k) is not None for p in ps) else None for k in ('points','fgm','fga','turnovers','ftm','fta','seconds','assists','rebounds','steals','blocks')} for s,ps in players.items()}
def period_ends(events):
    out=[];q=None
    for e in events:
        if q is not None and e['period']!=q:out.append(dict(period=q,sec=0,kind='END',side=None,pid='',pts=0))
        q=e['period'];out.append(e)
    if q is not None:out.append(dict(period=q,sec=0,kind='END',side=None,pid='',pts=0))
    return out
def basic(league,gid,date,home,away,score,source,time=''):return dict(league=league,id=str(gid),date=date,home=home,away=away,score=score,source=source,time=time)

def tpbl_schedule(today):
    seasons=sorted(js('https://api.tpbl.basketball/api/seasons'),key=lambda x:x['started_at'],reverse=True)
    games=[]
    for season in seasons[:2]:
        for x in js(f"https://api.tpbl.basketball/api/seasons/{season['id']}/games"):
            h,a=x['home_team'],x['away_team'];g=basic('tpbl',x['id'],x['game_date'],h['name'],a['name'],[h.get('won_score'),a.get('won_score')],f"https://tpbl.basketball/games/{x['id']}",x['game_time'][:5]);g['complete']=x['status']=='COMPLETED';g['division']=x.get('division_id');games.append(g)
    if not games:raise ValueError('TPBL schedule empty')
    return games
def tpbl_game(g,detail=True):
    base=f"https://api.tpbl.basketball/api/games/{g['id']}";box=js(base+'/stats');players={}
    for side in ('home','away'):
        ps=box[side+'_team']['players']['total'];ps=list(ps.values()) if isinstance(ps,dict) else ps
        players[side]=[player(p['id'],p['name'],p.get('score'),p.get('field_goals_made'),p.get('field_goals_attempted'),p.get('turnovers'),p.get('time_on_court'),ftm=optional_stat(p,'free_throws_made'),fta=optional_stat(p,'free_throws_attempted'),assists=optional_stat(p,'assists'),rebounds=optional_stat(p,'rebounds'),steals=optional_stat(p,'steals'),blocks=optional_stat(p,'blocks')) for p in ps]
    g['players']=players;g['stats']=totals(players);g['score']=[box[s+'_team']['teams']['total']['won_score'] for s in ('home','away')]
    for s in ('home','away'):
        t=box[s+'_team']['teams']['total']
        for k,field in [('fga','field_goals_attempted'),('fta','free_throws_attempted'),('turnovers','turnovers')]:
            if t.get(field) is not None:g['stats'][s][k]=integer(t[field])
    g['statsSource']=base+'/stats'
    if detail:
        b=js(base+'/broadcasts');ev=sorted((e for r in b['rounds'] for e in r['events']),key=lambda e:e['order']);missing=[e for e in ev if e.get('event_quarter_time') is None]
        last={}
        for e in ev:
            q=e['quarter']
            if e.get('event_quarter_time') is None:e['event_quarter_time']=last.get(q,(720 if q<=4 else 300)*1000)
            last[q]=e['event_quarter_time']
        lefts,nfix=tp.clean_clock(ev)
        hid=box['home_team']['id'];events=[]
        for e,left in zip(ev,lefts):
            side='home' if (e.get('team') or {}).get('id')==hid else 'away';p=e.get('player') or {};kind=tp.event_map(e)
            if e['event_type']=='Rotation':kind=('IN' if e['event_outcome']=='Entering' else 'OUT',0)
            if e['event_type']=='Timeout':kind=('TIMEOUT',0)
            if kind:events.append(dict(period=e['quarter'],sec=left,side=side,pid=str(p.get('id','')),name=p.get('name',''),kind=kind[0],pts=kind[1]))
        events=period_ends(events);g['events']=events;g['report']=analyze(events,players,g['score'],720);g['clockCorrections']=nfix;g['pbpSource']=base+'/broadcasts'
        if missing:
            g['report']['issues']['missing_clock']=len(missing);g['report']['lineups']=[]
            if any(e['quarter']==4 for e in missing):g['report']['key']=[]
    g['advanced']=metrics(g);return g

def plg_schedule(today):
    root='https://pleagueofficial.com';soup=BeautifulSoup(get(root+'/schedule-regular-season'),'lxml');pages=[soup]
    # New season can have no completed games; preserve the previous season.
    seasons=sorted(set(re.findall(r'/schedule-regular-season/(\d{4}-\d{2})',str(soup))),reverse=True)
    for season in seasons[:2]:pages.append(BeautifulSoup(get(root+'/schedule-regular-season/'+season),'lxml'))
    out={}
    for page in pages:
        for row in page.select('.match_row'):
            a=row.select_one('a[href*="/game/"]');date=row.select_one('.match_row_datetime');cl=' '.join(row.get('class',[]));m=re.search(r'd-(\d{4})-(\d{2})',cl)
            if not (a and date and m):continue
            mmdd=date.select_one('h5').get_text(strip=True);day=int(mmdd.split('/')[-1]);year=int(m[1]);month=int(m[2]);date_s=f'{year:04}-{month:02}-{day:02}'
            names=[x.get_text(strip=True) for x in row.select('.text-black > span.PC_only')]
            if len(names)!=2:continue
            scores=[integer(x.text) for x in row.select('h6.PC_only.ff8bit')]
            g=basic('plg',a['href'].split('/')[-1],date_s,names[1],names[0],list(reversed(scores)) if len(scores)==2 else [None,None],urljoin(root,a['href']),date.select_one('h6').text.strip())
            g['complete']='is-future' not in row.get('class',[]) and all(v is not None for v in g['score']) and sum(g['score'])>0;out[g['id']]=g
    if not out:raise ValueError('P+ schedule layout changed')
    return list(out.values())
def plg_game(g,detail=True):
    url=f"https://pleagueofficial.com/api/boxscore.preciser.php?id={g['id']}&away_tab=total&home_tab=total";box=js(url)['data'];players={}
    for s in ('home','away'):
        ps=[]
        for p in box[s]:
            m2,a2=map(int,(p['two_m_two'] or '0-0').split('-'));m3,a3=map(int,(p['trey_m_trey'] or '0-0').split('-'));mf,af=map(int,(p['ft_m_ft'] or '0-0').split('-'));ps.append(player(p['player_id'],p['name'],p['points'],m2+m3,a2+a3,p['turnover'],p['mins'],ftm=mf if p.get('ft_m_ft') or secs(p['mins'])==0 else None,fta=af if p.get('ft_m_ft') or secs(p['mins'])==0 else None,assists=optional_stat(p,'ast'),rebounds=optional_stat(p,'reb'),steals=optional_stat(p,'stl'),blocks=optional_stat(p,'blk')))
        players[s]=ps
    g['players']=players;g['stats']=totals(players);g['score']=[box['score_home'],box['score_away']];g['statsSource']=url
    for s in ('home','away'):
        t=box.get(s+'_total',{})
        if isinstance(t,dict):
            for k,field in [('fta','ft'),('turnovers','turnover')]:
                if t.get(field) is not None:g['stats'][s][k]=integer(t[field])
            if t.get('two') is not None and t.get('trey') is not None:g['stats'][s]['fga']=integer(t['two'])+integer(t['trey'])
    if detail:
        html=get(g['source']);m=re.search(r"getPlayByPlay\('([a-f\d-]+)'\)",html)
        if not m:raise ValueError('P+ public game UUID missing')
        url='https://pleagueofficial.com/api/playbyplay.php?uuid='+m[1];rows=pl.parse_pbp(get(url));fixed=pl.clean_clock(rows)
        ids={(s,pl.jn(p['jersey'])):str(p['player_id']) for s in ('home','away') for p in box[s]};starters={s:[str(p['player_id']) for p in box[s] if str(p['starter']).strip()] for s in ('home','away')};events=[]
        # Resolve known official jersey formatting / wrong-side records ONLY when
        # the official box score gives a unique exact player name across rosters.
        byname={}
        for s in ('home','away'):
            for p in box[s]:byname.setdefault(p['name'],[]).append((s,str(p['player_id'])))
        resolved=0
        for r in rows:
            if r['kind']!='ev':continue
            kind=pl.classify(r['desc'],r['act'])
            if r['desc'] in ('替換上場','下場休息'):kind=('IN' if r['desc']=='替換上場' else 'OUT',0)
            if r['desc']=='暫停':kind=('TIMEOUT',0)
            if kind:
                side=r['side'];pid=ids.get((side,r['jersey']),'');candidates=byname.get(r['name'],[])
                if len(candidates)==1 and candidates[0]!=(side,pid):side,pid=candidates[0];resolved+=1
                events.append(dict(period=r['period'],sec=r['sec'],side=side,pid=pid,name=r['name'],kind=kind[0],pts=kind[1]))
        events=period_ends(events);g['events']=events;g['report']=analyze(events,players,g['score'],720,starters);g['clockCorrections']=fixed;g['identityCorrections']=resolved;g['pbpSource']=url
    g['advanced']=metrics(g);return g

def b_schedule(today):
    from concurrent.futures import ThreadPoolExecutor
    dates=[today+timedelta(days=i) for i in range(-10,8)]
    def read(day):
        url=f'https://www.bleague.jp/schedule/?tab=1&year={day.year}&mon={day.month:02}&day={day.day:02}'
        soup=BeautifulSoup(get(url),'lxml');games=[]
        current=soup.select_one('.js-schedule-date-slider-item.is-current [data-day]')
        # A date without games can fall back to another date on official UI.
        if current and int(current['data-day'])!=day.day:return []
        for a in soup.select('#schedule-b1 a.data-game'):
            names=[x.text.strip() for x in a.select('.team-name')];key=re.search(r'ScheduleKey=(\d+)',a['href'])
            point=a.select_one('.point');score=[int(x) for x in re.findall(r'\d+',point.get_text(' ',strip=True))] if point else []
            clock=re.search(r'\b\d{1,2}:\d{2}\b',a.get_text(' ',strip=True));dt=datetime.combine(day,datetime.strptime(clock[0],'%H:%M').time(),timezone(timedelta(hours=9))).astimezone(TZ) if clock else None
            if len(names)!=2 or not key:continue
            g=basic('b',key[1],(dt.date() if dt else day).isoformat(),names[0],names[1],score[:2] if len(score)==2 else [None,None],f'https://www.bleague.jp/game_detail/?ScheduleKey={key[1]}',dt.strftime('%H:%M') if dt else '')
            g['complete']=len(score)==2 and ('FINAL' in a.get_text() or '試合終了' in a.get_text() or '結果' in a.get_text());games.append(g)
        return games
    with ThreadPoolExecutor(max_workers=4) as pool:parts=list(pool.map(read,dates))
    games={g['id']:g for part in parts for g in part}
    if not games:raise ValueError('B.LEAGUE schedule empty / layout changed')
    return list(games.values())
def b_game(g,detail=True):
    html=get(g['source']);match=re.search(r'_contexts_s3id\.data\s*=\s*',html)
    if not match:raise ValueError('B official embedded context missing')
    data=json.JSONDecoder().raw_decode(html[match.end():])[0];game=data['Game']
    if not game['GameEndedFlg']:raise ValueError('B game has not ended')
    players={}
    for s in ('home','away'):
        rows=data[s.title()+'Boxscores'];rows=[x for x in rows if x['PeriodCategory']==18]
        if not rows:raise ValueError('B full-game box score missing')
        players[s]=[player(x['PlayerID'],x['PlayerNameJ'],x.get('Point'),integer(x.get('PT2M'))+integer(x.get('PT3M')),integer(x.get('PT2A'))+integer(x.get('PT3A')),x.get('TO'),x.get('PlayTime'),ftm=optional_stat(x,'FTM'),fta=optional_stat(x,'FTA'),assists=optional_stat(x,'AS'),rebounds=optional_stat(x,'RB_TOT'),steals=optional_stat(x,'ST'),blocks=optional_stat(x,'BS')) for x in rows if x.get('PlayerID')]
    g['players']=players;g['stats']=totals(players);g['score']=[game['HomeTeamScore'],game['AwayTeamScore']];g['date']=data['ymd'];g['statsSource']=g['source']
    total=next((x for x in data['Summaries'] if x['PeriodCategory']==18),{})
    for s in ('home','away'):
        for k,field in [('fta','FTA'),('turnovers','TO'),('fga','PTA')]:
            field=s.title()+'Team'+field
            if total.get(field) is not None:g['stats'][s][k]=integer(total[field])
    if detail:
        # Newer pages render the visible timeline in JavaScript. Its official
        # embedded context already contains the entire chronological timeline.
        events=[]
        for r in data['PlayByPlays']:
            cd=r.get('ActionCD1');kind=bl.ACT.get(cd)
            if cd in (86,87):kind=('IN' if cd==86 else 'OUT',0)
            if cd==88:kind=('TIMEOUT',0)
            if kind:
                side='home' if str(r.get('TeamID'))==str(game['HomeTeamID']) else 'away'
                events.append(dict(period=r['Period'],sec=secs(r['RestTime']),side=side,pid=str(r.get('PlayerID1') or ''),name=r.get('PlayerNameJ1') or '',kind=kind[0],pts=kind[1]))
        events=period_ends(events);g['events']=events;g['report']=analyze(events,players,g['score'],600);g['pbpSource']=g['source']+'#playbyplay'
    g['advanced']=metrics(g);return g

def news(name,url):
    soup=BeautifulSoup(get(url),'lxml');out=[];seen=set();links=soup.select('a[href]')
    links.sort(key=lambda a:0 if re.search(r'game-recap|game-center|vs-|survive|sweep|drops-',a['href']) else 1)
    for a in links:
        u=urljoin(url,a['href']);path=urlparse(u).path
        if urlparse(u).hostname!=urlparse(url).hostname or '/news/' not in path or path.rstrip('/').endswith('/news') or u in seen:continue
        title=a.get_text(' ',strip=True)
        if not title:
            article=BeautifulSoup(get(u),'lxml');h=article.select_one('h1');title=h.get_text(' ',strip=True) if h else ''
        if not title or len(title)<8:continue
        if len(title)>180:title=title[:177]+'…'
        seen.add(u);out.append(dict(title=title,url=u))
        if len(out)==3:break
    if not out:raise ValueError('Official news links missing')
    return dict(name=name,source=url,items=out)
def cba_news():
    url='https://portal-server.cbaleague.com/news/list?page=1&page_size=5';data=js(url)
    payload=data.get('data',data);rows=payload.get('data',payload.get('list',payload.get('records',[]))) if isinstance(payload,dict) else payload
    if not rows:raise ValueError('CBA news schema changed')
    reports=[x for x in rows if re.search('战报|夺得|决赛|击败|战胜',x['title'])]
    selected=sorted(reports or rows,key=lambda x:x.get('publish_date',''),reverse=True)[:3]
    return dict(name='CBA',source='https://www.cbaleague.com/#/news',items=[dict(title=x['title'],url=f"https://www.cbaleague.com/#/news/detail/{x['id']}",date=x.get('publish_date','')) for x in selected])
