"""Conservative joins for city records from sources without a shared ID.

FBI, Census, and older history files use a suffix-stripped state/name key.
That key is only a lookup bucket: it is not a unique place identifier.
"""
import json
import re
import unicodedata
from collections import defaultdict


PLACE_SUFFIXES = re.compile(
    r"\s+(city|town|village|township|CDP|borough|municipality)\s*$", re.IGNORECASE
)


def full_place_name(name):
    folded = unicodedata.normalize("NFKD", name or "").encode("ascii", "ignore").decode("ascii")
    return re.sub(r"[^a-z0-9]+", "", folded.lower())


def legacy_city_key(city):
    base = PLACE_SUFFIXES.sub("", city.get("name") or "")
    # Mirror the already-published JSON keys exactly, including their older
    # ASCII-only handling of accented names.
    normalized = re.sub(r"[^a-z0-9]+", "", base.strip().lower())
    return "{}|{}".format(city.get("state") or "", normalized)


def city_candidates_by_key(cities):
    groups = defaultdict(list)
    for city in cities:
        if city.get("name") and city.get("state"):
            groups[legacy_city_key(city)].append(city)
    return groups


def match_city_source(city, source_by_key, candidates, allow_city_suffix=False):
    """Return a source row only if its name selects this one Zillow place."""
    key = legacy_city_key(city)
    bucket = source_by_key.get(key)
    sources = bucket if isinstance(bucket, list) else [bucket]
    group = candidates.get(key, [])
    selected = []
    for source in sources:
        if not isinstance(source, dict) or not source.get("name"):
            continue
        if source.get("state") and source["state"] != city["state"]:
            continue
        source_name = full_place_name(source["name"])
        matches = [item for item in group if full_place_name(item["name"]) == source_name]
        if not matches and allow_city_suffix and re.search(r"\s+city\s*$", source["name"], re.IGNORECASE):
            short_name = full_place_name(re.sub(r"\s+city\s*$", "", source["name"], flags=re.IGNORECASE))
            matches = [item for item in group if full_place_name(item["name"]) == short_name]
        if len(matches) == 1 and matches[0] is city:
            selected.append(source)
    return selected[0] if len(selected) == 1 else None


def city_history_key(city):
    """A stable identity that retains county and full Zillow place name."""
    parts = [
        str(city.get("state") or "").strip().upper(),
        str(city.get("county") or "").strip().casefold(),
        str(city.get("name") or "").strip().casefold(),
    ]
    return "city:" + json.dumps(parts, ensure_ascii=False, separators=(",", ":"))


def _matches_latest(points, city):
    if not isinstance(points, list) or not points:
        return False
    latest = points[-1]
    return (
        isinstance(latest, dict)
        and latest.get("as_of") == city.get("as_of")
        and latest.get("value") == city.get("value")
    )


def safe_city_history(city, history, candidates):
    """Use old history only when one current city owns it and its endpoint fits."""
    current = history.get(city_history_key(city), [])
    if current:
        if not _matches_latest(current, city):
            return []
        old = history.get(legacy_city_key(city), [])
        if (len(candidates.get(legacy_city_key(city), [])) == 1
                and isinstance(old, list) and old
                and isinstance(old[-1], dict) and isinstance(current[0], dict)
                and old[-1].get("as_of") == current[0].get("as_of")
                and old[-1].get("value") == current[0].get("value")):
            return old[:-1] + current
        return current

    if len(candidates.get(legacy_city_key(city), [])) != 1:
        return []
    old = history.get(legacy_city_key(city), [])
    return old if _matches_latest(old, city) else []
