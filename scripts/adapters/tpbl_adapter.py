#!/usr/bin/env python3
"""TPBL 逐球 JSON (api/games/<id>/broadcasts) -> daily_report.py 用的事件 CSV；可用 stats.json 對帳。
用法: python tpbl_adapter.py broadcasts.json --stats stats.json --game-id 1489 --date 2026-04-26 --out events_tpbl.csv [--append]
"""
import csv, json, argparse
from collections import defaultdict, Counter

Q_SEC = 720  # TPBL 每節12分鐘；延長賽5分鐘
FIELDS = ['game_id', 'date', 'home', 'away', 'period', 'sec_left', 'team', 'player', 'event', 'pts',
          'home_score', 'away_score', 'lu_home', 'lu_away', 'q_sec']

def event_map(e):
    t, o = e['event_type'], e['event_outcome']
    made = o in ('Made', 'AndOne')
    if t == 'TwoPointer': return ('FG2', 2) if made else ('M2', 0)
    if t == 'ThreePointer': return ('FG3', 3) if made else ('M3', 0)
    if t == 'FreeThrow': return ('FT', 1) if made else ('FTX', 0)
    if t == 'Rebound': return ('OREB' if o == 'Offensive' else 'DREB', 0)
    return {'Assist': ('AST', 0), 'Steal': ('STL', 0), 'Block': ('BLK', 0), 'Turnover': ('TOV', 0)}.get(t)

def clean_clock(ev):
    """時間欄位偶有人工輸入的離群值(例如罰球時間比犯規還早)。每節找「最長的非遞增序列」當可信時間，其餘事件沿用前一個可信時間。"""
    byq, left, fixed = defaultdict(list), [round(e['event_quarter_time'] / 1000) for e in ev], 0
    for i, e in enumerate(ev): byq[e['quarter']].append(i)
    for q, idx in byq.items():
        v = [left[i] for i in idx]; n = len(v); best, prev = [1] * n, [-1] * n
        for j in range(n):
            for i in range(j):
                if v[i] >= v[j] and best[i] + 1 > best[j]: best[j], prev[j] = best[i] + 1, i
        k, keep = max(range(n), key=lambda j: best[j]), set()
        while k != -1: keep.add(k); k = prev[k]
        cur = Q_SEC if q <= 4 else 300
        for j, i in enumerate(idx):
            if j in keep: cur = v[j]
            else: left[i] = cur; fixed += 1
    return left, fixed

def convert(b, game_id, date):
    ev = sorted((e for r in b['rounds'] for e in r['events']), key=lambda e: e['order'])
    lefts, nfix = clean_clock(ev)
    cp = ev[0]['current_points']; hid, aid = cp['home_team']['id'], cp['away_team']['id']
    home, away = cp['home_team']['name'], cp['away_team']['name']
    side_of = {hid: 'home', aid: 'away'}; name = {}
    court = {'home': set(), 'away': set()}; run = [0, 0]; out = []; qa = defaultdict(list); ended = set()
    last_left = {}; last_q = None
    box = defaultdict(Counter)      # (player_id, round) 事件累加的 box score，用來對帳
    sec = defaultdict(float)        # (player_id, round) 上場秒數
    pm = defaultdict(int)           # (player_id, round) +/-
    def credit(q, left):  # 把上一個時間點到現在的秒數記給場上球員
        dt = max(0, last_left.get(q, Q_SEC if q <= 4 else 300) - left)
        for s in court:
            for p in court[s]: sec[(p, q)] += dt
    def emit(q, left, side, player, evn, pts):
        out.append(dict(game_id=game_id, date=date, home=home, away=away, period=q, sec_left=left, team=(home, away)[side == 'away'],
                        player=player, event=evn, pts=pts, home_score=run[0], away_score=run[1],
                        lu_home='|'.join(sorted(name[p] for p in court['home'])),
                        lu_away='|'.join(sorted(name[p] for p in court['away'])), q_sec=Q_SEC))
    if nfix: qa['時間離群值已校正'].append(nfix)
    for i, e in enumerate(ev):
        q = e['quarter']; left = lefts[i]
        if last_q is not None and q != last_q and last_q not in ended:  # 上一節收尾
            credit(last_q, 0); emit(last_q, 0, 'home', '', 'END', 0); ended.add(last_q)
        last_q = q
        credit(q, left); last_left[q] = left
        if e['event_type'] == 'Rotation' and left == 0 and q not in ended:  # 節末全員離場前先收尾，才記得到場上5人
            emit(q, 0, 'home', '', 'END', 0); ended.add(q)
        p = e.get('player'); side = side_of[e['team']['id']]
        if p: name[p['id']] = p['name']
        if e['event_type'] == 'Rotation':
            (court[side].add if e['event_outcome'] == 'Entering' else court[side].discard)(p['id']); continue
        m = event_map(e)
        if not m: continue
        evn, pts = m
        if any(len(court[s]) != 5 for s in court): qa['場上人數≠5'].append((q, left))
        if p and p['id'] not in court[side]: qa['球員不在場上'].append((q, left, p['name'], evn))
        emit(q, left, side, p['name'] if p else '', evn, pts)
        if pts:
            run[side == 'away'] += pts
            for s in court:
                for pid in court[s]: pm[(pid, q)] += pts if s == side else -pts
        if p:
            c = box[(p['id'], q)]; c['score'] += pts
            if evn in ('FG2', 'FG3', 'M2', 'M3'): c['fga'] += 1; c['fgm'] += evn[0] == 'F'
            if evn in ('FG3', 'M3'): c['3pa'] += 1; c['3pm'] += evn == 'FG3'
            if evn in ('FT', 'FTX'): c['fta'] += 1; c['ftm'] += evn == 'FT'
            if evn in ('OREB', 'DREB'): c['reb'] += 1
            if evn in ('AST', 'STL', 'BLK', 'TOV'): c[evn.lower()] += 1
    credit(last_q, 0)
    if last_q not in ended: emit(last_q, 0, 'home', '', 'END', 0)
    return out, qa, tuple(run), box, sec, pm, (home, away)

def reconcile(stats, box, sec, pm, final):
    """逐球員、逐節對照官方 stats.json。回傳 (比較格數, 不符清單)。"""
    key = {'score': 'score', 'fgm': 'field_goals_made', 'fga': 'field_goals_attempted', '3pm': 'three_pointers_made',
           '3pa': 'three_pointers_attempted', 'ftm': 'free_throws_made', 'fta': 'free_throws_attempted',
           'reb': 'rebounds', 'ast': 'assists', 'stl': 'steals', 'blk': 'blocks', 'tov': 'turnovers'}
    n, bad = 0, defaultdict(list)
    for team in ('home_team', 'away_team'):
        for q, plist in stats[team]['players']['rounds'].items():
            for st in plist.values():
                pid, q = st['id'], int(q)
                for k, sk in key.items():
                    n += 1
                    if box[(pid, q)][k] != st.get(sk, 0): bad[k].append((st['name'], q, box[(pid, q)][k], st.get(sk, 0)))
                n += 1
                if pm[(pid, q)] != st.get('plus_minus', 0): bad['+/-'].append((st['name'], q, pm[(pid, q)], st.get('plus_minus', 0)))
                n += 1
                if abs(sec[(pid, q)] - st.get('time_on_court', 0)) > 3: bad['上場秒數(>3秒差)'].append((st['name'], q, round(sec[(pid, q)]), st.get('time_on_court', 0)))
    tot = (stats['home_team']['teams']['total'].get('won_score'), stats['away_team']['teams']['total'].get('won_score'))
    if tot != final: bad['最終比分'].append((final, tot))
    return n, bad

if __name__ == '__main__':
    ap = argparse.ArgumentParser(); ap.add_argument('broadcasts'); ap.add_argument('--stats')
    ap.add_argument('--game-id', required=True); ap.add_argument('--date', required=True)
    ap.add_argument('--out', default='events_tpbl.csv'); ap.add_argument('--append', action='store_true'); a = ap.parse_args()
    b = json.load(open(a.broadcasts, encoding='utf-8'))
    out, qa, final, box, sec, pm, (home, away) = convert(b, a.game_id, a.date)
    with open(a.out, 'a' if a.append else 'w', newline='', encoding='utf-8') as f:
        w = csv.DictWriter(f, fieldnames=FIELDS)
        if not a.append: w.writeheader()
        w.writerows(out)
    print(f'{home}(主) {final[0]} : {final[1]} {away}(客)；輸出 {len(out)} 列')
    for k, v in qa.items(): print(' 提醒', k, len(v), v[:4])
    if a.stats:
        n, bad = reconcile(json.load(open(a.stats, encoding='utf-8')), box, sec, pm, final)
        print(f'對帳 {n} 格：', '全部相符' if not bad else f'{sum(len(v) for v in bad.values())} 格不符')
        for k, v in bad.items(): print(' ', k, len(v), v[:6])
