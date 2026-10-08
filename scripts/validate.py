import json
from pathlib import Path
from urllib.parse import urlparse
from database import connect,check
data=json.loads((Path(__file__).resolve().parents[1]/'data/site.json').read_text(encoding='utf8'))
assert [x['id'] for x in data['leagues']]==['tpbl','plg','b']
for league in data['leagues']:
    assert len(league['recent'])<=5
    for g in league['recent']:
        assert len(g['score'])==2 and all(isinstance(x,int) and x>=0 for x in g['score'])
        assert urlparse(g['source']).scheme=='https'
        assert len(g['analysis'])==3
        if g.get('stats'):
            assert [g['stats'][s]['points'] for s in ('home','away')]==g['score'],g['id']
print('Data structure, league order, official references and score totals validated.')
with connect() as conn:print('SQLite integrity, foreign keys and scores:',check(conn))
