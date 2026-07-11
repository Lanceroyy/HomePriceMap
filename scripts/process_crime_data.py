#!/usr/bin/env python3
"""
One-time / annual processor for FBI Crime in the United States (CIUS) data.

Unlike fetch_data.py (which pulls from a stable Zillow URL daily), the FBI's
Crime Data Explorer is a JS-rendered app with no stable direct-download URL,
so this script processes files that must be manually downloaded each year
from https://cde.ucr.cjis.gov/LATEST/webapp/#/pages/downloads
(collection: "Offenses Known to Law Enforcement") and placed in
data/CrimeData/:

    CIUS_Table_8_Offenses_Known_to_Law_Enforcement_by_State_by_City_2024.xlsx
    CIUS_Table_10_Offenses_Known_to_Law_Enforcement_by_State_by_Metropolitan_and_Nonmetropolitan_Counties_2024.xlsx

Only Table 8 (city) is used for real crime-rate math, because it includes
population (so we can compute a per-100k rate) and because Table 10's county
figures are sheriff/county-department-only per the FBI's own footnote --
they exclude crimes handled by a city's own police department, which would
badly understate crime in any county containing an incorporated city.

Instead, county-level figures are rolled up as a population-weighted average
of that county's own cities' crime rates (matched via data/city_prices.json,
which already carries each city's parent county name from Zillow's data).
This reuses data we already have instead of needing a second crosswalk.

Outputs:
    data/crime_data_city.json    keyed by "STATE|normalizedcityname" (same
                                  key shape as city_history.json)
    data/crime_data_county.json  keyed by 5-digit county FIPS (same keys as
                                  county_prices.json)

Requires data/city_prices.json and data/county_prices.json to already exist
with REAL fetched data (not the placeholder sample data) -- the county name
carried on each city record is what makes the city-to-county rollup possible
at all, and a 20-row sample won't produce a meaningful crime dataset.

Usage:
    pip install -r requirements.txt
    python scripts/process_crime_data.py
"""
import json
import re
import sys
from pathlib import Path

import openpyxl

ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT / "data"
CRIME_DIR = DATA_DIR / "CrimeData"
CITY_XLSX = CRIME_DIR / "CIUS_Table_8_Offenses_Known_to_Law_Enforcement_by_State_by_City_2024.xlsx"
CITY_PRICES_PATH = DATA_DIR / "city_prices.json"
COUNTY_PRICES_PATH = DATA_DIR / "county_prices.json"
CRIME_YEAR = 2024

PLACE_SUFFIXES = re.compile(
    r"\s+(city|town|village|township|CDP|borough|municipality)\s*$", re.IGNORECASE
)
COUNTY_SUFFIXES = re.compile(
    r"\s+(county|parish|borough|census area|municipality|municipio|city and borough)\s*$",
    re.IGNORECASE,
)

STATE_ABBR = {
    "ALABAMA": "AL", "ALASKA": "AK", "ARIZONA": "AZ", "ARKANSAS": "AR",
    "CALIFORNIA": "CA", "COLORADO": "CO", "CONNECTICUT": "CT", "DELAWARE": "DE",
    "DISTRICT OF COLUMBIA": "DC", "FLORIDA": "FL", "GEORGIA": "GA", "HAWAII": "HI",
    "IDAHO": "ID", "ILLINOIS": "IL", "INDIANA": "IN", "IOWA": "IA",
    "KANSAS": "KS", "KENTUCKY": "KY", "LOUISIANA": "LA", "MAINE": "ME",
    "MARYLAND": "MD", "MASSACHUSETTS": "MA", "MICHIGAN": "MI", "MINNESOTA": "MN",
    "MISSISSIPPI": "MS", "MISSOURI": "MO", "MONTANA": "MT", "NEBRASKA": "NE",
    "NEVADA": "NV", "NEW HAMPSHIRE": "NH", "NEW JERSEY": "NJ", "NEW MEXICO": "NM",
    "NEW YORK": "NY", "NORTH CAROLINA": "NC", "NORTH DAKOTA": "ND", "OHIO": "OH",
    "OKLAHOMA": "OK", "OREGON": "OR", "PENNSYLVANIA": "PA", "RHODE ISLAND": "RI",
    "SOUTH CAROLINA": "SC", "SOUTH DAKOTA": "SD", "TENNESSEE": "TN", "TEXAS": "TX",
    "UTAH": "UT", "VERMONT": "VT", "VIRGINIA": "VA", "WASHINGTON": "WA",
    "WEST VIRGINIA": "WV", "WISCONSIN": "WI", "WYOMING": "WY",
    "PUERTO RICO": "PR",
}


def normalize_place(name: str) -> str:
    name = PLACE_SUFFIXES.sub("", name or "")
    name = name.strip().lower()
    return re.sub(r"[^a-z0-9]+", "", name)


def normalize_county(name: str) -> str:
    name = COUNTY_SUFFIXES.sub("", name or "")
    name = name.strip().lower()
    return re.sub(r"[^a-z0-9]+", "", name)


def num(v):
    """FBI sheets sometimes have blank cells or text footnote markers instead
    of 0; treat anything non-numeric as 0 rather than crashing the run."""
    if v is None:
        return 0
    try:
        return float(v)
    except (TypeError, ValueError):
        return 0


def parse_table8(path: Path):
    wb = openpyxl.load_workbook(path, data_only=True)
    ws = wb.active
    rows = []
    state_raw = None
    for row in ws.iter_rows(min_row=5, values_only=True):
        state_cell, city_cell = row[0], row[1]
        if state_cell and str(state_cell).strip().isupper() and city_cell:
            state_raw = str(state_cell).strip()
        if not city_cell or not state_raw:
            continue
        # Footnote rows have long sentence-like text in column A/B and no
        # usable population figure; skip anything that doesn't look like a
        # real row (population must parse as a number).
        population = row[2]
        if population is None or not isinstance(population, (int, float)):
            continue
        state_abbr = STATE_ABBR.get(state_raw)
        if not state_abbr:
            continue
        # The FBI appends footnote markers directly onto some city names
        # (e.g. "Los Angeles2" pointing at footnote 2), which would otherwise
        # break name matching against city_prices.json.
        city_clean = re.sub(r"\d+$", "", str(city_cell)).strip()
        rows.append({
            "state": state_abbr,
            "city": city_clean,
            "population": num(population),
            "violent_crime": num(row[3]),
            "murder": num(row[4]),
            "rape": num(row[5]),
            "robbery": num(row[6]),
            "aggravated_assault": num(row[7]),
            "property_crime": num(row[8]),
            "burglary": num(row[9]),
            "larceny_theft": num(row[10]),
            "motor_vehicle_theft": num(row[11]),
            "arson": num(row[12]) if len(row) > 12 else 0,
        })
    return rows


def rate_per_100k(count, population):
    if not population:
        return None
    return round((count / population) * 100000, 1)


def main():
    if not CITY_XLSX.exists():
        sys.exit(
            f"ERROR: {CITY_XLSX} not found. Download Table 8 (Offenses Known to "
            "Law Enforcement by State by City) from the FBI Crime Data Explorer "
            "and place it in data/CrimeData/ first."
        )
    if not CITY_PRICES_PATH.exists() or not COUNTY_PRICES_PATH.exists():
        sys.exit(
            "ERROR: data/city_prices.json and data/county_prices.json must "
            "exist first -- run scripts/fetch_data.py (or wait for the daily "
            "workflow) before running this script."
        )

    city_prices = json.loads(CITY_PRICES_PATH.read_text())["cities"]
    county_prices = json.loads(COUNTY_PRICES_PATH.read_text())["counties"]

    if len(city_prices) < 1000 or len(county_prices) < 500:
        print(
            f"WARNING: city_prices.json has {len(city_prices)} cities and "
            f"county_prices.json has {len(county_prices)} counties -- this "
            "looks like placeholder/sample data, not a real fetch. The crime "
            "rollup will be nearly empty. Run scripts/fetch_data.py for real "
            "first, or re-run this script once real data is live."
        )

    # city key (STATE|normalizedname) -> county name, for the rollup join
    city_to_county = {}
    for c in city_prices:
        key = f"{c['state']}|{normalize_place(c['name'])}"
        if c.get("county"):
            city_to_county[key] = c["county"]

    # county key (STATE|normalizedcountyname) -> fips
    county_key_to_fips = {}
    for fips, rec in county_prices.items():
        key = f"{rec['state']}|{normalize_county(rec['name'])}"
        county_key_to_fips[key] = fips

    print(f"Parsing {CITY_XLSX.name} ...")
    crime_rows = parse_table8(CITY_XLSX)
    print(f"  -> {len(crime_rows)} city rows parsed")

    city_out = {}
    matched_cities = 0
    county_acc = {}

    for r in crime_rows:
        key = f"{r['state']}|{normalize_place(r['city'])}"
        city_out[key] = {
            "name": r["city"],
            "state": r["state"],
            "population": int(r["population"]),
            "year": CRIME_YEAR,
            "violent_crime_rate": rate_per_100k(r["violent_crime"], r["population"]),
            "property_crime_rate": rate_per_100k(r["property_crime"], r["population"]),
            "murder_rate": rate_per_100k(r["murder"], r["population"]),
            "source": "FBI CIUS Table 8 (Offenses Known to Law Enforcement by City)",
        }

        county_name = city_to_county.get(key)
        if not county_name:
            continue
        county_key = f"{r['state']}|{normalize_county(county_name)}"
        fips = county_key_to_fips.get(county_key)
        if not fips:
            continue

        matched_cities += 1
        acc = county_acc.setdefault(fips, {
            "population": 0, "violent_crime": 0, "property_crime": 0,
            "murder": 0, "cities_matched": 0,
        })
        acc["population"] += r["population"]
        acc["violent_crime"] += r["violent_crime"]
        acc["property_crime"] += r["property_crime"]
        acc["murder"] += r["murder"]
        acc["cities_matched"] += 1

    county_out = {}
    for fips, acc in county_acc.items():
        rec = county_prices[fips]
        county_out[fips] = {
            "name": rec["name"],
            "state": rec["state"],
            "year": CRIME_YEAR,
            "cities_matched": acc["cities_matched"],
            "population_covered": int(acc["population"]),
            "violent_crime_rate": rate_per_100k(acc["violent_crime"], acc["population"]),
            "property_crime_rate": rate_per_100k(acc["property_crime"], acc["population"]),
            "murder_rate": rate_per_100k(acc["murder"], acc["population"]),
            "source": (
                "Population-weighted average of matched cities' FBI CIUS "
                "Table 8 crime rates (county-level FBI figures exclude "
                "crimes reported by city police departments, so a direct "
                "county number would understate crime in counties with "
                "incorporated cities)"
            ),
        }

    (DATA_DIR / "crime_data_city.json").write_text(
        json.dumps({"year": CRIME_YEAR, "count": len(city_out), "cities": city_out}, separators=(",", ":"))
    )
    (DATA_DIR / "crime_data_county.json").write_text(
        json.dumps({"year": CRIME_YEAR, "count": len(county_out), "counties": county_out}, separators=(",", ":"))
    )

    print(f"Wrote {len(city_out)} city crime records.")
    print(
        f"Matched {matched_cities}/{len(crime_rows)} crime rows to a known city "
        f"in city_prices.json, rolling up to {len(county_out)}/{len(county_prices)} "
        "counties with at least one matched city."
    )


if __name__ == "__main__":
    main()
