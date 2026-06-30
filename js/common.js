// Shared helpers for counties.js and cities.js

const COLOR_RAMP = ["#1a3a5c", "#1e5f8a", "#2389b0", "#34b3a8", "#4fcf8b", "#a8e063", "#f4d35e", "#f4a259", "#ef6461", "#d63d5e"];

function fmtMoney(v) {
  if (v == null) return "n/a";
  return "$" + Math.round(v).toLocaleString();
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

function renderLegend(el, breaks) {
  const edges = [0, ...breaks, Infinity];
  let html = "<div style='font-weight:600;margin-bottom:6px;color:var(--text-dim);text-transform:uppercase;font-size:11px;letter-spacing:.04em;'>Median price</div>";
  for (let i = 0; i < edges.length - 1; i++) {
    const lo = edges[i] === 0 ? "$0" : fmtMoney(edges[i]);
    const hi = edges[i + 1] === Infinity ? "+" : fmtMoney(edges[i + 1]);
    html += `<div class="row"><span class="swatch" style="background:${COLOR_RAMP[i]}"></span>${lo} – ${hi}</div>`;
  }
  el.innerHTML = html;
}

function showInfo(el, { title, value, yoy }) {
  const cls = yoy > 0 ? "up" : yoy < 0 ? "down" : "";
  el.innerHTML = `
    <div class="region-name">${title}</div>
    <div class="region-value">${fmtMoney(value)}</div>
    <div class="region-yoy ${cls}">${fmtYoy(yoy)} year-over-year</div>
  `;
}
