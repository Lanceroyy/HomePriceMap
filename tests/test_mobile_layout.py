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


if __name__ == "__main__":
    unittest.main()
