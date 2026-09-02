const map = L.map("map", { zoomControl: true, minZoom: 3, maxZoom: 14 }).setView([39.5, -98.35], 4);

L.tileLayer("https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png?key=cb1_2tab_1_882b300870963eb677e951f7", {
  attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors &copy; <a href="https://carto.com/attributions">CARTO</a>',
  subdomains: "abcd",
  maxZoom: 19,
}).addTo(map);

const infoBox = document.getElementById("infoBox");
const legendEl = document.getElementById("legend");
const searchBox = document.getElementById("searchBox");
const cityListEl = document.getElementById("cityList");

const markerBySearchLabel = {};
const markerByCityCounty = {};
const canonicalMarkerByKey = {};
let crimeByCityKey = {};
let incomeByCityKey = {};

function cityProfileUrl(rec, crime, isCanonicalRecord) {
  if (!isCanonicalRecord || !crime || (crime.population || 0) < 5000) return null;
  return `cities/${rec.state.toLowerCase()}-${slugifyRegion(rec.name)}.html`;
}

function cityShareUrl(key, county) {
  const url = new URL(window.location.href);
  url.search = "";
  url.searchParams.set("city", key);
  if (county) url.searchParams.set("county", county);
  return url.href;
}

function setCityUrl(key, county) {
  const url = new URL(window.location.href);
  url.search = "";
  if (key) url.searchParams.set("city", key);
  if (county) url.searchParams.set("county", county);
  window.history.replaceState(null, "", url.pathname + url.search + url.hash);
}

Promise.all([
  fetch("data/city_prices.json").then(r => r.json()),
  fetch("data/crime_data_city.json").then(r => r.ok ? r.json() : null).catch(() => null),
  fetch("data/income_data_city.json").then(r => r.ok ? r.json() : null).catch(() => null),
])
  .then(([priceData, crimeData, incomeData]) => {
    if (crimeData) crimeByCityKey = crimeData.cities;
    if (incomeData) incomeByCityKey = incomeData.cities;

    const cities = priceData.cities;
    const breaks = PRICE_BREAKS;
    renderLegend(legendEl, breaks);

    const cluster = L.layerGroup().addTo(map);

    // Zillow occasionally has two same-named places in one state. Standalone
    // pages intentionally keep only the highest-priced record for each slug,
    // so make that same record the canonical target for legacy ?city= links.
    // County-qualified links preserve access to every individual map marker.
    const cityCountByKey = {};
    const canonicalRecordByKey = {};
    cities.forEach(rec => {
      const key = `${rec.name}, ${rec.state}`;
      cityCountByKey[key] = (cityCountByKey[key] || 0) + 1;
      const current = canonicalRecordByKey[key];
      if (!current || (rec.value ?? -Infinity) > (current.value ?? -Infinity)) {
        canonicalRecordByKey[key] = rec;
      }
    });

    function selectCity(hit, method) {
      const crime = crimeByCityKey[hit.crimeKey];
      const countyParam = hit.isDuplicate ? hit.rec.county : null;
      setCityUrl(hit.key, countyParam);
      showInfo(infoBox, {
        title: hit.label, value: hit.rec.value, yoy: hit.rec.yoy_pct,
        crime, income: incomeByCityKey[hit.crimeKey], track: method,
        regionType: "city",
        profileUrl: cityProfileUrl(hit.rec, crime, canonicalRecordByKey[hit.key] === hit.rec),
        shareUrl: cityShareUrl(hit.key, countyParam),
      });
    }

    cities.forEach(rec => {
      const key = `${rec.name}, ${rec.state}`;
      const isDuplicate = cityCountByKey[key] > 1;
      const label = isDuplicate ? `${key} (${rec.county})` : key;
      const crimeKey = `${rec.state}|${normalizePlace(rec.name)}`;
      const radius = 4 + Math.min(10, Math.sqrt(rec.value) / 120);
      const marker = L.circleMarker([rec.lat, rec.lon], {
        radius,
        fillColor: colorForValue(rec.value, breaks),
        fillOpacity: 0.85,
        color: "#0f1419",
        weight: 1,
      });

      marker.bindTooltip(`${label}<br><b>${fmtMoney(rec.value)}</b>`, { sticky: true });
      marker.on("click", () => {
        map.setView([rec.lat, rec.lon], Math.max(map.getZoom(), 9));
        selectCity({ marker, rec, crimeKey, key, label, isDuplicate }, "map_click");
      });

      marker.addTo(cluster);
      const hit = { marker, rec, crimeKey, key, label, isDuplicate };
      markerBySearchLabel[label] = hit;
      markerByCityCounty[`${key}|${rec.county}`] = hit;
      if (canonicalRecordByKey[key] === rec) canonicalMarkerByKey[key] = hit;
    });

    const names = Object.keys(markerBySearchLabel).sort();
    cityListEl.innerHTML = names.map(n => `<option value="${escapeAttr(n)}"></option>`).join("");

    searchBox.addEventListener("change", () => {
      const hit = markerBySearchLabel[searchBox.value];
      if (hit) {
        map.setView([hit.rec.lat, hit.rec.lon], 10);
        selectCity(hit, "search");
        hit.marker.openTooltip();
      }
    });

    // Shareable city links mirror the county map's ?fips= deep links.
    const params = new URLSearchParams(window.location.search);
    const linkedCity = params.get("city");
    const linkedCounty = params.get("county");
    const linkedHit = linkedCity && (linkedCounty
      ? markerByCityCounty[`${linkedCity}|${linkedCounty}`]
      : canonicalMarkerByKey[linkedCity]);
    if (linkedHit) {
      map.setView([linkedHit.rec.lat, linkedHit.rec.lon], 10);
      selectCity(linkedHit, "deep_link");
      linkedHit.marker.openTooltip();
    }
  })
  .catch(err => {
    console.error(err);
    infoBox.innerHTML = `<div class="placeholder">Couldn't load map data. Check your connection and try again.</div>`;
  });
