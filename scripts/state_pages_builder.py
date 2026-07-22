#!/usr/bin/env python3
"""
Generates one static SEO listicle page per state from data/county_prices.json
("most expensive / most affordable counties in <State>"), plus a states.html
hub page linking to all of them, and rewrites sitemap.xml to include every
county page (recomputed the same way seo_pages_builder.py builds them) plus
every state page and static page.

Runs as part of the daily GitHub Actions workflow, right after
seo_pages_builder.py, so it always reflects the latest committed data with
zero manual steps. It intentionally re-derives county page URLs itself
(rather than importing seo_pages_builder) so it stays a simple, independent
script -- the slugify convention is duplicated by design, not by accident.

Output:
    states/<slug>.html   one listicle page per state
    states.html           hub page linking to every state
    sitemap.xml            rewritten to include static + county + state URLs

Usage:
    python scripts/state_pages_builder.py
"""
import json
import re
import statistics
import sys
import unicodedata
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA_PATH = ROOT / "data" / "county_prices.json"
CRIME_PATH = ROOT / "data" / "crime_data_county.json"
INCOME_PATH = ROOT / "data" / "income_data_county.json"
OUT_DIR = ROOT / "states"
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
    '<script async src="https://pagead2.googlesyndication.com/pagead/js/adsbygoogle.js?client=ca-pub-4948007323848015" crossorigin="anonymous"></script>',
])

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


def fmt_rate(v):
    if v is None:
        return "n/a"
    return format(round(v), ",")


def county_url(name, state):
    return SITE_URL + "/counties/" + state.lower() + "-" + slugify(name) + ".html"


def county_href_relative(name, state, from_states_dir=True):
    prefix = "../counties/" if from_states_dir else "counties/"
    return prefix + state.lower() + "-" + slugify(name) + ".html"


ROW_TEMPLATE = (
    '<div style="display:flex;justify-content:space-between;padding:8px 0;'
    'border-bottom:1px solid var(--border);font-size:14px;">'
    '<span>{rank}. <a href="{href}">{name}</a></span>'
    '<b style="color:var(--accent-2);">{value}</b></div>'
)

CRIME_ROW_TEMPLATE = (
    '<div style="display:flex;justify-content:space-between;padding:8px 0;'
    'border-bottom:1px solid var(--border);font-size:14px;">'
    '<span>{rank}. <a href="{href}">{name}</a></span>'
    '<b style="color:{color};">{value} /100k</b></div>'
)

STATE_PAGE_TEMPLATE = """<!DOCTYPE html>
<html lang="en">
<head>
{ga}
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>{title}</title>
<meta name="description" content="{description}">
<link rel="canonical" href="{canonical}">
<link rel="icon" href="/favicon.ico" sizes="32x32">
<link rel="icon" type="image/png" href="/assets/icon-512.png" sizes="512x512">
<link rel="apple-touch-icon" href="/assets/apple-touch-icon.png">
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
    {{"@type": "ListItem", "position": 2, "name": "States", "item": "{site_url}/states.html"}},
    {{"@type": "ListItem", "position": 3, "name": "{state_name}", "item": "{canonical}"}}
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
  <p style="font-size:13px;color:var(--text-dim);"><a href="../index.html">Home</a> &rsaquo; <a href="../states.html">States</a> &rsaquo; {state_name}</p>
  <h1 style="font-size:30px;">Home Prices by County in {state_name}</h1>
  <p>{intro}</p>
</div>

{lists_section}

{affordability_section}

{crime_section}

{faq_section}

<div class="hero" style="text-align:left;max-width:760px;">
  <p><a href="../counties.html">View all of {state_name} on the interactive county map &rarr;</a></p>
</div>

<footer class="site-footer">
  Data source: <a href="https://www.zillow.com/research/data/" target="_blank" rel="noopener">Zillow Research (ZHVI)</a>,
  refreshed daily via automated job. Not affiliated with or endorsed by Zillow.
  &middot; <a href="../about.html">About</a>
  &middot; <a href="../methodology.html">Data &amp; Methodology</a>
  &middot; <a href="../contact.html">Contact</a>
  &middot; <a href="../privacy-policy.html">Privacy Policy</a>
</footer>

</body>
</html>
"""

LIST_BLOCK = """<div class="content-section" style="padding-top:0;">
  <h2>{heading}</h2>
  {rows}
</div>
"""


def build_state_list_block(heading, counties, state):
    rows = "\n".join(
        ROW_TEMPLATE.format(
            rank=i + 1,
            href=county_href_relative(c["name"], state),
            name=c["name"],
            value=fmt_money(c["value"]),
        )
        for i, c in enumerate(counties)
    )
    return LIST_BLOCK.format(heading=heading, rows=rows)


def build_crime_list_block(heading, counties, state, color):
    rows = "\n".join(
        CRIME_ROW_TEMPLATE.format(
            rank=i + 1,
            href=county_href_relative(c["name"], state),
            name=c["name"],
            value=fmt_rate(c["violent_crime_rate"]),
            color=color,
        )
        for i, c in enumerate(counties)
    )
    return LIST_BLOCK.format(heading=heading, rows=rows)


RATIO_ROW_TEMPLATE = (
    '<div style="display:flex;justify-content:space-between;padding:8px 0;'
    'border-bottom:1px solid var(--border);font-size:14px;">'
    '<span>{rank}. <a href="{href}">{name}</a></span>'
    '<b style="color:{color};">{value}&times; income</b></div>'
)


def build_ratio_list_block(heading, counties, state, color):
    rows = "\n".join(
        RATIO_ROW_TEMPLATE.format(
            rank=i + 1,
            href=county_href_relative(c["name"], state),
            name=c["name"],
            # Top-coded income means the true ratio can only be lower than this.
            value=("&le;" if c["top_coded"] else "") + "{:.1f}".format(c["ratio"]),
            color=color,
        )
        for i, c in enumerate(counties)
    )
    return LIST_BLOCK.format(heading=heading, rows=rows)


def build_affordability_section(group, state_name, abbr, income_by_fips, n_total):
    """Ranks counties by home price divided by median household income -- a
    standard housing affordability measure, and a more useful signal than
    price alone (a cheap county where nobody earns much can be harder to buy
    into than an expensive one with high wages)."""
    rows = []
    for c in group:
        rec = income_by_fips.get(c["fips"])
        if not rec:
            continue
        income = rec.get("median_household_income")
        if not income:
            continue
        rows.append({
            **c,
            "income": income,
            "top_coded": bool(rec.get("top_coded")),
            "ratio": c["value"] / income,
        })

    if not rows:
        return ""

    rows.sort(key=lambda r: r["ratio"])
    n_cov = len(rows)

    intro = (
        "This ranks each county by its median home value divided by its median household "
        "income &mdash; how many years of a typical local income it would take to buy a "
        "typical local home. Housing researchers generally treat about 3&times; income as "
        "manageable and 5&times; or more as severely stretched. Coverage is {n_cov} of {n_total} "
        "tracked {counties_word} in {state_name}; income figures come from the Census Bureau's "
        "American Community Survey and home values from Zillow."
    ).format(
        n_cov=n_cov, n_total=n_total, state_name=state_name,
        counties_word="county" if n_total == 1 else "counties",
    )

    intro_block = (
        '<div class="content-section" style="padding-top:0;">'
        "<h2>Housing Affordability by County in {state_name}</h2>"
        '<p style="color:var(--text-dim);font-size:13px;line-height:1.6;margin:0;">{intro}</p>'
        "</div>"
    ).format(state_name=state_name, intro=intro)

    if n_cov <= 12:
        lists = build_ratio_list_block(
            "{} Counties Ranked by Housing Affordability".format(state_name),
            rows, abbr, "var(--accent-2)",
        )
    else:
        lists = (
            build_ratio_list_block(
                "Most Affordable Counties in {} Relative to Local Income".format(state_name),
                rows[:10], abbr, "var(--accent-2)",
            )
            + build_ratio_list_block(
                "Least Affordable Counties in {} Relative to Local Income".format(state_name),
                list(reversed(rows[-10:])), abbr, "var(--warn)",
            )
        )

    return intro_block + lists


FAQ_BLOCK = """<div class="content-section" style="padding-top:0;">
  <h2>Frequently asked questions about {state_name} home prices</h2>
  <div class="faq-item">
    <h4>Which county in {state_name} has the most expensive homes?</h4>
    <p>{top_name} has the highest median home value in {state_name} at {top_value}. This is often searched as the "richest" or "wealthiest" county in {state_name} &mdash; though it's worth being precise about what's being measured here: median home value reflects property prices, not household income or net worth. The two usually correlate, but a county can have expensive homes without having the highest-earning residents, particularly in areas with a lot of vacation or second homes.</p>
  </div>
{income_faq}
  <div class="faq-item">
    <h4>What is the cheapest county in {state_name}?</h4>
    <p>{bottom_name} has the lowest median home value of the {n} {state_name} {counties_word} tracked here, at {bottom_value}. Keep in mind that low home prices often reflect limited local job markets, distance from major metro areas, or shrinking population &mdash; affordability alone doesn't tell you whether somewhere is a good fit.</p>
  </div>
  <div class="faq-item">
    <h4>How do {state_name} home prices compare to the rest of the country?</h4>
    <p>The typical (median) county in {state_name} has a home value of {state_median}, against {national_median} for the median U.S. county &mdash; {compare_phrase}. Figures come from Zillow's Home Value Index and are refreshed daily on this site.</p>
  </div>
</div>
"""


INCOME_FAQ_ITEM = """  <div class="faq-item">
    <h4>Which county in {state_name} has the highest household income?</h4>
    <p>{name} has the highest median household income in {state_name} at {income}{plus}. If what you're really after is the "richest" or "wealthiest" county in {state_name}, this is the closer answer &mdash; income measures what households actually earn each year, while home values measure what property costs. Neither is quite the same as wealth, which would also account for savings, investments and property people already own outright.</p>
  </div>
"""


def build_faq_section(ranked, state_name, n, state_median, national_median, income_by_fips=None):
    top = ranked[0]
    bottom = ranked[-1]

    income_faq = ""
    if income_by_fips:
        with_income = [
            (income_by_fips[c["fips"]], c)
            for c in ranked
            if c["fips"] in income_by_fips
            and income_by_fips[c["fips"]].get("median_household_income")
        ]
        if with_income:
            rec, _ = max(with_income, key=lambda p: p[0]["median_household_income"])
            income_faq = INCOME_FAQ_ITEM.format(
                state_name=state_name,
                name=rec["name"],
                income=fmt_money(rec["median_household_income"]),
                plus="+" if rec.get("top_coded") else "",
            )

    pct = round((state_median / national_median - 1) * 100, 1)
    if pct > 0:
        compare_phrase = "roughly {}% higher".format(abs(pct))
    elif pct < 0:
        compare_phrase = "roughly {}% lower".format(abs(pct))
    else:
        compare_phrase = "almost exactly in line with the national figure"

    return FAQ_BLOCK.format(
        state_name=state_name,
        income_faq=income_faq,
        top_name=top["name"],
        top_value=fmt_money(top["value"]),
        bottom_name=bottom["name"],
        bottom_value=fmt_money(bottom["value"]),
        n=n,
        counties_word="county" if n == 1 else "counties",
        state_median=fmt_money(state_median),
        national_median=fmt_money(national_median),
        compare_phrase=compare_phrase,
    )


def build_crime_section(group, state_name, abbr, crime_by_fips, n_total):
    crime_ranked = []
    for c in group:
        rec = crime_by_fips.get(c["fips"])
        if not rec or rec.get("violent_crime_rate") is None:
            continue
        crime_ranked.append({**c, "violent_crime_rate": rec["violent_crime_rate"]})

    if not crime_ranked:
        return ""

    crime_ranked.sort(key=lambda c: c["violent_crime_rate"])
    n_crime = len(crime_ranked)

    crime_intro = (
        "Violent crime rates below are a population-weighted average of each county's reporting "
        "cities from the FBI's Uniform Crime Reporting Program, covering {n_crime} of {n_total} "
        "tracked counties in {state_name}. Counties with no FBI-reporting city aren't shown."
    ).format(n_crime=n_crime, n_total=n_total, state_name=state_name)

    intro_block = (
        '<div class="content-section" style="padding-top:0;">'
        "<h2>Crime Rates by County in {state_name}</h2>"
        '<p style="color:var(--text-dim);font-size:13px;line-height:1.6;margin:0;">{crime_intro}</p>'
        "</div>"
    ).format(state_name=state_name, crime_intro=crime_intro)

    if n_crime <= 12:
        crime_lists = build_crime_list_block(
            "Counties in {} Ranked by Violent Crime Rate (Safest First)".format(state_name),
            crime_ranked, abbr, "var(--accent-2)",
        )
    else:
        safest = crime_ranked[:10]
        most_dangerous = list(reversed(crime_ranked[-10:]))
        crime_lists = (
            build_crime_list_block(
                "Safest Counties in {} (Lowest Violent Crime Rate)".format(state_name),
                safest, abbr, "var(--accent-2)",
            )
            + build_crime_list_block(
                "Most Dangerous Counties in {} (Highest Violent Crime Rate)".format(state_name),
                most_dangerous, abbr, "var(--warn)",
            )
        )

    return intro_block + crime_lists


def build_state_pages(county_data, crime_data, income_data=None):
    counties = county_data["counties"]
    items = [
        {"fips": fips, **rec}
        for fips, rec in counties.items()
        if rec.get("value") is not None and rec.get("name") and rec.get("state")
    ]

    crime_by_fips = crime_data["counties"] if crime_data else {}
    income_by_fips = income_data["counties"] if income_data else {}

    all_values = [c["value"] for c in items]
    national_median = statistics.median(all_values)

    by_state = {}
    for c in items:
        by_state.setdefault(c["state"], []).append(c)

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    urls = []
    hub_rows = []

    for abbr in sorted(by_state.keys(), key=lambda a: ABBR_TO_NAME.get(a, a)):
        group = by_state[abbr]
        state_name = ABBR_TO_NAME.get(abbr, abbr)
        ranked = sorted(group, key=lambda c: c["value"], reverse=True)
        state_median = statistics.median(c["value"] for c in group)
        n = len(ranked)

        pct_vs_national = round((state_median / national_median - 1) * 100, 1)
        if pct_vs_national > 0:
            compare = fmt_pct(pct_vs_national) + " above"
        elif pct_vs_national < 0:
            compare = fmt_pct(pct_vs_national) + " below"
        else:
            compare = "in line with"

        intro = (
            "HomePriceMap tracks {n} {counties_word} in {state_name}. The typical (median) county "
            "in the state has a home value of {state_median}, which is {compare} the U.S. national "
            "county median of {national_median}. Below are the most expensive and most affordable "
            "counties in {state_name} by current median home value."
        ).format(
            n=n,
            counties_word="county" if n == 1 else "counties",
            state_name=state_name,
            state_median=fmt_money(state_median),
            compare=compare,
            national_median=fmt_money(national_median),
        )

        if n <= 12:
            intro = (
                "HomePriceMap tracks {n} {counties_word} in {state_name}. The typical (median) county "
                "in the state has a home value of {state_median}, which is {compare} the U.S. national "
                "county median of {national_median}. Below are all tracked counties in {state_name}, "
                "ranked by current median home value."
            ).format(
                n=n,
                counties_word="county" if n == 1 else "counties",
                state_name=state_name,
                state_median=fmt_money(state_median),
                compare=compare,
                national_median=fmt_money(national_median),
            )
            lists_section = build_state_list_block(
                "All Counties in {} by Home Price".format(state_name), ranked, abbr
            )
        else:
            top10 = ranked[:10]
            bottom10 = list(reversed(ranked[-10:]))
            lists_section = (
                build_state_list_block(
                    "Most Expensive Counties in {}".format(state_name), top10, abbr
                )
                + build_state_list_block(
                    "Cheapest & Most Affordable Counties in {}".format(state_name), bottom10, abbr
                )
            )

        affordability_section = build_affordability_section(group, state_name, abbr, income_by_fips, n)
        crime_section = build_crime_section(group, state_name, abbr, crime_by_fips, n)
        faq_section = build_faq_section(
            ranked, state_name, n, state_median, national_median, income_by_fips
        )

        slug = slugify(state_name)
        filename = slug + ".html"
        canonical = SITE_URL + "/states/" + filename

        html = STATE_PAGE_TEMPLATE.format(
            ga=GA_SNIPPET,
            title="Most Expensive & Cheapest Counties in {} ({}) | Home Price Map".format(
                state_name, group[0].get("as_of", "")[:4]
            ),
            description="Ranked list of the most expensive and most affordable counties in {} by median home price, updated daily from Zillow Research data.".format(
                state_name
            ),
            canonical=canonical,
            site_url=SITE_URL,
            state_name=state_name,
            intro=intro,
            lists_section=lists_section,
            affordability_section=affordability_section,
            crime_section=crime_section,
            faq_section=faq_section,
        )

        (OUT_DIR / filename).write_text(html, encoding="utf-8")
        urls.append(canonical)
        hub_rows.append((state_name, "states/" + filename, n))

    build_hub_page(hub_rows)
    return urls


HUB_TEMPLATE = """<!DOCTYPE html>
<html lang="en">
<head>
{ga}
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Home Prices by State | Home Price Map</title>
<meta name="description" content="Browse the most expensive and most affordable counties in every U.S. state, ranked by median home price.">
<link rel="canonical" href="{site_url}/states.html">
<link rel="icon" href="/favicon.ico" sizes="32x32">
<link rel="icon" type="image/png" href="/assets/icon-512.png" sizes="512x512">
<link rel="apple-touch-icon" href="/assets/apple-touch-icon.png">
<meta property="og:type" content="website">
<meta property="og:url" content="{site_url}/states.html">
<meta property="og:title" content="Home Prices by State | Home Price Map">
<meta property="og:description" content="Browse the most expensive and most affordable counties in every U.S. state, ranked by median home price.">
<meta property="og:image" content="{site_url}/assets/og-image.jpg">
<meta name="twitter:card" content="summary_large_image">
<meta name="twitter:title" content="Home Prices by State | Home Price Map">
<meta name="twitter:description" content="Browse the most expensive and most affordable counties in every U.S. state, ranked by median home price.">
<meta name="twitter:image" content="{site_url}/assets/og-image.jpg">
<link rel="stylesheet" href="css/style.css">
</head>
<body>

<header class="topbar">
  <div class="brand">Home<span>Price</span>Map</div>
  <nav>
    <a href="index.html">Home</a>
    <a href="counties.html">Counties</a>
    <a href="cities.html">Cities</a>
    <a href="states.html" class="active">States</a>
  </nav>
</header>

<div class="hero" style="text-align:left;max-width:760px;">
  <h1 style="font-size:30px;">Home Prices by State</h1>
  <p>Pick a state to see its most expensive and most affordable counties, ranked by current median home value.</p>
</div>

<div class="content-section" style="padding-top:0;">
  <div style="display:grid;grid-template-columns:repeat(auto-fill,minmax(170px,1fr));gap:10px;">
{links}
  </div>
</div>

<footer class="site-footer">
  Data source: <a href="https://www.zillow.com/research/data/" target="_blank" rel="noopener">Zillow Research (ZHVI)</a>,
  refreshed daily via automated job. Not affiliated with or endorsed by Zillow.
  &middot; <a href="about.html">About</a>
  &middot; <a href="methodology.html">Data &amp; Methodology</a>
  &middot; <a href="contact.html">Contact</a>
  &middot; <a href="privacy-policy.html">Privacy Policy</a>
</footer>

</body>
</html>
"""


def build_hub_page(hub_rows):
    links = "\n".join(
        '    <a class="choice-card" style="padding:12px 14px;" href="{href}">{name} <span style="color:var(--text-dim);font-size:12px;">({n})</span></a>'.format(
            href=href, name=name, n=n
        )
        for name, href, n in hub_rows
    )
    html = HUB_TEMPLATE.format(ga=GA_SNIPPET, site_url=SITE_URL, links=links)
    (ROOT / "states.html").write_text(html, encoding="utf-8")


def build_sitemap(state_urls, county_data):
    counties = county_data["counties"]
    county_urls = [
        county_url(rec["name"], rec["state"])
        for rec in counties.values()
        if rec.get("value") is not None and rec.get("name") and rec.get("state")
    ]
    static_urls = [
        SITE_URL + "/",
        SITE_URL + "/counties.html",
        SITE_URL + "/cities.html",
        SITE_URL + "/states.html",
        SITE_URL + "/about.html",
        SITE_URL + "/methodology.html",
        SITE_URL + "/contact.html",
        SITE_URL + "/privacy-policy.html",
    ]
    all_urls = static_urls + county_urls + state_urls
    lines = ['<?xml version="1.0" encoding="UTF-8"?>', '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">']
    for u in all_urls:
        lines.append("  <url><loc>" + u + "</loc></url>")
    lines.append("</urlset>")
    (ROOT / "sitemap.xml").write_text("\n".join(lines) + "\n", encoding="utf-8")


def main():
    if not DATA_PATH.exists():
        print("ERROR: " + str(DATA_PATH) + " not found. Run fetch_data.py first.")
        return 1
    county_data = json.loads(DATA_PATH.read_text())
    counties = county_data["counties"]
    if len(counties) < 500:
        print(
            "WARNING: county_prices.json has {} counties -- this looks like "
            "placeholder/sample data, not a real fetch. Skipping state page "
            "generation to avoid publishing garbage pages.".format(len(counties))
        )
        return 1

    crime_data = None
    if CRIME_PATH.exists():
        crime_data = json.loads(CRIME_PATH.read_text())
    else:
        print("NOTE: {} not found -- state pages will skip crime rate lists.".format(CRIME_PATH))

    income_data = None
    if INCOME_PATH.exists():
        income_data = json.loads(INCOME_PATH.read_text())
    else:
        print("NOTE: {} not found -- state pages will skip affordability lists.".format(INCOME_PATH))

    state_urls = build_state_pages(county_data, crime_data, income_data)
    build_sitemap(state_urls, county_data)
    print("Generated {} state pages, states.html hub page, and rewrote sitemap.xml.".format(len(state_urls)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
