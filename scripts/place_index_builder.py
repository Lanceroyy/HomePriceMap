#!/usr/bin/env python3
"""Build the compact place catalog used by search and comparison.

The catalog deliberately contains only URLs that have static profile pages:
all priced counties and the same crime/population-qualified cities selected by
city_pages_builder.py. It joins the small set of facts needed by the browser so
visitors never have to download all source datasets to compare two places.
"""
import argparse
import json
from pathlib import Path

from city_identity import city_candidates_by_key, match_city_source
from city_pages_builder import MIN_POPULATION, slugify


ROOT = Path(__file__).resolve().parent.parent
DEFAULT_DATA_DIR = ROOT / "data"
DEFAULT_OUTPUT = DEFAULT_DATA_DIR / "place_index.json"


def _read_required(path):
    if not path.exists():
        raise FileNotFoundError("Required data file not found: {}".format(path))
    return json.loads(path.read_text(encoding="utf-8"))


def _read_section(path, section):
    if not path.exists():
        return {}
    payload = json.loads(path.read_text(encoding="utf-8"))
    value = payload.get(section, {})
    return value if isinstance(value, dict) else {}


def _ratio(value, income):
    if not isinstance(value, (int, float)) or not isinstance(income, (int, float)) or income <= 0:
        return None
    return round(value / income, 2)


def _county_place(fips, record, income, crime):
    income_value = income.get("median_household_income") if income else None
    return {
        "id": "county:{}".format(fips),
        "type": "county",
        "name": record["name"],
        "state": record["state"],
        "county": None,
        "url": "/counties/{}-{}.html".format(record["state"].lower(), slugify(record["name"])),
        "value": record.get("value"),
        "yoy_pct": record.get("yoy_pct"),
        "as_of": record.get("as_of"),
        "income": income_value,
        "income_top_coded": bool(income.get("top_coded")) if income else False,
        "price_to_income": _ratio(record.get("value"), income_value),
        "violent_crime_rate": crime.get("violent_crime_rate") if crime else None,
        "property_crime_rate": crime.get("property_crime_rate") if crime else None,
        "population": None,
        "population_covered": crime.get("population_covered") if crime else None,
        "cities_matched": crime.get("cities_matched") if crime else None,
    }


def _city_place(record, crime, income):
    income_value = income.get("median_household_income") if income else None
    return {
        "id": "city:{}-{}".format(record["state"].lower(), slugify(record["name"])),
        "type": "city",
        "name": record["name"],
        "state": record["state"],
        "county": record.get("county"),
        "url": "/cities/{}-{}.html".format(record["state"].lower(), slugify(record["name"])),
        "value": record.get("value"),
        "yoy_pct": record.get("yoy_pct"),
        "as_of": record.get("as_of"),
        "income": income_value,
        "income_top_coded": bool(income.get("top_coded")) if income else False,
        "price_to_income": _ratio(record.get("value"), income_value),
        "violent_crime_rate": crime.get("violent_crime_rate"),
        "property_crime_rate": crime.get("property_crime_rate"),
        "population": crime.get("population"),
        "population_covered": None,
        "cities_matched": None,
    }


def build_catalog(data_dir=DEFAULT_DATA_DIR):
    """Return a deterministic catalog from the datasets under *data_dir*."""
    data_dir = Path(data_dir)
    county_payload = _read_required(data_dir / "county_prices.json")
    city_payload = _read_required(data_dir / "city_prices.json")
    city_candidates = city_candidates_by_key(city_payload.get("cities", []))

    county_income = _read_section(data_dir / "income_data_county.json", "counties")
    city_income = _read_section(data_dir / "income_data_city.json", "cities")
    county_crime = _read_section(data_dir / "crime_data_county.json", "counties")
    city_crime = _read_section(data_dir / "crime_data_city.json", "cities")

    places = []
    for fips, record in sorted(county_payload.get("counties", {}).items()):
        if not record.get("name") or not record.get("state") or record.get("value") is None:
            continue
        places.append(
            _county_place(
                fips,
                record,
                county_income.get(fips),
                county_crime.get(fips),
            )
        )

    # Match city_pages_builder exactly: eligible cities are ranked by value
    # within state, then the first URL slug wins when Zillow contains a
    # duplicate/punctuation variant.
    eligible_by_state = {}
    for record in city_payload.get("cities", []):
        if not record.get("name") or not record.get("state") or record.get("value") is None:
            continue
        crime = match_city_source(record, city_crime, city_candidates)
        if not crime or (crime.get("population") or 0) < MIN_POPULATION:
            continue
        income = match_city_source(record, city_income, city_candidates, allow_city_suffix=True)
        eligible_by_state.setdefault(record["state"], []).append((record, crime, income))

    seen_slugs = set()
    for state in sorted(eligible_by_state):
        ranked = sorted(eligible_by_state[state], key=lambda item: item[0]["value"], reverse=True)
        for record, crime, income in ranked:
            profile_slug = "{}-{}".format(state.lower(), slugify(record["name"]))
            if profile_slug in seen_slugs:
                continue
            seen_slugs.add(profile_slug)
            places.append(_city_place(record, crime, income))

    places.sort(key=lambda place: (
        place["name"].casefold(), place["state"], place["type"], place["id"]
    ))
    updated = county_payload.get("updated") or city_payload.get("updated")
    return {"updated": updated, "count": len(places), "places": places}


def write_catalog(catalog, output_path=DEFAULT_OUTPUT):
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(catalog, ensure_ascii=False, separators=(",", ":")) + "\n",
        encoding="utf-8",
    )


def build_summary(data_dir=DEFAULT_DATA_DIR):
    """Homepage coverage counters should not require downloading the price feeds.

    Count priced source records, not published profiles: the interactive map
    covers more cities than qualify for an individual page.
    """
    data_dir = Path(data_dir)
    counties = _read_required(data_dir / "county_prices.json")
    cities = _read_required(data_dir / "city_prices.json")
    return {
        "county_count": sum(r.get("value") is not None for r in counties.get("counties", {}).values()),
        "city_count": sum(r.get("value") is not None for r in cities.get("cities", [])),
        "updated": counties.get("updated") or cities.get("updated"),
    }


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data-dir", type=Path, default=DEFAULT_DATA_DIR)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--summary-output", type=Path,
                        help="Also write compact homepage stats to this explicit path")
    args = parser.parse_args(argv)

    catalog = build_catalog(args.data_dir)
    write_catalog(catalog, args.output)
    if args.summary_output:
        write_catalog(build_summary(args.data_dir), args.summary_output)
    print("Generated {} with {:,} published places.".format(args.output, catalog["count"]))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
