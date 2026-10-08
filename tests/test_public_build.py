import importlib.util,json,tempfile,unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('public_build',ROOT/'scripts/build_public.py');module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
class PublicBuildTests(unittest.TestCase):
    def test_published_snapshot_contains_real_data_and_excludes_private_database(self):
        with tempfile.TemporaryDirectory() as tmp:
            out=Path(tmp)/'public';module.build(out);page=(out/'index.html').read_text(encoding='utf8');d=json.loads((ROOT/'data/site.json').read_text(encoding='utf8'))
            self.assertNotIn('資料讀取中。',page)
            self.assertIn('application/ld+json',page)
            self.assertIn('rel="canonical"',page)
            for league in d['leagues']:
                for game in league.get('recent',[])[:3]:self.assertIn(module.e(game['home']),page);self.assertIn(module.e(game['source']),page)
            self.assertFalse(list(out.rglob('*.sqlite3')))
            self.assertFalse((out/'data/archive.json').exists())
            self.assertTrue((out/'reports/index.html').exists())
    def test_untrusted_strings_are_escaped_and_non_https_sources_not_linked(self):
        self.assertEqual(module.e('<script>'), '&lt;script&gt;')
        self.assertNotIn('href',module.link('unsafe','javascript:alert(1)'))
        self.assertIn('&amp;',module.link('source','https://example.com/?a=1&b=2'))
