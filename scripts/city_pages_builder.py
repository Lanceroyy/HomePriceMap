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
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT / "data"
CITY_PATH = DATA_DIR / "city_prices.json"
COUNTY_PATH = DATA_DIR / "county_prices.json"
CITY_CRIME_PATH = DATA_DIR / "crime_data_city.json"
OUT_DIR = ROOT / "cities"
SITE_URL = "https://homepricemap.us"

# A crime rate computed over a few hundred residents swings wildly on a single
# incident. 5,000 is the same floor used for county rollups in
# process_crime_data.py, kept consistent so the two never disagree.
MIN_POPULATION = 5000

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
    {{"@type": "ListItem", "position": 2, "name": "Cities", "item": "{site_url}/cities.html"}},
    {{"@type": "ListItem", "position": 3, "name": "{city_name}, {state}", "item": "{canonical}"}}
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
    <button class="theme-toggle" type="button" onclick="toggleTheme()" aria-label="Toggle dark mode">Dark</button>
  </nav>
</header>

<div class="hero" style="text-align:left;max-width:760px;">
  <p style="font-size:13px;color:var(--text-dim);"><a href="../index.html">Home</a> &rsaquo; <a href="../cities.html">Cities</a> &rsaquo; {city_name}, {state}</p>
  <h1 style="font-size:30px;">Median Home Price in {city_name}, {state}</h1>
  <p>The median home value in <b>{city_name}, {state}</b> is <b>{value_fmt}</b> as of {as_of}, {yoy_sentence}</p>
</div>

<div class="choice-grid" style="grid-template-columns:repeat(3,1fr);max-width:760px;">
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

<div class="hero" style="text-align:left;max-width:760px;">
  <p>{comparison}</p>
</div>

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


def faq_section(name, state, value, yoy, crime, county_name, county_value, state_median):
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
        "How much does a house cost in {}, {}?".format(name, state),
        "The median home value in {n} is <b>{v}</b>. {t} That is {p} the typical {sn} "
        "city tracked here.".format(n=name, v=fmt_money(value), t=trend, p=phrase,
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


def build():
    for p in (CITY_PATH, COUNTY_PATH, CITY_CRIME_PATH):
        if not p.exists():
            sys.exit("ERROR: {} not found.".format(p))

    cities = json.loads(CITY_PATH.read_text())["cities"]
    counties = json.loads(COUNTY_PATH.read_text())["counties"]
    crime = json.loads(CITY_CRIME_PATH.read_text())["cities"]

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
        cr = crime.get("{}|{}".format(c["state"], normalize_place(c["name"])))
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

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    urls = []
    seen = set()

    for st, grp in by_state.items():
        ranked = sorted(grp, key=lambda x: x[0]["value"], reverse=True)
        for pos, (c, cr) in enumerate(ranked):
            name, state, value = c["name"], c["state"], c["value"]
            slug = "{}-{}".format(state.lower(), slugify(name))
            if slug in seen:      # two same-named places in one state
                continue
            seen.add(slug)

            filename = slug + ".html"
            canonical = "{}/cities/{}".format(SITE_URL, filename)
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
                "{n} ranks {r} of {t} {sn} cities tracked here by median home value, and sits "
                "{vs} the state's city median of {sm}.".format(
                    n=name, r="#" + str(pos + 1), t=len(ranked),
                    sn=ABBR_TO_NAME.get(state, state), vs=vs_phrase, sm=fmt_money(smed))
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
                description="The median home value in {}, {} is {}, {} See local crime rates and how it compares to {}.".format(
                    name, state, fmt_money(value), yoy_sentence,
                    county_rec["name"] if county_rec else ABBR_TO_NAME.get(state, state)),
                canonical=canonical,
                site_url=SITE_URL,
                city_name=name,
                state=state,
                value_fmt=fmt_money(value),
                yoy_fmt=("n/a" if yoy is None else ("+" if yoy > 0 else "") + str(yoy) + "%"),
                population_fmt=format(int(cr.get("population") or 0), ","),
                as_of=as_of,
                yoy_sentence=yoy_sentence,
                comparison=comparison,
                crime_section=crime_section(name, cr, national_violent),
                faq_section=faq_section(name, state, value, yoy, cr,
                                        county_rec["name"] if county_rec else None,
                                        county_rec["value"] if county_rec else None,
                                        smed),
                nearby_section=nearby_section,
            )
            (OUT_DIR / filename).write_text(html, encoding="utf-8")
            urls.append(canonical)

    return urls


def main():
    urls = build()
    print("Generated {} city pages (threshold: FBI crime data covering >= {:,} residents).".format(
        len(urls), MIN_POPULATION))
    return 0


if __name__ == "__main__":
    sys.exit(main())
