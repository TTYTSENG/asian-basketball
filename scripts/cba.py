"""Public CBA data-site adapter; no login or private endpoints.

The official browser decodes AES-ECB responses with a published client key.
Unknown events fail analysis validation; no lineup or possession is invented.
"""
import base64,json,re,time
from datetime import timedelta
from concurrent.futures import ThreadPoolExecutor
from curl_cffi import requests
from cryptography.hazmat.primitives.ciphers import Cipher,algorithms,modes

BASE='https://data-server.cbaleague.com'
PUBLIC='https://www.cbaleague.com/data/'
def api(path,body=None):
    error=None
    for attempt in range(3):
        try:
            kwargs=dict(impersonate='chrome',timeout=35,headers={'Accept':'application/json','Referer':PUBLIC})
            r=requests.get(BASE+path,**kwargs) if body is None else requests.post(BASE+path,json=body,**kwargs)
            r.raise_for_status();value=r.json()
            if isinstance(value,str):
                dec=Cipher(algorithms.AES(b'uVayqL4ONKjFbVzQ'),modes.ECB()).decryptor()
                raw=dec.update(base64.b64decode(value,validate=True))+dec.finalize();pad=raw[-1]
                if not 1<=pad<=16 or raw[-pad:]!=bytes([pad])*pad:raise ValueError('CBA public response format changed')
                value=json.loads(raw[:-pad])
            return value
        except Exception as exc:error=exc;time.sleep(attempt+1)
    raise RuntimeError(f'CBA official endpoint unavailable: {path}: {error}')

def schedule(today):
    from sources import basic
    days=[today+timedelta(days=i) for i in range(-35,7)]
    # Month metadata avoids requesting empty dates and catches schema changes.
    months={}
    for d in days:
        key=(d.year,d.month)
        if key not in months:months[key]=api(f'/api/schedules/month?year={d.year}&month={d.month:02}')
    active={r['scheduleTime'][:10] for rows in months.values() for r in rows if (r.get('scheduleNum') or 0)>0}
    def read(d):return api('/api/schedules/day?day='+d.isoformat()+'&auto=0')
    with ThreadPoolExecutor(max_workers=3) as pool:parts=list(pool.map(read,[d for d in days if d.isoformat() in active]))
    out={}
    for rows in parts:
        for x in rows:
            # CBA league only: regular season, playoffs and preseason, no youth/all-star/cup.
            if str(x.get('matchTypeId')) not in ('1','2','3'):continue
            dt=x['scheduleTime'];gid=str(x['scheduleId'])
            g=basic('cba',gid,dt[:10],x['homeTeamName'],x['visitingTeamName'],[x.get('homeTeamScore'),x.get('visitingTeamScore')],PUBLIC+'#/gameReport?scheduleId='+gid+'&date='+dt[:10]+'&isToMatch=0',dt[11:16])
            g.update(complete=x['status']==4,competition=x.get('scheduleTypeName','CBA'),season=x.get('season'),quarter=x.get('quarter'),analysisOnly=True)
            out[gid]=g
    return list(out.values())

def parse_events(rows,players,score,teams=None):
    identities={}
    for side,ps in players.items():
        for p in ps:identities.setdefault(p['name'],[]).append((side,p['id']))
    def who(name):
        found=identities.get(name,[])
        return found[0] if len(found)==1 else (None,'')
    events=[];previous={'home':0,'away':0};unknown=0
    for r in rows:
        text=r.get('textualFormat','');names=r.get('playerCNNames') or [];q=r.get('quarterNum');minute=r.get('minutes');second=r.get('seconds')
        if q is None or minute is None or second is None:unknown+=1;continue
        sec=minute*60+second;side,pid=who(names[0]) if names else (None,'')
        def add(kind,pts=0,s=side,p=pid,name=names[0] if names else ''):events.append(dict(period=q,sec=sec,side=s,pid=p,name=name,kind=kind,pts=pts))
        current={'home':r.get('homeScore'),'away':r.get('visitorScore')}
        deltas={s:current[s]-previous[s] for s in current if current[s] is not None}
        if len(deltas)!=2 or any(v<0 or v>3 for v in deltas.values()):unknown+=1
        previous={s:current[s] if current[s] is not None else previous[s] for s in current}
        if '换下了' in text:
            m=re.search(r'队换人，(.+?)换下了(.+?)$',text)
            if m:
                ins,inp=who(m[1]);outs,outp=who(m[2])
                if ins and ins==outs:add('OUT',s=outs,p=outp,name=m[2]);add('IN',s=ins,p=inp,name=m[1])
                else:unknown+=1
            else:unknown+=1
            continue
        if '暂停' in text:add('TIMEOUT');continue
        if '失误' in text:
            if side:add('TOV')
            else:unknown+=1
        elif '罚' in text and ('命中' in text or '不中' in text):
            if side:add('FT' if deltas.get(side)==1 else 'FTX',deltas.get(side,0))
            else:unknown+=1
        elif any(deltas.values()):
            scoring=[s for s,v in deltas.items() if v>0]
            if len(scoring)==1 and side==scoring[0] and deltas[side] in (2,3):add('FG'+str(deltas[side]),deltas[side])
            else:unknown+=1
        elif '不中' in text:
            if side:add('M3' if '三分' in text else 'M2')
            else:unknown+=1
        for m in re.finditer(r'([^，。 ()]+?)(?:抢到进攻篮板|获得防守篮板|断下|的助攻)',text):
            name=m[1];s,p=who(name)
            # Steal phrasing has 被 prefix; assist phrasing may have 接到 prefix.
            if not s:
                matches=[n for n in identities if name.endswith(n)]
                if len(matches)==1:name=matches[0];s,p=who(name)
            if s:add('OREB' if '进攻篮板' in m[0] else 'DREB' if '防守篮板' in m[0] else 'STL' if '断下' in m[0] else 'AST',s=s,p=p,name=name)
        # Team rebounds still terminate/extend an ATO possession when side is known.
        for suffix,kind in [('队抢到进攻篮板','OREB'),('队获得防守篮板','DREB')]:
            if suffix in text:
                team_sides=[s for s,name in (teams or {}).items() if name+suffix in text]
                if len(team_sides)==1:add(kind,s=team_sides[0],p='',name='')
                else:unknown+=1
    if [previous['home'],previous['away']]!=score:unknown+=1
    return events,unknown

def game(g,detail=True):
    from sources import player,totals,period_ends
    from engine import analyze
    from advanced import metrics
    path='/api/player-match-datas/data-count';box=api(path,{'scheduleId':g['id']});players={};starters={}
    for side,field in [('home','homeCounts'),('away','visitingCounts')]:
        rows=[p for p in box[field] if p.get('playerId') is not None]
        if not rows:raise ValueError('CBA player box score missing')
        required=('points','fieldGoals','fieldGoalsAttempted','turnovers','upTime')
        if any(any(p.get(k) is None for k in required) for p in rows):raise ValueError('CBA essential statistics missing')
        players[side]=[player(p['playerId'],p['cnAlias'],p['points'],p['fieldGoals'],p['fieldGoalsAttempted'],p['turnovers'],p['upTime'],ftm=p.get('freeThrows'),fta=p.get('freeThrowsAttempted'),assists=p.get('assists'),rebounds=p.get('rebounds'),steals=p.get('steals'),blocks=p.get('blocked'),fouls=p.get('fouls')) for p in rows]
        starters[side]=[str(p['playerId']) for p in rows if p.get('gameStart')==1]
    g['players']=players;g['stats']=totals(players);g['statsSource']=g['source']
    for side,field in [('home','homeCounts'),('away','visitingCounts')]:
        for row in box[field]:
            if row.get('playerId') is None:
                for k in ('turnovers','rebounds'):
                    if row.get(k) is not None:g['stats'][side][k]+=row[k]
    if [g['stats'][s]['points'] for s in ('home','away')]!=g['score']:raise ValueError('CBA box score does not match final score')
    if detail:
        try:
            rows=[];offset=0
            for _ in range(20):
                result=api('/api/schedule-eventses/filterPage?startNum='+str(offset),{'scheduleId':g['id'],'quarterNum':None});batch=result['records']
                if not batch:break
                rows.extend(batch);offset+=len(batch)
                if offset>=result['total']:break
            else:raise ValueError('CBA event pagination incomplete')
            if not rows:raise ValueError('CBA play-by-play missing')
            events,unknown=parse_events(rows,players,g['score'],{s:g[s] for s in ('home','away')})
            qsec=max(r['minutes']*60+r['seconds'] for r in rows if r['quarterNum']==1)
            if qsec not in (600,720):raise ValueError('CBA period duration unavailable')
            g['events']=period_ends(events);g['report']=analyze(g['events'],players,g['score'],qsec,starters);g['pbpSource']=g['source'];g['periodSeconds']=qsec
            if unknown:
                g['report']['issues']['unparsed_events']=unknown;g['report']['key']=[];g['report']['keyPlayers']=[];g['report']['lineups']=[]
                # Block ATO when an event/clock/score cannot be reconstructed.
                g['report']['issues']['missing_clock']=unknown
            if g['report']['issues'].get('box_fga'):
                g['report']['issues']['missing_clock']=max(1,g['report']['issues'].get('missing_clock',0))
        except Exception as exc:g['detailError']=str(exc)[:160]
    g['advanced']=metrics(g);return g
