#!/usr/bin/env python3
"""
Daily data refresh for the Home Price Map.

Downloads Zillow Research's free ZHVI (Zillow Home Value Index) CSVs for
counties and cities, extracts the latest median home value and year-over-year
change for each region, and writes two small JSON files the static frontend
reads directly:

    data/county_prices.json   keyed by 5-digit county FIPS
    data/city_prices.json     list of cities with lat/lon (joined against
                               data/city_coords.json, built separately by
                               build_city_coords.py)

Zillow republishes these CSVs monthly (around the 16th), but there's no harm
in polling daily -- the script just re-writes the same numbers until a new
month lands. No API key required.

Usage:
    python scripts/fetch_data.py
"""
import csv
import io
import json
import re
import sys
import urllib.request
from datetime import datetime, date
from pathlib import Path

COUNTY_CSV_URL = (
    "https://files.zillowstatic.com/research/public_csvs/zhvi/"
    "County_zhvi_uc_sfrcondo_tier_0.33_0.67_sm_sa_month.csv"
)
CITY_CSV_URL = (
    "https://files.zillowstatic.com/research/public_csvs/zhvi/"
    "City_zhvi_uc_sfrcondo_tier_0.33_0.67_sm_sa_month.csv"
)

ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT / "data"
HISTORY_DIR = DATA_DIR / "history"
CITY_COORDS_PATH = DATA_DIR / "city_coords.json"

DATE_COL_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
PLACE_SUFFIXES = re.compile(
    r"\s+(city|town|village|township|CDP|borough|municipality)\s*$", re.IGNORECASE
)


def fetch_csv(url: str) -> list[dict]:
    print(f"Downloading {url} ...")
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=120) as resp:
        raw = resp.read().decode("utf-8-sig")
    reader = csv.DictReader(io.StringIO(raw))
    rows = list(reader)
    print(f"  -> {len(rows)} rows")
    return rows


def date_columns(rows: list[dict]) -> list[str]:
    if not rows:
        return []
    cols = [c for c in rows[0].keys() if DATE_COL_RE.match(c)]
    cols.sort()
    return cols


def latest_value(row: dict, cols: list[str]):
    """Walk backwards from the most recent month until we find a value."""
    for col in reversed(cols):
        v = row.get(col)
        if v not in (None, ""):
            try:
                return col, float(v)
            except ValueError:
                continue
    return None, None


def yoy_value(row: dict, cols: list[str], latest_col: str):
    if not latest_col:
        return None
    try:
        latest_date = datetime.strptime(latest_col, "%Y-%m-%d").date()
    except ValueError:
        return None
    target = date(latest_date.year - 1, latest_date.month, 1)
    target_str = target.strftime("%Y-%m-%d")
    # exact column may not exist (months are usually month-end dates); find
    # the closest date column to ~12 months back.
    candidates = [c for c in cols if c <= latest_col]
    best = None
    for c in candidates:
        c_date = datetime.strptime(c, "%Y-%m-%d").date()
        months_back = (latest_date.year - c_date.year) * 12 + (latest_date.month - c_date.month)
        if 11 <= months_back <= 13:
            best = c
            if months_back == 12:
                break
    if not best:
        return None
    v = row.get(best)
    if v in (None, ""):
        return None
    try:
        return float(v)
    except ValueError:
        return None


def normalize(name: str) -> str:
    name = PLACE_SUFFIXES.sub("", name)
    name = name.strip().lower()
    name = re.sub(r"[^a-z0-9]+", "", name)
    return name


def build_county_data(rows: list[dict], cols: list[str]) -> dict:
    out = {}
    for row in rows:
        state_fips = (row.get("StateCodeFIPS") or "").strip()
        county_fips = (row.get("MunicipalCodeFIPS") or "").strip()
        if not state_fips or not county_fips:
            continue
        fips = state_fips.zfill(2) + county_fips.zfill(3)
        latest_col, value = latest_value(row, cols)
        if value is None:
            continue
        yoy = yoy_value(row, cols, latest_col)
        yoy_pct = round((value / yoy - 1) * 100, 2) if yoy else None
        out[fips] = {
            "name": row.get("RegionName"),
            "state": row.get("StateName") or row.get("State"),
            "value": round(value),
            "yoy_pct": yoy_pct,
            "as_of": latest_col,
        }
    return out


def build_city_data(rows: list[dict], cols: list[str], coords: dict) -> list:
    out = []
    matched, unmatched = 0, 0
    for row in rows:
        name = row.get("RegionName") or row.get("City")
        state = row.get("State") or row.get("StateName")
        if not name or not state:
            continue
        key = f"{state}|{normalize(name)}"
        loc = coords.get(key)
        if not loc:
            unmatched += 1
            continue
        matched += 1
        latest_col, value = latest_value(row, cols)
        if value is None:
            continue
        yoy = yoy_value(row, cols, latest_col)
        yoy_pct = round((value / yoy - 1) * 100, 2) if yoy else None
        out.append({
            "name": name,
            "state": state,
            "county": row.get("CountyName"),
            "lat": loc["lat"],
            "lon": loc["lon"],
            "value": round(value),
            "yoy_pct": yoy_pct,
            "as_of": latest_col,
        })
    print(f"  city match rate: {matched} matched, {unmatched} unmatched")
    return out


def load_history(path: Path) -> dict:
    if path.exists():
        try:
            return json.loads(path.read_text())
        except json.JSONDecodeError:
            print(f"  WARNING: {path} was unreadable, starting fresh history file.")
    return {}


def update_history(history_path: Path, keyed_data: dict) -> None:
    """Append one time-series point per region, but only when the underlying
    Zillow data month (as_of) actually advances. Zillow republishes monthly,
    so this keeps history at ~12 points/year/region instead of 365 identical
    daily copies.
    """
    history = load_history(history_path)
    series = history.setdefault("series", {})
    changed = False
    for key, rec in keyed_data.items():
        as_of = rec.get("as_of")
        value = rec.get("value")
        if as_of is None or value is None:
            continue
        points = series.setdefault(key, [])
        if points and points[-1]["as_of"] == as_of:
            continue  # already have this month recorded
        points.append({"as_of": as_of, "value": value, "yoy_pct": rec.get("yoy_pct")})
        changed = True
    if changed:
        history["updated"] = datetime.utcnow().isoformat() + "Z"
        history_path.parent.mkdir(parents=True, exist_ok=True)
        history_path.write_text(json.dumps(history, separators=(",", ":")))
        print(f"  history: appended new monthly snapshot -> {history_path.name}")
    else:
        print(f"  history: no new Zillow month yet, {history_path.name} unchanged")


def main():
    DATA_DIR.mkdir(parents=True, exist_ok=True)

    county_rows = fetch_csv(COUNTY_CSV_URL)
    county_cols = date_columns(county_rows)
    county_data = build_county_data(county_rows, county_cols)

    city_rows = fetch_csv(CITY_CSV_URL)
    city_cols = date_columns(city_rows)

    if not CITY_COORDS_PATH.exists():
        print(
            f"WARNING: {CITY_COORDS_PATH} not found. Run "
            "scripts/build_city_coords.py once first. Writing empty city list."
        )
        coords = {}
    else:
        coords = json.loads(CITY_COORDS_PATH.read_text())

    city_data = build_city_data(city_rows, city_cols, coords) if coords else []

    now = datetime.utcnow().isoformat() + "Z"

    county_out = {
        "updated": now,
        "source": "Zillow Research ZHVI (https://www.zillow.com/research/data/)",
        "count": len(county_data),
        "counties": county_data,
    }
    city_out = {
        "updated": now,
        "source": "Zillow Research ZHVI (https://www.zillow.com/research/data/)",
        "count": len(city_data),
        "cities": city_data,
    }

    (DATA_DIR / "county_prices.json").write_text(json.dumps(county_out, separators=(",", ":")))
    (DATA_DIR / "city_prices.json").write_text(json.dumps(city_out, separators=(",", ":")))

    print(f"Wrote {len(county_data)} counties and {len(city_data)} cities.")

    # Archive a time-series point per region (skipped automatically if this
    # month's Zillow numbers haven't changed since the last recorded point).
    update_history(HISTORY_DIR / "county_history.json", county_data)
    city_keyed = {f"{d['state']}|{normalize(d['name'])}": d for d in city_data}
    update_history(HISTORY_DIR / "city_history.json", city_keyed)


if __name__ == "__main__":
    sys.exit(main())
