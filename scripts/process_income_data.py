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

# Census GEO_ID prefixes identify the geography level, which lets us just drop
# the downloads in as-named rather than depending on someone renaming them
# correctly a year from now.
GEO_PREFIX_COUNTY = "0500000US"
GEO_PREFIX_PLACE = "1600000US"
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


def classify_csv(path):
    """Peek at the first data row's GEO_ID to work out which geography this
    export covers. Returns 'county', 'place', or None for files that aren't
    B19013 data exports (the folder also collects the little national-summary
    CSV and the metadata files that come in the same download)."""
    try:
        with path.open(newline="", encoding="utf-8-sig") as f:
            reader = csv.reader(f)
            header = next(reader, None)
            if not header:
                return None
            cleaned = [h.strip() for h in header]
            if "GEO_ID" not in cleaned:
                return None
            gi = cleaned.index("GEO_ID")
            for row in reader:
                if len(row) <= gi:
                    continue
                geo = row[gi].strip()
                if geo in ("", "Geography"):
                    continue  # human-readable second header row
                if geo.startswith(GEO_PREFIX_COUNTY):
                    return "county"
                if geo.startswith(GEO_PREFIX_PLACE):
                    return "place"
                return None
    except (OSError, csv.Error):
        return None
    return None


def discover_inputs():
    """Maps geography level -> csv path for everything usable in IncomeData/."""
    found = {}
    if not INCOME_DIR.exists():
        return found
    for path in sorted(INCOME_DIR.glob("*.csv")):
        kind = classify_csv(path)
        if kind and kind not in found:
            found[kind] = path
    return found


def split_place_name(full_name):
    """'Los Angeles city, California' -> ('Los Angeles city', 'CA')"""
    if "," not in full_name:
        return None, None
    place, _, state_name = full_name.rpartition(",")
    return place.strip(), STATE_ABBR.get(state_name.strip())


def main():
    inputs = discover_inputs()
    if not inputs:
        sys.exit(
            "ERROR: no usable B19013 exports found in {}.\nDownload table "
            "B19013 from https://data.census.gov (ACS 5-Year Estimates "
            "Detailed Tables) for the County and/or Place geographies and drop "
            "the '*-Data.csv' files in that folder -- filenames don't matter, "
            "the geography is detected from the GEO_ID column."
            .format(INCOME_DIR)
        )

    county_csv = inputs.get("county")
    place_csv = inputs.get("place")
    for kind, path in sorted(inputs.items()):
        print("Found {} data: {}".format(kind, path.name))
    if not place_csv:
        print("NOTE: no Place-level export found -- city income will be skipped. "
              "The city map simply won't show income until one is added.")
    if not county_csv:
        print("NOTE: no County-level export found -- county income will be skipped.")

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
    county_unmatched = []
    for geo_id, name, income, capped in read_acs_rows(county_csv) if county_csv else []:
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
            county_unmatched.append(name)
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
    for geo_id, full_name, income, capped in read_acs_rows(place_csv) if place_csv else []:
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

    # Only write a file if we actually had input for it -- otherwise a
    # partial download would silently wipe out good data from a previous run.
    if county_csv:
        (DATA_DIR / "income_data_county.json").write_text(
            json.dumps({"count": len(county_out), "counties": county_out}, separators=(",", ":"))
        )
    if place_csv:
        (DATA_DIR / "income_data_city.json").write_text(
            json.dumps({"count": len(city_out), "cities": city_out}, separators=(",", ":"))
        )

    print()
    if county_csv:
        print("Counties: parsed {} rows, {} suppressed/no estimate, {} not in price data, matched {} of {} priced counties ({:.1f}%).".format(
            county_rows, county_suppressed, len(county_unmatched),
            len(county_out), len(county_prices),
            100.0 * len(county_out) / max(1, len(county_prices))))
        if county_unmatched:
            print("          unmatched sample: {}".format(", ".join(county_unmatched[:5])))
    if place_csv:
        print("Cities:   parsed {} rows, {} suppressed/no estimate, matched {} of {} priced cities ({:.1f}%).".format(
            place_rows, place_suppressed, len(city_out), len(city_prices),
            100.0 * len(city_out) / max(1, len(city_prices))))
    return 0


if __name__ == "__main__":
    sys.exit(main())
