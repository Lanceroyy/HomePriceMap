#!/usr/bin/env python3
"""
Generates one static SEO landing page per city from data/city_prices.json.

Deliberately does NOT generate a page for all ~17,600 cities Zillow prices.
Google already declined to index 181 of the 3,072 county pages as "crawled,
currently not indexed" -- publishing another 17,600 thin pages would make
that worse, not better. Instead a city gets a page only when there is enough
data to say something specific about it:

  * Zillow publishes a home value, AND
  * the FBI publishes crime data for its police department, AND
  * that department covers at least MIN_POPULATION residents

which is about 4,000 cities. The rest remain on the interactive city map,
they just don't get a standalone page competing for the same crawl budget.

Output:
    cities/<state>-<slug>.html

Run after fetch_data.py (and after process_crime_data.py, whenever the annual
FBI file is refreshed). sitemap.xml is written by state_pages_builder.py,
which picks these URLs up via the same threshold logic.

Usage:
    python scripts/city_pages_builder.py
"""
import json
import re
import statistics
import sys
import unicodedata
from datetime import date
from html import escape
from pathlib import Path
from urllib.parse import quote_plus

from city_identity import city_candidates_by_key, match_city_source, safe_city_history
from profile_components import load_history_series, prune_stale_html, render_history_section

ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT / "data"
CITY_PATH = DATA_DIR / "city_prices.json"
COUNTY_PATH = DATA_DIR / "county_prices.json"
CITY_CRIME_PATH = DATA_DIR / "crime_data_city.json"
CITY_INCOME_PATH = DATA_DIR / "income_data_city.json"
CITY_HISTORY_PATH = DATA_DIR / "history" / "city_history.json"
OUT_DIR = ROOT / "cities"
SITE_URL = "https://homepricemap.us"

# A crime rate computed over a few hundred residents swings wildly on a single
# incident. 5,000 is the same floor used for county rollups in
# process_crime_data.py, kept consistent so the two never disagree.
MIN_POPULATION = 5000
MIN_EXPECTED_PROFILES = 3000

# These profiles already have measurable search interest. The named peers
# are a deliberately small local-context pilot, not a template for every city.
PILOT_PEERS = {
    ("CA", "Los Angeles"): ("Long Beach", "Pasadena", "Santa Monica"),
    ("CA", "Beverly Hills"): ("Los Angeles", "Santa Monica", "West Hollywood"),
    ("GA", "Canton"): ("Woodstock", "Holly Springs"),
}

GA_SNIPPET = "\n".join([
    '<script src="/js/analytics-loader.js"></script>',
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

PLACE_SUFFIXES = re.compile(
    r"\s+(city|town|village|township|CDP|borough|municipality)\s*$", re.IGNORECASE
)
COUNTY_SUFFIXES = re.compile(
    r"\s+(county|parish|borough|census area|municipality|municipio|city and borough)\s*$",
    re.IGNORECASE,
)


def slugify(name):
    name = unicodedata.normalize("NFKD", name).encode("ascii", "ignore").decode("ascii")
    return re.sub(r"[^a-z0-9]+", "-", name.strip().lower()).strip("-")


def normalize_place(name):
    return re.sub(r"[^a-z0-9]+", "", PLACE_SUFFIXES.sub("", name or "").strip().lower())


def fmt_money(v):
    return "$" + format(round(v), ",")


def fmt_pct_bare(v):
    return "n/a" if v is None else str(abs(v)) + "%"


def fmt_rate(v):
    return "n/a" if v is None else format(int(round(v)), ",")


PAGE_TEMPLATE = """<!DOCTYPE html>
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
<script>(function(){{var d=document.documentElement;try{{var t=localStorage.getItem("theme");if(t)d.setAttribute("data-theme",t);}}catch(e){{}}function cur(){{return d.getAttribute("data-theme")||(window.matchMedia("(prefers-color-scheme: dark)").matches?"dark":"light");}}function label(){{var b=document.querySelector(".theme-toggle");if(b)b.textContent=cur()==="dark"?"Light":"Dark";}}window.toggleTheme=function(){{var n=cur()==="dark"?"light":"dark";d.setAttribute("data-theme",n);try{{localStorage.setItem("theme",n);}}catch(e){{}}label();}};document.addEventListener("DOMContentLoaded",label);}})();</script>
<link rel="stylesheet" href="../css/style.css">
<script type="application/ld+json">
{{
  "@context": "https://schema.org",
  "@type": "BreadcrumbList",
  "itemListElement": [
    {{"@type": "ListItem", "position": 1, "name": "Home", "item": "{site_url}/"}},
    {{"@type": "ListItem", "position": 2, "name": "States", "item": "{site_url}/states.html"}},
    {{"@type": "ListItem", "position": 3, "name": "{state_name}", "item": "{site_url}/states/{state_slug}.html"}},
    {{"@type": "ListItem", "position": 4, "name": "{city_name}, {state}", "item": "{canonical}"}}
  ]
}}
</script>
</head>
<body>

<header class="topbar">
  <div class="brand">Home<span>Price</span>Map</div>
  <nav>
    <a href="/">Home</a>
    <a href="../counties.html">Counties</a>
    <a href="../cities.html">Cities</a>
    <a href="../states.html">States</a>
    <a href="../compare.html">Compare</a>
    <button class="theme-toggle" type="button" onclick="toggleTheme()" aria-label="Toggle dark mode">Dark</button>
  </nav>
</header>

<div class="hero" style="text-align:left;max-width:760px;">
  <p style="font-size:13px;color:var(--text-dim);"><a href="/">Home</a> &rsaquo; <a href="../states.html">States</a> &rsaquo; <a href="../states/{state_slug}.html">{state_name}</a> &rsaquo; {city_name}</p>
  <h1 style="font-size:30px;">Median Home Price in {city_name}, {state}</h1>
  <p>The median home value in <b>{city_name}, {state}</b> is <b>{value_fmt}</b> as of {as_of}, {yoy_sentence}</p>
  {map_link}
  <p><a class="button-link" href="../compare.html#places={compare_id}">Compare {city_name} with another place</a></p>
</div>

<div class="choice-grid profile-stats">
  <div class="choice-card" style="text-align:center;">
    <p style="color:var(--text-dim);font-size:13px;margin:0 0 6px;">Median Home Value</p>
    <p class="figure" style="font-size:22px;font-weight:700;color:var(--accent-2);margin:0;">{value_fmt}</p>
  </div>
  <div class="choice-card" style="text-align:center;">
    <p style="color:var(--text-dim);font-size:13px;margin:0 0 6px;">Year-over-Year</p>
    <p class="figure" style="font-size:22px;font-weight:700;margin:0;">{yoy_fmt}</p>
  </div>
  <div class="choice-card" style="text-align:center;">
    <p style="color:var(--text-dim);font-size:13px;margin:0 0 6px;">Population</p>
    <p class="figure" style="font-size:22px;font-weight:700;margin:0;">{population_fmt}</p>
  </div>
</div>

{history_section}

<div class="hero" style="text-align:left;max-width:760px;">
  <p>{comparison}</p>
</div>

{local_comparison_section}

{targeted_context_section}

{income_section}

{crime_section}

{faq_section}

{nearby_section}

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


def crime_section(name, crime, national_violent):
    violent = crime.get("violent_crime_rate")
    if violent is None:
        return ""
    prop = crime.get("property_crime_rate")
    below = sum(1 for r in national_violent if r < violent)
    pct = round(100.0 * below / len(national_violent)) if national_violent else 0

    if pct <= 25:
        compare = "lower than most cities that report to the FBI"
    elif pct <= 75:
        compare = "around the middle of the range for reporting cities"
    else:
        compare = "higher than most cities that report to the FBI"

    prop_sentence = (
        " Property crime runs at <b>{}</b> per 100,000.".format(fmt_rate(prop))
        if prop is not None else ""
    )
    return """
<div class="hero" style="text-align:left;max-width:760px;">
  <h2 style="font-size:20px;">Crime in {name}</h2>
  <p>{name} police recorded a violent crime rate of <b>{violent}</b> per 100,000 residents in {year} &mdash; {compare}.{prop_sentence}</p>
  <p style="font-size:13px;color:var(--text-dim);">Reported by the city's own police department to the FBI's Uniform Crime Reporting Program (<a href="../methodology.html">what this covers</a>).</p>
</div>
""".format(name=name, violent=fmt_rate(violent), year=crime.get("year", ""),
           compare=compare, prop_sentence=prop_sentence)


def income_section(name, value, income):
    if not income or not income.get("median_household_income"):
        return ""

    annual_income = income["median_household_income"]
    ratio = value / annual_income
    capped = bool(income.get("top_coded"))
    ratio_phrase = (
        "no more than <b>{:.1f}&times;</b>" if capped else "about <b>{:.1f}&times;</b>"
    ).format(ratio)
    income_fmt = fmt_money(annual_income) + ("+" if capped else "")

    return """
<div class="hero" style="text-align:left;max-width:760px;">
  <h2 style="font-size:20px;">Housing affordability in {name}</h2>
  <p>Median household income in {name} is <b>{income}</b>, so the typical home value is {ratio_phrase} annual household income. This is a simple price-to-income benchmark rather than a monthly payment estimate; it does not account for mortgage rates, down payments, taxes or insurance.</p>
  <p style="font-size:13px;color:var(--text-dim);">Household income comes from the U.S. Census Bureau's ACS 5-Year Estimates, table B19013 (<a href="../methodology.html">how the affordability measure works</a>).</p>
</div>
""".format(name=name, income=income_fmt, ratio_phrase=ratio_phrase)


def faq_section(name, state, value, yoy, income, crime, county_name, county_value, state_median):
    items = []

    if yoy is None:
        trend = "Year-over-year change isn't currently available."
    elif yoy > 0:
        trend = "That's up {} from a year earlier.".format(fmt_pct_bare(yoy))
    elif yoy < 0:
        trend = "That's down {} from a year earlier.".format(fmt_pct_bare(yoy))
    else:
        trend = "That's essentially unchanged from a year earlier."

    # state_median here is the median across TRACKED CITIES in the state, not
    # across its counties -- the wording has to match or the page contradicts
    # the comparison line above it.
    vs_state = round((value / state_median - 1) * 100, 1)
    phrase = ("about {}% above".format(abs(vs_state)) if vs_state > 0
              else "about {}% below".format(abs(vs_state)) if vs_state < 0
              else "in line with")
    items.append((
        "What is the average home price in {}, {}?".format(name, state),
        "People often call this an average home price, but the figure shown here is "
        "Zillow's typical home value (ZHVI), not a simple arithmetic average. In {n}, "
        "that value is <b>{v}</b>. {t} It is {p} the typical {sn} city tracked here."
        .format(n=name, v=fmt_money(value), t=trend, p=phrase,
                sn=ABBR_TO_NAME.get(state, state)),
    ))

    if county_name and county_value:
        diff = round((value / county_value - 1) * 100, 1)
        rel = ("more expensive than" if diff > 0 else "cheaper than" if diff < 0 else "about the same as")
        items.append((
            "Is {} expensive compared to the surrounding area?".format(name),
            "Homes in {n} are {r} {cn} as a whole, where the median is {cv}"
            "{pctpart}.".format(n=name, r=rel, cn=county_name, cv=fmt_money(county_value),
                                pctpart="" if diff == 0 else " &mdash; a difference of about {}%".format(abs(diff))),
        ))

    if income and income.get("median_household_income"):
        annual_income = income["median_household_income"]
        ratio = value / annual_income
        capped = bool(income.get("top_coded"))
        items.append((
            "Is {} affordable?".format(name),
            "Median household income here is <b>{income}</b>, so the typical home value is "
            "{bound}<b>{ratio:.1f}&times;</b> annual household income. This ratio is a broad "
            "comparison measure, not a mortgage-payment estimate.".format(
                income=fmt_money(annual_income) + ("+" if capped else ""),
                bound="no more than " if capped else "about ",
                ratio=ratio,
            ),
        ))

    if crime and crime.get("violent_crime_rate") is not None:
        items.append((
            "Is {} a safe place to live?".format(name),
            "{n} police reported <b>{v}</b> violent crimes per 100,000 residents, covering a "
            "population of about {p}. Crime rates are one input among many &mdash; they vary "
            "block to block within a city, and this figure is a citywide average.".format(
                n=name, v=fmt_rate(crime["violent_crime_rate"]),
                p=format(int(crime.get("population") or 0), ",")),
        ))

    if not items:
        return ""
    blocks = "\n".join(
        '  <div class="faq-item"><h3 style="font-size:15px;margin:0 0 4px;">{q}</h3><p>{a}</p></div>'.format(q=q, a=a)
        for q, a in items
    )
    return ('<div class="content-section" style="padding-top:0;max-width:760px;margin:0 auto;">\n'
            '  <h2 style="font-size:20px;">Common questions about {name}</h2>\n{b}\n</div>\n'
            ).format(name=name, b=blocks)


def meta_description(name, state, value, yoy_sentence, income, comparison_name):
    """Uses city income when available because it is more distinctive than a
    bare price result. Falls back to the existing crime/comparison promise."""
    base = "The median home value in {}, {} is {}, {}".format(
        name, state, fmt_money(value), yoy_sentence
    )
    if income and income.get("median_household_income"):
        ratio = value / income["median_household_income"]
        qualifier = "no more than" if income.get("top_coded") else "about"
        tail = " That's {} {:.1f}x local household income.".format(qualifier, ratio)
    else:
        tail = " See local crime rates and how it compares to {}.".format(comparison_name)

    # Google truncates snippets to the device's available width, not a fixed
    # character count. Keep distinctive context even for longer city names.
    return base + tail


def targeted_context_section(city, income, county_record):
    """Interpret the two high-interest profiles without expanding the peer pilot."""
    key = (city.get("state"), city.get("name"))
    if key not in {("CA", "Beverly Hills"), ("CO", "Aspen")}:
        return ""
    value = city.get("value")
    annual_income = (income or {}).get("median_household_income")
    if not isinstance(value, (int, float)) or value <= 0 or not isinstance(annual_income, (int, float)) or annual_income <= 0:
        return ""
    try:
        month = date.fromisoformat(city.get("as_of", "")).strftime("%B %Y")
    except (TypeError, ValueError):
        return ""
    name = escape(city["name"])
    capped = bool(income.get("top_coded"))
    ratio = value / annual_income
    context = (
        "In {month}, {name}'s typical home value was <b>{value}</b>, "
        "{bound}<b>{ratio:.1f}&times;</b> its ACS median annual household income of <b>{income}</b>. "
        "That is a comparison of two area-level measures, not a required salary to buy a home. "
        "The income figure describes local households, not just homebuyers; it does not measure "
        "their savings, equity, or monthly housing costs."
    ).format(month=month, name=name, value=fmt_money(value), ratio=ratio,
             bound="no more than " if capped else "about ",
             income=fmt_money(annual_income) + ("+" if capped else ""))
    if (county_record and county_record.get("name") == city.get("county")
            and county_record.get("state") == city.get("state")
            and county_record.get("as_of") == city.get("as_of")
            and isinstance(county_record.get("value"), (int, float)) and county_record["value"] > 0):
        diff = (value / county_record["value"] - 1) * 100
        relative = ("{:.1f}% {}".format(abs(diff), "above" if diff > 0 else "below")
                    if abs(diff) >= .05 else "approximately equal to")
        context += (
            ' The city value is {relative} the same-month <a href="../counties/{state}-{slug}.html">'
            '{county}</a> figure of {value}. A county aggregate is not an average of the city '
            'values listed here, and does not describe every neighborhood.'
        ).format(relative=relative, state=city["state"].lower(), slug=slugify(county_record["name"]),
                 county=escape(county_record["name"]), value=fmt_money(county_record["value"]))
    article = ('<p><a href="../los-angeles-county-home-price-gaps.html">'
               'Why one Los Angeles County price hides very different city markets &rarr;</a></p>'
               if key == ("CA", "Beverly Hills") else "")
    return ('<section class="hero" style="text-align:left;max-width:760px;">'
            '<h2 style="font-size:20px;">How to interpret {name}\'s home-price figure</h2>'
            '<p>{context}</p>{article}</section>').format(name=name, context=context, article=article)


def local_comparison_section(city, eligible_by_location):
    """Use only same-county, same-month peers with a published city profile."""
    peer_names = PILOT_PEERS.get((city.get("state"), city.get("name")), ())
    value = city.get("value")
    county = city.get("county")
    as_of = city.get("as_of")
    if not peer_names or not county or not as_of or not isinstance(value, (int, float)) or value <= 0:
        return ""

    items = []
    for peer_name in peer_names:
        peer = eligible_by_location.get((city["state"], county, peer_name))
        if not peer or peer.get("state") != city["state"] or peer.get("county") != county:
            continue
        peer_value = peer.get("value")
        if peer.get("as_of") != as_of or not isinstance(peer_value, (int, float)) or peer_value <= 0:
            continue
        difference = (peer_value / value - 1) * 100
        if abs(difference) < 0.05:
            comparison = "about the same as {}".format(escape(city["name"]))
        else:
            comparison = "{:.1f}% {} than {}".format(
                abs(difference), "higher" if difference > 0 else "lower", escape(city["name"])
            )
        items.append(
            '  <li><a href="{}-{}.html">{}</a>: <b>{}</b> ({})</li>'.format(
                city["state"].lower(), slugify(peer["name"]), escape(peer["name"]),
                fmt_money(peer_value), comparison,
            )
        )

    if not items:
        return ""
    return (
        '<section class="hero local-comparison" style="text-align:left;max-width:760px;">\n'
        '  <h2 style="font-size:20px;">How do other {county} cities compare with {name}?</h2>\n'
        '  <p>These published city profiles use Zillow ZHVI typical home values '
        'for the same reporting month ({as_of}):</p>\n'
        '  <ul>\n{items}\n  </ul>\n'
        '  <p style="font-size:13px;color:var(--text-dim);">These are citywide typical '
        'values, not individual listing or sale prices.</p>\n'
        '</section>'
    ).format(
        county=escape(county), name=escape(city["name"]), as_of=escape(as_of),
        items="\n".join(items),
    )


def build():
    for p in (CITY_PATH, COUNTY_PATH, CITY_CRIME_PATH):
        if not p.exists():
            sys.exit("ERROR: {} not found.".format(p))

    cities = json.loads(CITY_PATH.read_text())["cities"]
    city_candidates = city_candidates_by_key(cities)
    counties = json.loads(COUNTY_PATH.read_text())["counties"]
    crime = json.loads(CITY_CRIME_PATH.read_text())["cities"]
    income = (
        json.loads(CITY_INCOME_PATH.read_text()).get("cities", {})
        if CITY_INCOME_PATH.exists() else {}
    )
    history = load_history_series(CITY_HISTORY_PATH)

    # county lookup by (state, normalized county name) so each city can be
    # compared against, and linked to, its own county page
    county_by_key = {}
    for fips, rec in counties.items():
        key = "{}|{}".format(rec["state"], re.sub(r"[^a-z0-9]+", "", COUNTY_SUFFIXES.sub("", rec["name"]).strip().lower()))
        county_by_key[key] = rec

    eligible = []
    for c in cities:
        if c.get("value") is None or not c.get("name") or not c.get("state"):
            continue
        cr = match_city_source(c, crime, city_candidates)
        if not cr or (cr.get("population") or 0) < MIN_POPULATION:
            continue
        eligible.append((c, cr))

    national_violent = sorted(
        r["violent_crime_rate"] for _, r in eligible if r.get("violent_crime_rate") is not None
    )

    by_state = {}
    for c, cr in eligible:
        by_state.setdefault(c["state"], []).append((c, cr))

    state_median = {
        st: statistics.median([c["value"] for c, _ in grp]) for st, grp in by_state.items()
    }

    # Profile slugs retain the highest-priced same-name city in each state.
    # Use that exact deduplication for pilot links so a displayed peer value
    # can never describe a different city than its destination profile.
    canonical_eligible = {}
    for c, _ in sorted(eligible, key=lambda pair: pair[0]["value"], reverse=True):
        canonical_eligible.setdefault((c["state"], slugify(c["name"])), c)
    eligible_by_location = {
        (c["state"], c.get("county"), c["name"]): c
        for c in canonical_eligible.values()
    }

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    urls = []
    expected_filenames = set()
    seen = set()

    for st, grp in by_state.items():
        ranked = sorted(grp, key=lambda x: x[0]["value"], reverse=True)
        for pos, (c, cr) in enumerate(ranked):
            name, state, value = c["name"], c["state"], c["value"]
            state_name = ABBR_TO_NAME.get(state, state)
            state_slug = slugify(state_name)
            slug = "{}-{}".format(state.lower(), slugify(name))
            if slug in seen:      # two same-named places in one state
                continue
            seen.add(slug)

            filename = slug + ".html"
            expected_filenames.add(filename)
            canonical = "{}/cities/{}".format(SITE_URL, filename)
            income_rec = match_city_source(c, income, city_candidates, allow_city_suffix=True)
            yoy = c.get("yoy_pct")
            as_of = c.get("as_of", "")

            if yoy is None:
                yoy_sentence = "with no year-over-year comparison currently available."
            elif yoy > 0:
                yoy_sentence = "up {} from a year earlier.".format(fmt_pct_bare(yoy))
            elif yoy < 0:
                yoy_sentence = "down {} from a year earlier.".format(fmt_pct_bare(yoy))
            else:
                yoy_sentence = "unchanged from a year earlier."

            # county context + internal link to the county page
            county_name = c.get("county")
            county_rec = None
            if county_name:
                ck = "{}|{}".format(state, re.sub(r"[^a-z0-9]+", "", COUNTY_SUFFIXES.sub("", county_name).strip().lower()))
                county_rec = county_by_key.get(ck)

            smed = state_median[state]
            vs = round((value / smed - 1) * 100, 1)
            vs_phrase = ("{}% above".format(abs(vs)) if vs > 0
                         else "{}% below".format(abs(vs)) if vs < 0 else "in line with")
            comparison = (
                "{n} ranks {r} of {t} <a href=\"../states/{ss}.html\">{sn}</a> cities tracked here by median home value, and sits "
                "{vs} the state's city median of {sm}.".format(
                    n=name, r="#" + str(pos + 1), t=len(ranked),
                    ss=state_slug, sn=state_name, vs=vs_phrase, sm=fmt_money(smed))
            )
            if county_rec:
                comparison += ' It sits in <a href="../counties/{cs}-{cslug}.html">{cn}</a>, where the county-wide median is {cv}.'.format(
                    cs=state.lower(), cslug=slugify(county_rec["name"]),
                    cn=county_rec["name"], cv=fmt_money(county_rec["value"]))

            # link to cities nearest in price, forming a chain across the state
            # rather than every page pointing at the same expensive few
            lo, hi = max(0, pos - 4), pos + 5
            nearby = [x for x in ranked[lo:hi] if x[0]["name"] != name]
            if nearby:
                links = " &middot; ".join(
                    '<a href="{}-{}.html">{}</a>'.format(x[0]["state"].lower(), slugify(x[0]["name"]), x[0]["name"])
                    for x in nearby
                )
                nearby_section = (
                    '<div class="hero" style="text-align:left;max-width:760px;">\n'
                    '  <h2 style="font-size:16px;color:var(--text-dim);text-transform:uppercase;letter-spacing:.04em;">Cities with similar home prices in {st}</h2>\n'
                    "  <p>{links}</p>\n</div>\n"
                ).format(st=state, links=links)
            else:
                nearby_section = ""

            html = PAGE_TEMPLATE.format(
                ga=GA_SNIPPET,
                title="Median Home Price in {}, {} ({}) | Home Price Map".format(name, state, as_of[:4]),
                description=escape(meta_description(
                    name, state, value, yoy_sentence, income_rec,
                    county_rec["name"] if county_rec else state_name,
                ), quote=True),
                canonical=canonical,
                site_url=SITE_URL,
                city_name=name,
                map_link=(
                    '<p><a href="../cities.html#city={}">View {} on the interactive city map &rarr;</a></p>'.format(
                        quote_plus("{}, {}".format(name, state)), escape(name)
                    ) if isinstance(c.get("lat"), (int, float)) and isinstance(c.get("lon"), (int, float)) else ""
                ),
                compare_id=quote_plus("city:{}-{}".format(state.lower(), slugify(name))),
                state=state,
                state_name=state_name,
                state_slug=state_slug,
                value_fmt=fmt_money(value),
                yoy_fmt=("n/a" if yoy is None else ("+" if yoy > 0 else "") + str(yoy) + "%"),
                population_fmt=format(int(cr.get("population") or 0), ","),
                as_of=as_of,
                yoy_sentence=yoy_sentence,
                comparison=comparison,
                local_comparison_section=local_comparison_section(c, eligible_by_location),
                targeted_context_section=targeted_context_section(c, income_rec, county_rec),
                income_section=income_section(name, value, income_rec),
                crime_section=crime_section(name, cr, national_violent),
                faq_section=faq_section(
                                        name, state, value, yoy, income_rec, cr,
                                        county_rec["name"] if county_rec else None,
                                        county_rec["value"] if county_rec else None,
                                        smed),
                nearby_section=nearby_section,
                history_section=render_history_section(
                    safe_city_history(c, history, city_candidates),
                    "{}, {}".format(name, state),
                ),
            )
            (OUT_DIR / filename).write_text(html, encoding="utf-8")
            urls.append(canonical)

    prune_stale_html(
        OUT_DIR,
        expected_filenames,
        minimum_expected=MIN_EXPECTED_PROFILES,
    )
    return urls


def main():
    urls = build()
    print("Generated {} city pages (threshold: FBI crime data covering >= {:,} residents).".format(
        len(urls), MIN_POPULATION))
    return 0


if __name__ == "__main__":
    sys.exit(main())
