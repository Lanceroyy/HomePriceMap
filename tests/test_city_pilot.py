import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

from city_pages_builder import local_comparison_section, targeted_context_section, meta_description  # noqa: E402


def city(name, state, county, value, as_of="2026-07-31"):
    return {
        "name": name,
        "state": state,
        "county": county,
        "value": value,
        "as_of": as_of,
    }


class CityPilotTests(unittest.TestCase):
    def test_targeted_context_explains_income_without_a_payment_promise(self):
        target = city('Aspen', 'CO', 'Pitkin County', 3_000_000)
        income = {'median_household_income': 75000}
        county = {'name': 'Pitkin County', 'state': 'CO', 'value': 1_500_000, 'as_of': target['as_of']}
        html = targeted_context_section(target, income, county)
        self.assertIn('40.0', html)
        self.assertIn('$75,000', html)
        self.assertIn('100.0% above', html)
        self.assertIn('July 2026', html)
        self.assertIn('not a required salary', html)
        self.assertIn('co-pitkin-county.html', html)
        county['as_of'] = '2026-06-30'
        self.assertNotIn('100.0% above', targeted_context_section(target, income, county))
        county['as_of'] = target['as_of']
        county['state'] = 'CA'
        self.assertNotIn('100.0% above', targeted_context_section(target, income, county))

    def test_targeted_context_is_limited_and_handles_missing_capped_income(self):
        self.assertEqual('', targeted_context_section(city('Denver', 'CO', 'Denver County', 500000), {}, {}))
        target = city('Beverly Hills', 'CA', 'Los Angeles County', 3_000_000)
        self.assertEqual('', targeted_context_section(target, None, None))
        self.assertEqual('', targeted_context_section(target, {'median_household_income':0}, None))
        html = targeted_context_section(target, {'median_household_income':250000, 'top_coded':True}, None)
        self.assertIn('no more than', html)
        self.assertIn('$250,000+', html)
        self.assertIn('../los-angeles-county-home-price-gaps.html', html)

    def test_long_descriptions_keep_distinctive_income_information(self):
        name = 'A deliberately long city name used to test informative descriptions'
        description = meta_description(name, 'CA', 1_000_000, 'up 2% from a year earlier.',
                                       {'median_household_income':100000}, 'Los Angeles County')
        self.assertIn('about 10.0x local household income', description)
        capped = meta_description('Aspen', 'CO', 3_000_000, 'down 2% from a year earlier.',
                                  {'median_household_income':250000, 'top_coded':True}, 'Pitkin County')
        self.assertIn('down 2%', capped)
        self.assertIn('no more than 12.0x', capped)

    def setUp(self):
        self.la = city("Los Angeles", "CA", "Los Angeles County", 1_000_000)
        self.canton = city("Canton", "GA", "Cherokee County", 500_000)
        records = [
            city("Long Beach", "CA", "Los Angeles County", 900_000),
            city("Pasadena", "CA", "Los Angeles County", 1_200_000),
            city("Santa Monica", "CA", "Los Angeles County", 1_500_000),
            city("Woodstock", "GA", "Cherokee County", 450_000),
            city("Holly Springs", "GA", "Cherokee County", 400_000),
        ]
        self.eligible = {
            (record["state"], record["county"], record["name"]): record
            for record in records
        }

    def test_los_angeles_uses_same_month_published_peers_and_real_deltas(self):
        html = local_comparison_section(self.la, self.eligible)
        self.assertIn("Los Angeles County", html)
        self.assertIn('href="ca-long-beach.html"', html)
        self.assertIn("$900,000", html)
        self.assertIn("10.0% lower", html)
        self.assertIn('href="ca-pasadena.html"', html)
        self.assertIn("20.0% higher", html)
        self.assertIn('href="ca-santa-monica.html"', html)
        self.assertIn("50.0% higher", html)
        self.assertIn("typical home values", html)

    def test_canton_uses_cherokee_county_peers(self):
        html = local_comparison_section(self.canton, self.eligible)
        self.assertIn('href="ga-woodstock.html"', html)
        self.assertIn('href="ga-holly-springs.html"', html)
        self.assertNotIn("Pasadena", html)

    def test_beverly_hills_ca_adds_only_published_local_peers(self):
        target = city("Beverly Hills", "CA", "Los Angeles County", 4_000_000)
        peers = [
            self.la,
            city("Santa Monica", "CA", "Los Angeles County", 2_000_000),
            city("West Hollywood", "CA", "Los Angeles County", 1_200_000),
        ]
        eligible = {(p["state"], p["county"], p["name"]): p for p in peers}
        html = local_comparison_section(target, eligible)
        self.assertIn('href="ca-los-angeles.html"', html)
        self.assertIn("75.0% lower than Beverly Hills", html)
        self.assertIn('href="ca-santa-monica.html"', html)
        self.assertIn("50.0% lower than Beverly Hills", html)
        self.assertIn('href="ca-west-hollywood.html"', html)
        self.assertIn("70.0% lower than Beverly Hills", html)
        self.assertEqual("", local_comparison_section(
            city("Beverly Hills", "MI", "Oakland County", 600_000), eligible
        ))
        peers[1]["as_of"] = "2026-06-30"
        peers[2]["county"] = "Orange County"
        html = local_comparison_section(target, eligible)
        self.assertIn("Los Angeles</a>", html)
        self.assertNotIn("Santa Monica</a>", html)
        self.assertNotIn("West Hollywood</a>", html)

    def test_wrong_county_stale_month_and_unpublished_peers_are_omitted(self):
        self.eligible[("CA", "Los Angeles County", "Pasadena")]["county"] = "Orange County"
        self.eligible[("CA", "Los Angeles County", "Santa Monica")]["as_of"] = "2026-06-30"
        html = local_comparison_section(self.la, self.eligible)
        self.assertIn("Long Beach", html)
        self.assertNotIn("Pasadena", html)
        self.assertNotIn("Santa Monica", html)
        self.assertEqual("", local_comparison_section(self.la, {}))
        self.assertEqual("", local_comparison_section(city("Denver", "CO", "Denver County", 500_000), self.eligible))

    def test_escapes_displayed_county_and_rejects_invalid_values(self):
        self.la["county"] = "Los Angeles & <Metro>"
        peer = self.eligible.pop(("CA", "Los Angeles County", "Long Beach"))
        peer["county"] = self.la["county"]
        self.eligible[("CA", peer["county"], peer["name"])] = peer
        html = local_comparison_section(self.la, self.eligible)
        self.assertIn("Los Angeles &amp; &lt;Metro&gt;", html)
        self.assertNotIn("<Metro>", html)
        self.la["value"] = 0
        self.assertEqual("", local_comparison_section(self.la, self.eligible))

    def test_maintained_pages_link_directly_to_pilot_profiles(self):
        for filename in ("index.html", "cities.html"):
            text = (ROOT / filename).read_text(encoding="utf-8")
            with self.subTest(filename=filename):
                self.assertIn('href="cities/ca-los-angeles.html"', text)
                self.assertIn('href="cities/ga-canton.html"', text)


if __name__ == "__main__":
    unittest.main()
