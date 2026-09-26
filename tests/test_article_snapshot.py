import json
import statistics
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class ArticleSnapshotTests(unittest.TestCase):
    def test_affordability_article_is_dated_and_matches_june_prices(self):
        article = (ROOT / "cheapest-counties-arent-the-most-affordable.html").read_text(encoding="utf-8")
        home = (ROOT / "index.html").read_text(encoding="utf-8")
        counties = json.loads((ROOT / "data/county_prices.json").read_text(encoding="utf-8"))["counties"]
        history = json.loads((ROOT / "data/history/county_history.json").read_text(encoding="utf-8"))["series"]
        income = json.loads((ROOT / "data/income_data_county.json").read_text(encoding="utf-8"))["counties"]

        self.assertIn("A June 2026 snapshot", article)
        self.assertIn("June 30, 2026", article)
        self.assertIn("June 2026 snapshot", home)
        self.assertNotIn("Figures current as of the most recent releases", article)

        figures = [
            ("KY", "Owsley County", 141654, 6.4),
            ("VA", "Fairfax County", 779439, 5.1),
            ("MD", "Montgomery County", 627198, 4.7),
            ("AZ", "Maricopa County", 461315, 5.2),
            ("IL", "Cook County", 343350, 4.1),
            ("TX", "Harris County", 282169, 3.8),
            ("NM", "Socorro County", 199187, 5.4),
            ("TN", "Hancock County", 180167, 5.2),
            ("AL", "Greene County", 135952, 4.7),
            ("NM", "Los Alamos County", 593582, 4.0),
            ("VA", "Stafford County", 547004, 4.0),
        ]
        by_name = {(rec["state"], rec["name"]): fips for fips, rec in counties.items()}
        for state, name, expected_price, expected_ratio in figures:
            with self.subTest(name=name):
                fips = by_name[(state, name)]
                june = next(point for point in history[fips] if point["as_of"] == "2026-06-30")
                self.assertEqual(expected_price, june["value"])
                self.assertEqual(expected_ratio, round(june["value"] / income[fips]["median_household_income"], 1))

        june_ratios = []
        for fips, income_rec in income.items():
            point = next((point for point in history.get(fips, []) if point["as_of"] == "2026-06-30"), None)
            if point and income_rec.get("median_household_income"):
                june_ratios.append(point["value"] / income_rec["median_household_income"])
        self.assertEqual(3062, len(june_ratios))
        self.assertEqual(3.7, round(statistics.median(june_ratios), 1))


if __name__ == "__main__":
    unittest.main()
