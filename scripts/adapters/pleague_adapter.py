#!/usr/bin/env python3
"""P+ League 逐球(PLAY BY PLAY) + box score -> daily_report.py 用的事件 CSV，並用 box score 對帳。
用法: python pleague_adapter.py pbp.json --box boxscore.json --game-id 709 --date 2026-05-17 \
        --home 桃園璞園領航猿 --away 洋基工程 --out events_pleague.csv [--append]
pbp.json: 回應 {"error":"","data":"<table ...>"}；boxscore.json: boxscore.preciser.php?id=709&... 的回應。
資料特性(已由真實回應確認): 無球員ID只有背號+姓名；先發不在逐球內(取自 box score 的 starter 欄)；
 左欄 bar_away=客隊、右欄 bar_home=主隊；比分格式「客 - 主」且為事件發生「後」比分；每節12分鐘。
"""
import re, csv, json, argparse
from collections import defaultdict, Counter
from bs4 import BeautifulSoup

Q_SEC = 720
FIELDS = ['game_id', 'date', 'home', 'away', 'period', 'sec_left', 'team', 'player', 'event', 'pts',
          'home_score', 'away_score', 'lu_home', 'lu_away', 'q_sec']

def jn(j): return str(j).strip()  # 保留 00 與 0；兩者可以是不同球員。

def classify(desc, act):
    """回傳 (事件, 分數) 或 None(不輸出，如犯規/暫停/跳球)。"""
    if '罰' in desc and ('罰進' in desc or '不進' in desc):
        return ('FT', 1) if '罰進' in desc else ('FTX', 0)
    if desc.endswith('得分'):
        return ('FG3', 3) if act == 3 else ('FG2', 2)
    if desc.endswith('不進'):
        return ('M3', 0) if '三分' in desc else ('M2', 0)
    if '進攻籃板' in desc: return ('OREB', 0)
    if '防守籃板' in desc: return ('DREB', 0)
    if desc.endswith('助攻'): return ('AST', 0)
    if desc.endswith('抄截'): return ('STL', 0)
    if desc.endswith('阻攻'): return ('BLK', 0)
    if '失誤' in desc or '出界' in desc: return ('TOV', 0)
    return None

def parse_pbp(raw):
    html = json.loads(raw)['data'] if raw.lstrip().startswith('{') else raw
    rows, period, unknown = [], None, Counter()
    for tr in BeautifulSoup(html, 'lxml').select('tr'):
        cls = tr.get('class', [])
        if 'quater-tr' in cls:
            lab = tr.select_one('.quater').get_text(strip=True)
            m = re.match(r'Q(\d)|OT(\d)', lab)
            if m: period = int(m[1]) if m[1] else 4 + int(m[2])
            elif lab.lower().startswith('final'): period = None
            rows.append(dict(kind='period', period=period)); continue
        t = tr.select_one('.countdown')
        td = tr.select_one('td.bar_home, td.bar_away')
        txt = tr.select_one('.pbp_detail_text')
        if not (t and td and txt): continue
        mm, ss = t.get_text(strip=True).split(':')
        side = 'home' if 'bar_home' in td.get('class', []) else 'away'
        text = txt.get_text(' ', strip=True)
        a = tr.select_one('.pbp_detail_action'); act = None
        if a and 'd-none' not in a.get('class', []):
            m = re.match(r'\+(\d)$', a.get_text(strip=True)); act = int(m[1]) if m else None
        sc = tr.select_one('.match_score'); score = None
        if sc and 'd-none' not in sc.get('class', []):
            m = re.match(r'(\d+)\s*-\s*(\d+)', sc.get_text(strip=True))
            if m: score = (int(m[1]), int(m[2]))  # (客, 主)
        m = re.match(r'#(\w+)\s+(\S+)\s*(.*)', text)
        jersey, name, desc = (jn(m[1]), m[2], m[3].strip()) if m else ('', '', text.strip())
        rows.append(dict(kind='ev', period=period, sec=int(mm) * 60 + int(ss), side=side, jersey=jersey, name=name,
                         desc=desc, act=act, score=score))
    return rows

def clean_clock(rows):
    """時間欄位以輸入順序為準，偶有倒退(例如換人時間比罰球早)。每節取最長非遞增序列，其餘沿用前一個可信時間。"""
    byp = defaultdict(list)
    for i, r in enumerate(rows):
        if r['kind'] == 'ev': byp[r['period']].append(i)
    fixed = 0
    for p, idx in byp.items():
        v = [rows[i]['sec'] for i in idx]; n = len(v); best, prev = [1] * n, [-1] * n
        for j in range(n):
            for i in range(j):
                if v[i] >= v[j] and best[i] + 1 > best[j]: best[j], prev[j] = best[i] + 1, i
        k, keep = max(range(n), key=lambda j: best[j]), set()
        while k != -1: keep.add(k); k = prev[k]
        cur = Q_SEC if p <= 4 else 300
        for j, i in enumerate(idx):
            if j in keep: cur = v[j]
            else: rows[i]['sec'] = cur; fixed += 1
    return fixed

def convert(rows, box, game_id, date, home, away):
    fixed = clean_clock(rows)
    side_list = {'home': box['home'], 'away': box['away']}
    pid = {(s, jn(p['jersey'])): p['player_id'] for s in side_list for p in side_list[s]}
    court = {s: {jn(p['jersey']) for p in side_list[s] if p['starter'].strip()} for s in side_list}
    nm = defaultdict(Counter)
    for r in rows:
        if r['kind'] == 'ev' and r['jersey']: nm[(r['side'], r['jersey'])][r['name']] += 1
    name = lambda s, j: nm[(s, j)].most_common(1)[0][0] if nm[(s, j)] else next(
        (p['name'] for p in side_list[s] if jn(p['jersey']) == j), j)
    team = {'home': home, 'away': away}
    run = {'away': 0, 'home': 0}; out = []; qa = defaultdict(list)
    stat = defaultdict(Counter); sec = defaultdict(float); pm = defaultdict(int)
    last_left = {}; cur_p = None

    def lu(s): return '|'.join(sorted(name(s, j) for j in court[s]))
    def emit(p, left, s, who, ev, pts):
        out.append(dict(game_id=game_id, date=date, home=home, away=away, period=p, sec_left=left, team=team[s],
                        player=who, event=ev, pts=pts, home_score=run['home'], away_score=run['away'],
                        lu_home=lu('home'), lu_away=lu('away'), q_sec=Q_SEC))
    def credit(p, left):
        dt = max(0, last_left.get(p, Q_SEC if p <= 4 else 300) - left)
        for s in court:
            for j in court[s]: sec[(s, j)] += dt

    for r in rows:
        if r['kind'] == 'period':
            if cur_p is not None:  # 上一節收尾(此時新一節的換人尚未套用)
                credit(cur_p, 0); emit(cur_p, 0, 'home', '', 'END', 0)
            cur_p = r['period']; continue
        p, left, s, j = r['period'], r['sec'], r['side'], r['jersey']
        credit(p, left); last_left[p] = left
        if r['desc'] in ('替換上場', '下場休息'):
            (court[s].add if r['desc'] == '替換上場' else court[s].discard)(j); continue
        c = classify(r['desc'], r['act'])
        if not c: continue
        ev, pts = c
        if any(len(court[x]) != 5 for x in court): qa['場上人數≠5'].append((p, left))
        if j and j not in court[s]: qa['球員不在場上'].append((p, left, r['name'], ev))
        emit(p, left, s, name(s, j) if j else '', ev, pts)
        if pts:
            run[s] += pts
            for x in court:
                for jj in court[x]: pm[(x, jj)] += pts if x == s else -pts
        if r['score']:
            a, h = r['score']
            if (a, h) != (run['away'], run['home']): qa['比分不連續'].append((p, left, (run['away'], run['home']), (a, h)))
            run['away'], run['home'] = a, h
        if j:
            c2 = stat[(s, j)]; c2['pts'] += pts
            if ev in ('FG2', 'M2'): c2['2pa'] += 1; c2['2pm'] += ev == 'FG2'
            if ev in ('FG3', 'M3'): c2['3pa'] += 1; c2['3pm'] += ev == 'FG3'
            if ev in ('FT', 'FTX'): c2['fta'] += 1; c2['ftm'] += ev == 'FT'
            if ev == 'OREB': c2['reb_o'] += 1
            if ev == 'DREB': c2['reb_d'] += 1
            if ev in ('AST', 'STL', 'BLK', 'TOV'): c2[ev.lower()] += 1
    if cur_p is not None: credit(cur_p, 0); emit(cur_p, 0, 'home', '', 'END', 0)
    return out, qa, fixed, stat, sec, pm, (run['home'], run['away'])

def reconcile(box, stat, sec, pm, final):
    n, bad = 0, defaultdict(list)
    mk = lambda s: tuple(int(x) for x in s.split('-'))
    for s in ('home', 'away'):
        for p in box[s]:
            j = jn(p['jersey']); c = stat[(s, j)]; nm_ = p['name']
            m2, a2 = mk(p['two_m_two']); m3, a3 = mk(p['trey_m_trey']); mf, af = mk(p['ft_m_ft'])
            for k, mine, off in (('得分', c['pts'], p['points']), ('2PM', c['2pm'], m2), ('2PA', c['2pa'], a2),
                                 ('3PM', c['3pm'], m3), ('3PA', c['3pa'], a3), ('FTM', c['ftm'], mf), ('FTA', c['fta'], af),
                                 ('進攻籃板', c['reb_o'], p['reb_o']), ('防守籃板', c['reb_d'], p['reb_d']),
                                 ('助攻', c['ast'], p['ast']), ('抄截', c['stl'], p['stl']), ('阻攻', c['blk'], p['blk']),
                                 ('失誤', c['tov'], p['turnover']), ('+/-', pm[(s, j)], p['positive'])):
                n += 1
                if mine != off: bad[k].append((nm_, mine, off))
            mm, ss = p['mins'].split(':'); off_sec = int(mm) * 60 + int(ss); n += 1
            if abs(sec[(s, j)] - off_sec) > 5: bad['上場秒數(>5秒差)'].append((nm_, round(sec[(s, j)]), off_sec))
    if (final[0], final[1]) != (box['score_home'], box['score_away']): bad['最終比分'].append((final, (box['score_home'], box['score_away'])))
    return n, bad

if __name__ == '__main__':
    ap = argparse.ArgumentParser(); ap.add_argument('pbp'); ap.add_argument('--box', required=True)
    ap.add_argument('--game-id', required=True); ap.add_argument('--date', required=True)
    ap.add_argument('--home', required=True); ap.add_argument('--away', required=True)
    ap.add_argument('--out', default='events_pleague.csv'); ap.add_argument('--append', action='store_true'); a = ap.parse_args()
    box = json.loads(open(a.box, encoding='utf-8-sig').read())['data']
    rows = parse_pbp(open(a.pbp, encoding='utf-8-sig').read())
    out, qa, fixed, stat, sec, pm, final = convert(rows, box, a.game_id, a.date, a.home, a.away)
    with open(a.out, 'a' if a.append else 'w', newline='', encoding='utf-8') as f:
        w = csv.DictWriter(f, fieldnames=FIELDS)
        if not a.append: w.writeheader()
        w.writerows(out)
    print(f'{a.home}(主) {final[0]} : {final[1]} {a.away}(客)；輸出 {len(out)} 列；時間離群值已校正 {fixed} 筆')
    for k, v in qa.items(): print(' 提醒', k, len(v), v[:4])
    n, bad = reconcile(box, stat, sec, pm, final)
    print(f'對帳 {n} 格：', '全部相符' if not bad else f'{sum(len(v) for v in bad.values())} 格不符')
    for k, v in bad.items(): print(' ', k, len(v), v[:6])
