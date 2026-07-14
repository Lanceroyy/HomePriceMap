const map = L.map("map", { zoomControl: true, minZoom: 3, maxZoom: 14 }).setView([39.5, -98.35], 4);

L.tileLayer("https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png", {
  attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors &copy; <a href="https://carto.com/attributions">CARTO</a>',
  subdomains: "abcd",
  maxZoom: 19,
}).addTo(map);

const infoBox = document.getElementById("infoBox");
const legendEl = document.getElementById("legend");
const searchBox = document.getElementById("searchBox");
const cityListEl = document.getElementById("cityList");

const markerByKey = {};
let crimeByCityKey = {};

Promise.all([
  fetch("data/city_prices.json").then(r => r.json()),
  fetch("data/crime_data_city.json").then(r => r.ok ? r.json() : null).catch(() => null),
])
  .then(([priceData, crimeData]) => {
    if (crimeData) crimeByCityKey = crimeData.cities;

    const cities = priceData.cities;
    const breaks = PRICE_BREAKS;
    renderLegend(legendEl, breaks);

    const cluster = L.layerGroup().addTo(map);

    cities.forEach(rec => {
      const key = `${rec.name}, ${rec.state}`;
      const crimeKey = `${rec.state}|${normalizePlace(rec.name)}`;
      const radius = 4 + Math.min(10, Math.sqrt(rec.value) / 120);
      const marker = L.circleMarker([rec.lat, rec.lon], {
        radius,
        fillColor: colorForValue(rec.value, breaks),
        fillOpacity: 0.85,
        color: "#0f1419",
        weight: 1,
      });

      marker.bindTooltip(`${key}<br><b>${fmtMoney(rec.value)}</b>`, { sticky: true });
      marker.on("click", () => {
        map.setView([rec.lat, rec.lon], Math.max(map.getZoom(), 9));
        showInfo(infoBox, { title: key, value: rec.value, yoy: rec.yoy_pct, crime: crimeByCityKey[crimeKey] });
      });

      marker.addTo(cluster);
      markerByKey[key] = { marker, rec, crimeKey };
    });

    const names = Object.keys(markerByKey).sort();
    cityListEl.innerHTML = names.map(n => `<option value="${n}"></option>`).join("");

    searchBox.addEventListener("change", () => {
      const hit = markerByKey[searchBox.value];
      if (hit) {
        map.setView([hit.rec.lat, hit.rec.lon], 10);
        showInfo(infoBox, { title: searchBox.value, value: hit.rec.value, yoy: hit.rec.yoy_pct, crime: crimeByCityKey[hit.crimeKey] });
        hit.marker.openTooltip();
      }
    });
  })
  .catch(err => {
    console.error(err);
    infoBox.innerHTML = `<div class="placeholder">Couldn't load map data. Check your connection and try again.</div>`;
  });
