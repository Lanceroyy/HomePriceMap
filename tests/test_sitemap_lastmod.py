import json
from contextlib import ExitStack
from datetime import datetime, timezone
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
from page_provenance import PageProvenance
import city_pages_builder as city_builder
import seo_pages_builder as county_builder
import state_pages_builder as state_builder


class PageProvenanceTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.page = self.root / 'counties/example.html'
        self.page.parent.mkdir()
        self.ledger = self.root / 'data/sitemap_page_provenance.json'

    def writer(self, stamp='2024-02-29'):
        return PageProvenance(self.root, written_on=stamp)

    def seed(self):
        writer = self.writer()
        writer.write(self.page, '<main>$100,000</main>')
        writer.save()

    def test_new_generated_page_records_actual_write_date_not_source_month(self):
        self.seed()
        self.assertEqual('2024-02-29', self.writer().lastmod_for(self.page))
        self.assertTrue(self.ledger.is_file())

    def test_unchanged_page_retains_date_across_runs_and_does_not_rewrite(self):
        self.seed()
        before = self.ledger.read_bytes()
        writer = self.writer('2024-03-02')
        with patch.object(Path, 'write_text', side_effect=AssertionError('unexpected page write')):
            writer.write(self.page, '<main>$100,000</main>')
        writer.save()
        self.assertEqual('2024-02-29', writer.lastmod_for(self.page))
        self.assertEqual(before, self.ledger.read_bytes())

    def test_real_content_change_advances_only_its_date(self):
        self.seed()
        writer = self.writer('2024-03-02')
        writer.write(self.page, '<main>$110,000</main>')
        writer.save()
        self.assertEqual('2024-03-02', self.writer().lastmod_for(self.page))

    def test_existing_unchanged_page_without_provenance_stays_unknown(self):
        self.page.write_text('<main>Existing</main>', encoding='utf-8')
        writer = self.writer()
        writer.write(self.page, '<main>Existing</main>')
        writer.save()
        self.assertIsNone(self.writer().lastmod_for(self.page))

    def test_line_endings_and_checkout_mtime_are_not_new_content(self):
        writer = self.writer()
        writer.write(self.page, '<main>Value\n$100,000</main>')
        writer.save()
        self.page.write_bytes(b'<main>Value\r\n$100,000</main>')
        later = self.writer('2024-03-02')
        later.write(self.page, '<main>Value\n$100,000</main>')
        later.save()
        self.assertEqual('2024-02-29', later.lastmod_for(self.page))

    def test_invalid_or_absent_evidence_dates_are_never_inferred(self):
        for stamp in ('', 'bad', '2024-02-30', '20240229', '2024-2-29', '2999-01-01', True):
            with self.subTest(stamp=stamp):
                writer = self.writer(stamp)
                writer.write(self.page, '<main>{}</main>'.format(stamp))
                writer.save()
                self.assertIsNone(self.writer().lastmod_for(self.page))

    def test_invalid_matching_ledger_date_is_not_repaired_by_noop_build(self):
        self.seed()
        original = json.loads(self.ledger.read_text())
        for stamp in (None, '', False, '2024-02-30', '2999-01-01', '2024-02-29T00:00:00Z'):
            with self.subTest(stamp=stamp):
                original['pages']['counties/example.html']['lastmod'] = stamp
                self.ledger.write_text(json.dumps(original), encoding='utf-8')
                writer = self.writer('2024-03-02')
                writer.write(self.page, '<main>$100,000</main>')
                writer.save()
                self.assertIsNone(writer.lastmod_for(self.page))

    def test_absent_corrupt_or_wrong_version_ledger_omits_dates(self):
        self.seed()
        for payload in ('{', '[]', '{"version":2,"pages":{}}', '{"version":true,"pages":{}}',
                        '{"version":1,"pages":[]}'):
            with self.subTest(payload=payload):
                self.ledger.write_text(payload, encoding='utf-8')
                self.assertIsNone(self.writer().lastmod_for(self.page))
        self.ledger.unlink()
        self.assertIsNone(self.writer().lastmod_for(self.page))

    def test_out_of_band_edit_cannot_reuse_old_date(self):
        self.seed()
        self.page.write_text('<main>Unproven change</main>', encoding='utf-8')
        writer = self.writer('2024-03-02')
        self.assertIsNone(writer.lastmod_for(self.page))
        writer.write(self.page, '<main>Unproven change</main>')
        writer.save()
        self.assertIsNone(self.writer().lastmod_for(self.page))

    def test_missing_pages_and_unpublished_records_lose_dates(self):
        self.seed()
        self.page.unlink()
        writer = self.writer()
        self.assertIsNone(writer.lastmod_for(self.page))
        writer.retain([])
        writer.save()
        self.assertEqual({}, json.loads(self.ledger.read_text())['pages'])

    def test_paths_cannot_escape_site_root(self):
        writer = self.writer()
        with self.assertRaises(ValueError):
            writer.write(self.root.parent / 'outside.html', 'no')

    def test_failed_page_write_cannot_create_new_provenance(self):
        writer = self.writer()
        with patch.object(Path, 'write_text', side_effect=OSError('fixture write failure')):
            with self.assertRaises(OSError):
                writer.write(self.page, 'new')
        self.assertIsNone(writer.lastmod_for(self.page))
        writer.save()
        self.assertFalse(self.ledger.exists())

    def test_failed_atomic_save_preserves_old_ledger_and_cleans_only_own_temp(self):
        self.seed()
        original = self.ledger.read_bytes()
        writer = self.writer('2024-03-02')
        writer.write(self.page, '<main>$120,000</main>')
        with patch.object(Path, 'replace', side_effect=OSError('fixture replace failure')):
            with self.assertRaises(OSError):
                writer.save()
        self.assertEqual(original, self.ledger.read_bytes())
        self.assertEqual([], list(self.ledger.parent.glob('.page-provenance-*.tmp')))
        # Old evidence does not validate the newly changed page after failure.
        self.assertIsNone(self.writer().lastmod_for(self.page))

    def test_corrupt_ledger_can_recover_only_from_a_real_new_write(self):
        self.seed()
        self.ledger.write_text('{', encoding='utf-8')
        writer = self.writer('2024-03-02')
        writer.write(self.page, '<main>$130,000</main>')
        writer.save()
        self.assertEqual('2024-03-02', self.writer().lastmod_for(self.page))

    def test_restored_identical_output_retains_known_date_instead_of_rebuild_day(self):
        self.seed()
        self.page.unlink()
        writer = self.writer('2024-03-02')
        writer.write(self.page, '<main>$100,000</main>')
        writer.save()
        self.assertEqual('2024-02-29', self.writer().lastmod_for(self.page))

    def test_restored_identical_output_with_unknown_date_stays_unknown(self):
        self.page.write_text('<main>Legacy</main>')
        writer = self.writer()
        writer.write(self.page, '<main>Legacy</main>')
        writer.save()
        self.page.unlink()
        later = self.writer('2024-03-02')
        later.write(self.page, '<main>Legacy</main>')
        later.save()
        self.assertIsNone(self.writer().lastmod_for(self.page))

    def test_default_date_is_captured_at_write_even_across_utc_midnight(self):
        with patch('page_provenance.datetime') as clock:
            clock.now.return_value = datetime(2024, 2, 29, 23, 59, tzinfo=timezone.utc)
            writer = PageProvenance(self.root)
            clock.now.return_value = datetime(2024, 3, 1, 0, 1, tzinfo=timezone.utc)
            writer.write(self.page, '<main>New content</main>')
            writer.save()
            self.assertEqual('2024-03-01', writer.lastmod_for(self.page))


class SitemapLastmodIntegrationTests(unittest.TestCase):
    def test_final_builder_verifies_dates_and_retains_url_selection(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            city = root / 'cities/ca-example.html'
            city.parent.mkdir()
            city.write_text('<main>Existing city</main>')
            writer = PageProvenance(root, written_on='2024-02-29')
            county = root / 'counties/ca-example-county.html'
            county.parent.mkdir()
            writer.write(county, '<main>Changed county</main>')
            writer.save()
            data = {'updated':'2024-03-02T00:00:00Z', 'counties':{
                '06001': {'name':'Example County', 'state':'CA', 'value':100000, 'as_of':'2023-12-31'},
                '06002': {'name':'Excluded County', 'state':'CA', 'value':None}}}
            with patch.object(state_builder, 'ROOT', root):
                state_builder.build_sitemap([], data)
            ns = {'s':'http://www.sitemaps.org/schemas/sitemap/0.9'}
            urls = {n.findtext('s:loc', namespaces=ns):n.findtext('s:lastmod', namespaces=ns)
                    for n in ET.fromstring((root/'sitemap.xml').read_bytes())}
            self.assertEqual('2024-02-29', urls['https://homepricemap.us/counties/ca-example-county.html'])
            self.assertIsNone(urls['https://homepricemap.us/cities/ca-example.html'])
            self.assertIsNone(urls['https://homepricemap.us/'])
            self.assertNotIn('https://homepricemap.us/counties/ca-excluded-county.html', urls)
            self.assertFalse(any('404.html' in url or '?' in url for url in urls))

    def test_small_sequential_builder_runs_preserve_hub_date_and_detect_real_changes(self):
        with tempfile.TemporaryDirectory() as directory, ExitStack() as stack:
            root = Path(directory)
            data_dir = root / 'data'
            data_dir.mkdir()
            county_data = {'counties':{'06001':{'name':'Example County', 'state':'CA',
                           'value':100000, 'yoy_pct':2.0, 'as_of':'2023-12-31'}}}
            city_data = {'cities':[{'name':'Example', 'state':'CA', 'county':'Example County',
                         'value':110000, 'yoy_pct':1.0, 'as_of':'2023-12-31'}]}
            crime = {'cities':{'CA|example':{'name':'Example','state':'CA','population':6000,
                      'violent_crime_rate':100, 'property_crime_rate':200}}}
            (data_dir/'city_prices.json').write_text(json.dumps(city_data))
            (data_dir/'crime_data_city.json').write_text(json.dumps(crime))
            day = ['2024-02-29']
            for module in (city_builder, county_builder, state_builder):
                stack.enter_context(patch.object(module, 'ROOT', root))
                stack.enter_context(patch.object(module, 'OUT_DIR', root / {
                    city_builder:'cities', county_builder:'counties', state_builder:'states'}[module]))
                stack.enter_context(patch.object(module, 'PageProvenance',
                                    lambda site_root: PageProvenance(site_root, written_on=day[0])))
            for name, filename in (('CITY_PATH','city_prices.json'), ('COUNTY_PATH','county_prices.json'),
                                   ('CITY_CRIME_PATH','crime_data_city.json'),
                                   ('CITY_INCOME_PATH','missing-income.json'), ('CITY_HISTORY_PATH','missing-history.json')):
                stack.enter_context(patch.object(city_builder, name, data_dir / filename))
            for name, value in (('CITY_PATH',data_dir/'city_prices.json'), ('CITY_DIR',root/'cities'),
                                ('HISTORY_PATH',data_dir/'missing-history.json')):
                stack.enter_context(patch.object(county_builder, name, value))
            stack.enter_context(patch.object(city_builder, 'MIN_EXPECTED_PROFILES', 1))
            stack.enter_context(patch.object(county_builder, 'MIN_EXPECTED_PROFILES', 1))

            def run():
                (data_dir/'county_prices.json').write_text(json.dumps(county_data))
                city_builder.build()
                county_builder.build_pages(county_data)
                # The intermediate county sitemap must not erase provenance.
                county_builder.build_sitemap([])
                state_urls = state_builder.build_state_pages(county_data, None, city_data=city_data)
                state_builder.build_sitemap(state_urls, county_data)

            run()
            hub = root / 'states.html'
            county_page = root / 'counties/ca-example-county.html'
            city_page = root / 'cities/ca-example.html'
            for page in (hub, county_page, city_page, root/'states/california.html'):
                self.assertEqual('2024-02-29', PageProvenance(root).lastmod_for(page))
            day[0] = '2024-03-02'
            run()
            self.assertEqual('2024-02-29', PageProvenance(root).lastmod_for(county_page))
            county_data['counties']['06001']['value'] = 120000
            run()
            self.assertEqual('2024-03-02', PageProvenance(root).lastmod_for(county_page))
            self.assertEqual('2024-02-29', PageProvenance(root).lastmod_for(hub))

    def test_workflow_persists_provenance_without_changing_order(self):
        workflow = (ROOT/'.github/workflows/update-data.yml').read_text(encoding='utf-8')
        self.assertIn('data/sitemap_page_provenance.json', workflow)
        positions = [workflow.index('python scripts/' + script) for script in (
            'city_pages_builder.py', 'seo_pages_builder.py', 'place_index_builder.py', 'state_pages_builder.py')]
        self.assertEqual(sorted(positions), positions)


if __name__ == '__main__':
    unittest.main()
