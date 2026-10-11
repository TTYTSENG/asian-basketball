import sys,unittest
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
import cba

class CBAAdapterTest(unittest.TestCase):
    def test_scoring_and_miss_and_assist(self):
        players={'home':[{'name':'甲','id':'1'},{'name':'乙','id':'2'}],'away':[{'name':'丙','id':'3'}]}
        rows=[dict(quarterNum=4,minutes=4,seconds=0,homeScore=2,visitorScore=0,playerCNNames=['甲','乙'],textualFormat='甲接到乙的助攻，上篮命中得分'),dict(quarterNum=4,minutes=3,seconds=55,homeScore=2,visitorScore=0,playerCNNames=['丙'],textualFormat='丙三分跳投不中')]
        events,unknown=cba.parse_events(rows,players,[2,0])
        self.assertEqual(unknown,0)
        self.assertEqual([e['kind'] for e in events],['FG2','AST','M3'])
        self.assertEqual(events[1]['pid'],'2')
    def test_substitution_direction(self):
        players={'home':[{'name':'甲','id':'1'},{'name':'乙','id':'2'}],'away':[]}
        rows=[dict(quarterNum=1,minutes=8,seconds=0,homeScore=0,visitorScore=0,playerCNNames=['乙','甲'],textualFormat='主队换人，乙换下了甲')]
        events,unknown=cba.parse_events(rows,players,[0,0])
        self.assertEqual([(e['kind'],e['pid']) for e in events],[('OUT','1'),('IN','2')])
        self.assertEqual(unknown,0)
    def test_unidentified_scoring_fails_closed(self):
        rows=[dict(quarterNum=1,minutes=8,seconds=0,homeScore=2,visitorScore=0,playerCNNames=['未知'],textualFormat='未知得分')]
        events,unknown=cba.parse_events(rows,{'home':[],'away':[]},[2,0])
        self.assertEqual(events,[]);self.assertGreater(unknown,0)
    def test_missing_clock_fails_closed(self):
        events,unknown=cba.parse_events([dict(quarterNum=1,minutes=None,seconds=0)],{'home':[],'away':[]},[0,0])
        self.assertEqual(events,[]);self.assertEqual(unknown,1)

if __name__=='__main__':unittest.main()
