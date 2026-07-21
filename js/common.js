// Shared helpers for counties.js and cities.js

// Fixed dollar-value breakpoints, NOT quantile/equal-count breaks. Home
// prices are heavily right-skewed (a long tail of very expensive counties
// and cities), so an equal-count scheme puts the entire top ~10% of the
// country -- everywhere from ~$450K up to Nantucket's $3.09M -- into a
// single color. Fixed breaks give the upper half of the market the same
// number of color buckets as the lower half, so high-cost areas are
// actually distinguishable from each other instead of all reading as
// "the expensive color."
const PRICE_BREAKS = [125000, 175000, 225000, 275000, 350000, 450000, 600000, 800000, 1100000, 1600000, 2500000];
const COLOR_RAMP = ["#16324f", "#1a3a5c", "#1e5f8a", "#2389b0", "#2fa8a0", "#4fcf8b", "#a8e063", "#f4d35e", "#f4a259", "#ef6461", "#d63d5e", "#8b1e3f"];

// --- Mortgage-rate affiliate CTA -----------------------------------------
// Set AFFILIATE_URL once you're approved for an affiliate program (e.g.
// LendingTree, Credible, Rocket Mortgage). Leave it null and the CTA simply
// won't render anywhere -- no broken/placeholder links go live by accident.
// Takes priority over the house-plans CTA below when active, since a
// mortgage-rate check is relevant everywhere, not just affordable markets.
const AFFILIATE_URL = null; // e.g. "https://www.lendingtree.com/your-affiliate-id"
const AFFILIATE_LABEL = "Check today's mortgage rates";

// --- House-plans affiliate CTA (Architectural Designs, via CJ) -----------
// Only shown on affordable markets (median value at or below the
// threshold) -- "browse house plans to build" is a coherent thought for
// someone looking at a cheap county, but not for someone looking at
// Nantucket. Threshold is roughly the point where a meaningful majority of
// U.S. counties fall below it (national county median is ~$234K).
const HOUSEPLANS_URL = "https://www.anrdoezrs.net/click-101818616-15735175";
const HOUSEPLANS_LABEL = "Building instead? Browse house plans";
const HOUSEPLANS_MAX_VALUE = 300000;

function affiliateCta(regionLabel, value) {
  if (AFFILIATE_URL) {
    return `<a class="mortgage-cta" href="${AFFILIATE_URL}" target="_blank" rel="noopener sponsored">${AFFILIATE_LABEL} in ${regionLabel} &rarr;</a>`;
  }
  if (HOUSEPLANS_URL && value != null && value <= HOUSEPLANS_MAX_VALUE) {
    return `<a class="mortgage-cta" href="${HOUSEPLANS_URL}" target="_blank" rel="noopener sponsored">${HOUSEPLANS_LABEL} &rarr;</a>`;
  }
  return "";
}

// Mirrors normalize_place() in scripts/process_crime_data.py / fetch_data.py
// so city names produce the same lookup key client-side as the crime/history
// JSON files were keyed with server-side.
const PLACE_SUFFIX_RE = /\s+(city|town|village|township|CDP|borough|municipality)\s*$/i;
function normalizePlace(name) {
  if (!name) return "";
  return name.replace(PLACE_SUFFIX_RE, "").trim().toLowerCase().replace(/[^a-z0-9]+/g, "");
}

function fmtRate(v) {
  if (v == null) return "n/a";
  return Math.round(v).toLocaleString();
}

function crimeBlock(crime) {
  if (!crime) return "";
  const coverage = crime.cities_matched
    ? `<div class="crime-coverage">Based on ${crime.cities_matched} reporting ${crime.cities_matched === 1 ? "city" : "cities"} in this county</div>`
    : "";
  return `
    <div class="crime-block">
      <div class="crime-title">Crime (${crime.year}, per 100k residents)</div>
      <div class="crime-row"><span>Violent crime</span><b>${fmtRate(crime.violent_crime_rate)}</b></div>
      <div class="crime-row"><span>Property crime</span><b>${fmtRate(crime.property_crime_rate)}</b></div>
      ${coverage}
    </div>
  `;
}

function fmtMoney(v) {
  if (v == null) return "n/a";
  return "$" + Math.round(v).toLocaleString();
}

// Price-to-income is computed here at render time rather than stored in
// income_data_*.json, because home prices refresh daily while the Census
// income figures refresh once a year -- a stored ratio would drift out of
// date the moment Zillow publishes new numbers.
function incomeBlock(income, value) {
  if (!income || !income.median_household_income) return "";
  const inc = income.median_household_income;
  const incLabel = income.top_coded ? fmtMoney(inc) + "+" : fmtMoney(inc);

  let ratioRow = "";
  if (value != null) {
    const ratio = value / inc;
    // Rough rule of thumb in housing research: around 3x income or below is
    // considered manageable, 5x and up is severely stretched.
    const cls = ratio >= 5 ? "ratio-high" : ratio <= 3 ? "ratio-low" : "";
    // When income is top-coded the true figure is at least that much, so the
    // real ratio can only be lower than what we can compute -- hence "≤".
    const prefix = income.top_coded ? "≤&nbsp;" : "";
    ratioRow = `<div class="income-row"><span>Price to income</span><b class="${cls}">${prefix}${ratio.toFixed(1)}&times;</b></div>`;
  }

  return `
    <div class="income-block">
      <div class="income-title">Income &amp; affordability</div>
      <div class="income-row"><span>Median household income</span><b>${incLabel}</b></div>
      ${ratioRow}
    </div>
  `;
}

function fmtYoy(v) {
  if (v == null) return "n/a";
  const sign = v > 0 ? "+" : "";
  return `${sign}${v.toFixed(1)}%`;
}

// Build quantile-based breakpoints from an array of numeric values.
function quantileBreaks(values, n) {
  const sorted = values.filter(v => v != null).sort((a, b) => a - b);
  const breaks = [];
  for (let i = 1; i < n; i++) {
    const idx = Math.floor((i / n) * sorted.length);
    breaks.push(sorted[Math.min(idx, sorted.length - 1)]);
  }
  return breaks;
}

function colorForValue(value, breaks) {
  if (value == null) return "#3a4452";
  for (let i = 0; i < breaks.length; i++) {
    if (value <= breaks[i]) return COLOR_RAMP[i];
  }
  return COLOR_RAMP[COLOR_RAMP.length - 1];
}

// The legend is always expanded on desktop. On mobile (see the max-width:700px
// block in style.css) the rows collapse behind the title, which doubles as a
// tap target -- 12 price bands is a lot of screen to give up permanently on a
// phone, and the info box already reports exact values for whatever you tap.
function renderLegend(el, breaks) {
  const edges = [0, ...breaks, Infinity];
  let rows = "";
  for (let i = 0; i < edges.length - 1; i++) {
    const lo = edges[i] === 0 ? "$0" : fmtMoney(edges[i]);
    const hi = edges[i + 1] === Infinity ? "+" : fmtMoney(edges[i + 1]);
    rows += `<div class="row"><span class="swatch" style="background:${COLOR_RAMP[i]}"></span>${lo} – ${hi}</div>`;
  }
  el.innerHTML = `
    <button type="button" class="legend-toggle" aria-expanded="false">Median price<span class="legend-caret"></span></button>
    <div class="legend-body">${rows}</div>
  `;
  const btn = el.querySelector(".legend-toggle");
  btn.addEventListener("click", () => {
    const isOpen = el.classList.toggle("open");
    btn.setAttribute("aria-expanded", isOpen ? "true" : "false");
  });
}

function showInfo(el, { title, value, yoy, crime, income }) {
  const cls = yoy > 0 ? "up" : yoy < 0 ? "down" : "";
  el.innerHTML = `
    <div class="region-name">${title}</div>
    <div class="region-value">${fmtMoney(value)}</div>
    <div class="region-yoy ${cls}">${fmtYoy(yoy)} year-over-year</div>
    ${incomeBlock(income, value)}
    ${crimeBlock(crime)}
    ${affiliateCta(title, value)}
  `;
}
