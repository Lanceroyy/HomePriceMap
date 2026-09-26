(function () {
  "use strict";

  // FBI/Census keys drop a legal suffix, so one key can contain two places.
  // Treat that key as a search bucket, never as proof of identity.
  const suffix = /\s+(city|town|village|township|CDP|borough|municipality)\s*$/i;

  function fullName(name) {
    return String(name || "")
      .normalize("NFKD")
      .replace(/[\u0300-\u036f]/g, "")
      .replace(/[^\x00-\x7F]/g, "")
      .toLowerCase()
      .replace(/[^a-z0-9]+/g, "");
  }

  function legacyKey(city) {
    const base = String(city.name || "").replace(suffix, "").trim().toLowerCase();
    return `${city.state}|${base.replace(/[^a-z0-9]+/g, "")}`;
  }

  function groups(cities) {
    const index = new Map();
    cities.forEach((city) => {
      if (!city.name || !city.state) return;
      const key = legacyKey(city);
      if (!index.has(key)) index.set(key, []);
      index.get(key).push(city);
    });
    return index;
  }

  function matchedSource(city, sourceByKey, candidates, allowCitySuffix) {
    const key = legacyKey(city);
    const bucket = sourceByKey && sourceByKey[key];
    const sources = Array.isArray(bucket) ? bucket : [bucket];
    const group = candidates.get(key) || [];
    const selected = sources.filter((source) => {
      if (!source || !source.name || (source.state && source.state !== city.state)) return false;
      const sourceName = fullName(source.name);
      let matches = group.filter((candidate) => fullName(candidate.name) === sourceName);
      if (!matches.length && allowCitySuffix && /\s+city\s*$/i.test(source.name)) {
        const shortName = fullName(source.name.replace(/\s+city\s*$/i, ""));
        matches = group.filter((candidate) => fullName(candidate.name) === shortName);
      }
      return matches.length === 1 && matches[0] === city;
    });
    return selected.length === 1 ? selected[0] : null;
  }

  function hasCoordinates(city) {
    return Number.isFinite(city.lat) && Number.isFinite(city.lon);
  }

  window.CityIdentity = { groups, matchedSource, hasCoordinates };
})();
