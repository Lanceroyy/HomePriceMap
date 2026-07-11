const map = L.map("map", { zoomControl: true, minZoom: 3, maxZoom: 12 }).setView([39.5, -98.35], 4);

L.tileLayer("https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png", {
  attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors &copy; <a href="https://carto.com/attributions">CARTO</a>',
  subdomains: "abcd",
  maxZoom: 19,
}).addTo(map);

const infoBox = document.getElementById("infoBox");
const legendEl = document.getElementById("legend");
const searchBox = document.getElementById("searchBox");
const countyListEl = document.getElementById("countyList");

const layerByKey = {};
const layerByFips = {};

let crimeByFips = {};

Promise.all([
  fetch("data/county_prices.json").then(r => r.json()),
  fetch("https://cdn.jsdelivr.net/npm/us-atlas@3/counties-10m.json").then(r => r.json()),
  fetch("data/crime_data_county.json").then(r => r.ok ? r.json() : null).catch(() => null),
]).then(([priceData, topo, crimeData]) => {
  const counties = priceData.counties;
  if (crimeData) crimeByFips = crimeData.counties;
  const values = Object.values(counties).map(c => c.value);
  const breaks = quantileBreaks(values, COLOR_RAMP.length);
  renderLegend(legendEl, breaks);

  const geojson = topojson.feature(topo, topo.objects.counties);

  const layer = L.geoJSON(geojson, {
    style: feature => {
      const fips = String(feature.id).padStart(5, "0");
      const rec = counties[fips];
      return {
        fillColor: colorForValue(rec ? rec.value : null, breaks),
        fillOpacity: 0.85,
        color: "#0f1419",
        weight: 0.5,
      };
    },
    onEachFeature: (feature, lyr) => {
      const fips = String(feature.id).padStart(5, "0");
      const rec = counties[fips];
      if (!rec) return;

      const key = `${rec.name}, ${rec.state}`;
      layerByKey[key] = lyr;
      layerByFips[fips] = lyr;

      lyr.bindTooltip(`${rec.name}, ${rec.state}<br><b>${fmtMoney(rec.value)}</b>`, { sticky: true });

      lyr.on("mouseover", () => {
        lyr.setStyle({ weight: 2, color: "#ffffff" });
        showInfo(infoBox, { title: key, value: rec.value, yoy: rec.yoy_pct, crime: crimeByFips[fips] });
      });
      lyr.on("mouseout", () => {
        lyr.setStyle({ weight: 0.5, color: "#0f1419" });
      });
      lyr.on("click", () => {
        map.fitBounds(lyr.getBounds(), { maxZoom: 8 });
        showInfo(infoBox, { title: key, value: rec.value, yoy: rec.yoy_pct, crime: crimeByFips[fips] });
      });
    },
  }).addTo(map);

  // Populate search datalist
  const names = Object.keys(layerByKey).sort();
  countyListEl.innerHTML = names.map(n => `<option value="${n}"></option>`).join("");

  searchBox.addEventListener("change", () => {
    const lyr = layerByKey[searchBox.value];
    if (lyr) {
      map.fitBounds(lyr.getBounds(), { maxZoom: 8 });
      const fips = Object.keys(counties).find(f => `${counties[f].name}, ${counties[f].state}` === searchBox.value);
      const rec = counties[fips];
      if (rec) showInfo(infoBox, { title: searchBox.value, value: rec.value, yoy: rec.yoy_pct, crime: crimeByFips[fips] });
    }
  });

  // Deep link support: /counties.html?fips=06037 flies to and highlights that county.
  // Used by the SEO county pages' "View on interactive map" links.
  const params = new URLSearchParams(window.location.search);
  const linkedFips = params.get("fips");
  if (linkedFips && layerByFips[linkedFips]) {
    const lyr = layerByFips[linkedFips];
    const rec = counties[linkedFips];
    map.fitBounds(lyr.getBounds(), { maxZoom: 8 });
    lyr.setStyle({ weight: 3, color: "#ffffff" });
    if (rec) showInfo(infoBox, { title: `${rec.name}, ${rec.state}`, value: rec.value, yoy: rec.yoy_pct, crime: crimeByFips[linkedFips] });
  }
}).catch(err => {
  console.error(err);
  infoBox.innerHTML = `<div class="placeholder">Couldn't load map data. Check your connection and try again.</div>`;
});
