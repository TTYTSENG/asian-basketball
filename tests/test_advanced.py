import sys,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from advanced import usage,ato_sequences,metrics

def e(kind,sec=300,side='home',pid='1',pts=0,q=4):return dict(kind=kind,period=q,sec=sec,side=side,pid=pid,pts=pts)
class AdvancedTests(unittest.TestCase):
    def test_usage_known_share(self):
        p=dict(fga=10,fta=0,turnovers=0,seconds=1440);team=dict(fga=100,fta=0,turnovers=0,seconds=14400)
        self.assertEqual(usage(p,team),20)
        p['seconds']=0;self.assertIsNone(usage(p,team));p.pop('fta');self.assertIsNone(usage(p,team))
    def test_usage_free_throw_weight(self):
        p=dict(fga=0,fta=10,turnovers=0,seconds=1440);team=dict(fga=80,fta=50,turnovers=0,seconds=14400)
        self.assertAlmostEqual(usage(p,team),8.62745098)
    def test_ato_timeout_caller_not_assumed_offense(self):
        a=ato_sequences([e('TIMEOUT',side='away'),e('FG2',sec=290,pts=2),e('END',sec=0)])
        r=a['records'][0];self.assertEqual(r['offense'],'home');self.assertEqual(r['points'],2);self.assertTrue(r['offensive_success'])
        self.assertIsNone(r['inbounder']);self.assertIsNone(r['receiver'])
    def test_ato_offensive_rebound_extends_possession(self):
        a=ato_sequences([e('TIMEOUT'),e('M2',sec=290),e('OREB',sec=289),e('FG3',sec=285,pts=3,pid='2'),e('END',sec=0)])
        self.assertEqual(a['records'][0]['points'],3);self.assertEqual(a['records'][0]['finisher'],'2');self.assertEqual(a['summary'][0]['attack_n'],1)
    def test_ato_turnover_and_defensive_rebound(self):
        a=ato_sequences([e('TIMEOUT'),e('TOV',sec=299),e('TIMEOUT',sec=200),e('M2',sec=190),e('DREB',sec=188,side='away')])
        self.assertEqual(a['summary'][0]['attack_success'],0);self.assertEqual(a['summary'][1]['defense_success'],2);self.assertEqual(a['summary'][0]['turnovers'],1)
    def test_and_one_vs_ft_first(self):
        a=ato_sequences([e('TIMEOUT'),e('FG2',sec=290,pts=2),e('FT',sec=290,pts=1),e('END',sec=0)])
        self.assertEqual(a['records'][0]['points'],3)
        b=ato_sequences([e('TIMEOUT'),e('FT',sec=300,pts=1)])
        self.assertEqual(b['excluded'],1);self.assertEqual(b['summary'][0]['attack_n'],0)
    def test_incomplete_or_invalid_sequences_excluded(self):
        events=[e('TIMEOUT'),e('M2',sec=290),e('FG2',sec=280,pts=2)]
        self.assertEqual(ato_sequences(events)['excluded'],1)
        valid=[e('TIMEOUT'),e('FG2',sec=290,pts=2),e('END',sec=0)]
        self.assertEqual(ato_sequences(valid,{'box_turnovers':1})['summary'][0]['attack_n'],0)
    def test_tracking_and_vorp_never_fabricated(self):
        p=dict(id='1',name='甲',seconds=600,points=10,fgm=4,fga=8,fta=2,ftm=2,turnovers=0,assists=5,rebounds=3,steals=1,blocks=0)
        g=dict(players={'home':[p]},stats={'home':dict(fga=80,fta=20,turnovers=10,seconds=14400)})
        r=metrics(g);row=r['players'][0]
        self.assertIsNone(row['ast_to']);self.assertIsNone(row['potential_assists']);self.assertIsNone(row['vorp']);self.assertEqual(row['eff'],15)
        self.assertEqual(r['benchmark']['id'],'1')
    def test_missing_active_player_stat_not_zero(self):
        from sources import optional_stat,totals
        self.assertIsNone(optional_stat({'mins':'10:00'},'ast'))
        self.assertEqual(optional_stat({'mins':'DNP'},'ast'),0)
        self.assertIsNone(totals({'home':[{'fta':None}]})['home']['fta'])
