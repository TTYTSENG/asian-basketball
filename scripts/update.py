"""Refresh official schedules, box scores, news and reproducible daily reports."""
import argparse,json,copy,sys
from pathlib import Path
from datetime import datetime,timedelta
from concurrent.futures import ThreadPoolExecutor,as_completed
from sources import TZ,tpbl_schedule,plg_schedule,b_schedule,tpbl_game,plg_game,b_game,news,cba_news
from engine import finalize
from database import bootstrap,archive as db_archive,snapshot,persist,export

ROOT=Path(__file__).resolve().parents[1];DATA=ROOT/'data'
CONFIG=[('tpbl','TPBL','https://tpbl.basketball/schedule',tpbl_schedule,tpbl_game),('plg','P. LEAGUE+','https://pleagueofficial.com/schedule-regular-season',plg_schedule,plg_game),('b','日本 B.LEAGUE（最高級別）','https://www.bleague.jp/schedule/',b_schedule,b_game)]
GUIDES=[
 {'name':'TPBL','description':'臺灣職業籃球聯盟，以主客場例行賽與季後賽競逐冠軍。每節十二分鐘；賽季隊伍、球員註冊與季後賽資格以當季官方章程為準。','links':[{'label':'聯盟與賽制／官方首頁','url':'https://tpbl.basketball/'},{'label':'球隊與球員資料','url':'https://tpbl.basketball/teams'},{'label':'官方戰績','url':'https://tpbl.basketball/standings'}]},
 {'name':'P. LEAGUE+','description':'臺灣職業籃球聯盟，賽事包含例行賽與季後賽。每節十二分鐘，當季參賽隊伍與賽務章程由聯盟公布。','teams':['臺北富邦勇士','桃園璞園領航猿','洋基工程','台鋼獵鷹'],'links':[{'label':'聯盟介紹','url':'https://pleagueofficial.com/about'},{'label':'當季賽務章程','url':'https://pleagueofficial.com/rulebook'},{'label':'球隊資料','url':'https://pleagueofficial.com/#team'},{'label':'球員資料','url':'https://pleagueofficial.com/all-players'},{'label':'官方戰績','url':'https://pleagueofficial.com/standings'}]},
 {'name':'日本 B.LEAGUE','description':'日本男子職業籃球聯盟。2026–27 起採 B.PREMIER、B.ONE 與 B.NEXT 架構；本頁賽程以最高級別為主。每節十分鐘，賽季賽制與俱樂部名單以官方公布為準。','links':[{'label':'聯盟介紹','url':'https://www.bleague.jp/about/'},{'label':'賽制與分級','url':'https://www.bleague.jp/regulation/'},{'label':'俱樂部資料','url':'https://www.bleague.jp/club/'},{'label':'球員資料','url':'https://www.bleague.jp/roster/'},{'label':'官方排名','url':'https://www.bleague.jp/standings/'}]},
 {'name':'EASL 東亞超級聯賽','description':'亞洲俱樂部跨聯盟競賽，以分組與決賽階段競逐冠軍。參賽席次、球隊與賽程依各季公告更新。','links':[{'label':'官方賽程、球隊與賽制','url':'https://www.easl.basketball/'},{'label':'官方戰報','url':'https://www.easl.basketball/news'}]},
 {'name':'CBA','description':'中國男子職業籃球聯賽，包含例行賽與季後賽。隊伍、球員註冊、積分及季後賽規則請以當季官方公告為準。','links':[{'label':'聯盟與球隊資料','url':'https://www.cbaleague.com/'},{'label':'官方球員與比賽數據','url':'https://www.cbaleague.com/data/#/'},{'label':'官方新聞','url':'https://www.cbaleague.com/#/news'}]},
 {'name':'FIBA 亞洲國際賽事','description':'國家代表隊賽事，關注亞洲盃與世界盃亞洲區資格賽。資格賽依窗口舉行，決賽以分組及淘汰階段進行；分組、球員名單與晉級方式以各屆賽事公告為準。','links':[{'label':'FIBA 亞洲賽事入口','url':'https://www.fiba.basketball/en/regions/asia'},{'label':'2027 世界盃亞洲區資格賽','url':'https://www.fiba.basketball/en/events/fiba-basketball-world-cup-2027-asian-qualifiers'},{'label':'2025 亞洲盃資料庫','url':'https://www.fiba.basketball/en/events/fiba-asiacup-2025'}]}
]

def load(path,default):
    return json.loads(path.read_text(encoding='utf8')) if path.exists() else default
def write(path,data):
    path.parent.mkdir(parents=True,exist_ok=True);temp=path.with_suffix('.tmp');temp.write_text(json.dumps(data,ensure_ascii=False,indent=2),encoding='utf8');temp.replace(path)
def run(today):
    conn=bootstrap();now=datetime.now(TZ).isoformat(timespec='seconds');old=snapshot(conn) or {};archive=db_archive(conn);old_leagues={x['id']:x for x in old.get('leagues',[])};leagues=[];errors=[];schedules={}
    for lid,name,url,schedule,game in CONFIG:
        print('Updating',name,flush=True)
        previous=old_leagues.get(lid,{});league=dict(id=lid,name=name,source=url,upcoming=[],recent=[])
        try:
            allgames=schedule(today);schedules[lid]=allgames;done=sorted([g for g in allgames if g['complete'] and g['date']<=today.isoformat()],key=lambda g:(g['date'],g['time'],g['id']),reverse=True)
            league['upcoming']=sorted([g for g in allgames if not g['complete'] and today.isoformat()<=g['date']<=(today+timedelta(days=6)).isoformat()],key=lambda g:(g['date'],g['time'],g['id']))
            latest=done[:5];wanted={g['id']:(g,True) for g in latest}
            # Bootstrap histories for teams appearing in the three displayed reports.
            # For each report include its teams' last three matches before it.
            for recent in latest[:3]:
                for team in (recent['home'],recent['away']):
                    prior=[g for g in done if g['date']<recent['date'] and team in (g['home'],g['away'])][:3]
                    for g in prior:wanted.setdefault(g['id'],(g,False))
            with ThreadPoolExecutor(max_workers=3) as pool:
                pending={}
                for gid,(g,detail) in wanted.items():
                    key=lid+':'+gid;cached=archive.get(key)
                    # Recent games are refreshed to pick up official corrections.
                    if cached and cached.get('advanced') and cached.get('players') and not detail:continue
                    pending[pool.submit(game,copy.deepcopy(g),detail)]=(key,g)
                for future in as_completed(pending):
                    key,g=pending[future]
                    try:archive[key]=future.result()
                    except Exception as exc:
                        print('Game unavailable',key,str(exc)[:200],flush=True);errors.append(key)
                        if key not in archive:archive[key]={**g,'detailError':str(exc)[:150]}
            for g in latest:
                obj=copy.deepcopy(archive.get(lid+':'+g['id'],g));league['recent'].append(finalize(obj,archive))
            league['lastSuccess']=now
            bad=[g for g in league['recent'] if not g.get('players')]
            if bad:league['error']=f'{len(bad)} 場詳細統計尚未取得；將在下次更新重試。'
            if lid=='tpbl':GUIDES[0]['teams']=sorted(set(g[s] for g in allgames for s in ('home','away')))
            guide=next(x for x in GUIDES if x['name']==({'tpbl':'TPBL','plg':'P. LEAGUE+','b':'日本 B.LEAGUE'}[lid]))
            if lid=='b':guide['teams']=sorted(set(g[s] for g in allgames for s in ('home','away')))
            guide['players']=list(dict.fromkeys(p['name'] for g in latest[:3] for ps in archive.get(lid+':'+g['id'],{}).get('players',{}).values() for p in ps if p.get('seconds',0)>0))[:8]
        except Exception as exc:
            print('League failed',name,str(exc)[:200],flush=True);errors.append(lid)
            if previous:league=copy.deepcopy(previous)
            league['error']='官方來源暫時無法讀取；保留上次成功資料，待下次排程重試。'
        leagues.append(league)
    feeds=[('EASL 東超','https://www.easl.basketball/news',lambda:news('EASL 東超','https://www.easl.basketball/news')),('CBA','https://www.cbaleague.com/#/news',cba_news),('FIBA 亞洲賽事','https://www.fiba.basketball/en/events/fiba-basketball-world-cup-2027-asian-qualifiers/news',lambda:news('FIBA 亞洲賽事','https://www.fiba.basketball/en/events/fiba-basketball-world-cup-2027-asian-qualifiers/news'))]
    old_news={x['name']:x for x in old.get('news',[])};news_items=[]
    for name,url,fetch in feeds:
        try:x=fetch();x['lastSuccess']=now
        except Exception as exc:
            print('News failed',name,str(exc)[:200],flush=True);errors.append(name);x=copy.deepcopy(old_news.get(name,dict(name=name,source=url,items=[])));x['error']='官方新聞暫時無法取得，請使用官方入口。'
        news_items.append(x)
    for g in leagues:
        for recent in g['recent']:recent.pop('players',None);recent.pop('report',None);recent.pop('events',None)
    site=dict(generatedAt=now,asOf=today.isoformat(),leagues=leagues,news=news_items,guides=GUIDES,errors=errors)
    persist(conn,archive,site,schedules);export(conn,DATA);conn.close()
    # Archive a date-stamped daily report. Bounded retention keeps the free repo small.
    daily=DATA/'reports'
    for path in sorted(daily.glob('*.json'))[:-90]:path.unlink()
    print('Updated',len(archive),'archived games; issues:',errors,flush=True)
    return errors
if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--date',help='YYYY-MM-DD, for reproducible source tests');args=parser.parse_args()
    today=datetime.strptime(args.date,'%Y-%m-%d').date() if args.date else datetime.now(TZ).date();run(today)
