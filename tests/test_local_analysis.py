import json
import re
import unittest
import tempfile
import sys
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import urlsplit
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
ARTICLE = 'los-angeles-county-home-price-gaps.html'
SNAPSHOT = 'data/analysis/los-angeles-county-2026-08.json'
sys.path.insert(0, str(ROOT / 'scripts'))
import state_pages_builder


class ChartParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.rows = []
        self.links = []

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag == 'a':
            self.links.append(attrs.get('href', ''))
        if 'data-place-id' in attrs:
            self.rows.append({'id':attrs['data-place-id'], 'value':int(attrs['data-value'])})
        if attrs.get('class') == 'analysis-price-bar':
            self.rows[-1]['width'] = float(re.search(r'width:([\d.]+)%', attrs['style']).group(1))


class LocalAnalysisTests(unittest.TestCase):
    def setUp(self):
        self.snapshot = json.loads((ROOT / SNAPSHOT).read_text(encoding='utf-8'))
        self.article = (ROOT / ARTICLE).read_text(encoding='utf-8')

    def test_main_finding_and_counts_match_frozen_snapshot(self):
        cities = self.snapshot['cities']
        self.assertEqual(76, len(cities))
        self.assertEqual(76, len({c['id'] for c in cities}))
        self.assertTrue(all(c['state'] == 'CA' and c['county'] == 'Los Angeles County'
                            and c['as_of'] == '2026-08-31' for c in cities))
        cheapest, expensive = min(cities, key=lambda c:c['value']), max(cities, key=lambda c:c['value'])
        self.assertEqual(('Lancaster', 'Beverly Hills'), (cheapest['name'], expensive['name']))
        self.assertEqual(7.9, round(expensive['value'] / cheapest['value'], 1))
        self.assertIn('7.9', self.article)
        self.assertIn('76 published city profiles', self.article)
        self.assertIn('August 31, 2026', self.article)
        self.assertIn('October 6, 2026', self.article)
        self.assertIn('not an average of', self.article)
        self.assertIn('not neighboring-city', self.article)

    def test_chart_values_and_linear_widths_match_data(self):
        parser = ChartParser()
        parser.feed(self.article)
        by_id = {p['id']:p for p in self.snapshot['cities'] + [self.snapshot['county']]}
        self.assertEqual(7, len(parser.rows))
        largest = max(p['value'] for p in self.snapshot['cities'])
        for row in parser.rows:
            with self.subTest(place=row['id']):
                self.assertEqual(by_id[row['id']]['value'], row['value'])
                self.assertAlmostEqual(row['value'] / largest * 100, row['width'], places=2)
                self.assertIn('${:,}'.format(row['value']), self.article)
                self.assertIn(by_id[row['id']]['url'], parser.links)
        for href in parser.links:
            if href.startswith('/') and not href.startswith('//'):
                local = urlsplit(href).path.lstrip('/') or 'index.html'
                self.assertTrue((ROOT / local).is_file(), href)

    def test_article_discovery_and_metadata(self):
        self.assertIn('href="{}"'.format(ARTICLE), (ROOT / 'index.html').read_text(encoding='utf-8'))
        self.assertIn('SITE_URL + "/{}"'.format(ARTICLE),
                      (ROOT / 'scripts/state_pages_builder.py').read_text(encoding='utf-8'))
        self.assertEqual(1, self.article.count('<h1>'))
        self.assertIn('href="https://homepricemap.us/{}"'.format(ARTICLE), self.article)
        self.assertIn('src="/js/analytics-loader.js"', self.article)
        self.assertIn('href="/compare.html#places=city:ca-beverly-hills,city:ca-los-angeles,city:ca-lancaster"', self.article)
        self.assertIn('href="/{}"'.format(SNAPSHOT), self.article)
        self.assertIn('aria-hidden="true"', self.article)
        self.assertNotIn('name="robots" content="noindex', self.article)

    def test_final_sitemap_generation_includes_article_once(self):
        with tempfile.TemporaryDirectory() as directory:
            output_root = Path(directory)
            with patch.object(state_pages_builder, 'ROOT', output_root):
                state_pages_builder.build_sitemap([], {'counties':{}})
            sitemap = (output_root / 'sitemap.xml').read_text()
            self.assertEqual(1, sitemap.count('<loc>https://homepricemap.us/{}</loc>'.format(ARTICLE)))
            self.assertNotIn('404.html', sitemap)


if __name__ == '__main__':
    unittest.main()
