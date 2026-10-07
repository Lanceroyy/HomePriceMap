import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
from place_index_builder import build_summary, main, write_catalog


class HomeStatsTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.data = Path(self.tmp.name)
        self.counties = {'updated': '2026-10-05T07:40:35.228667Z', 'count': 999,
                         'counties': {'01': {'value': 200000}, '02': {'value': None}}}
        self.cities = {'updated': '2026-10-04T00:00:00Z', 'count': 999,
                       'cities': [{'value': 300000}, {'value': 400000}, {'value': None}]}
        for filename, payload in [('county_prices.json', self.counties), ('city_prices.json', self.cities)]:
            (self.data / filename).write_text(json.dumps(payload), encoding='utf-8')

    def test_counts_actual_priced_records_not_metadata(self):
        self.assertEqual({'county_count': 1, 'city_count': 2, 'updated': self.counties['updated']},
                         build_summary(self.data))

    def test_summary_is_small_and_round_trips(self):
        output = self.data / 'summary.json'
        write_catalog(build_summary(self.data), output)
        self.assertLess(output.stat().st_size, 512)
        self.assertEqual(build_summary(self.data), json.loads(output.read_text()))

    def test_missing_input_is_not_silently_replaced_with_zero(self):
        (self.data / 'city_prices.json').unlink()
        with self.assertRaises(FileNotFoundError):
            build_summary(self.data)

    def test_workflow_explicitly_builds_and_stages_summary(self):
        workflow = (ROOT / '.github/workflows/update-data.yml').read_text()
        self.assertIn('--summary-output data/site_summary.json', workflow)
        self.assertIn('git add data/site_summary.json ', workflow)

    def test_home_uses_summary_loader_not_full_price_datasets(self):
        home = (ROOT / 'index.html').read_text(encoding='utf-8')
        self.assertIn('js/home-stats.js', home)
        self.assertNotIn('county_prices.json', home)
        self.assertNotIn('city_prices.json', home)
        self.assertIn('role="status"', home)

    def test_custom_catalog_output_does_not_implicitly_write_summary(self):
        # Empty sources still produce a valid empty catalog with no optional joins.
        (self.data / 'county_prices.json').write_text('{"counties":{}}')
        (self.data / 'city_prices.json').write_text('{"cities":[]}')
        output = self.data / 'custom.json'
        main(['--data-dir', str(self.data), '--output', str(output)])
        self.assertTrue(output.exists())
        self.assertFalse((self.data / 'site_summary.json').exists())
        summary = self.data / 'nested/summary.json'
        main(['--data-dir', str(self.data), '--output', str(output), '--summary-output', str(summary)])
        self.assertEqual(0, json.loads(summary.read_text())['city_count'])


if __name__ == '__main__':
    unittest.main()
