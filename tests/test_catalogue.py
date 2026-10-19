import copy
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
from update import select_refresh_games
from catalogue import game_path, load_games, build_catalogue
from database import connect, persist


def fixture(gid, date='2026-10-18', complete=True):
    return dict(league='b', id=str(gid), date=date, time='18:00', home='主隊',
                away='客隊', score=[2, 0] if complete else [None, None],
                complete=complete, source='https://www.bleague.jp/game_detail/?ScheduleKey='+str(gid))


class FullMatchdayTests(unittest.TestCase):
    def test_all_games_on_latest_day_selected_not_only_five(self):
        for count in (6, 12):
            games = [fixture(i) for i in range(count)]
            latest, wanted = select_refresh_games(games, {}, '2026-10-19')
            self.assertEqual({g['id'] for g in latest}, {str(i) for i in range(count)})
            self.assertTrue(all(detail for _, detail in wanted.values()))

    def test_incomplete_future_and_duplicate_ids(self):
        games = [fixture(i) for i in range(6)]
        games += [fixture(0), fixture(7, complete=False), fixture(8, '2026-10-20')]
        latest, wanted = select_refresh_games(games, {}, '2026-10-19')
        self.assertEqual(len(latest), 6)
        self.assertNotIn('7', wanted)
        self.assertNotIn('8', wanted)

    def test_previous_day_not_cut_in_half_and_old_failures_retried(self):
        games = [fixture(1), *[fixture(i, '2026-10-17') for i in range(2, 14)],
                 fixture(20, '2026-10-05')]
        latest, wanted = select_refresh_games(games, {}, '2026-10-19')
        self.assertEqual(len(latest), 13)
        self.assertIn('20', wanted)

    def test_database_history_and_all_single_game_pages(self):
        cache = ROOT / '.cache/catalogue-tests'
        cache.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(dir=cache) as tmp:
            directory = Path(tmp)
            conn = connect(directory / 'test.sqlite3')
            games = [fixture(i) for i in range(12)] + [fixture(99, complete=False)]
            site = dict(generatedAt='2026-10-19T01:00:00+08:00', asOf='2026-10-19',
                        errors=[], news=[], guides=[], leagues=[dict(
                            id='b', name='B.LEAGUE', source='https://www.bleague.jp/',
                            upcoming=[], recent=[])])
            persist(conn, {}, site, {'b': games})
            conn.close()
            rows = load_games(directory / 'test.sqlite3', site)
            self.assertEqual(len(rows), 13)
            def render(g):
                return '<p>官方賽事 '+g['id']+'</p>'
            urls = build_catalogue(directory / 'public', site, rows, render)
            for g in games:
                self.assertTrue((directory / 'public' / game_path(g)).exists())
            self.assertEqual(len([u for u in urls if '/games/b/' in u]), 13)
            self.assertTrue((directory / 'public/history/index.html').exists())

