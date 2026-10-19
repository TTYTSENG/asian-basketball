import sys
import unittest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
from advanced import observation_metrics


class ObservationTests(unittest.TestCase):
    def test_known_ratios_and_estimates(self):
        h = dict(points=100, fgm=35, fga=80, three_made=10, three_attempted=30,
                 ftm=20, fta=25, offensive_rebounds=10, defensive_rebounds=30,
                 assists=20, turnovers=12, seconds=12000)
        a = dict(h, points=90, ftm=10, defensive_rebounds=25, offensive_rebounds=8)
        result = observation_metrics(dict(league='b', stats={'home':h, 'away':a}))
        self.assertAlmostEqual(result['teams']['home']['efg'], 50)
        self.assertAlmostEqual(result['teams']['home']['oreb_pct'], 100*10/35)
        self.assertAlmostEqual(result['teams']['home']['ts'], 100*100/(2*(80+.44*25)))
        self.assertAlmostEqual(result['possessions_est'], 94)
        self.assertAlmostEqual(result['teams']['home']['off_rating_est'], 10000/94)
        self.assertEqual(result['regulation_minutes'], 40)

    def test_missing_not_zero_and_zero_denominators(self):
        g = dict(league='tpbl', stats={'home':dict(points=0, fgm=0, fga=0, ftm=0, fta=0)})
        r = observation_metrics(g)
        self.assertIsNone(r['teams']['home']['ts'])
        self.assertIsNone(r['teams']['home']['efg'])
        self.assertIsNone(r['possessions_est'])
        self.assertEqual(r['regulation_minutes'], 48)

    def test_inconsistent_shots_are_not_published(self):
        h=dict(points=10, fgm=5, fga=10, three_made=6, three_attempted=4, fta=0, ftm=0)
        r=observation_metrics(dict(league='b',stats={'home':h}))
        self.assertIsNone(r['teams']['home']['efg'])
        self.assertTrue(r['warnings'])
