"""Transparent single-game metrics. No inferred optical tracking or fake VORP."""

def observation_metrics(g):
    """Publish auditable box-score ratios; missing inputs remain unavailable."""
    stats=g.get('stats',{});warnings=[];teams={}
    def ratio(n,d):return 100*n/d if n is not None and d is not None and d>0 else None
    for side in ('home','away'):
        t=stats.get(side,{});opp=stats.get('away' if side=='home' else 'home',{})
        pts,fgm,fga,ftm,fta=(t.get(k) for k in ('points','fgm','fga','ftm','fta'))
        m3,a3=t.get('three_made'),t.get('three_attempted')
        valid_shots=all(v is not None and v>=0 for v in (fgm,fga,m3,a3)) and m3<=a3<=fga and m3<=fgm<=fga
        if valid_shots and pts is not None and ftm is not None:
            valid_shots=pts==2*fgm+m3+ftm
        if m3 is not None and not valid_shots:warnings.append(side+'：投籃欄位未通過一致性核對')
        reb=t.get('offensive_rebounds');dreb=t.get('defensive_rebounds')
        orebd=reb+opp['defensive_rebounds'] if reb is not None and opp.get('defensive_rebounds') is not None else None
        drebd=dreb+opp['offensive_rebounds'] if dreb is not None and opp.get('offensive_rebounds') is not None else None
        tsden=2*(fga+.44*fta) if fga is not None and fta is not None else None
        teams[side]=dict(ts=ratio(pts,tsden),fta_rate=ratio(fta,fga),
            assisted_fg_pct=ratio(t.get('assists'),fgm),ft_points_pct=ratio(ftm,pts),
            efg=ratio(fgm+.5*m3,fga) if valid_shots else None,
            three_attempt_pct=ratio(a3,fga) if valid_shots else None,
            three_points_pct=ratio(3*m3,pts) if valid_shots else None,
            oreb_pct=ratio(reb,orebd),dreb_pct=ratio(dreb,drebd),
            paint_points=t.get('paint_points'),second_chance_points=t.get('second_chance_points'),
            fast_break_points=t.get('fast_break_points'),off_rating_est=None,tov_pct_est=None,
            source_counts={k:t.get(k) for k in ('points','fgm','fga','three_made','three_attempted','ftm','fta','assists','turnovers','offensive_rebounds','defensive_rebounds')})
    poss=[]
    for side in ('home','away'):
        t=stats.get(side,{})
        if all(t.get(k) is not None and t[k]>=0 for k in ('fga','offensive_rebounds','turnovers','fta')):
            poss.append(t['fga']-t['offensive_rebounds']+t['turnovers']+.44*t['fta'])
    estimate=sum(poss)/2 if len(poss)==2 and min(poss)>0 else None
    for side in teams:
        teams[side]['off_rating_est']=ratio(stats.get(side,{}).get('points'),estimate)
        teams[side]['tov_pct_est']=ratio(stats.get(side,{}).get('turnovers'),estimate)
    duration=g.get('periodSeconds')
    regulation=4*duration/60 if duration in (600,720) else (40 if g.get('league')=='b' else 48 if g.get('league') in ('tpbl','plg') else None)
    return dict(teams=teams,possessions_est=estimate,regulation_minutes=regulation,
                warnings=warnings,method='回合為雙方(FGA−ORB＋TOV＋0.44×FTA)平均估計；不是官方逐回合或追蹤數據。TS%同樣使用0.44估計係數。')
def usage(p,team):
    required=('fta','fga','turnovers','seconds')
    if any(p.get(k) is None or team.get(k) is None for k in required):return None
    denominator=team['fga']+.44*team['fta']+team['turnovers']
    if p['seconds']<=0 or team['seconds']<=0 or denominator<=0:return None
    # Conventional box-score USG estimate, with team playing time / 5.
    return 100*(p['fga']+.44*p['fta']+p['turnovers'])*(team['seconds']/5)/(p['seconds']*denominator)

def ato_sequences(events,issues=None):
    """First identifiable possession after each timeout, fail closed on ambiguity.

    Made baskets wait through same-clock and-one free throws. Offensive boards
    extend the possession. FT-first, period-only and missing turnover boundaries
    are excluded rather than invented. Timeout caller is not presumed offense.
    """
    records=[];pending=None;quarter=None
    def finish(reason=None):
        nonlocal pending
        if pending is None:return
        r=pending;r['eligible']=reason is None;r['exclusion']=reason
        if reason is None:r['offensive_success']=r['points']>0;r['defensive_success']=r['points']==0
        r.pop('made',None);r.pop('first_shot',None);r.pop('last_sec',None);records.append(r);pending=None
    for e in events:
        q=e['period'];kind=e['kind'];side=e.get('side');sec=e['sec']
        if pending and q!=quarter:
            finish(None if pending.get('made') else '跨節且回合未能完整辨識')
        quarter=q
        if pending and pending.get('made') and sec<pending['last_sec']:
            finish()
        if kind=='TIMEOUT':
            if pending:finish(None if pending.get('made') else '下一次暫停前未能完整辨識')
            pending=dict(period=q,timeout_sec=sec,timeout_side=side,offense=None,defense=None,points=0,turnovers=0,finisher=None,inbounder=None,receiver=None,first_shot=False,made=False,last_sec=sec)
            continue
        if pending is None:continue
        if kind in ('IN','OUT','AST','STL','BLK','FOUL'):continue
        if kind=='END':finish(None if pending.get('made') else '節末回合結果未能完整辨識');continue
        if pending['offense'] is None:
            if kind in ('FT','FTX'):
                finish('暫停後先出現罰球，無法確認新進攻回合起點');continue
            if kind in ('DREB','OREB'):
                finish('暫停後先出現籃板，無法確認新進攻回合起點');continue
            if kind not in ('FG2','FG3','M2','M3','TOV'):continue
            if side not in ('home','away'):finish('缺少進攻隊別');continue
            pending['offense']=side;pending['defense']='away' if side=='home' else 'home'
        offense=pending['offense']
        if pending['made']:
            if kind in ('FT','FTX') and side==offense and sec==pending['last_sec']:
                pending['points']+=e.get('pts',0);pending['finisher']=e.get('pid') or pending['finisher'];continue
            if kind in ('FG2','FG3','M2','M3','TOV','FT','FTX','DREB','OREB'):finish();continue
        if kind=='TOV' and side==offense:
            pending['turnovers']=1;pending['finisher']=e.get('pid') or None;finish();continue
        if kind in ('FG2','FG3','M2','M3'):
            if side!=offense:finish('缺少明確的球權轉換紀錄');continue
            if pending['first_shot']:finish('未記錄進攻籃板，無法確認是否同一回合');continue
            pending['first_shot']=True;pending['finisher']=e.get('pid') or None;pending['last_sec']=sec
            if kind in ('FG2','FG3'):pending['points']+=e.get('pts',0);pending['made']=True
        elif kind=='OREB' and side==offense:pending['first_shot']=False
        elif kind=='DREB' and side!=offense:finish()
        elif kind in ('FT','FTX'):finish('未提供足以確認罰球歸屬的進攻回合資料')
    if pending:finish(None if pending.get('made') else '逐球結尾缺少完整回合結果')
    # Timing corrections are disclosed separately; missing clocks or bad scoring
    # make these sequences unsuitable for a success-rate comparison.
    if issues and any(issues.get(k) for k in ('score','clock','missing_clock','box_points','box_fgm','box_turnovers')):
        for r in records:r['eligible']=False;r['exclusion']='逐球得分、時間或失誤驗證不足';r.pop('offensive_success',None);r.pop('defensive_success',None)
    summaries=[]
    for side in ('home','away'):
        attack=[r for r in records if r['eligible'] and r['offense']==side];defense=[r for r in records if r['eligible'] and r['defense']==side]
        summaries.append(dict(side=side,attack_n=len(attack),attack_success=sum(r['offensive_success'] for r in attack),defense_n=len(defense),defense_success=sum(r['defensive_success'] for r in defense),points=sum(r['points'] for r in attack),turnovers=sum(r['turnovers'] for r in attack)))
    return dict(records=records,summary=summaries,excluded=sum(not r['eligible'] for r in records),total=len(records))

def metrics(g):
    output=[]
    for side,ps in g.get('players',{}).items():
        team=g.get('stats',{}).get(side,{})
        for p in ps:
            if p.get('seconds',0)<=0:continue
            eff=None
            if all(p.get(k) is not None for k in ('rebounds','assists','steals','blocks','fta','ftm')):
                eff=p['points']+p['rebounds']+p['assists']+p['steals']+p['blocks']-(p['fga']-p['fgm'])-(p['fta']-p['ftm'])-p['turnovers']
            ast=p.get('assists');tov=p.get('turnovers');ratio=ast/tov if ast is not None and tov else None
            output.append(dict(id=p['id'],side=side,name=p['name'],seconds=p['seconds'],points=p['points'],usg=usage(p,team),eff=eff,assists=ast,turnovers=tov,ast_to=ratio,potential_assists=None,passes_made=None,passes_received=None,secondary_assists=None,vorp=None))
    eligible=[p for p in output if p['seconds']>=600 and p['eff'] is not None]
    benchmark=max(eligible,key=lambda p:(p['eff'],p['points'],-p['turnovers'],p['id'])) if eligible else None
    return dict(players=sorted(output,key=lambda p:(p['side'],-(p['usg'] or 0),p['id'])),benchmark=benchmark,observation=observation_metrics(g),
        benchmark_method='本場 EFF 最高且至少上場十分鐘的球員；EFF 是傳統綜合效率，不是整體能力排名。',
        tracking_status='官網逐球沒有完整的傳球者、接球者與傳球鏈，潛在助攻、傳出／接球次數及次級助攻尚不可計算；不以助攻次數代替。',
        vorp_status='尚無適用 TPBL、P+、B.LEAGUE 且完成驗證的 BPM 模型、替補基準與完整賽季球權資料，暫不計算 VORP；不把單場正負值當作 BPM。',
        ato=ato_sequences(g.get('events',[]),g.get('report',{}).get('issues',{})))
