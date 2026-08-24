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
  if (cta) {
    trackEvent("affiliate_click", {
      affiliate: cta.dataset.affiliate || "unknown",
      region: cta.dataset.region || "",
      region_type: cta.dataset.regionType || "",
      region_value: Number(cta.dataset.value) || 0,
      selection_method: cta.dataset.selectionMethod || "preview",
    });
    return;
  }

  const profileLink = e.target.closest && e.target.closest(".profile-link");
  if (profileLink) {
    trackEvent("profile_click", {
      region: profileLink.dataset.region || "",
      region_type: profileLink.dataset.regionType || "",
      selection_method: profileLink.dataset.selectionMethod || "preview",
    });
    return;
  }

  const shareButton = e.target.closest && e.target.closest(".share-region");
  if (!shareButton) return;
  shareRegion(shareButton);
});

async function shareRegion(button) {
  const url = button.dataset.shareUrl;
  const title = button.dataset.region || "Home Price Map";
  if (!url) return;

  if (navigator.share) {
    try {
      await navigator.share({ title, text: `Home price data for ${title}`, url });
      trackEvent("share", {
        method: "native",
        content_type: button.dataset.regionType || "region",
        item_id: title,
        selection_method: button.dataset.selectionMethod || "preview",
      });
      return;
    } catch (e) {
      // Closing the native share sheet is an intentional cancellation. Other
      // failures can still recover by copying the URL below.
      if (e && e.name === "AbortError") return;
    }
  }

  try {
    if (!navigator.clipboard || !window.isSecureContext) {
      throw new Error("Clipboard unavailable");
    }
    await navigator.clipboard.writeText(url);
    showShareStatus(button, "Copied!");
    trackEvent("share", {
      method: "clipboard",
      content_type: button.dataset.regionType || "region",
      item_id: title,
      selection_method: button.dataset.selectionMethod || "preview",
    });
  } catch (e) {
    showShareStatus(button, "Copy failed");
  }
}

function showShareStatus(button, text) {
  const original = button.textContent;
  button.textContent = text;
  window.setTimeout(() => { button.textContent = original; }, 1600);
}

// Fixed dollar-value breakpoints, NOT quantile/equal-count breaks. Home
// prices are heavily right-skewed, so an equal-count scheme would drop the
// entire top ~10% of the country -- everywhere from ~$450K to Nantucket's
// $3M+ -- into one bucket, which is exactly the flattening this is meant to
// avoid.
//
// Eight bands. Fewer bands means more colour separation between them, which
// matters because neighbouring counties usually sit one band apart -- if
// adjacent bands look alike, the whole map reads as one flat colour. Breaks
// are chosen so no band holds more than ~22% of counties; the top two are
// deliberately sparse because genuinely expensive counties are rare and the
// point is to make them stand out rather than blend into the bulk.
const PRICE_BREAKS = [150000, 200000, 260000, 340000, 460000, 650000, 1000000];

// Viridis, sampled at stops chosen by search rather than evenly spaced.
//
// The ramp this replaced (ColorBrewer YlOrBr) was safe for colour blindness
// but varied almost entirely in lightness, so its bands were all browns and
// oranges -- and since ~87% of counties fall in the lower half of the range,
// most of the map came out one flat colour. Viridis moves through hue as
// well (deep purple, blue, teal, green, yellow), which is what actually lets
// two neighbouring counties read as different.
//
// Measured against the old ramp: median separation between adjacent bands in
// normal vision 31.2 vs 19.9, and the worst pair under simulated colour
// blindness 16.1 vs 10.5. Better on both counts, not a trade. Lightness still
// rises monotonically, so "darker = cheaper" holds in greyscale or in print.
const COLOR_RAMP = ["#440154", "#414487", "#2f6c8e", "#21918c", "#22a884", "#44bf70", "#7ad151", "#fde725"];

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
function affiliateCta(regionLabel, value, regionType, selectionMethod) {
  const attrs = `data-region="${escapeAttr(regionLabel)}" data-region-type="${escapeAttr(regionType)}" data-selection-method="${escapeAttr(selectionMethod || "preview")}" data-value="${value == null ? "" : Math.round(value)}"`;
  if (AFFILIATE_URL) {
    return `<a class="mortgage-cta" data-affiliate="mortgage" ${attrs} href="${AFFILIATE_URL}" target="_blank" rel="noopener sponsored">${AFFILIATE_LABEL} in ${regionLabel} &rarr;</a>`;
  }
  if (HOUSEPLANS_URL && value != null && value <= HOUSEPLANS_MAX_VALUE) {
    return `<a class="mortgage-cta" data-affiliate="house-plans" ${attrs} href="${HOUSEPLANS_URL}" target="_blank" rel="noopener sponsored">${HOUSEPLANS_LABEL} &rarr;</a>`;
  }
  return "";
}

function regionActions(regionLabel, regionType, profileUrl, shareUrl, selectionMethod) {
  if (!profileUrl && !shareUrl) return "";
  const attrs = `data-region="${escapeAttr(regionLabel)}" data-region-type="${escapeAttr(regionType)}" data-selection-method="${escapeAttr(selectionMethod || "preview")}"`;
  const profile = profileUrl
    ? `<a class="profile-link" ${attrs} href="${escapeAttr(profileUrl)}">View full profile &rarr;</a>`
    : "";
  const share = shareUrl
    ? `<button class="share-region" type="button" ${attrs} data-share-url="${escapeAttr(shareUrl)}" aria-label="Share ${escapeAttr(regionLabel)}" aria-live="polite">Share</button>`
    : "";
  return `<div class="region-actions">${profile}${share}</div>`;
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

// Matches the Python builders' slugify() closely enough that an interactive
// map can link to the generated profile without shipping a second lookup file.
function slugifyRegion(name) {
  return String(name || "")
    .normalize("NFKD")
    .replace(/[\u0300-\u036f]/g, "")
    .toLowerCase()
    .trim()
    .replace(/[^a-z0-9]+/g, "-")
    .replace(/^-+|-+$/g, "");
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
  // Desaturated slate for counties Zillow doesn't price. Measured at deltaE
  // 29 from the nearest ramp step, so "no data" can't read as a price band.
  if (value == null) return "#3d3f42";
  for (let i = 0; i < breaks.length; i++) {
    if (value <= breaks[i]) return COLOR_RAMP[i];
  }
  return COLOR_RAMP[COLOR_RAMP.length - 1];
}

// The legend is always expanded on desktop. On mobile (see the max-width:700px
// block in style.css) the rows collapse behind the title, which doubles as a
// tap target -- eight price bands is still a lot of screen to give up
// permanently on a phone, and the info box already reports exact values for
// whatever you tap.
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
function showInfo(el, { title, value, yoy, crime, income, track, regionType, profileUrl, shareUrl }) {
  const cls = yoy > 0 ? "up" : yoy < 0 ? "down" : "";
  const type = regionType || "region";
  const ctaHtml = affiliateCta(title, value, type, track);
  el.innerHTML = `
    <div class="region-name">${title}</div>
    <div class="region-value">${fmtMoney(value)}</div>
    <div class="region-yoy ${cls}">${fmtYoy(yoy)} year-over-year</div>
    ${incomeBlock(income, value)}
    ${crimeBlock(crime)}
    ${regionActions(title, type, profileUrl, shareUrl, track)}
    ${ctaHtml}
  `;

  if (track) {
    trackEvent("region_select", {
      region: title,
      region_type: type,
      region_value: value == null ? 0 : Math.round(value),
      selection_method: track,
      has_crime_data: !!crime,
      has_income_data: !!income,
    });
    if (ctaHtml) {
      trackEvent("affiliate_cta_view", {
        affiliate: AFFILIATE_URL ? "mortgage" : "house-plans",
        region: title,
        region_type: type,
        region_value: value == null ? 0 : Math.round(value),
        selection_method: track,
      });
    }
  }
}
