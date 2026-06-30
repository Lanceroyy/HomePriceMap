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

BOM = "﻿"

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


def clean_key(k: str) -> str:
    return k.strip().lstrip(BOM)


def main():
    print(f"Downloading {GAZETTEER_URL} ...")
    req = urllib.request.Request(GAZETTEER_URL, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=60) as resp:
        raw = resp.read()

    zf = zipfile.ZipFile(io.BytesIO(raw))
    txt_name = next(n for n in zf.namelist() if n.lower().endswith(".txt"))
    raw_bytes = zf.read(txt_name)
    # utf-8-sig strips a leading UTF-8 byte-order-mark if present (Census's
    # gazetteer files often have one). Decoding that BOM as latin-1 instead
    # glues garbage characters onto the first header name ("USPS" becomes
    # unmatchable), which silently produces zero matches with no error.
    try:
        data = raw_bytes.decode("utf-8-sig")
    except UnicodeDecodeError:
        data = raw_bytes.decode("latin-1").lstrip(BOM)

    reader = csv.DictReader(io.StringIO(data), delimiter="\t")
    fieldnames = [clean_key(f) for f in (reader.fieldnames or [])]
    print(f"Detected columns: {fieldnames}")
    if "USPS" not in fieldnames or "NAME" not in fieldnames:
        print("WARNING: expected columns USPS/NAME not found - check delimiter/encoding.")

    # Gazetteer columns include: USPS (state abbr), NAME, INTPTLAT, INTPTLONG
    lookup = {}
    count = 0
    skipped = 0
    for row in reader:
        row = {clean_key(k): (v.strip() if v else v) for k, v in row.items() if k}
        state = row.get("USPS")
        name = row.get("NAME")
        lat = row.get("INTPTLAT")
        lon = row.get("INTPTLONG")
        if not (state and name and lat and lon):
            skipped += 1
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

    print(f"Wrote {count} places to {OUT_PATH} ({skipped} rows skipped as incomplete)")
    if count == 0:
        print("ERROR: 0 places written - something is still wrong with parsing. "
              "Check the 'Detected columns' line above against USPS/NAME/INTPTLAT/INTPTLONG.")


if __name__ == "__main__":
    sys.exit(main())
