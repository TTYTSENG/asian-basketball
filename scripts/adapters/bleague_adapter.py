#!/usr/bin/env python3
"""B.LEAGUE「テキスト速報」HTML(.result-box) -> daily_report.py 用の事件 CSV，並做資料對帳。
用法: python bleague_adapter.py pbp.html --game-id 506428 --date 2026-10-04 --home 島根 --away 名古屋D --out events.csv
"""
import re, csv, argparse
from collections import Counter, defaultdict
from bs4 import BeautifulSoup

# data-action-cd -> (我們的事件, 分數)；未列出的(犯規、換人、暫停等)不輸出
ACT = {1: ('FG3', 3), 2: ('M3', 0), 3: ('FG2', 2), 4: ('FG2', 2), 5: ('M2', 0), 6: ('M2', 0), 7: ('FT', 1), 8: ('FTX', 0),
       9: ('DREB', 0), 10: ('OREB', 0), 11: ('BLK', 0), 12: ('AST', 0), 13: ('TOV', 0), 14: ('STL', 0),
       17: ('TOV', 0), 18: ('DREB', 0), 19: ('OREB', 0)}
SUB_IN, SUB_OUT = 86, 87
FIELDS = ['game_id', 'date', 'home', 'away', 'period', 'sec_left', 'team', 'player', 'event', 'pts',
          'home_score', 'away_score', 'lu_home', 'lu_away']

def parse_rows(html):
    box = BeautifulSoup(html, 'lxml').select_one('div.result-box')
    rows, period, warn = [], None, []
    for el in box.find_all(recursive=False):
        cls = el.get('class', [])
        if 'result-box-ttl' in cls:  # 新到舊排列：「第N節終了」之後的事件屬於第N節
            t = el.get_text(strip=True)
            m = re.match(r'第(\d)クォーター終了', t)
            if m: period = int(m[1])
            elif '延長' in t and '終了' in t:
                n = re.search(r'(\d)', t); period = 4 + (int(n[1]) if n else 1)
            continue
        if 'result-box-play' not in cls: continue
        cd = int(el['data-action-cd'])
        sides = el.find_all('div', class_='play-result', recursive=False)
        tm = el.select_one('.time')
        sec = int(tm.text.split(':')[0]) * 60 + int(tm.text.split(':')[1]) if tm else None
        sc = el.select_one('.play-score')
        score = (int(sc.select_one('.left').text), int(sc.select_one('.right').text)) if sc else None
        for i, s in enumerate(sides):
            txt = s.select_one('.play-text').get_text(' ', strip=True) if s.select_one('.play-text') else ''
            if not txt: continue
            c = s.get('class', [])
            side = 'home' if 'bg-home' in c else 'away' if 'bg-away' in c else ('home', 'away')[i] if len(sides) == 2 else None
            if cd == 88 or side is None: continue
            if ('bg-home' in c or 'bg-away' in c) and side != ('home', 'away')[i]: warn.append(f'side/position mismatch no={el.get("data-no")}')
            img = s.select_one('img'); pid = name = ''
            if img:
                m = re.search(r'/roster/(\d+)/[\d-]+/(\d+)_', img.get('src', ''))
                pid, name = (m[2] if m else ''), img.get('alt', '')
            pt = re.search(r'\((\d+)点\)', txt)
            rows.append(dict(code=cd, period=period, sec=sec, side=side, pid=pid, name=name, score=score,
                             cum_pts=int(pt[1]) if pt else None))
    rows.reverse()  # 轉成時間順序
    return rows, warn

def convert(rows, game_id, date, home, away):
    names = defaultdict(Counter)
    for r in rows:
        if r['pid']: names[r['pid']][r['name']] += 1
    canon = {p: c.most_common(1)[0][0] for p, c in names.items()}
    team = {'home': home, 'away': away}
    court = {'home': set(), 'away': set()}; run = [0, 0]; out = []; qa = defaultdict(list)
    pts_sum = Counter(); cum_max = {}; last_period = None
    def emit(period, sec, side, player, ev, pts):
        out.append(dict(game_id=game_id, date=date, home=home, away=away, period=period, sec_left=sec, team=team[side],
                        player=player, event=ev, pts=pts, home_score=run[0], away_score=run[1],
                        lu_home='|'.join(sorted(canon[p] for p in court['home'])),
                        lu_away='|'.join(sorted(canon[p] for p in court['away']))))
    for r in rows:
        if last_period is not None and r['period'] != last_period:  # 補上上一節結束列，讓上場時間算完整
            emit(last_period, 0, 'home', '', 'END', 0)
        last_period = r['period']
        if r['code'] in (SUB_IN, SUB_OUT):
            (court[r['side']].add if r['code'] == SUB_IN else court[r['side']].discard)(r['pid']); continue
        if r['code'] not in ACT: continue
        ev, pts = ACT[r['code']]
        if any(len(court[s]) != 5 for s in court): qa['場上人數≠5'].append((r['period'], r['sec']))
        if r['pid'] and r['pid'] not in court[r['side']]: qa['球員不在場上'].append((r['period'], r['sec'], canon[r['pid']]))
        emit(r['period'], r['sec'], r['side'], canon.get(r['pid'], ''), ev, pts)
        if r['score']:
            exp = (run[0] + (pts if r['side'] == 'home' else 0), run[1] + (pts if r['side'] == 'away' else 0))
            if exp != r['score']: qa['比分不連續'].append((r['period'], r['sec'], exp, r['score']))
            run[:] = r['score']
        elif pts: qa['得分事件缺比分'].append((r['period'], r['sec'])); run[0 if r['side'] == 'home' else 1] += pts
        if pts and r['pid']: pts_sum[r['pid']] += pts
        if r['cum_pts'] and r['pid']: cum_max[r['pid']] = max(cum_max.get(r['pid'], 0), r['cum_pts'])
    emit(last_period, 0, 'home', '', 'END', 0)
    for p, c in cum_max.items():
        if pts_sum[p] != c: qa['球員累計得分不符'].append((canon[p], pts_sum[p], c))
    return out, qa, tuple(run)

if __name__ == '__main__':
    ap = argparse.ArgumentParser()
    ap.add_argument('html'); ap.add_argument('--game-id', required=True); ap.add_argument('--date', required=True)
    ap.add_argument('--home', required=True); ap.add_argument('--away', required=True); ap.add_argument('--out', default='events.csv')
    ap.add_argument('--append', action='store_true', help='附加到既有 CSV（累積歷史場次）')
    a = ap.parse_args()
    rows, warn = parse_rows(open(a.html, encoding='utf-8').read())
    out, qa, final = convert(rows, a.game_id, a.date, a.home, a.away)
    new = not a.append
    with open(a.out, 'w' if new else 'a', newline='', encoding='utf-8') as f:
        w = csv.DictWriter(f, fieldnames=FIELDS)
        if new: w.writeheader()
        w.writerows(out)
    print(f'事件列 {len(rows)} -> 輸出 {len(out)} 列；最終比分 {final[0]}:{final[1]}')
    print('對帳：', '全部通過' if not qa and not warn else '')
    for k, v in qa.items(): print(' ', k, len(v), v[:5])
    for x in warn[:5]: print(' ', x)
