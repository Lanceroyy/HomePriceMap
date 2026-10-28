from contextlib import ExitStack
from html.parser import HTMLParser
import json
from pathlib import Path
import re
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
from profile_components import source_period_label, render_data_freshness
from page_provenance import PageProvenance
import city_pages_builder as city_builder
import seo_pages_builder as county_builder
import state_pages_builder as state_builder


class FreshnessComponentTests(unittest.TestCase):
    def test_valid_source_month_and_mixed_period_are_not_check_dates(self):
        self.assertEqual('February 2024', source_period_label([
            {'value':100, 'as_of':'2024-02-29'}, {'value':200, 'as_of':'2024-02-01'}]))
        self.assertEqual('December 2023 – February 2024', source_period_label([
            {'value':100, 'as_of':'2024-02-29'}, {'value':200, 'as_of':'2023-12-31'}]))

    def test_missing_and_invalid_dates_fail_closed_without_hiding_priced_rows(self):
        for stamp in (None, '', 'bad', '2024-02-30', '20240229', '2024-2-29', 123, True):
            with self.subTest(stamp=stamp):
                self.assertEqual('Unavailable', source_period_label([
                    {'value':100, 'as_of':'2024-02-29'}, {'value':200, 'as_of':stamp}]))
        for records in (None, [], [{'value':None, 'as_of':'2024-02-29'}]):
            self.assertEqual('Unavailable', source_period_label(records))

    def test_unpriced_records_do_not_change_the_displayed_source_scope(self):
        self.assertEqual('February 2024', source_period_label([
            {'value':100, 'as_of':'2024-02-29'}, {'value':None, 'as_of':'bad'}]))

    def test_source_scopes_links_and_separate_refresh_note_are_explicit(self):
        html = render_data_freshness(
            counties=[{'value':100, 'as_of':'2024-01-31'}],
            cities=[{'value':100, 'as_of':'2024-02-29'}])
        self.assertIn('County housing-data period:</b> January 2024', html)
        self.assertIn('City housing-data period:</b> February 2024', html)
        self.assertIn('href="../data/county_prices.json"', html)
        self.assertIn('href="../data/city_prices.json"', html)
        self.assertIn('retrieval/check time (UTC)', html)
        self.assertIn('monthly', html)
        self.assertIn('not new daily prices', html)
        self.assertIn('Income and crime data are updated separately', html)
        self.assertNotIn('<script', html)

    def test_hub_prefix_absent_sources_and_unknown_dates_are_honest(self):
        html = render_data_freshness(counties=[], prefix='')
        self.assertIn('County housing-data period:</b> Unavailable', html)
        self.assertIn('href="data/county_prices.json"', html)
        self.assertNotIn('City housing-data period', html)
        self.assertNotIn('city_prices.json', html)
        html = render_data_freshness(cities=[{'value':100, 'as_of':'<script>alert(1)</script>'}])
        self.assertNotIn('<script', html)
        self.assertIn('Unavailable', html)


class GeneratedFreshnessTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.data = self.root / 'data'
        self.data.mkdir()
        self.counties = {'updated':'2024-04-01T00:00:00Z', 'counties':{
            '06001':{'name':'Example County','state':'CA','value':100000,'yoy_pct':2,'as_of':'2024-01-31'},
            '06002':{'name':'Other County','state':'CA','value':200000,'yoy_pct':3,'as_of':'2024-03-31'},
            '06003':{'name':'Unpriced County','state':'CA','value':None,'as_of':'bad'}}}
        self.cities = {'updated':'2024-04-02T00:00:00Z', 'cities':[
            {'name':'Example','state':'CA','county':'Example County','value':110000,'yoy_pct':1,'as_of':'2024-02-29'},
            {'name':'Tiny','state':'CA','county':'Other County','value':120000,'as_of':'bad'}]}
        self.crime = {'cities':{
            'CA|example':{'name':'Example','state':'CA','population':6000,'violent_crime_rate':100,'property_crime_rate':200},
            'CA|tiny':{'name':'Tiny','state':'CA','population':4999}}}

    def build(self, day='2024-04-03'):
        for filename, payload in (('county_prices.json',self.counties), ('city_prices.json',self.cities),
                                   ('crime_data_city.json',self.crime)):
            (self.data/filename).write_text(json.dumps(payload), encoding='utf-8')
        with ExitStack() as stack:
            for module, folder in ((city_builder,'cities'),(county_builder,'counties'),(state_builder,'states')):
                stack.enter_context(patch.object(module, 'ROOT', self.root))
                stack.enter_context(patch.object(module, 'OUT_DIR', self.root/folder))
                stack.enter_context(patch.object(module, 'PageProvenance',
                    lambda root:PageProvenance(root, written_on=day)))
            for name, filename in (('CITY_PATH','city_prices.json'),('COUNTY_PATH','county_prices.json'),
                ('CITY_CRIME_PATH','crime_data_city.json'),('CITY_INCOME_PATH','missing.json'),
                ('CITY_HISTORY_PATH','missing.json')):
                stack.enter_context(patch.object(city_builder, name, self.data/filename))
            for name, value in (('CITY_PATH',self.data/'city_prices.json'),('CITY_DIR',self.root/'cities'),
                                ('HISTORY_PATH',self.data/'missing.json')):
                stack.enter_context(patch.object(county_builder, name, value))
            stack.enter_context(patch.object(city_builder,'MIN_EXPECTED_PROFILES',1))
            stack.enter_context(patch.object(county_builder,'MIN_EXPECTED_PROFILES',1))
            city_builder.build()
            county_builder.build_pages(self.counties)
            state_builder.build_state_pages(self.counties, None, city_data=self.cities)
        return {name:(self.root/name).read_text(encoding='utf-8') for name in (
            'cities/ca-example.html','counties/ca-example-county.html','states/california.html','states.html')}

    def test_all_generated_surfaces_have_correct_source_period_and_no_daily_price_claim(self):
        pages = self.build()
        expected = {'cities/ca-example.html':'February 2024','counties/ca-example-county.html':'January 2024',
                    'states/california.html':'January 2024 – March 2024','states.html':'January 2024 – March 2024'}
        for path, html in pages.items():
            with self.subTest(path=path):
                self.assertIn(expected[path], html)
                self.assertIn('aria-label="Data freshness"', html)
                self.assertIn('retrieval/check time (UTC)', html)
                self.assertIn('monthly', html)
                self.assertNotIn('refreshed daily', html)
                self.assertNotIn('2024-04-01', html)
                self.assertNotIn('2024-04-02', html)
                self.assertEqual(1, html.count('<h1'))
                HTMLParser().feed(html)
        self.assertIn('City housing-data period:</b> February 2024', pages['states/california.html'])
        self.assertNotIn('City housing-data period', pages['states.html'])
        self.assertFalse((self.root/'cities/ca-tiny.html').exists())

    def test_valid_input_seo_titles_remain_exact(self):
        pages = self.build()
        titles = ['Median Home Price in Example, CA (2024) | Home Price Map',
                  'Median Home Price in Example County, CA (2024) | Home Price Map',
                  'Most Expensive & Cheapest Counties in California (2024) | Home Price Map',
                  'Home Prices by State | Home Price Map']
        for html, title in zip(pages.values(), titles):
            self.assertEqual(title, re.search(r'<title>(.*?)</title>',html).group(1))

    def test_invalid_and_missing_observation_dates_render_unavailable_without_crash(self):
        for stamp in (None, 'bad', '2024-02-30', '20240229', 123):
            with self.subTest(stamp=stamp):
                self.counties['counties']['06001']['as_of'] = stamp
                self.cities['cities'][0]['as_of'] = stamp
                pages = self.build()
                for html in pages.values():
                    self.assertIn('housing-data period:</b> Unavailable', html)
                    self.assertNotIn(' as of bad', html)

    def test_only_retrieval_changes_do_not_churn_generated_bytes_or_lastmod(self):
        first = self.build()
        self.counties['updated'] = '2024-04-04T04:00:00Z'
        self.cities['updated'] = 'invalid-check-timestamp'
        second = self.build('2024-04-05')
        self.assertEqual(first, second)
        for path in first:
            self.assertEqual('2024-04-03', PageProvenance(self.root).lastmod_for(self.root/path))

    def test_observation_change_updates_label_without_changing_unchanged_hub_date(self):
        self.build()
        self.cities['cities'][0]['as_of'] = '2024-03-31'
        pages = self.build('2024-04-05')
        self.assertIn('City housing-data period:</b> March 2024', pages['cities/ca-example.html'])
        self.assertEqual('2024-04-05', PageProvenance(self.root).lastmod_for(self.root/'cities/ca-example.html'))
        self.assertEqual('2024-04-03', PageProvenance(self.root).lastmod_for(self.root/'states.html'))

    def test_pilot_shaped_invalid_dates_cannot_crash_or_invent_same_month_comparison(self):
        for name, key in (('Los Angeles','losangeles'),('Long Beach','longbeach')):
            self.cities['cities'].append({'name':name,'state':'CA','county':'Example County',
                                         'value':150000,'yoy_pct':1,'as_of':123})
            self.crime['cities']['CA|'+key] = {'name':name,'state':'CA','population':6000,
                'violent_crime_rate':100,'property_crime_rate':200}
        for stamp in (123, None, 'bad', '2024-02-30', '20240229'):
            with self.subTest(stamp=stamp):
                for city in self.cities['cities'][2:]:
                    city['as_of'] = stamp
                self.build()
                html = (self.root/'cities/ca-los-angeles.html').read_text(encoding='utf-8')
                self.assertIn('City housing-data period:</b> Unavailable', html)
                self.assertNotIn('class="hero local-comparison"', html)
        for city in self.cities['cities'][2:]:
            city['as_of'] = '2024-02-29'
        self.build()
        html = (self.root/'cities/ca-los-angeles.html').read_text(encoding='utf-8')
        self.assertIn('for the same reporting month (2024-02-29)', html)
        self.assertIn('about the same as Los Angeles', html)


if __name__ == '__main__':
    unittest.main()
