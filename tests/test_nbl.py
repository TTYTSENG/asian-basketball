import copy,sys,unittest
from datetime import date
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
import nbl

def fixture():
    players=[];teams=[]
    for tid,pts in [('h',2),('a',0)]:
        for i in range(5):
            players.append(dict(period='0',team={'id':tid},player={'id':tid+str(i),'full_name':tid+str(i)},participated=True,starter=True,minutes='40:00',points=pts if i==0 else 0,field_goals_made=pts//2 if i==0 else 0,field_goals_attempted=1 if i==0 else 0,turnovers=0,free_throws_made=0,free_throws_attempted=0,assists=0,rebounds=0,steals=0,blocks=0,offensive_rebounds=0,defensive_rebounds=0,three_points_made=0,three_points_attempted=0))
        teams.append(dict(period='0',team={'id':tid},points=pts,field_goals_made=pts//2,field_goals_attempted=1,turnovers=1,free_throws_made=0,free_throws_attempted=0,minutes=200,assists=0,rebounds=0,steals=0,blocks=0,offensive_rebounds=0,defensive_rebounds=0,three_points_made=0,three_points_attempted=0))
    g=dict(league='nbl',id='g',date='2026-10-18',home='Home',away='Away',score=[2,0],statsSource='https://schedule.nbl.com.au/api/calendar/match?match=g&league=NBL')
    m=dict(match_status='complete',home_team={'id':'h'},away_team={'id':'a'},home_score='2',away_score='0',player_match_statistics=players,team_match_statistics=teams,play_by_play=[])
    return g,m

def event(id,kind='2pt',clock='04:00',period=4,**extra):
    return dict(action_id=id,action_type=kind,clock=clock,period=period,team={'id':'h'},player={'id':'h0','full_name':'h0'},success=True,**extra)

class NBLAdapterTest(unittest.TestCase):
    def test_schedule_filters_exhibitions_and_converts_utc_across_date(self):
        row=dict(id='g',starts_at_ms=1792321200000,home={'id':'h','name':'Home'},away={'id':'a','name':'Away'},home_score=None,away_score=None,phase='scheduled',season_type='regular',season_id='s')
        with patch.object(nbl,'js',return_value={'matches':[row,dict(row,id='test',season_type='test'),dict(row,id='pre',season_type='preseason')]}):
            result=nbl.schedule(date(2026,10,21))
        self.assertEqual(len(result),1)
        self.assertEqual((result[0]['date'],result[0]['time']),('2026-10-18','19:00'))
        self.assertFalse(result[0]['complete']);self.assertEqual(result[0]['score'],[None,None])

    def test_full_totals_team_turnover_and_usage(self):
        g,m=fixture();partial=copy.deepcopy(m['player_match_statistics'][0]);partial['period']='1';partial['points']=99
        m['player_match_statistics'].append(partial)
        result=nbl.parse_game(g,m,False)
        self.assertEqual(result['stats']['home']['points'],2)
        self.assertEqual(result['stats']['home']['turnovers'],1)
        self.assertEqual(result['stats']['home']['seconds'],12000)
        p=next(p for p in result['advanced']['players'] if p['id']=='h0')
        self.assertEqual(p['usg'],50)
        self.assertEqual(result['advanced']['observation']['regulation_minutes'],40)

    def test_schedule_box_mismatch_rejected(self):
        g,m=fixture();m['home_score']='3'
        with self.assertRaisesRegex(ValueError,'schedule and box'):nbl.parse_game(g,m)

    def test_player_box_mismatch_and_missing_active_stat_rejected(self):
        g,m=fixture();m['player_match_statistics'][0]['points']=1
        with self.assertRaisesRegex(ValueError,'player points'):nbl.parse_game(g,m)
        g,m=fixture();m['player_match_statistics'][0]['field_goals_attempted']=None
        with self.assertRaisesRegex(ValueError,'active player'):nbl.parse_game(g,m)

    def test_action_ids_sort_without_silently_reordering_clocks(self):
        rows=[event(3,clock='04:10'),event(1,'timeOut',clock='04:20'),event(2,clock='04:00')]
        normalized,missing=nbl.normalize_events(rows,'h','a')
        self.assertEqual([e['sec'] for e in normalized],[260,240,250]);self.assertEqual(missing,0)
        g,m=fixture();m['play_by_play']=[event(1,'timeOut'),event(2),event(3,'foul',clock='04:10')]
        result=nbl.parse_game(g,m)
        self.assertGreater(result['report']['issues']['clock'],0)
        self.assertEqual(result['report']['keyPlayers'],[]);self.assertEqual(result['report']['lineups'],[])
        self.assertEqual(sum(r['attack_n'] for r in result['advanced']['ato']['summary']),0)

    def test_missing_clock_stops_time_dependent_outputs(self):
        g,m=fixture();m['play_by_play']=[event(1,'timeOut'),event(2),event(3,'foul',clock=None)]
        result=nbl.parse_game(g,m)
        self.assertEqual(result['report']['issues']['missing_clock'],1)
        self.assertEqual(result['report']['keyPlayers'],[])
        self.assertEqual(sum(r['attack_n'] for r in result['advanced']['ato']['summary']),0)

if __name__=='__main__':unittest.main()
