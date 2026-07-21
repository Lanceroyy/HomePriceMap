#!/usr/bin/env python3
"""
Annual processor for U.S. Census ACS median household income (table B19013).

Like the FBI crime data, this is a once-a-year manual refresh rather than part
of the daily job -- ACS 5-year estimates are published annually, and as of
May 2026 the Census API requires an API key, which a static site's public
workflow shouldn't need to carry. Downloading the CSV export sidesteps that
entirely.

To refresh (roughly once a year, when new ACS 5-year estimates drop):

  1. Go to https://data.census.gov and search for table B19013
  2. Pick the newest "ACS 5-Year Estimates Detailed Tables"
  3. Download it twice, once per geography level:
       - Geography > County > All Counties within United States
       - Geography > Place  > All Places within United States
  4. Unzip both and drop the "*-Data.csv" files into data/IncomeData/,
     renamed to county.csv and place.csv

Outputs:
    data/income_data_county.json   keyed by 5-digit county FIPS (same keys as
                                     county_prices.json)
    data/income_data_city.json     keyed by "STATE|normalizedcityname" (same
                                     key shape as crime_data_city.json)

Deliberately NOT stored here: the price-to-income ratio. Home prices refresh
daily while income refreshes yearly, so baking a ratio into this file would
start drifting the moment Zillow publishes anything new. The ratio is computed
at render time instead -- in js/common.js for the maps, and in
scripts/state_pages_builder.py for the state pages.

Usage:
    python scripts/process_income_data.py
"""
import csv
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT / "data"
INCOME_DIR = DATA_DIR / "IncomeData"
COUNTY_CSV = INCOME_DIR / "county.csv"
PLACE_CSV = INCOME_DIR / "place.csv"
CITY_PRICES_PATH = DATA_DIR / "city_prices.json"
COUNTY_PRICES_PATH = DATA_DIR / "county_prices.json"

# Mirrors normalize_place() in process_crime_data.py and normalizePlace() in
# js/common.js so the same city resolves to the same key in all three.
PLACE_SUFFIXES = re.compile(
    r"\s+(city|town|village|township|CDP|borough|municipality)\s*$", re.IGNORECASE
)

STATE_ABBR = {
    "Alabama": "AL", "Alaska": "AK", "Arizona": "AZ", "Arkansas": "AR",
    "California": "CA", "Colorado": "CO", "Connecticut": "CT", "Delaware": "DE",
    "District of Columbia": "DC", "Florida": "FL", "Georgia": "GA", "Hawaii": "HI",
    "Idaho": "ID", "Illinois": "IL", "Indiana": "IN", "Iowa": "IA",
    "Kansas": "KS", "Kentucky": "KY", "Louisiana": "LA", "Maine": "ME",
    "Maryland": "MD", "Massachusetts": "MA", "Michigan": "MI", "Minnesota": "MN",
    "Mississippi": "MS", "Missouri": "MO", "Montana": "MT", "Nebraska": "NE",
    "Nevada": "NV", "New Hampshire": "NH", "New Jersey": "NJ", "New Mexico": "NM",
    "New York": "NY", "North Carolina": "NC", "North Dakota": "ND", "Ohio": "OH",
    "Oklahoma": "OK", "Oregon": "OR", "Pennsylvania": "PA", "Rhode Island": "RI",
    "South Carolina": "SC", "South Dakota": "SD", "Tennessee": "TN", "Texas": "TX",
    "Utah": "UT", "Vermont": "VT", "Virginia": "VA", "Washington": "WA",
    "West Virginia": "WV", "Wisconsin": "WI", "Wyoming": "WY",
    "Puerto Rico": "PR",
}


def normalize_place(name):
    name = PLACE_SUFFIXES.sub("", name or "")
    name = name.strip().lower()
    return re.sub(r"[^a-z0-9]+", "", name)


def parse_income(raw):
    """ACS suppresses or annotates a lot of cells. Anything that isn't a plain
    number -- '-', 'N', '(X)', '**', null -- means no usable estimate, so treat
    it as missing rather than guessing. Top-coded values like '250,000+' are
    real data though, so keep the number and flag it."""
    if raw is None:
        return None, False
    s = str(raw).strip().replace(",", "").replace("$", "")
    if not s or s in {"-", "N", "(X)", "**", "***", "*****", "null"}:
        return None, False
    capped = s.endswith("+")
    if capped:
        s = s[:-1]
    try:
        v = float(s)
    except ValueError:
        return None, False
    if v <= 0:
        return None, False
    return int(round(v)), capped


def read_acs_rows(path):
    """Yields (geo_id, name, income, capped) from a data.census.gov export.

    These files carry two header rows: the machine header (GEO_ID, NAME,
    B19013_001E, ...) and then a human-readable one ("Geography",
    "Geographic Area Name", "Estimate!!Median household income..."). The
    second row has to be skipped or it parses as a bogus record."""
    with path.open(newline="", encoding="utf-8-sig") as f:
        reader = csv.reader(f)
        try:
            header = next(reader)
        except StopIteration:
            return

        cols = {name.strip(): i for i, name in enumerate(header)}
        geo_i = cols.get("GEO_ID")
        name_i = cols.get("NAME")
        # The estimate column is B19013_001E; fall back to a prefix match in
        # case the year suffix or table variant differs slightly.
        est_i = cols.get("B19013_001E")
        if est_i is None:
            for name, i in cols.items():
                if name.startswith("B19013_001") and name.endswith("E"):
                    est_i = i
                    break

        if geo_i is None or name_i is None or est_i is None:
            sys.exit(
                "ERROR: {} doesn't look like a B19013 export -- expected "
                "GEO_ID, NAME and B19013_001E columns, found: {}".format(
                    path.name, ", ".join(header[:8])
                )
            )

        for row in reader:
            if len(row) <= max(geo_i, name_i, est_i):
                continue
            geo_id = row[geo_i].strip()
            if not geo_id or geo_id == "Geography":
                continue  # the human-readable second header row
            income, capped = parse_income(row[est_i])
            yield geo_id, row[name_i].strip(), income, capped


def split_place_name(full_name):
    """'Los Angeles city, California' -> ('Los Angeles city', 'CA')"""
    if "," not in full_name:
        return None, None
    place, _, state_name = full_name.rpartition(",")
    return place.strip(), STATE_ABBR.get(state_name.strip())


def main():
    missing = [p for p in (COUNTY_CSV, PLACE_CSV) if not p.exists()]
    if missing:
        sys.exit(
            "ERROR: missing {}.\nDownload table B19013 from "
            "https://data.census.gov (ACS 5-Year Estimates Detailed Tables) "
            "for both County and Place geographies, then save the '*-Data.csv' "
            "files as data/IncomeData/county.csv and data/IncomeData/place.csv."
            .format(" and ".join(str(p) for p in missing))
        )

    county_prices = json.loads(COUNTY_PRICES_PATH.read_text())["counties"]
    city_prices = json.loads(CITY_PRICES_PATH.read_text())["cities"]

    if len(county_prices) < 500 or len(city_prices) < 1000:
        print(
            "WARNING: price data looks like placeholder/sample data "
            "({} counties, {} cities). Run scripts/fetch_data.py first, or "
            "coverage numbers below will be meaningless.".format(
                len(county_prices), len(city_prices)
            )
        )

    # ---- counties -------------------------------------------------------
    county_out = {}
    county_rows = 0
    county_suppressed = 0
    for geo_id, name, income, capped in read_acs_rows(COUNTY_CSV):
        county_rows += 1
        # County GEO_IDs look like '0500000US01001'; the trailing 5 digits are
        # the FIPS code, which is exactly how county_prices.json is keyed.
        fips = geo_id.split("US")[-1].strip()
        if len(fips) != 5 or not fips.isdigit():
            continue
        if income is None:
            county_suppressed += 1
            continue
        if fips not in county_prices:
            continue
        rec = county_prices[fips]
        county_out[fips] = {
            "name": rec["name"],
            "state": rec["state"],
            "median_household_income": income,
            "top_coded": capped,
            "source": "U.S. Census Bureau, ACS 5-Year Estimates, table B19013",
        }

    # ---- cities / places ------------------------------------------------
    price_city_keys = set()
    for c in city_prices:
        price_city_keys.add("{}|{}".format(c["state"], normalize_place(c["name"])))

    city_out = {}
    place_rows = 0
    place_suppressed = 0
    for geo_id, full_name, income, capped in read_acs_rows(PLACE_CSV):
        place_rows += 1
        place_name, state_abbr = split_place_name(full_name)
        if not place_name or not state_abbr:
            continue
        if income is None:
            place_suppressed += 1
            continue
        key = "{}|{}".format(state_abbr, normalize_place(place_name))
        # Only keep places we actually plot, and don't let a later duplicate
        # (e.g. a CDP sharing a city's name) clobber an earlier match.
        if key not in price_city_keys or key in city_out:
            continue
        city_out[key] = {
            "name": place_name,
            "state": state_abbr,
            "median_household_income": income,
            "top_coded": capped,
            "source": "U.S. Census Bureau, ACS 5-Year Estimates, table B19013",
        }

    (DATA_DIR / "income_data_county.json").write_text(
        json.dumps({"count": len(county_out), "counties": county_out}, separators=(",", ":"))
    )
    (DATA_DIR / "income_data_city.json").write_text(
        json.dumps({"count": len(city_out), "cities": city_out}, separators=(",", ":"))
    )

    print("Counties: parsed {} rows, {} suppressed/no estimate, matched {} of {} priced counties.".format(
        county_rows, county_suppressed, len(county_out), len(county_prices)))
    print("Cities:   parsed {} rows, {} suppressed/no estimate, matched {} of {} priced cities.".format(
        place_rows, place_suppressed, len(city_out), len(city_prices)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
