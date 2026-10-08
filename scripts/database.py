"""SQLite persistence and backward-compatible static website exports.

All imports are one transaction. Official game/player IDs are scoped by league.
SQLite is kept in the repository by Actions and never copied to public/.
"""
import argparse,hashlib,json,sqlite3
from pathlib import Path
from datetime import datetime,timezone

ROOT=Path(__file__).resolve().parents[1]
DB=ROOT/'data/basketball.sqlite3'
def dumps(value):return json.dumps(value,ensure_ascii=False,separators=(',',':'))
def team_key(name):return hashlib.sha256(name.encode('utf8')).hexdigest()[:20]
def connect(path=DB):
    path=Path(path);path.parent.mkdir(parents=True,exist_ok=True)
    conn=sqlite3.connect(path);conn.row_factory=sqlite3.Row
    conn.execute('PRAGMA foreign_keys=ON');conn.execute('PRAGMA busy_timeout=5000')
    conn.executescript((Path(__file__).with_name('schema.sql')).read_text(encoding='utf8'))
    return conn
def snapshot(conn,key='site'):
    row=conn.execute('SELECT payload_json FROM snapshots WHERE snapshot_key=?',(key,)).fetchone()
    return json.loads(row[0]) if row else None
def archive(conn):
    return {r['league_id']+':'+r['game_id']:json.loads(r['payload_json']) for r in conn.execute('SELECT league_id,game_id,payload_json FROM games WHERE has_detail=1')}
def put_game(conn,g,stamp,detail=False):
    lid=g['league'];gid=str(g['id'])
    for side in ('home','away'):
        conn.execute('INSERT OR IGNORE INTO teams VALUES(?,?,?)',(lid,team_key(g[side]),g[side]))
    old=conn.execute('SELECT has_detail FROM games WHERE league_id=? AND game_id=?',(lid,gid)).fetchone()
    # A schedule-only record must not erase an existing completed box score.
    if old and old[0] and not detail:return
    score=g.get('score',[None,None]);complete=all(isinstance(x,int) for x in score) and (g.get('complete') or sum(score)>0)
    conn.execute('''INSERT INTO games VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)
        ON CONFLICT(league_id,game_id) DO UPDATE SET
        game_date=excluded.game_date,game_time=excluded.game_time,
        home_team_key=excluded.home_team_key,away_team_key=excluded.away_team_key,
        home_score=excluded.home_score,away_score=excluded.away_score,
        completed=excluded.completed,has_detail=excluded.has_detail,
        official_url=excluded.official_url,payload_json=excluded.payload_json,imported_at=excluded.imported_at''',
        (lid,gid,g['date'],g.get('time',''),team_key(g['home']),team_key(g['away']),*score,int(bool(complete)),int(detail),g['source'],dumps(g),stamp))
    for role,field in [('game','source'),('statistics','statsSource'),('play_by_play','pbpSource')]:
        if g.get(field):conn.execute('INSERT OR REPLACE INTO game_sources VALUES(?,?,?,?)',(lid,gid,role,g[field]))
    if not detail:return
    # Replace one game's child rows to apply official corrections, including DNP.
    conn.execute('DELETE FROM player_game_stats WHERE league_id=? AND game_id=?',(lid,gid))
    for side,ps in g.get('players',{}).items():
        for p in ps:
            pid=str(p['id']);conn.execute('INSERT INTO players VALUES(?,?,?) ON CONFLICT(league_id,player_id) DO UPDATE SET name=excluded.name',(lid,pid,p['name']))
            conn.execute('INSERT INTO player_game_stats VALUES(?,?,?,?,?,?,?,?,?)',(lid,gid,pid,side,p['points'],p['fgm'],p['fga'],p['turnovers'],p['seconds']))
    conn.execute('DELETE FROM lineup_stats WHERE league_id=? AND game_id=?',(lid,gid))
    for lu in g.get('report',{}).get('lineups',[]):
        cursor=conn.execute('INSERT INTO lineup_stats(league_id,game_id,side,label,seconds,net_points) VALUES(?,?,?,?,?,?)',(lid,gid,lu['side'],lu['label'],lu['seconds'],lu['net']))
        for pid in lu['ids']:conn.execute('INSERT INTO lineup_members VALUES(?,?,?)',(cursor.lastrowid,lid,str(pid)))
    conn.execute('DELETE FROM player_advanced_stats WHERE league_id=? AND game_id=?',(lid,gid))
    raw={p['id']:p for ps in g.get('players',{}).values() for p in ps}
    for p in g.get('advanced',{}).get('players',[]):
        box=raw.get(p['id'],{})
        values=[box.get(k) for k in ('ftm','fta','assists','rebounds','steals','blocks')]+[p.get(k) for k in ('usg','eff','ast_to','potential_assists','passes_made','passes_received','secondary_assists','vorp')]
        conn.execute('INSERT INTO player_advanced_stats VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)',(lid,gid,p['id'],*values))
    conn.execute('DELETE FROM ato_sequences WHERE league_id=? AND game_id=?',(lid,gid))
    for n,r in enumerate(g.get('advanced',{}).get('ato',{}).get('records',[]),1):
        conn.execute('INSERT INTO ato_sequences VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?)',(lid,gid,n,r['period'],r['timeout_sec'],r['offense'],r['defense'],r['points'],r['turnovers'],int(r['eligible']),r['exclusion'],r['inbounder'],r['receiver'],r['finisher']))
def persist(conn,games,site,schedules=None):
    stamp=datetime.now(timezone.utc).isoformat(timespec='seconds');generated=site['generatedAt']
    with conn:
        for l in site['leagues']:conn.execute('INSERT OR REPLACE INTO leagues VALUES(?,?,?)',(l['id'],l['name'],l['source']))
        for lid,name,url in [('easl','EASL 東超','https://www.easl.basketball/'),('cba','CBA','https://www.cbaleague.com/'),('fiba','FIBA 亞洲賽事','https://www.fiba.basketball/')]:conn.execute('INSERT OR REPLACE INTO leagues VALUES(?,?,?)',(lid,name,url))
        for g in games.values():put_game(conn,g,stamp,detail=True)
        for league in site['leagues']:
            for g in league['upcoming']+league['recent']:put_game(conn,g,stamp)
            for g in league['recent']:
                conn.execute('DELETE FROM game_analyses WHERE league_id=? AND game_id=?',(league['id'],str(g['id'])))
                for n,(title,content) in enumerate(g.get('analysis',[]),1):
                    conn.execute('INSERT INTO game_analyses VALUES(?,?,?,?,?,?,?)',(league['id'],str(g['id']),n,title,content,g.get('quality',''),generated))
        for rows in (schedules or {}).values():
            for g in rows:put_game(conn,g,stamp)
        news_ids={'EASL 東超':'easl','CBA':'cba','FIBA 亞洲賽事':'fiba'}
        for feed in site.get('news',[]):
            for item in feed['items']:
                conn.execute('''INSERT INTO news_articles VALUES(?,?,?,?,?,?) ON CONFLICT(league_id,url) DO UPDATE SET
                    title=excluded.title,published_date=excluded.published_date,last_seen_at=excluded.last_seen_at''',
                    (news_ids[feed['name']],item['url'],item['title'],item.get('date'),stamp,stamp))
        for key in ('site','report:'+site['asOf']):conn.execute('INSERT OR REPLACE INTO snapshots VALUES(?,?,?)',(key,dumps(site),generated))
        conn.execute('INSERT INTO update_runs(generated_at,imported_at,source_errors_json) VALUES(?,?,?)',(generated,stamp,dumps(site.get('errors',[]))))
        check(conn)  # Validate before COMMIT; invalid aggregate scores roll back too.
def export(conn,directory=ROOT/'data'):
    directory=Path(directory);directory.mkdir(parents=True,exist_ok=True);site=snapshot(conn)
    if site is None:raise ValueError('Database contains no website snapshot')
    for path,value in [(directory/'site.json',site),(directory/'archive.json',archive(conn)),(directory/'reports'/(site['asOf']+'.json'),site)]:
        path.parent.mkdir(parents=True,exist_ok=True);temp=path.with_suffix('.tmp');temp.write_text(json.dumps(value,ensure_ascii=False,indent=2),encoding='utf8');temp.replace(path)
def bootstrap(path=DB,directory=ROOT/'data'):
    conn=connect(path)
    if snapshot(conn) is None:
        directory=Path(directory)
        site=json.loads((directory/'site.json').read_text(encoding='utf8'))
        games=json.loads((directory/'archive.json').read_text(encoding='utf8'))
        persist(conn,games,site)
    return conn
def check(conn):
    assert conn.execute('PRAGMA integrity_check').fetchone()[0]=='ok'
    assert not conn.execute('PRAGMA foreign_key_check').fetchall()
    bad=conn.execute('''SELECT g.league_id,g.game_id FROM games g JOIN player_game_stats s
        USING(league_id,game_id) GROUP BY g.league_id,g.game_id HAVING
        SUM(CASE WHEN s.side='home' THEN s.points ELSE 0 END)!=g.home_score OR
        SUM(CASE WHEN s.side='away' THEN s.points ELSE 0 END)!=g.away_score''').fetchall()
    assert not bad,[(r[0],r[1]) for r in bad]
    return {t:conn.execute('SELECT COUNT(*) FROM '+t).fetchone()[0] for t in ['leagues','teams','players','games','player_game_stats','lineup_stats','game_analyses','news_articles','update_runs','insights','player_advanced_stats','ato_sequences']}
if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--export',action='store_true');args=parser.parse_args()
    with bootstrap() as conn:
        print(json.dumps(check(conn),ensure_ascii=False,indent=2))
        if args.export:export(conn)
