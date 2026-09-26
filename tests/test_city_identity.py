import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

from city_identity import (  # noqa: E402
    city_candidates_by_key,
    city_history_key,
    legacy_city_key,
    match_city_source,
    safe_city_history,
)
from fetch_data import build_city_data  # noqa: E402
from process_crime_data import matched_county_for_crime_row  # noqa: E402
from build_city_coords import add_coordinate  # noqa: E402


def city(name, state, county, value):
    return {"name": name, "state": state, "county": county,
            "value": value, "as_of": "2026-07-31"}


class CityIdentityTests(unittest.TestCase):
    def test_fbi_and_census_records_match_only_the_right_hot_springs(self):
        hot_springs = city("Hot Springs", "AR", "Garland County", 245356)
        village = city("Hot Springs Village", "AR", "Garland County", 309546)
        candidates = city_candidates_by_key([hot_springs, village])
        crime = {"AR|hotsprings": {"name": "Hot Springs Village", "state": "AR", "population": 15861}}
        income = {"AR|hotsprings": {"name": "Hot Springs city", "state": "AR", "median_household_income": 47760}}

        self.assertIsNone(match_city_source(hot_springs, crime, candidates))
        self.assertIs(crime["AR|hotsprings"], match_city_source(village, crime, candidates))
        self.assertIs(income["AR|hotsprings"], match_city_source(hot_springs, income, candidates, allow_city_suffix=True))
        self.assertIsNone(match_city_source(village, income, candidates, allow_city_suffix=True))
        crime["AR|hotsprings"] = [
            {"name": "Hot Springs", "state": "AR", "population": 38001},
            {"name": "Hot Springs Village", "state": "AR", "population": 15861},
        ]
        self.assertEqual(38001, match_city_source(hot_springs, crime, candidates)["population"])
        self.assertEqual(15861, match_city_source(village, crime, candidates)["population"])

    def test_same_named_cities_in_different_counties_stay_ambiguous(self):
        first = city("Gaines", "MI", "Kent County", 200000)
        second = city("Gaines", "MI", "Genesee County", 250000)
        candidates = city_candidates_by_key([first, second])
        crime = {"MI|gaines": {"name": "Gaines", "state": "MI", "population": 8000}}
        self.assertIsNone(match_city_source(first, crime, candidates))
        self.assertIsNone(match_city_source(second, crime, candidates))
        self.assertIsNone(matched_county_for_crime_row(
            {"state": "MI", "city": "Gaines"}, candidates))

    def test_crime_rollup_selects_county_by_full_name_not_last_record(self):
        city_record = city("Lincoln", "CA", "Placer County", 600000)
        township = city("Lincoln Township", "CA", "San Joaquin County", 400000)
        candidates = city_candidates_by_key([city_record, township])
        self.assertEqual("Placer County", matched_county_for_crime_row(
            {"state": "CA", "city": "Lincoln"}, candidates))
        self.assertEqual("San Joaquin County", matched_county_for_crime_row(
            {"state": "CA", "city": "Lincoln Township"}, candidates))

    def test_legacy_history_is_used_only_for_a_unique_matching_city(self):
        la = city("Los Angeles", "CA", "Los Angeles County", 946268)
        royal_oak = city("Royal Oak", "MI", "Oakland County", 337493)
        township = city("Royal Oak Township", "MI", "Oakland County", 140469)
        candidates = city_candidates_by_key([la, royal_oak, township])
        legacy = [{"as_of": "2026-06-30", "value": 949479},
                  {"as_of": "2026-07-31", "value": 946268}]
        history = {legacy_city_key(la): legacy,
                   legacy_city_key(royal_oak): [{"as_of": "2026-07-31", "value": 140469}]}

        self.assertEqual(legacy, safe_city_history(la, history, candidates))
        self.assertEqual([], safe_city_history(royal_oak, history, candidates))
        self.assertEqual([], safe_city_history(township, history, candidates))
        history[city_history_key(royal_oak)] = [{"as_of": "2026-07-31", "value": 337493}]
        self.assertEqual(history[city_history_key(royal_oak)], safe_city_history(royal_oak, history, candidates))
        la["value"] = 1
        self.assertEqual([], safe_city_history(la, history, candidates))

    def test_coordinate_collision_keeps_prices_but_omits_uncertain_markers(self):
        rows = [
            {"RegionName": "Hot Springs", "State": "AR", "CountyName": "Garland County", "2026-07-31": "245356"},
            {"RegionName": "Hot Springs Village", "State": "AR", "CountyName": "Garland County", "2026-07-31": "309546"},
            {"RegionName": "Los Angeles", "State": "CA", "CountyName": "Los Angeles County", "2026-07-31": "946268"},
        ]
        coords = {"AR|hotsprings": {"name": "Hot Springs", "lat": 34.48, "lon": -93.05},
                  "CA|losangeles": {"name": "Los Angeles", "lat": 34.02, "lon": -118.41}}
        result = build_city_data(rows, ["2026-07-31"], coords)
        self.assertEqual(3, len(result))
        self.assertIsNone(result[0]["lat"])
        self.assertIsNone(result[1]["lon"])
        self.assertEqual(34.02, result[2]["lat"])

    def test_coordinate_source_name_must_match_city(self):
        rows = [
            {"RegionName": "Ocean City", "State": "MD", "CountyName": "Worcester County", "2026-07-31": "400000"},
            {"RegionName": "Carson City", "State": "NV", "CountyName": "Carson City", "2026-07-31": "450000"},
            {"RegionName": "Canton", "State": "GA", "CountyName": "Cherokee County", "2026-07-31": "500000"},
        ]
        coords = {
            "MD|ocean": {"name": "Ocean", "lat": 39.6, "lon": -78.9},
            "NV|carson": {"name": "Carson", "lat": 39.1, "lon": -119.7},
            "GA|canton": {"name": "Canton", "lat": 34.2, "lon": -84.5},
        }
        result = build_city_data(rows, ["2026-07-31"], coords)
        self.assertEqual(3, len(result))
        self.assertIsNone(result[0]["lat"])
        self.assertIsNone(result[1]["lat"])
        self.assertEqual(34.2, result[2]["lat"])
        modern_coords = dict(coords)
        modern_coords["MD|ocean"] = {**coords["MD|ocean"], "source_name": "Ocean city"}
        modern_coords["NV|carson"] = {**coords["NV|carson"], "source_name": "Carson City"}
        modern = build_city_data(rows, ["2026-07-31"], modern_coords)
        self.assertIsNone(modern[0]["lat"])
        self.assertEqual(39.1, modern[1]["lat"])

    def test_gazetteer_duplicate_key_is_marked_ambiguous(self):
        lookup = {}
        self.assertFalse(add_coordinate(lookup, "MD", "Ocean city", 39.1, -74.5))
        self.assertEqual("Ocean city", lookup["MD|ocean"]["source_name"])
        self.assertTrue(add_coordinate(lookup, "MD", "Ocean town", 39.6, -78.9))
        self.assertEqual({"ambiguous": True}, lookup["MD|ocean"])
        self.assertFalse(add_coordinate(lookup, "MD", "Ocean village", 39.2, -75.0))

    def test_city_map_loads_identity_guard_and_skips_uncertain_markers(self):
        page = (ROOT / "cities.html").read_text(encoding="utf-8")
        script = (ROOT / "js" / "cities.js").read_text(encoding="utf-8")
        self.assertLess(page.index('src="js/city-identity.js"'), page.index('src="js/cities.js"'))
        self.assertIn("cities.filter(window.CityIdentity.hasCoordinates)", script)
        self.assertIn("window.CityIdentity.matchedSource(rec, crimeByCityKey", script)
        self.assertIn("window.CityIdentity.matchedSource(rec, incomeByCityKey", script)


if __name__ == "__main__":
    unittest.main()
