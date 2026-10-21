"""Australian NBL official Game Centre JSON, normalized to the shared archive.

UTC epoch schedule times are converted to Taipei. Only period=0 box scores
are full-game totals; event array position is never treated as chronology.
"""
from datetime import datetime,timezone
from urllib.parse import urlencode
from sources import js,basic,player,totals,period_ends,secs,TZ
from engine import analyze
from advanced import metrics

BASE='https://schedule.nbl.com.au'
def ident(value):return str(value.get('id','')) if isinstance(value,dict) else str(value or '')

def schedule(today):
    year=today.year-int(today.month<7)
    rows=js(BASE+'/api/calendar/schedule?league=NBL&year='+str(year)).get('matches')
    if not isinstance(rows,list) or not rows:raise ValueError('NBL official schedule empty or changed')
    out=[]
    for row in rows:
        if row.get('season_type') not in ('regular','playoffs','postseason'):continue
        stamp=row.get('starts_at_ms')
        if stamp is None:continue
        dt=datetime.fromtimestamp(stamp/1000,timezone.utc).astimezone(TZ)
        home,away=row['home'],row['away'];gid=str(row['id'])
        score=[row.get('home_score'),row.get('away_score')]
        score=[int(x) if x is not None else None for x in score]
        source=BASE+'/match?'+urlencode(dict(league='NBL',match=gid,year=year,season=row.get('season_id','')))
        g=basic('nbl',gid,dt.date().isoformat(),home['name'],away['name'],score,source,dt.strftime('%H:%M'))
        g.update(complete=row.get('phase')=='complete',season=str(year)+'–'+str(year+1)[-2:],competition='澳洲 NBL',periodSeconds=600,homeId=ident(home),awayId=ident(away))
        if g['complete'] and any(x is None for x in score):raise ValueError('NBL final score missing')
        out.append(g)
    return out

def normalize_events(rows,home_id,away_id):
    events=[];missing=0
    # IDs preserve the official action order, including same-clock substitutions.
    for r in sorted(rows,key=lambda r:int(r['action_id'])):
        kind=r.get('action_type');sub=r.get('sub_type','')
        action=None;points=0
        if kind in ('2pt','3pt'):
            if not isinstance(r.get('success'),bool):missing+=1;continue
            points=int(kind[0]) if r['success'] else 0;action=('FG' if r['success'] else 'M')+kind[0]
        elif kind=='freeThrow':
            if not isinstance(r.get('success'),bool):missing+=1;continue
            points=int(r['success']);action='FT' if points else 'FTX'
        elif kind=='substitution':action={'In':'IN','Out':'OUT'}.get(sub)
        elif kind=='rebound':action={'Offensive':'OREB','Defensive':'DREB'}.get(sub)
        elif kind=='period' and sub=='End':action='END'
        else:action={'assist':'AST','turnover':'TOV','steal':'STL','block':'BLK','timeOut':'TIMEOUT','foul':'FOUL'}.get(kind)
        if not action:continue
        q=r.get('period');clock=r.get('clock')
        if q is None or clock is None:missing+=1;continue
        tid=ident(r.get('team'));side='home' if tid==home_id else 'away' if tid==away_id else None
        if side is None and action!='END':missing+=1;continue
        p=r.get('player') or {}
        events.append(dict(period=int(q),sec=secs(clock),side=side,pid=ident(p) or str(r.get('personId') or ''),name=p.get('full_name',''),kind=action,pts=points))
    return events,missing

def parse_game(g,m,detail=True):
    if m.get('match_status')!='complete':raise ValueError('NBL game not completed')
    home_id,away_id=ident(m['home_team']),ident(m['away_team'])
    score=[int(m['home_score']),int(m['away_score'])]
    if g['score']!=score:raise ValueError('NBL schedule and box score mismatch')
    g['periodSeconds']=600
    players={};starters={}
    fields={'ftm':'free_throws_made','fta':'free_throws_attempted','assists':'assists','rebounds':'rebounds','steals':'steals','blocks':'blocks','offensive_rebounds':'offensive_rebounds','defensive_rebounds':'defensive_rebounds','three_made':'three_points_made','three_attempted':'three_points_attempted'}
    required=('points','field_goals_made','field_goals_attempted','turnovers')
    for side,tid in [('home',home_id),('away',away_id)]:
        rows=[r for r in m['player_match_statistics'] if str(r.get('period'))=='0' and ident(r.get('team'))==tid]
        if not rows:raise ValueError('NBL full-game player statistics missing')
        players[side]=[];starters[side]=[]
        for r in rows:
            played=bool(r.get('participated'));time=r.get('minutes')
            if played and (not time or any(r.get(k) is None for k in required)):raise ValueError('NBL active player statistics missing')
            p=r['player'];extra={k:r.get(v) for k,v in fields.items()}
            players[side].append(player(ident(p),p['full_name'],r.get('points'),r.get('field_goals_made'),r.get('field_goals_attempted'),r.get('turnovers'),time,**extra))
            if r.get('starter') is True:starters[side].append(ident(p))
    g['players']=players;g['stats']=totals(players)
    if [g['stats'][s]['points'] for s in ('home','away')]!=g['score']:raise ValueError('NBL player points and final score mismatch')
    for side,tid in [('home',home_id),('away',away_id)]:
        rows=[r for r in m['team_match_statistics'] if str(r.get('period'))=='0' and ident(r.get('team'))==tid]
        if len(rows)!=1 or int(rows[0]['points'])!=g['score'][0 if side=='home' else 1]:raise ValueError('NBL team totals missing or inconsistent')
        r=rows[0]
        for k,f in {'points':'points','fgm':'field_goals_made','fga':'field_goals_attempted','turnovers':'turnovers',**fields}.items():g['stats'][side][k]=r.get(f)
        # Team minutes are five players combined (200 in a 40-minute game).
        if r.get('minutes') is not None:g['stats'][side]['seconds']=float(r['minutes'])*60
    if detail:
        events,missing=normalize_events(m.get('play_by_play',[]),home_id,away_id)
        g['events']=period_ends(events);g['report']=analyze(g['events'],players,g['score'],600,starters)
        if missing or not events:
            g['report']['issues']['missing_clock']=max(1,missing)
            for k in ('key','keyPlayers','lineups'):g['report'][k]=[]
        g['pbpSource']=g['statsSource']
    g['advanced']=metrics(g)
    return g

def game(g,detail=True):
    url=BASE+'/api/calendar/match?'+urlencode(dict(match=g['id'],league='NBL'))
    g['statsSource']=url
    return parse_game(g,js(url)['match'],detail)
