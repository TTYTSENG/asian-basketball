import sys,json,sqlite3,tempfile,unittest,copy
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from database import connect,persist,archive,snapshot,export,check

class DatabaseTests(unittest.TestCase):
    def setUp(self):
        test_root=(Path(__file__).resolve().parents[1]/'.cache/database-tests').resolve();test_root.mkdir(parents=True,exist_ok=True)
        self.temp=tempfile.TemporaryDirectory(dir=test_root);self.path=Path(self.temp.name).resolve()
        assert self.path.is_relative_to(test_root)
        self.conn=connect(self.path/'test.sqlite3')
        self.g=dict(league='tpbl',id='100',date='2026-10-07',time='19:00',home='甲隊',away='乙隊',score=[2,0],complete=True,source='https://tpbl.basketball/games/100',players={'home':[dict(id='7',name='甲球員',points=2,fgm=1,fga=1,turnovers=0,seconds=600)],'away':[]})
        self.site=dict(generatedAt='2026-10-08T07:17:00+08:00',asOf='2026-10-08',errors=[],news=[],leagues=[dict(id='tpbl',name='TPBL',source='https://tpbl.basketball/',upcoming=[],recent=[])])
    def tearDown(self):self.conn.close();self.temp.cleanup()
    def test_round_trip_and_idempotent_import(self):
        for _ in range(2):persist(self.conn,{'tpbl:100':self.g},self.site)
        self.assertEqual(archive(self.conn)['tpbl:100'],self.g)
        counts=check(self.conn);self.assertEqual(counts['games'],1);self.assertEqual(counts['player_game_stats'],1)
        export(self.conn,self.path/'out');self.assertEqual(json.loads((self.path/'out/site.json').read_text(encoding='utf8')),self.site)
    def test_invalid_correction_rolls_back_transaction(self):
        persist(self.conn,{'tpbl:100':self.g},self.site)
        bad=copy.deepcopy(self.g);bad['players']['home'][0]['fga']=0
        with self.assertRaises(sqlite3.IntegrityError):persist(self.conn,{'tpbl:100':bad},self.site)
        self.assertEqual(archive(self.conn)['tpbl:100'],self.g);self.assertEqual(check(self.conn)['update_runs'],1)
    def test_schedule_does_not_erase_box_score(self):
        persist(self.conn,{'tpbl:100':self.g},self.site)
        schedule={k:v for k,v in self.g.items() if k!='players'}
        persist(self.conn,{},self.site,{'tpbl':[schedule]})
        self.assertEqual(check(self.conn)['player_game_stats'],1);self.assertEqual(archive(self.conn)['tpbl:100'],self.g)
    def test_official_ids_scoped_by_league(self):
        other=copy.deepcopy(self.g);other['league']='plg'
        site=copy.deepcopy(self.site);site['leagues'].append(dict(id='plg',name='P+',source='https://pleagueofficial.com/',upcoming=[],recent=[]))
        persist(self.conn,{'tpbl:100':self.g,'plg:100':other},site)
        counts=check(self.conn);self.assertEqual(counts['players'],2);self.assertEqual(counts['games'],2)
    def test_official_correction_updates_existing_row(self):
        persist(self.conn,{'tpbl:100':self.g},self.site)
        revised=copy.deepcopy(self.g);revised['players']['home'][0]['turnovers']=1
        persist(self.conn,{'tpbl:100':revised},self.site)
        self.assertEqual(self.conn.execute('SELECT turnovers FROM player_game_stats').fetchone()[0],1)
        self.assertEqual(check(self.conn)['player_game_stats'],1)
    def test_bad_aggregate_score_rolls_back(self):
        persist(self.conn,{'tpbl:100':self.g},self.site)
        bad=copy.deepcopy(self.g);bad['score']=[3,0]
        with self.assertRaises(AssertionError):persist(self.conn,{'tpbl:100':bad},self.site)
        self.assertEqual(archive(self.conn)['tpbl:100']['score'],[2,0])
