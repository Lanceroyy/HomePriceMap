#!/usr/bin/env python3
"""
Generates one static SEO landing page per county from data/county_prices.json,
plus sitemap.xml and robots.txt.

Runs as part of the daily GitHub Actions workflow, right after fetch_data.py,
so the pages always reflect the latest committed data with zero manual steps.

Output:
    counties/<state>-<slug>.html   one page per county
    sitemap.xml
    robots.txt

Usage:
    python scripts/seo_pages_builder.py
"""
import json
import re
import statistics
import sys
import unicodedata
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA_PATH = ROOT / "data" / "county_prices.json"
OUT_DIR = ROOT / "counties"
SITE_URL = "https://homepricemap.us"

GA_SNIPPET = "\n".join([
    '<!-- Google tag (gtag.js) -->',
    '<script async src="https://www.googletagmanager.com/gtag/js?id=G-2K8JWH5ZKY"></script>',
    '<script>',
    '  window.dataLayer = window.dataLayer || [];',
    "  function gtag(){dataLayer.push(arguments);}",
    "  gtag('js', new Date());",
    "  gtag('config', 'G-2K8JWH5ZKY');",
    '</script>',
])


def slugify(name):
    name = unicodedata.normalize("NFKD", name).encode("ascii", "ignore").decode("ascii")
    name = name.strip().lower()
    name = re.sub(r"[^a-z0-9]+", "-", name)
    return name.strip("-")


def fmt_money(v):
    return "$" + format(round(v), ",")


def fmt_pct(v):
    if v is None:
        return "n/a"
    sign = "+" if v > 0 else ""
    return sign + str(v) + "%"


ABBR_TO_NAME = {
    "AL": "Alabama", "AK": "Alaska", "AZ": "Arizona", "AR": "Arkansas",
    "CA": "California", "CO": "Colorado", "CT": "Connecticut", "DE": "Delaware",
    "DC": "District of Columbia", "FL": "Florida", "GA": "Georgia", "HI": "Hawaii",
    "ID": "Idaho", "IL": "Illinois", "IN": "Indiana", "IA": "Iowa",
    "KS": "Kansas", "KY": "Kentucky", "LA": "Louisiana", "ME": "Maine",
    "MD": "Maryland", "MA": "Massachusetts", "MI": "Michigan", "MN": "Minnesota",
    "MS": "Mississippi", "MO": "Missouri", "MT": "Montana", "NE": "Nebraska",
    "NV": "Nevada", "NH": "New Hampshire", "NJ": "New Jersey", "NM": "New Mexico",
    "NY": "New York", "NC": "North Carolina", "ND": "North Dakota", "OH": "Ohio",
    "OK": "Oklahoma", "OR": "Oregon", "PA": "Pennsylvania", "RI": "Rhode Island",
    "SC": "South Carolina", "SD": "South Dakota", "TN": "Tennessee", "TX": "Texas",
    "UT": "Utah", "VT": "Vermont", "VA": "Virginia", "WA": "Washington",
    "WV": "West Virginia", "WI": "Wisconsin", "WY": "Wyoming", "PR": "Puerto Rico",
}


def ordinal(n):
    if 10 <= n % 100 <= 20:
        suffix = "th"
    else:
        suffix = {1: "st", 2: "nd", 3: "rd"}.get(n % 10, "th")
    return str(n) + suffix


PAGE_TEMPLATE = """<!DOCTYPE html>
<html lang="en">
<head>
{ga}
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>{title}</title>
<meta name="description" content="{description}">
<link rel="canonical" href="{canonical}">
<meta property="og:type" content="website">
<meta property="og:url" content="{canonical}">
<meta property="og:title" content="{title}">
<meta property="og:description" content="{description}">
<meta property="og:image" content="{site_url}/assets/og-image.jpg">
<meta name="twitter:card" content="summary_large_image">
<meta name="twitter:title" content="{title}">
<meta name="twitter:description" content="{description}">
<meta name="twitter:image" content="{site_url}/assets/og-image.jpg">
<link rel="stylesheet" href="../css/style.css">
<script type="application/ld+json">
{{
  "@context": "https://schema.org",
  "@type": "BreadcrumbList",
  "itemListElement": [
    {{"@type": "ListItem", "position": 1, "name": "Home", "item": "{site_url}/"}},
    {{"@type": "ListItem", "position": 2, "name": "Counties", "item": "{site_url}/counties.html"}},
    {{"@type": "ListItem", "position": 3, "name": "{county_name}, {state}", "item": "{canonical}"}}
  ]
}}
</script>
</head>
<body>

<header class="topbar">
  <div class="brand">Home<span>Price</span>Map</div>
  <nav>
    <a href="../index.html">Home</a>
    <a href="../counties.html">Counties</a>
    <a href="../cities.html">Cities</a>
    <a href="../states.html">States</a>
  </nav>
</header>

<div class="hero" style="text-align:left;max-width:760px;">
  <p style="font-size:13px;color:var(--text-dim);"><a href="../index.html">Home</a> &rsaquo; <a href="../counties.html">Counties</a> &rsaquo; {county_name}, {state}</p>
  <h1 style="font-size:30px;">Median Home Price in {county_name}, {state}</h1>
  <p>The median home value in <b>{county_name}, {state}</b> is <b>{value_fmt}</b> as of {as_of}, {yoy_sentence}</p>
</div>

<div class="choice-grid" style="grid-template-columns:repeat(3,1fr);max-width:760px;">
  <div class="choice-card" style="text-align:center;">
    <p style="color:var(--text-dim);font-size:13px;margin:0 0 6px;">Median Home Value</p>
    <p style="font-size:22px;font-weight:700;color:var(--accent-2);margin:0;">{value_fmt}</p>
  </div>
  <div class="choice-card" style="text-align:center;">
    <p style="color:var(--text-dim);font-size:13px;margin:0 0 6px;">Year-over-Year</p>
    <p style="font-size:22px;font-weight:700;margin:0;">{yoy_fmt}</p>
  </div>
  <div class="choice-card" style="text-align:center;">
    <p style="color:var(--text-dim);font-size:13px;margin:0 0 6px;">National Rank</p>
    <p style="font-size:22px;font-weight:700;margin:0;">#{national_rank} of {national_total}</p>
  </div>
</div>

<div class="hero" style="text-align:left;max-width:760px;">
  <p>{county_name} ranks {state_rank_ord} out of {state_total} counties in {state} by median home price, and is {national_compare_sentence} the U.S. national median of {national_median_fmt}. Within {state}, the typical county has a median home value of {state_median_fmt}, making {county_name} {state_compare_sentence} the {state} state median.</p>
  <p><a href="../counties.html?fips={fips}">View {county_name} on the interactive county map &rarr;</a></p>
</div>

{nearby_section}

<footer class="site-footer">
  Data source: <a href="https://www.zillow.com/research/data/" target="_blank" rel="noopener">Zillow Research (ZHVI)</a>,
  refreshed daily via automated job. Not affiliated with or endorsed by Zillow.
  &middot; <a href="../privacy-policy.html">Privacy Policy</a>
</footer>

</body>
</html>
"""

NEARBY_TEMPLATE = """<div class="hero" style="text-align:left;max-width:760px;">
  <h2 style="font-size:16px;color:var(--text-dim);text-transform:uppercase;letter-spacing:.04em;">Other Counties in {state}</h2>
  <p>{links}</p>
  <p style="margin-top:10px;"><a href="../states/{state_slug}.html">See the full ranked list of {state_name} counties &rarr;</a></p>
</div>
"""


def build_pages(county_data):
    counties = county_data["counties"]
    items = [
        {"fips": fips, **rec}
        for fips, rec in counties.items()
        if rec.get("value") is not None and rec.get("name") and rec.get("state")
    ]

    all_values = [c["value"] for c in items]
    national_median = statistics.median(all_values)
    national_total = len(items)

    by_value_desc = sorted(items, key=lambda c: c["value"], reverse=True)
    national_rank = {c["fips"]: i + 1 for i, c in enumerate(by_value_desc)}

    by_state = {}
    for c in items:
        by_state.setdefault(c["state"], []).append(c)

    state_median = {st: statistics.median([c["value"] for c in group]) for st, group in by_state.items()}
    state_rank = {}
    for st, group in by_state.items():
        ranked = sorted(group, key=lambda c: c["value"], reverse=True)
        for i, c in enumerate(ranked):
            state_rank[c["fips"]] = i + 1

    slug_by_fips = {}
    for c in items:
        slug = c["state"].lower() + "-" + slugify(c["name"])
        slug_by_fips[c["fips"]] = slug

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    urls = []

    for c in items:
        fips = c["fips"]
        name = c["name"]
        state = c["state"]
        value = c["value"]
        yoy = c.get("yoy_pct")
        as_of = c.get("as_of", "")
        slug = slug_by_fips[fips]
        filename = slug + ".html"
        canonical = SITE_URL + "/counties/" + filename

        if yoy is None:
            yoy_sentence = "with no year-over-year comparison currently available."
        elif yoy > 0:
            yoy_sentence = "up " + fmt_pct(yoy) + " from a year earlier."
        elif yoy < 0:
            yoy_sentence = "down " + fmt_pct(abs(yoy)) + " from a year earlier."
        else:
            yoy_sentence = "unchanged from a year earlier."

        n_rank = national_rank[fips]
        s_rank = state_rank[fips]
        s_total = len(by_state[state])

        pct_vs_national = round((value / national_median - 1) * 100, 1)
        if pct_vs_national > 0:
            national_compare_sentence = fmt_pct(pct_vs_national) + " above"
        elif pct_vs_national < 0:
            national_compare_sentence = fmt_pct(pct_vs_national) + " below"
        else:
            national_compare_sentence = "in line with"

        s_med = state_median[state]
        pct_vs_state = round((value / s_med - 1) * 100, 1)
        if pct_vs_state > 0:
            state_compare_sentence = fmt_pct(pct_vs_state) + " above"
        elif pct_vs_state < 0:
            state_compare_sentence = fmt_pct(pct_vs_state) + " below"
        else:
            state_compare_sentence = "in line with"

        state_name = ABBR_TO_NAME.get(state, state)
        state_slug = slugify(state_name)

        nearby = sorted(by_state[state], key=lambda c2: c2["value"], reverse=True)
        nearby = [c2 for c2 in nearby if c2["fips"] != fips][:8]
        if nearby:
            links = " &middot; ".join(
                '<a href="{}.html">{}</a>'.format(slug_by_fips[c2["fips"]], c2["name"])
                for c2 in nearby
            )
        else:
            links = "This is the only tracked county in " + state_name + "."
        nearby_section = NEARBY_TEMPLATE.format(
            state=state, state_name=state_name, state_slug=state_slug, links=links
        )

        html = PAGE_TEMPLATE.format(
            ga=GA_SNIPPET,
            title="Median Home Price in " + name + ", " + state + " (" + as_of[:4] + ") | Home Price Map",
            description="The median home value in " + name + ", " + state + " is " + fmt_money(value) +
                         ", " + yoy_sentence + " Compare to state and national median home prices.",
            canonical=canonical,
            site_url=SITE_URL,
            county_name=name,
            state=state,
            value_fmt=fmt_money(value),
            yoy_fmt=fmt_pct(yoy),
            as_of=as_of,
            yoy_sentence=yoy_sentence,
            national_rank=n_rank,
            national_total=national_total,
            state_rank_ord=ordinal(s_rank),
            state_total=s_total,
            national_compare_sentence=national_compare_sentence,
            national_median_fmt=fmt_money(national_median),
            state_median_fmt=fmt_money(s_med),
            state_compare_sentence=state_compare_sentence,
            fips=fips,
            nearby_section=nearby_section,
        )

        (OUT_DIR / filename).write_text(html, encoding="utf-8")
        urls.append(canonical)

    return urls


def build_sitemap(urls):
    static_urls = [
        SITE_URL + "/",
        SITE_URL + "/counties.html",
        SITE_URL + "/cities.html",
        SITE_URL + "/privacy-policy.html",
    ]
    all_urls = static_urls + urls
    lines = ['<?xml version="1.0" encoding="UTF-8"?>', '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">']
    for u in all_urls:
        lines.append("  <url><loc>" + u + "</loc></url>")
    lines.append("</urlset>")
    (ROOT / "sitemap.xml").write_text("\n".join(lines) + "\n", encoding="utf-8")


def build_robots():
    content = "User-agent: *\nAllow: /\nSitemap: " + SITE_URL + "/sitemap.xml\n"
    (ROOT / "robots.txt").write_text(content, encoding="utf-8")


def main():
    if not DATA_PATH.exists():
        print("ERROR: " + str(DATA_PATH) + " not found. Run fetch_data.py first.")
        return 1
    county_data = json.loads(DATA_PATH.read_text())
    urls = build_pages(county_data)
    build_sitemap(urls)
    build_robots()
    print("Generated " + str(len(urls)) + " county pages, sitemap.xml, robots.txt.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
