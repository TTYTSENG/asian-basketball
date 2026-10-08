"""Deterministic analysis; substitutions are processed before the NEXT stint.

Events: period, sec, side, pid, name, kind, pts. Time counts DOWN.
No fabricated lineups, extrapolated medical fatigue or statistical significance.
"""
from collections import defaultdict, Counter

KINDS={'FG2','FG3','M2','M3','FT','FTX','AST','TOV','STL','BLK','OREB','DREB'}

def analyze(events, players, score, qsec, starters=None):
    court={s:set((starters or {}).get(s,[])) for s in ('home','away')}
    lineups={s:defaultdict(lambda:Counter(seconds=0,net=0)) for s in court}
    counts={s:defaultdict(Counter) for s in court}; clutch=defaultdict(Counter)
    total=Counter(home=0,away=0); issues=Counter(); previous=None; left=qsec
    def credit(dt):
        for s in court:
            if len(court[s])==5:lineups[s][tuple(sorted(court[s]))]['seconds']+=dt
            elif dt:issues['invalid_seconds']+=dt
    for e in events:
        q=e['period']; sec=e['sec']; side=e.get('side');pid=e.get('pid');kind=e.get('kind')
        if not q:continue
        if previous!=q:
            if previous is not None:credit(left)
            previous=q;left=qsec if q<=4 else 300
        if not 0<=sec<=(qsec if q<=4 else 300):issues['clock']+=1;continue
        if sec>left:issues['clock']+=1;sec=left
        credit(left-sec);left=sec
        if kind in ('IN','OUT'):
            if side and pid:
                if kind=='IN':court[side].add(pid)
                else:court[side].discard(pid)
            continue
        if kind not in KINDS:continue
        pts=e.get('pts',0);total[side]+=pts
        if pid:
            c=counts[side][pid];c['points']+=pts;c['turnovers']+=kind=='TOV'
            c['fgm']+=kind in ('FG2','FG3');c['fga']+=kind in ('FG2','FG3','M2','M3')
            c['assists']+=kind=='AST';c['steals']+=kind=='STL';c['blocks']+=kind=='BLK'
            if q==4 and 0<=sec<=300:
                c=clutch[(side,pid)];c['points']+=pts;c['assists']+=kind=='AST';c['steals']+=kind=='STL';c['blocks']+=kind=='BLK';c['turnovers']+=kind=='TOV'
            if pid not in court[side] and (pts or kind in ('M2','M3','FTX')):issues['absent_player']+=1
        if pts:
            for s in court:
                if len(court[s])==5:lineups[s][tuple(sorted(court[s]))]['net']+=pts if s==side else -pts
                else:issues['unknown_score']+=1
    if previous is not None:credit(left)
    if [total['home'],total['away']]!=list(score):issues['score']+=1
    # Published box score points/shot counts are an independent validation.
    for s in players:
        for p in players[s]:
            c=counts[s][p['id']]
            for k in ('points','fgm','fga','turnovers'):
                if int(p.get(k,0))!=c[k]:issues['box_'+k]+=1
    clean=bool(events) and not any(k!='box_turnovers' for k in issues)
    # A malformed clock affects the final-five-minute window as well.
    key=[];key_players=[]
    if events and not issues.get('score') and not issues.get('clock') and not any(k.startswith('box_') and k!='box_turnovers' for k in issues):
        ranked=sorted(clutch.items(),key=lambda x:(-x[1]['points'],-x[1]['assists'],-x[1]['steals'],-x[1]['blocks'],x[1]['turnovers'],x[0]))
        names={(s,p['id']):p['name'] for s in players for p in players[s]}
        for (s,pid),c in ranked[:3]:
            if not any(c.values()):continue
            tail=f"、{c['turnovers']} 失誤" if not issues.get('box_turnovers') else '（失誤紀錄需核對）'
            key.append(f"{names.get((s,pid),pid)}：{c['points']} 分、{c['assists']} 助攻、{c['steals']} 抄截、{c['blocks']} 阻攻"+tail)
            key_players.append(dict(name=names.get((s,pid),pid),side=s,**c,turnovers_valid=not issues.get('box_turnovers')))
    selected=[]
    if clean:
        for s in court:
            eligible=[(ids,c) for ids,c in lineups[s].items() if c['seconds']>=240]
            if len(eligible)>=2:
                best=max(eligible,key=lambda x:(x[1]['net'],x[1]['seconds'],x[0]));worst=min(eligible,key=lambda x:(x[1]['net'],-x[1]['seconds'],x[0]))
                if best[0]==worst[0]:continue
                for label,(ids,c) in [('最佳',best),('最差',worst)]:selected.append(dict(side=s,label=label,ids=list(ids),seconds=c['seconds'],net=c['net']))
    return {'key':key,'keyPlayers':key_players,'lineups':selected,'issues':dict(issues),'counts':counts}

def history_for(archive,league,pid,date,include=True):
    rows=[]
    for g in archive.values():
        if g['league']!=league or g['date']>date or (not include and g['date']==date):continue
        for ps in g.get('players',{}).values():
            for p in ps:
                if p['id']==pid and p.get('seconds',0)>0:rows.append(dict(date=g['date'],game=g['id'],**p))
    return sorted(rows,key=lambda x:(x['date'],x['game']),reverse=True)[:3]

def finalize(g,archive):
    report=g.get('report',{});key=report.get('key',[])
    first='；'.join(key) if key else '逐球資料或比分驗證不足，暫不判定。'
    lineup_text=[];display=[]
    for lu in report.get('lineups',[]):
        ps={p['id']:p for p in g['players'][lu['side']]}
        names=[ps[x]['name'] for x in lu['ids'] if x in ps]
        team=g[lu['side']];net=lu['net']
        lineup_text.append(f"{team} {lu['label']}：{'、'.join(names)}，共同 {lu['seconds']/60:.1f} 分鐘，淨得分 {net:+d}")
        display.append(dict(label=team+' '+lu['label'],team=team,kind=lu['label'],seconds=lu['seconds'],net=net,names=names,players=[dict(name=ps[x]['name'],history=history_for(archive,g['league'],x,g['date'])) for x in lu['ids'] if x in ps]))
    second='；'.join(lineup_text) or '尚無至少兩組共同上場四分鐘、且通過完整換人與比分驗證的五人組合。'
    changes=[];change_cards=[]
    for s,players in g.get('players',{}).items():
        for p in players:
            prev=history_for(archive,g['league'],p['id'],g['date'],False)
            if len(prev)<3 or p.get('seconds',0)<600:continue
            avg=sum(x['points'] for x in prev)/3;delta=p['points']-avg
            if abs(delta)>=8:
                change_cards.append(dict(name=p['name'],team=g[s],points=p['points'],average=avg,delta=delta,minutes=p['seconds']/60,previousMinutes=sum(x['seconds'] for x in prev)/180,fgm=p['fgm'],fga=p['fga']))
                changes.append((abs(delta),f"{p['name']} 本場 {p['points']} 分，較之前三場平均 {avg:.1f} 分{'增加' if delta>0 else '減少'} {abs(delta):.1f} 分；上場 {p['seconds']/60:.1f} 分鐘（之前平均 {sum(x['seconds'] for x in prev)/180:.1f} 分鐘），投籃 {p['fgm']}/{p['fga']}。此提示也可能受上場時間或對手影響。"))
    third=max(changes,key=lambda x:x[0])[1] if changes else '沒有符合門檻的得分變化，或球員之前三場實際出賽資料不足。門檻：本場至少十分鐘，得分相差至少八分。'
    g['analysis']=[['第四節最後五分鐘的關鍵球員',first],['五人組合與個人近三場',second],['球員特殊變化提示',third]];g['lineups']=display
    g['keyPlayers']=report.get('keyPlayers',[])
    g['playerChanges']=sorted(change_cards,key=lambda x:abs(x['delta']),reverse=True)[:1]
    issues=report.get('issues',{})
    labels={'absent_player':'出手球員不在重建陣容','score':'逐球得分與正式比分不符','clock':'事件時間倒退','missing_clock':'缺少事件時間','invalid_seconds':'陣容人數不足的秒數','unknown_score':'陣容不明的得分事件','box_points':'球員得分不符','box_fgm':'球員命中數不符','box_fga':'球員出手數不符','box_turnovers':'球員失誤紀錄不符'}
    g['quality']='逐球與官方比分／個人主要數據已對帳。' if report and not issues else '資料驗證限制：'+('、'.join(f'{labels.get(k,k)} {v}' for k,v in issues.items()) or '尚未取得逐球資料')+'；受影響指標停止判定。'
    if g.get('clockCorrections'):g['quality']+=f" 官方事件時間不一致，按事件順序校正 {g['clockCorrections']} 筆；共同上場時間為重建值。"
    if g.get('identityCorrections'):g['quality']+=f" 以官方名單中唯一相同姓名校正背號／隊別 {g['identityCorrections']} 筆。"
    return g
