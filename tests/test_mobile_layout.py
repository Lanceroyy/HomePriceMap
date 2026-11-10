import re
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PROFILE_BUILDERS = (
    ROOT / "scripts" / "city_pages_builder.py",
    ROOT / "scripts" / "seo_pages_builder.py",
)
DIV_TAG = re.compile(r"<div\b[^>]*>", re.IGNORECASE)
CLASS_ATTRIBUTE = re.compile(r'class=["\']([^"\']*)["\']', re.IGNORECASE)
STYLE_ATTRIBUTE = re.compile(r'style=["\']([^"\']*)["\']', re.IGNORECASE)


def has_inline_choice_grid_columns(text):
    for match in DIV_TAG.finditer(text):
        tag = match.group(0)
        class_match = CLASS_ATTRIBUTE.search(tag)
        style_match = STYLE_ATTRIBUTE.search(tag)
        if not class_match or not style_match:
            continue
        if (
            "choice-grid" in class_match.group(1).split()
            and "grid-template-columns" in style_match.group(1).lower()
        ):
            return True
    return False


def css_block(text, selector):
    start = text.index(selector)
    opening_brace = text.index("{", start)
    depth = 0
    for index in range(opening_brace, len(text)):
        if text[index] == "{":
            depth += 1
        elif text[index] == "}":
            depth -= 1
            if depth == 0:
                return text[opening_brace + 1:index]
    raise AssertionError(f"Unclosed CSS block: {selector}")


class MobileLayoutTests(unittest.TestCase):
    def test_map_pages_do_not_expose_the_developer_monetization_note(self):
        for name in ("counties.html", "cities.html"):
            with self.subTest(page=name):
                markup = (ROOT / name).read_text(encoding="utf-8")
                self.assertFalse(
                    "monetization.md" in markup.casefold(),
                    "Map visitors should not see references to the private development note.",
                )

    def test_inline_grid_detector_covers_class_and_attribute_variants(self):
        offenders = (
            '<div class="choice-grid" style="grid-template-columns:repeat(3,1fr)">',
            '<div class="choice-grid profile-stats" style="grid-template-columns:repeat(3,1fr)">',
            '<div style="grid-template-columns:repeat(3,1fr)" class="profile-stats choice-grid">',
        )
        for markup in offenders:
            with self.subTest(markup=markup):
                self.assertTrue(has_inline_choice_grid_columns(markup))

        self.assertFalse(
            has_inline_choice_grid_columns(
                '<div class="choice-grid profile-stats" style="text-align:center">'
            )
        )

    def test_profile_builders_do_not_override_responsive_choice_grid_columns(self):
        offenders = []
        for path in PROFILE_BUILDERS:
            text = path.read_text(encoding="utf-8")
            if has_inline_choice_grid_columns(text):
                offenders.append(path.relative_to(ROOT).as_posix())

            self.assertIn(
                '<div class="choice-grid profile-stats">',
                text,
                f"{path.relative_to(ROOT).as_posix()} must use the profile grid class",
            )

        self.assertEqual([], offenders)

    def test_profile_grid_keeps_three_desktop_columns_and_stacks_on_mobile(self):
        stylesheet = (ROOT / "css" / "style.css").read_text(encoding="utf-8")
        self.assertIn(
            ".profile-stats {\n"
            "  grid-template-columns: repeat(3, minmax(0, 1fr));\n"
            "  max-width: 760px;\n"
            "}",
            stylesheet,
        )
        mobile_styles = css_block(stylesheet, "@media (max-width: 700px)")
        self.assertIn(
            ".choice-grid.profile-stats { grid-template-columns: 1fr; }",
            mobile_styles,
        )

    def test_narrow_reading_page_navigation_wraps_without_changing_map_headers(self):
        stylesheet = (ROOT / "css" / "style.css").read_text(encoding="utf-8")
        narrow_styles = css_block(stylesheet, "@media (max-width: 440px)")
        self.assertIn("html:not(.map-page) header.topbar { flex-wrap: wrap; gap: 8px; }", narrow_styles)
        self.assertIn("html:not(.map-page) header.topbar nav { width: 100%; justify-content: space-between; }", narrow_styles)
        self.assertIn("margin-left: 0;", narrow_styles)

    def test_both_maps_move_the_existing_zoom_control_away_from_search(self):
        for name in ("counties", "cities"):
            with self.subTest(map=name):
                script = (ROOT / "js" / f"{name}.js").read_text(encoding="utf-8")
                self.assertIsNotNone(
                    re.search(r'(?m)^map\.zoomControl\.setPosition\("topright"\);', script),
                    "The existing zoom control must move to the upper right.",
                )

    def test_mobile_search_panel_leaves_room_for_touch_zoom_controls(self):
        stylesheet = (ROOT / "css" / "style.css").read_text(encoding="utf-8")
        map_styles = stylesheet[stylesheet.index(".map-wrap {"):]
        mobile_panel = css_block(css_block(map_styles, "@media (max-width: 700px)"), ".panel {")
        right = re.search(r"(?m)^\s*right:\s*(\d+)px;", mobile_panel)
        self.assertIsNotNone(right)
        # Leaflet's 30px touch button, two 2px borders and 10px margin, plus 8px gap.
        self.assertGreaterEqual(int(right.group(1)), 30 + 4 + 10 + 8)

    def test_short_map_legend_scrolls_below_zoom_controls(self):
        stylesheet = (ROOT / "css" / "style.css").read_text(encoding="utf-8")
        map_styles = stylesheet[stylesheet.index(".map-wrap {"):]
        legend = css_block(map_styles, "\n.legend {")
        self.assertIn("max-height: calc(100% - 100px);", legend)
        self.assertIn("overflow-y: auto;", legend)
        mobile = css_block(map_styles, "@media (max-width: 700px)")
        self.assertIn(
            "max-height: min(60vh, calc(100% - 100px));",
            css_block(mobile, ".legend {"),
        )

    def test_short_map_details_scroll_below_search(self):
        stylesheet = (ROOT / "css" / "style.css").read_text(encoding="utf-8")
        short_query = "@media (max-height: 400px)"
        self.assertIn(short_query, stylesheet, "Short maps need a separate details height cap.")
        narrow_query = "@media (max-width: 380px)"
        self.assertLess(stylesheet.index(short_query), stylesheet.index(narrow_query))
        details = css_block(css_block(stylesheet, short_query), ".info-box {")
        self.assertIn("max-height: calc(100% - 120px);", details)
        self.assertIn("overflow-y: auto;", details)


if __name__ == "__main__":
    unittest.main()
