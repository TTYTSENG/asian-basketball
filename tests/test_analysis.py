import sys,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from engine import analyze,history_for,finalize
from sources import secs
from adapters.pleague_adapter import jn

class AnalysisTests(unittest.TestCase):
    def event(self,sec,kind,pid='h1',pts=0,period=1,side='home'):
        return dict(period=period,sec=sec,kind=kind,pid=pid,side=side,pts=pts)
    def test_substitution_boundary(self):
        starters={'home':['h1','h2','h3','h4','h5'],'away':['a1','a2','a3','a4','a5']}
        ev=[self.event(720,'END'),self.event(420,'OUT','h5'),self.event(420,'IN','h6'),self.event(410,'FG2',pts=2),self.event(120,'FG2',pts=2),self.event(0,'END')]
        players={'home':[dict(id='h1',name='一',points=4,fgm=2,fga=2,turnovers=0)],'away':[]}
        r=analyze(ev,players,[4,0],720,starters)
        self.assertFalse(r['issues']);lus=r['lineups'];best=next(x for x in lus if x['label']=='最佳');worst=next(x for x in lus if x['label']=='最差')
        self.assertEqual(best['seconds'],420);self.assertEqual(best['net'],4);self.assertIn('h6',best['ids']);self.assertEqual(worst['seconds'],300);self.assertEqual(worst['net'],0)
    def test_q4_window_excludes_overtime(self):
        ev=[self.event(301,'FG2',pts=2,period=4),self.event(300,'FG2',pts=2,period=4),self.event(0,'FG2',pts=2,period=4),self.event(200,'FG3',pts=3,period=5)]
        r=analyze(ev,{'home':[dict(id='h1',name='甲',points=9,fgm=4,fga=4,turnovers=0)],'away':[]},[9,0],720)
        self.assertIn('4 分',r['key'][0]);self.assertFalse(r['lineups'])
    def test_mismatch_suppresses_claims(self):
        r=analyze([self.event(100,'FG2',pts=2)],{'home':[],'away':[]},[3,0],720)
        self.assertTrue(r['issues']['score']);self.assertFalse(r['key']);self.assertFalse(r['lineups'])
    def test_clock_reversal_suppresses_key_claim(self):
        r=analyze([self.event(100,'FG2',pts=2,period=4),self.event(110,'FG2',pts=2,period=4)],{'home':[],'away':[]},[4,0],720)
        self.assertTrue(r['issues']['clock']);self.assertFalse(r['key'])
    def test_history_stable_id_and_appearances(self):
        archive={str(i):dict(league='plg',id=str(i),date=f'2026-01-0{i}',players={'home':[dict(id='1',name='同名',seconds=600 if i!=3 else 0,points=i)]}) for i in range(1,6)}
        history=history_for(archive,'plg','1','2026-01-05',False)
        self.assertEqual([x['points'] for x in history],[4,2,1]);self.assertFalse(history_for(archive,'plg','2','2026-01-05'))
    def test_zero_jerseys_distinct_and_dnp(self):
        self.assertNotEqual(jn('00'),jn('0'));self.assertEqual(secs('DNP'),0)
    def test_turnover_mismatch_does_not_change_verified_scoring(self):
        ev=[self.event(300,'FG2',pts=2,period=4)]
        ps={'home':[dict(id='h1',name='甲',points=2,fgm=1,fga=1,turnovers=1)],'away':[]}
        r=analyze(ev,ps,[2,0],720)
        self.assertTrue(r['issues']['box_turnovers']);self.assertIn('2 分',r['key'][0]);self.assertIn('需核對',r['key'][0])
    def test_offcourt_non_scoring_stat_not_used_for_lineup_points(self):
        starters={'home':['h1','h2','h3','h4','h5'],'away':['a1','a2','a3','a4','a5']}
        r=analyze([self.event(600,'TOV','bench')],{'home':[dict(id='bench',name='板凳',points=0,fgm=0,fga=0,turnovers=1)],'away':[]},[0,0],720,starters)
        self.assertFalse(r['issues']);self.assertFalse(r['lineups'])
    def test_insufficient_history(self):
        g=dict(league='plg',id='1',date='2026-01-01',home='甲',away='乙',players={'home':[dict(id='1',name='球員',seconds=1000,points=40,fgm=15,fga=20)]})
        self.assertIn('資料不足',finalize(g,{})['analysis'][2][1])
if __name__=='__main__':unittest.main()
