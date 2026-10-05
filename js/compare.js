(function () {
  "use strict";

  const MAX_PLACES = 3;
  const selected = [];
  let placesById = new Map();

  const searchInput = document.getElementById("compareSearch");
  const searchResults = document.getElementById("compareSearchResults");
  const grid = document.getElementById("comparisonGrid");
  const emptyState = document.getElementById("comparisonEmpty");
  const errorState = document.getElementById("comparisonError");
  const limitMessage = document.getElementById("comparisonLimit");
  const copyButton = document.getElementById("copyComparison");
  const copyStatus = document.getElementById("copyStatus");

  function formatMoney(value) {
    return value == null ? "n/a" : `$${Math.round(value).toLocaleString()}`;
  }

  function formatPercent(value) {
    if (value == null) return "n/a";
    return `${value > 0 ? "+" : ""}${Number(value).toFixed(1)}%`;
  }

  function formatRate(value) {
    return value == null ? "n/a" : Math.round(value).toLocaleString();
  }

  function trackComparison(name, params) {
    if (typeof window.trackEvent === "function") window.trackEvent(name, params || {});
  }

  function idsFromHash() {
    if (!window.location.hash.startsWith("#places=")) return [];
    return window.location.hash
      .slice("#places=".length)
      .split(",")
      .map((part) => {
        try { return decodeURIComponent(part); } catch (error) { return ""; }
      })
      .filter(Boolean)
      .slice(0, MAX_PLACES);
  }

  function syncHash() {
    const fragment = selected.length
      ? `#places=${selected.map((place) => encodeURIComponent(place.id)).join(",")}`
      : "";
    history.replaceState(null, "", `${window.location.pathname}${fragment}`);
  }

  function metric(label, value, note) {
    const row = document.createElement("div");
    row.className = "comparison-metric";
    const term = document.createElement("dt");
    term.textContent = label;
    const description = document.createElement("dd");
    description.textContent = value;
    row.append(term, description);
    if (note) {
      const small = document.createElement("small");
      small.textContent = note;
      row.appendChild(small);
    }
    return row;
  }

  function makeCard(place) {
    const article = document.createElement("article");
    article.className = "comparison-card";
    article.dataset.placeId = place.id;

    const type = document.createElement("p");
    type.className = "comparison-type";
    type.textContent = place.type === "county" ? "County" : "City";
    const heading = document.createElement("h2");
    const link = document.createElement("a");
    link.href = place.url;
    link.textContent = `${place.name}, ${place.state}`;
    heading.appendChild(link);
    const location = document.createElement("p");
    location.className = "comparison-location";
    location.textContent = place.county || (place.type === "county" ? "County profile" : "City profile");

    const metrics = document.createElement("dl");
    metrics.className = "comparison-metrics";
    metrics.appendChild(metric("Typical home value", formatMoney(place.value)));
    metrics.appendChild(metric("Year-over-year", formatPercent(place.yoy_pct)));
    const ratio = place.price_to_income == null
      ? "n/a"
      : `${place.income_top_coded ? "≤" : ""}${Number(place.price_to_income).toFixed(1)}×`;
    metrics.appendChild(metric("Price to income", ratio, place.income == null ? "Income data unavailable" : `Income ${formatMoney(place.income)}${place.income_top_coded ? "+" : ""}`));
    metrics.appendChild(metric("Violent crime", formatRate(place.violent_crime_rate), "per 100,000 residents"));
    metrics.appendChild(metric("Property crime", formatRate(place.property_crime_rate), "per 100,000 residents"));
    if (place.population != null) {
      metrics.appendChild(metric("Population", Math.round(place.population).toLocaleString(), "FBI reporting population"));
    } else if (place.population_covered != null) {
      metrics.appendChild(metric("Crime coverage", Math.round(place.population_covered).toLocaleString(), `${place.cities_matched || 0} reporting cities`));
    }

    const remove = document.createElement("button");
    remove.className = "comparison-remove";
    remove.type = "button";
    remove.textContent = "Remove";
    remove.setAttribute("aria-label", `Remove ${place.name}, ${place.state} from comparison`);
    remove.addEventListener("click", () => removePlace(place.id));

    article.append(type, heading, location, metrics, remove);
    return article;
  }

  function render() {
    copyStatus.textContent = "";
    grid.replaceChildren(...selected.map(makeCard));
    emptyState.hidden = selected.length !== 0;
    grid.hidden = selected.length === 0;
    limitMessage.hidden = selected.length < MAX_PLACES;
    copyButton.disabled = selected.length < 2;
    syncHash();
  }

  function addPlace(place, shouldTrack) {
    if (!place || selected.some((item) => item.id === place.id)) {
      searchInput.value = "";
      return;
    }
    if (selected.length >= MAX_PLACES) {
      limitMessage.hidden = false;
      return;
    }
    selected.push(place);
    searchInput.value = "";
    render();
    searchInput.focus();
    if (shouldTrack) trackComparison("comparison_add", { place_id: place.id, place_type: place.type });
  }

  function removePlace(id) {
    const index = selected.findIndex((place) => place.id === id);
    if (index === -1) return;
    const removed = selected.splice(index, 1)[0];
    render();
    trackComparison("comparison_remove", { place_id: removed.id, place_type: removed.type });
  }

  async function fallbackCopy(value) {
    const textarea = document.createElement("textarea");
    textarea.value = value;
    textarea.setAttribute("readonly", "");
    textarea.style.position = "fixed";
    textarea.style.opacity = "0";
    document.body.appendChild(textarea);
    textarea.select();
    const copied = document.execCommand("copy");
    textarea.remove();
    if (!copied) throw new Error("Copy command failed");
  }

  async function copyComparison() {
    const url = `${window.location.origin}${window.location.pathname}${window.location.hash}`;
    try {
      if (navigator.clipboard && window.isSecureContext) {
        await navigator.clipboard.writeText(url);
      } else {
        await fallbackCopy(url);
      }
      copyStatus.textContent = "Comparison link copied.";
      trackComparison("comparison_share", { place_count: selected.length });
    } catch (error) {
      copyStatus.textContent = "Copy failed. Select the address in your browser to share it.";
    }
  }

  async function start() {
    try {
      const places = await window.HomePriceSearch.loadCatalog();
      placesById = new Map(places.map((place) => [place.id, place]));
      const restoredIds = [...new Set(idsFromHash())];
      restoredIds.forEach((id) => {
        const place = placesById.get(id);
        if (place && selected.length < MAX_PLACES) selected.push(place);
      });
      errorState.hidden = true;
      render();
    } catch (error) {
      console.error("Failed to initialize comparison", error);
      errorState.hidden = false;
      emptyState.hidden = true;
      searchInput.disabled = true;
      copyButton.disabled = true;
    }
  }

  window.HomePriceSearch.attach(searchInput, searchResults, {
    surface: "comparison",
    onSelect: (place) => addPlace(place, true),
  });
  copyButton.addEventListener("click", copyComparison);
  window.addEventListener("hashchange", () => {
    if (!placesById.size) return;
    selected.splice(0, selected.length);
    [...new Set(idsFromHash())].forEach((id) => {
      const place = placesById.get(id);
      if (place && selected.length < MAX_PLACES) selected.push(place);
    });
    render();
  });
  start();
})();
