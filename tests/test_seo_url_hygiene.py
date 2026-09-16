import re
import unittest
from pathlib import Path
from urllib.parse import urlparse


ROOT = Path(__file__).resolve().parents[1]
GENERATED_ROOT_HTML = {"states.html"}
SOURCE_FILES = [
    path for path in sorted(ROOT.glob("*.html"))
    if path.name not in GENERATED_ROOT_HTML
] + [
    ROOT / "scripts" / "city_pages_builder.py",
    ROOT / "scripts" / "seo_pages_builder.py",
    ROOT / "scripts" / "state_pages_builder.py",
]

HREF_PATTERN = re.compile(r'href=["\']([^"\']+)["\']')
QUERY_STATE_PATTERNS = {
    "county query state": re.compile(r'counties\.html\?fips='),
    "city query state": re.compile(r'cities\.html\?city='),
}


def is_same_origin_index_url(href):
    parsed = urlparse(href)
    if parsed.netloc and parsed.netloc.lower() != "homepricemap.us":
        return False
    return parsed.path.replace("\\", "/").rstrip("/").endswith("index.html")


class SeoUrlHygieneTests(unittest.TestCase):
    def test_index_url_detection_covers_common_variants(self):
        for href in (
            "index.html",
            "./index.html",
            "../index.html",
            "/index.html",
            "https://homepricemap.us/index.html",
        ):
            with self.subTest(href=href):
                self.assertTrue(is_same_origin_index_url(href))

        for href in ("/", "counties.html", "https://example.com/index.html"):
            with self.subTest(href=href):
                self.assertFalse(is_same_origin_index_url(href))

    def test_sources_do_not_link_to_noncanonical_internal_urls(self):
        offenders = []
        for path in SOURCE_FILES:
            text = path.read_text(encoding="utf-8")
            for match in HREF_PATTERN.finditer(text):
                if not is_same_origin_index_url(match.group(1)):
                    continue
                line = text.count("\n", 0, match.start()) + 1
                offenders.append(f"{path.relative_to(ROOT)}:{line}: index.html")

            for label, pattern in QUERY_STATE_PATTERNS.items():
                for match in pattern.finditer(text):
                    line = text.count("\n", 0, match.start()) + 1
                    offenders.append(f"{path.relative_to(ROOT)}:{line}: {label}")

        self.assertEqual([], offenders, "\n" + "\n".join(offenders))

    def test_sitemap_contains_only_canonical_urls(self):
        sitemap = (ROOT / "sitemap.xml").read_text(encoding="utf-8")
        urls = re.findall(r"<loc>([^<]+)</loc>", sitemap)
        self.assertTrue(urls)
        self.assertEqual([], [url for url in urls if "?" in url])
        self.assertEqual([], [url for url in urls if "/index.html" in url])

    def test_county_map_keeps_legacy_query_links_compatible(self):
        script = (ROOT / "js" / "counties.js").read_text(encoding="utf-8")
        self.assertIn(
            'const legacyParams = new URLSearchParams(window.location.search);',
            script,
        )
        self.assertIn(
            'const params = fragmentParams.has("fips") ? fragmentParams : legacyParams;',
            script,
        )
        self.assertIn('url.search = "";', script)
        self.assertIn('url.hash = params.toString();', script)


if __name__ == "__main__":
    unittest.main()
