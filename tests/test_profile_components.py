import math
import re
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

from profile_components import (  # noqa: E402
    load_history_series,
    prune_stale_html,
    render_history_section,
)


class ProfileHistoryComponentTests(unittest.TestCase):
    def test_requires_two_valid_observations(self):
        self.assertEqual("", render_history_section([], "Example"))
        self.assertEqual(
            "",
            render_history_section(
                [
                    {"as_of": "2026-07-31", "value": 100000},
                    {"as_of": "bad", "value": None},
                ],
                "Example",
            ),
        )

    def test_renders_sorted_accessible_svg_summary_and_table(self):
        html = render_history_section(
            [
                {"as_of": "2026-07-31", "value": 255000, "yoy_pct": 2.0},
                {"as_of": "2026-05-31", "value": 250000, "yoy_pct": 1.0},
                {"as_of": "2026-06-30", "value": 252500, "yoy_pct": 1.5},
            ],
            "Rock & Roll <County>",
        )

        self.assertIn('class="history-section"', html)
        self.assertIn('<svg class="history-chart"', html)
        self.assertIn('role="img"', html)
        self.assertIn("Rock &amp; Roll &lt;County&gt;", html)
        self.assertNotIn("Rock & Roll <County>", html)
        table_dates = re.findall(r"<tr><td>([^<]+)</td>", html)
        self.assertEqual(["May 2026", "Jun 2026", "Jul 2026"], table_dates)
        self.assertIn("$250,000", html)
        self.assertIn("$255,000", html)
        self.assertIn("increased by 2.0%", html)
        self.assertIn('<div class="sr-only">\n    <table class="history-table">', html)
        self.assertEqual(3, html.count("<tr><td>"))

    def test_flat_series_has_only_finite_svg_coordinates(self):
        html = render_history_section(
            [
                {"as_of": "2026-05-31", "value": 300000},
                {"as_of": "2026-06-30", "value": 300000},
                {"as_of": "2026-07-31", "value": 300000},
            ],
            "Flat County",
        )

        points_match = re.search(r'<polyline[^>]+points="([^"]+)"', html)
        self.assertIsNotNone(points_match)
        coordinates = [float(value) for pair in points_match.group(1).split() for value in pair.split(",")]
        self.assertTrue(all(math.isfinite(value) for value in coordinates))
        self.assertIn("was unchanged", html)

    def test_invalid_rows_are_filtered_without_crashing(self):
        html = render_history_section(
            [
                None,
                {},
                {"as_of": "2026-05-31", "value": "not-a-number"},
                {"as_of": "2026-06-30", "value": 100000},
                {"as_of": "2026-07-31", "value": 101000},
            ],
            "Example",
        )
        self.assertEqual(2, html.count("<tr><td>"))

    def test_malformed_series_and_yoy_values_are_safely_ignored(self):
        self.assertEqual("", render_history_section(42, "Bad Series"))
        html = render_history_section(
            [
                {"as_of": "2026-05-31", "value": 100000, "yoy_pct": "bad"},
                {"as_of": "2026-06-30", "value": 101000, "yoy_pct": True},
                {"as_of": "2026-07-31", "value": 102000, "yoy_pct": float("inf")},
            ],
            "Bad YoY",
        )
        self.assertEqual(3, html.count("<tr><td>"))
        self.assertEqual(3, html.count("<td>n/a</td>"))

    def test_visible_chart_labels_are_outside_scaled_svg(self):
        html = render_history_section(
            [
                {"as_of": "2026-05-31", "value": 100000},
                {"as_of": "2026-07-31", "value": 102000},
            ],
            "Readable County",
        )
        self.assertIn('class="history-chart-range"', html)
        self.assertIn('class="history-chart-labels"', html)
        self.assertNotIn("<text ", html)

    def test_history_loader_omits_missing_or_malformed_files(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            missing = Path(temp_dir) / "missing.json"
            malformed = Path(temp_dir) / "malformed.json"
            malformed.write_text("{not json", encoding="utf-8")
            wrong_shape = Path(temp_dir) / "wrong.json"
            wrong_shape.write_text('{"series": []}', encoding="utf-8")

            self.assertEqual({}, load_history_series(missing))
            self.assertEqual({}, load_history_series(malformed))
            self.assertEqual({}, load_history_series(wrong_shape))

    def test_prune_stale_html_removes_only_obsolete_builder_pages(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            output_dir = Path(temp_dir)
            keep_files = [output_dir / f"keep-{index}.html" for index in range(9)]
            stale = output_dir / "stale.html"
            unrelated = output_dir / "notes.txt"
            for keep in keep_files:
                keep.write_text("keep", encoding="utf-8")
            stale.write_text("stale", encoding="utf-8")
            unrelated.write_text("notes", encoding="utf-8")

            removed = prune_stale_html(
                output_dir, {keep.name for keep in keep_files}
            )

            self.assertEqual(["stale.html"], removed)
            self.assertTrue(all(keep.exists() for keep in keep_files))
            self.assertFalse(stale.exists())
            self.assertTrue(unrelated.exists())

    def test_prune_stale_html_refuses_empty_or_catastrophic_output(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            output_dir = Path(temp_dir)
            existing = [output_dir / f"page-{index}.html" for index in range(10)]
            for page in existing:
                page.write_text("generated", encoding="utf-8")

            with self.assertRaisesRegex(RuntimeError, "expected at least"):
                prune_stale_html(output_dir, set(), minimum_expected=1)
            self.assertTrue(all(page.exists() for page in existing))

            with self.assertRaisesRegex(RuntimeError, "more than 10%"):
                prune_stale_html(output_dir, {"page-0.html"}, minimum_expected=1)
            self.assertTrue(all(page.exists() for page in existing))


if __name__ == "__main__":
    unittest.main()
