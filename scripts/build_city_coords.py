#!/usr/bin/env python3
"""
One-time (re-run at most yearly) builder for data/city_coords.json.

Downloads the US Census Bureau's National Places Gazetteer File (public domain,
no API key, no signup) and produces a lookup keyed by "STATEABBR|NORMALIZED_NAME"
-> {name, state, lat, lon}.

This is kept SEPARATE from the daily fetch (scripts/fetch_data.py) because
place coordinates barely change year to year, while home prices change monthly.
Re-run this manually if you want to refresh coordinates (e.g. once a year when
Census publishes a new Gazetteer file).

Usage:
    python scripts/build_city_coords.py
"""
import csv
import io
import json
import re
import sys
import urllib.request
import zipfile
from pathlib import Path

GAZETTEER_URL = (
    "https://www2.census.gov/geo/docs/maps-data/data/gazetteer/"
    "2025_Gazetteer/2025_Gaz_place_national.zip"
)

ROOT = Path(__file__).resolve().parent.parent
OUT_PATH = ROOT / "data" / "city_coords.json"

# Census "place" names carry a legal/statistical suffix (e.g. "Springfield city",
# "Cary town") that Zillow's RegionName usually omits. Strip it so the two
# datasets join cleanly.
PLACE_SUFFIXES = re.compile(
    r"\s+(city|town|village|township|CDP|borough|municipality)\s*$", re.IGNORECASE
)


def normalize(name: str) -> str:
    name = PLACE_SUFFIXES.sub("", name)
    name = name.strip().lower()
    name = re.sub(r"[^a-z0-9]+", "", name)
    return name


def main():
    print(f"Downloading {GAZETTEER_URL} ...")
    req = urllib.request.Request(GAZETTEER_URL, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=60) as resp:
        raw = resp.read()

    zf = zipfile.ZipFile(io.BytesIO(raw))
    txt_name = next(n for n in zf.namelist() if n.lower().endswith(".txt"))
    data = zf.read(txt_name).decode("latin-1")

    reader = csv.DictReader(io.StringIO(data), delimiter="\t")
    # Gazetteer columns include: USPS (state abbr), NAME, INTPTLAT, INTPTLONG
    lookup = {}
    count = 0
    for row in reader:
        row = {k.strip(): v.strip() for k, v in row.items() if k}
        state = row.get("USPS")
        name = row.get("NAME")
        lat = row.get("INTPTLAT")
        lon = row.get("INTPTLONG")
        if not (state and name and lat and lon):
            continue
        key = f"{state}|{normalize(name)}"
        lookup[key] = {
            "name": PLACE_SUFFIXES.sub("", name).strip(),
            "state": state,
            "lat": float(lat),
            "lon": float(lon),
        }
        count += 1

    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(OUT_PATH, "w") as f:
        json.dump(lookup, f, separators=(",", ":"))

    print(f"Wrote {count} places to {OUT_PATH}")


if __name__ == "__main__":
    sys.exit(main())
