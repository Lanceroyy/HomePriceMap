// Shared helpers for counties.js and cities.js

// --- Analytics ------------------------------------------------------------
// Thin wrapper so nothing here depends on gtag actually being present. Ad
// blockers stop the GA script from loading for a meaningful share of
// visitors, and an uncaught ReferenceError in a click handler would break
// the affiliate link itself -- losing real revenue to collect a stat.
function trackEvent(name, params) {
  try {
    if (typeof gtag === "function") gtag("event", name, params || {});
  } catch (e) {
    /* analytics must never break the page */
  }
}

// Delegated listener: the info panel is re-rendered via innerHTML on every
// hover/click, so per-element listeners would be discarded constantly. One
// document-level listener survives all of it.
document.addEventListener("click", function (e) {
  const cta = e.target.closest && e.target.closest(".mortgage-cta");
  if (!cta) return;
  trackEvent("affiliate_click", {
    affiliate: cta.dataset.affiliate || "unknown",
    region: cta.dataset.region || "",
    region_value: Number(cta.dataset.value) || 0,
  });
});

// Fixed dollar-value breakpoints, NOT quantile/equal-count breaks. Home
// prices are heavily right-skewed (a long tail of very expensive counties
// and cities), so an equal-count scheme puts the entire top ~10% of the
// country -- everywhere from ~$450K up to Nantucket's $3.09M -- into a
// single color. Fixed breaks give the upper half of the market the same
// number of color buckets as the lower half, so high-cost areas are
// actually distinguishable from each other instead of all reading as
// "the expensive color."
// Nine bands rather than twelve. Crowding twelve steps into one ramp forced
// them close enough together that adjacent bands collided for colour-blind
// viewers; fewer, better-separated bands are both safer and easier to read
// off a legend. Three bands still sit above $600k so expensive counties stay
// distinguishable from one another.
const PRICE_BREAKS = [130000, 180000, 240000, 310000, 420000, 600000, 900000, 1500000];

// Plasma, sampled at hand-picked stops rather than evenly. The original
// blue-to-red rainbow put two adjacent steps at deltaE 1.4 under simulated
// protanopia -- literally the same colour to those viewers. These nine stops
// were chosen by searching the plasma range for the spacing that maximises
// the minimum separation under both deuteranopia and protanopia: the worst
// adjacent pair measures deltaE 13.7, comfortably distinguishable. Lightness
// also rises monotonically across the ramp, so "darker = cheaper" still holds
// in greyscale or on a poorly calibrated screen.
const COLOR_RAMP = ["#0d0887", "#a11b9b", "#bf3984", "#cc4778", "#d8576b", "#e97158", "#f68d45", "#fdbb2c", "#f0f921"];

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

// data-* attributes feed the delegated click handler above, so each affiliate
// click is attributed to the specific region and price that produced it.
function affiliateCta(regionLabel, value) {
  const attrs = `data-region="${escapeAttr(regionLabel)}" data-value="${value == null ? "" : Math.round(value)}"`;
  if (AFFILIATE_URL) {
    return `<a class="mortgage-cta" data-affiliate="mortgage" ${attrs} href="${AFFILIATE_URL}" target="_blank" rel="noopener sponsored">${AFFILIATE_LABEL} in ${regionLabel} &rarr;</a>`;
  }
  if (HOUSEPLANS_URL && value != null && value <= HOUSEPLANS_MAX_VALUE) {
    return `<a class="mortgage-cta" data-affiliate="house-plans" ${attrs} href="${HOUSEPLANS_URL}" target="_blank" rel="noopener sponsored">${HOUSEPLANS_LABEL} &rarr;</a>`;
  }
  return "";
}

// Region names come from JSON data, not user input, but they do contain
// quotes and ampersands in places -- escape before interpolating into an
// attribute so the markup can't be broken by a stray character.
function escapeAttr(s) {
  return String(s == null ? "" : s)
    .replace(/&/g, "&amp;")
    .replace(/"/g, "&quot;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;");
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
  // Warm grey for counties Zillow doesn't price. Measured at deltaE 28+ from
  // every cividis step under simulated colour blindness, so "no data" never
  // reads as a price band.
  if (value == null) return "#3a352e";
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

// `track` is the interaction that produced this panel ("map_click",
// "search", "deep_link"). Left undefined for hover previews on purpose --
// hovering across a choropleth fires constantly and would bury the
// deliberate selections in noise (and blow through GA's event quota).
function showInfo(el, { title, value, yoy, crime, income, track }) {
  const cls = yoy > 0 ? "up" : yoy < 0 ? "down" : "";
  el.innerHTML = `
    <div class="region-name">${title}</div>
    <div class="region-value">${fmtMoney(value)}</div>
    <div class="region-yoy ${cls}">${fmtYoy(yoy)} year-over-year</div>
    ${incomeBlock(income, value)}
    ${crimeBlock(crime)}
    ${affiliateCta(title, value)}
  `;

  if (track) {
    trackEvent("region_select", {
      region: title,
      region_value: value == null ? 0 : Math.round(value),
      method: track,
      has_crime_data: !!crime,
      has_income_data: !!income,
    });
  }
}
