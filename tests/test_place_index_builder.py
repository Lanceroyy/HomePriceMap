import json
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

from place_index_builder import build_catalog, write_catalog  # noqa: E402


class PlaceIndexBuilderTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.data_dir = Path(self.temp_dir.name)

        fixtures = {
            "county_prices.json": {
                "updated": "2026-07-31T00:00:00Z",
                "counties": {
                    "01001": {
                        "name": "Autauga County",
                        "state": "AL",
                        "value": 250000,
                        "yoy_pct": 2.5,
                        "as_of": "2026-07-31",
                    }
                },
            },
            "city_prices.json": {
                "updated": "2026-07-31T00:00:00Z",
                "cities": [
                    {
                        "name": "Alpha!",
                        "state": "AL",
                        "county": "Autauga County",
                        "value": 200000,
                        "yoy_pct": 1.0,
                        "as_of": "2026-07-31",
                    },
                    {
                        "name": "Alpha",
                        "state": "AL",
                        "county": "Autauga County",
                        "value": 210000,
                        "yoy_pct": 1.5,
                        "as_of": "2026-07-31",
                    },
                    {
                        "name": "Below Threshold",
                        "state": "AL",
                        "value": 150000,
                        "as_of": "2026-07-31",
                    },
                    {
                        "name": "Alpha city",
                        "state": "AL",
                        "county": "Autauga County",
                        "value": 190000,
                        "yoy_pct": 0.5,
                        "as_of": "2026-07-31",
                    },
                    {
                        "name": "Delta",
                        "state": "AL",
                        "county": "Autauga County",
                        "value": 220000,
                        "yoy_pct": 2.0,
                        "as_of": "2026-07-31",
                    },
                ],
            },
            "crime_data_county.json": {
                "counties": {
                    "01001": {
                        "violent_crime_rate": 210.2,
                        "property_crime_rate": 1700.4,
                        "population_covered": 42000,
                        "cities_matched": 3,
                    }
                }
            },
            "crime_data_city.json": {
                "cities": {
                    "AL|alpha": {
                        "name": "Alpha",
                        "state": "AL",
                        "population": 6000,
                        "violent_crime_rate": 120.0,
                        "property_crime_rate": 900.0,
                    },
                    "AL|belowthreshold": {
                        "name": "Below Threshold",
                        "state": "AL",
                        "population": 4999,
                        "violent_crime_rate": 100.0,
                    },
                    "AL|delta": {
                        "name": "Delta",
                        "state": "AL",
                        "population": 6000,
                        "violent_crime_rate": 120.0,
                        "property_crime_rate": 900.0,
                    },
                }
            },
            "income_data_county.json": {
                "counties": {
                    "01001": {
                        "median_household_income": 62500,
                        "top_coded": False,
                    }
                }
            },
            "income_data_city.json": {
                "cities": {
                    "AL|alpha": {
                        "name": "Alpha",
                        "state": "AL",
                        "median_household_income": 70000,
                        "top_coded": False,
                    },
                    "AL|delta": {
                        "name": "Delta city",
                        "state": "AL",
                        "median_household_income": 70000,
                        "top_coded": False,
                    },
                }
            },
        }
        for filename, payload in fixtures.items():
            (self.data_dir / filename).write_text(json.dumps(payload), encoding="utf-8")

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_build_catalog_joins_data_and_matches_published_profile_rules(self):
        catalog = build_catalog(self.data_dir)

        self.assertEqual("2026-07-31T00:00:00Z", catalog["updated"])
        self.assertEqual(2, catalog["count"])
        self.assertEqual(2, len(catalog["places"]))

        by_id = {place["id"]: place for place in catalog["places"]}
        county = by_id["county:01001"]
        self.assertEqual("/counties/al-autauga-county.html", county["url"])
        self.assertEqual("county", county["type"])
        self.assertEqual(62500, county["income"])
        self.assertEqual(4.0, county["price_to_income"])
        self.assertEqual(210.2, county["violent_crime_rate"])
        self.assertEqual(42000, county["population_covered"])

        city = by_id["city:al-delta"]
        self.assertEqual("Delta", city["name"])
        self.assertEqual(220000, city["value"])
        self.assertEqual("/cities/al-delta.html", city["url"])
        self.assertEqual(6000, city["population"])
        self.assertEqual(3.14, city["price_to_income"])
        self.assertNotIn("city:al-alpha", by_id)
        self.assertNotIn("city:al-alpha-city", by_id)
        self.assertNotIn("city:al-below-threshold", by_id)

    def test_catalog_is_deterministic_and_has_unique_profile_targets(self):
        first = build_catalog(self.data_dir)
        second = build_catalog(self.data_dir)

        self.assertEqual(first, second)
        ids = [place["id"] for place in first["places"]]
        urls = [place["url"] for place in first["places"]]
        self.assertEqual(len(ids), len(set(ids)))
        self.assertEqual(len(urls), len(set(urls)))
        self.assertTrue(all("?" not in url and "#" not in url for url in urls))
        self.assertEqual(
            sorted(first["places"], key=lambda p: (p["name"].casefold(), p["state"], p["type"], p["id"])),
            first["places"],
        )

    def test_optional_supporting_files_can_be_absent(self):
        for filename in (
            "crime_data_county.json",
            "crime_data_city.json",
            "income_data_county.json",
            "income_data_city.json",
        ):
            (self.data_dir / filename).unlink()

        catalog = build_catalog(self.data_dir)
        self.assertEqual(1, catalog["count"])
        county = catalog["places"][0]
        self.assertIsNone(county["income"])
        self.assertIsNone(county["violent_crime_rate"])

    def test_write_catalog_uses_stable_compact_json(self):
        output = self.data_dir / "nested" / "place_index.json"
        catalog = build_catalog(self.data_dir)

        write_catalog(catalog, output)

        raw = output.read_text(encoding="utf-8")
        self.assertTrue(raw.endswith("\n"))
        self.assertNotIn("\n  ", raw)
        self.assertEqual(catalog, json.loads(raw))


if __name__ == "__main__":
    unittest.main()
