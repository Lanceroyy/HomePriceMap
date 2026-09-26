import re
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
MAINTAINED_PAGES = (
    "about.html",
    "cheapest-counties-arent-the-most-affordable.html",
    "cities.html",
    "contact.html",
    "counties.html",
    "home-price-trends-by-state-2026.html",
    "index.html",
    "methodology.html",
    "privacy-policy.html",
)
BUILDERS = (
    "scripts/city_pages_builder.py",
    "scripts/seo_pages_builder.py",
    "scripts/state_pages_builder.py",
)


class DiscoveryFeatureTests(unittest.TestCase):
    def test_ga4_uses_production_only_shared_loader(self):
        for relative in MAINTAINED_PAGES + ("compare.html",) + BUILDERS:
            text = (ROOT / relative).read_text(encoding="utf-8")
            with self.subTest(page=relative):
                self.assertIn('<script src="/js/analytics-loader.js"></script>', text)
                self.assertNotIn("googletagmanager.com/gtag/js", text)

    def test_compare_page_has_canonical_accessible_search_and_states(self):
        html = (ROOT / "compare.html").read_text(encoding="utf-8")

        self.assertIn('<link rel="canonical" href="https://homepricemap.us/compare.html">', html)
        self.assertNotIn('name="robots" content="noindex', html)
        self.assertIn('id="compareSearch"', html)
        self.assertIn('role="combobox"', html)
        self.assertIn('aria-controls="compareSearchResults"', html)
        self.assertIn('id="compareSearchResults"', html)
        self.assertIn('id="comparisonEmpty"', html)
        self.assertIn('id="comparisonError"', html)
        self.assertIn('id="copyComparison"', html)
        self.assertIn('src="js/place-search.js"', html)
        self.assertIn('src="js/compare.js"', html)

    def test_homepage_has_direct_place_finder_and_comparison_entry(self):
        html = (ROOT / "index.html").read_text(encoding="utf-8")

        self.assertIn('id="homePlaceSearch"', html)
        self.assertIn('role="combobox"', html)
        self.assertIn('aria-controls="homePlaceSearchResults"', html)
        self.assertIn('id="homePlaceSearchResults"', html)
        self.assertIn('href="compare.html"', html)
        self.assertIn('src="js/place-search.js"', html)

    def test_search_controller_covers_keyboard_and_failure_states(self):
        script = (ROOT / "js" / "place-search.js").read_text(encoding="utf-8")

        for token in (
            '"ArrowDown"',
            '"ArrowUp"',
            '"Enter"',
            '"Escape"',
            "aria-activedescendant",
            "place_index.json",
            "normalize(\"NFD\")",
            "HomePriceSearch",
            "requestNumber += 1;",
        ):
            with self.subTest(token=token):
                self.assertIn(token, script)

    def test_comparison_controller_uses_fragment_not_query_state(self):
        script = (ROOT / "js" / "compare.js").read_text(encoding="utf-8")

        self.assertIn('const MAX_PLACES = 3;', script)
        self.assertIn('window.location.hash', script)
        self.assertIn('#places=', script)
        self.assertNotIn('window.location.search', script)
        self.assertIn('navigator.clipboard', script)
        self.assertIn('history.replaceState', script)
        self.assertIn('trackEvent', script)
        self.assertIn('copyStatus.textContent = "";', script)

    def test_navigation_and_builder_templates_link_to_compare(self):
        missing = []
        for relative in MAINTAINED_PAGES + BUILDERS:
            text = (ROOT / relative).read_text(encoding="utf-8")
            if not re.search(r'<a[^>]+href="(?:\.\./)?compare\.html"', text):
                missing.append(relative)
        self.assertEqual([], missing)

        for relative in ("scripts/city_pages_builder.py", "scripts/seo_pages_builder.py"):
            text = (ROOT / relative).read_text(encoding="utf-8")
            self.assertIn("compare.html#places={compare_id}", text)
            self.assertIn("history_section=render_history_section(", text)
            self.assertIn("prune_stale_html(", text)
            self.assertIn("minimum_expected=MIN_EXPECTED_PROFILES", text)

    def test_state_builder_sitemap_has_one_compare_url(self):
        builder = (ROOT / "scripts" / "state_pages_builder.py").read_text(encoding="utf-8")
        self.assertEqual(1, builder.count('SITE_URL + "/compare.html"'))

    def test_refresh_workflow_builds_catalog_before_final_state_builder(self):
        workflow = (ROOT / ".github" / "workflows" / "update-data.yml").read_text(encoding="utf-8")
        city_position = workflow.index("python scripts/city_pages_builder.py")
        county_position = workflow.index("python scripts/seo_pages_builder.py")
        catalog_position = workflow.index("python scripts/place_index_builder.py")
        state_position = workflow.index("python scripts/state_pages_builder.py")
        # County pages discover city links from files already on disk. The
        # city builder must prune/create those files first on every run.
        self.assertLess(city_position, county_position)
        self.assertLess(county_position, catalog_position)
        self.assertLess(catalog_position, state_position)
        self.assertIn("data/place_index.json", workflow)

    def test_feature_layout_has_mobile_and_accessibility_rules(self):
        stylesheet = (ROOT / "css" / "style.css").read_text(encoding="utf-8")
        for selector in (
            ".place-search",
            ".place-search-results",
            ".comparison-grid",
            ".comparison-card",
            ".history-chart",
            ".history-chart-labels",
            ".sr-only",
        ):
            with self.subTest(selector=selector):
                self.assertIn(selector, stylesheet)
        mobile = stylesheet[stylesheet.index("@media (max-width: 700px)") :]
        self.assertIn(".comparison-grid", mobile)
        self.assertIn("header.topbar nav a:first-child", mobile)
        self.assertIn(".theme-toggle { margin-left: 10px; }", mobile)
        self.assertIn(
            "grid-template-columns: repeat(auto-fit, minmax(280px, 1fr));",
            stylesheet,
        )


if __name__ == "__main__":
    unittest.main()
