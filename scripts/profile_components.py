"""Shared static components for generated city and county profiles."""
from datetime import date
from html import escape
import json
import math


def _money(value):
    return "${:,.0f}".format(value)


def _month_label(iso_date):
    parsed = date.fromisoformat(iso_date)
    return parsed.strftime("%b %Y")


def _valid_points(points):
    if not isinstance(points, (list, tuple)):
        return []
    valid = []
    for point in points:
        if not isinstance(point, dict):
            continue
        raw_date = point.get("as_of")
        value = point.get("value")
        if not isinstance(raw_date, str) or not isinstance(value, (int, float)) or isinstance(value, bool):
            continue
        if not math.isfinite(value):
            continue
        try:
            date.fromisoformat(raw_date)
        except ValueError:
            continue
        yoy = point.get("yoy_pct")
        if (
            not isinstance(yoy, (int, float))
            or isinstance(yoy, bool)
            or not math.isfinite(yoy)
        ):
            yoy = None
        valid.append({"as_of": raw_date, "value": float(value), "yoy_pct": yoy})
    return sorted(valid, key=lambda point: point["as_of"])


def load_history_series(path):
    """Return a history-series mapping without making profile builds brittle."""
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError, TypeError):
        return {}
    series = payload.get("series", {}) if isinstance(payload, dict) else {}
    return series if isinstance(series, dict) else {}


def prune_stale_html(
    output_dir,
    expected_filenames,
    minimum_expected=1,
    maximum_shrink_fraction=0.10,
):
    """Remove obsolete pages only when the completed output looks trustworthy."""
    expected = set(expected_filenames)
    if len(expected) < minimum_expected:
        raise RuntimeError(
            "Refusing to prune {}: expected at least {:,} generated pages, got {:,}.".format(
                output_dir, minimum_expected, len(expected)
            )
        )
    if not output_dir.is_dir():
        return []

    existing = sorted(output_dir.glob("*.html"))
    minimum_safe_count = math.ceil(len(existing) * (1 - maximum_shrink_fraction))
    if existing and len(expected) < minimum_safe_count:
        raise RuntimeError(
            "Refusing to prune {}: generated output would shrink by more than {:g}% "
            "({:,} existing pages, {:,} expected).".format(
                output_dir,
                maximum_shrink_fraction * 100,
                len(existing),
                len(expected),
            )
        )

    removed = []
    for path in existing:
        if path.name in expected:
            continue
        path.unlink()
        removed.append(path.name)
    return removed


def render_history_section(points, place_name):
    """Render an accessible static history chart, or empty text if too thin."""
    rows = _valid_points(points)
    if len(rows) < 2:
        return ""

    width, height = 720, 210
    left, right, top, bottom = 22, 22, 22, 22
    plot_width = width - left - right
    plot_height = height - top - bottom
    values = [row["value"] for row in rows]
    low, high = min(values), max(values)
    span = high - low
    if span == 0:
        span = max(abs(high) * 0.02, 1.0)
        low -= span / 2
        high += span / 2
    else:
        padding = span * 0.08
        low -= padding
        high += padding

    coordinates = []
    for index, row in enumerate(rows):
        x = left + (plot_width * index / (len(rows) - 1))
        y = top + ((high - row["value"]) / (high - low) * plot_height)
        coordinates.append((x, y))

    points_attr = " ".join("{:.1f},{:.1f}".format(x, y) for x, y in coordinates)
    first, last = rows[0], rows[-1]
    change = (last["value"] / first["value"] - 1) * 100 if first["value"] else 0
    if abs(change) < 0.05:
        direction = "was unchanged"
    elif change > 0:
        direction = "increased by {:.1f}%".format(change)
    else:
        direction = "decreased by {:.1f}%".format(abs(change))

    safe_name = escape(str(place_name))
    first_month = _month_label(first["as_of"])
    last_month = _month_label(last["as_of"])
    chart_title = "{} typical home value from {} to {}".format(safe_name, first_month, last_month)
    table_rows = "\n".join(
        "      <tr><td>{}</td><td>{}</td><td>{}</td></tr>".format(
            _month_label(row["as_of"]),
            _money(row["value"]),
            "n/a" if row.get("yoy_pct") is None else "{:+.1f}%".format(row["yoy_pct"]),
        )
        for row in rows
    )
    endpoint_dots = "\n".join(
        '        <circle cx="{:.1f}" cy="{:.1f}" r="4" />'.format(*point)
        for point in (coordinates[0], coordinates[-1])
    )

    return """
<section class="history-section" aria-labelledby="history-heading">
  <h2 id="history-heading">Home value history</h2>
  <p>The typical home value {direction}, from <b>{first_value}</b> in {first_month} to <b>{last_value}</b> in {last_month}.</p>
  <div class="history-chart-wrap">
    <div class="history-chart-range" aria-hidden="true"><span>Observed range</span><b>{low_value} &ndash; {high_value}</b></div>
    <svg class="history-chart" viewBox="0 0 {width} {height}" role="img" aria-label="{chart_title}">
      <title>{chart_title}</title>
      <line class="history-grid-line" x1="{left}" y1="{top}" x2="{left}" y2="{axis_bottom}" />
      <line class="history-grid-line" x1="{left}" y1="{axis_bottom}" x2="{axis_right}" y2="{axis_bottom}" />
      <polyline class="history-line" points="{points_attr}" />
{endpoint_dots}
    </svg>
    <div class="history-chart-labels" aria-hidden="true"><span>{first_month}</span><span>{last_month}</span></div>
  </div>
  <p class="history-note">Monthly Zillow Home Value Index snapshots retained by HomePriceMap. A short history is shown now and grows automatically as each new monthly release arrives.</p>
  <div class="sr-only">
    <table class="history-table">
      <caption>{safe_name} monthly home value history</caption>
      <thead><tr><th scope="col">Month</th><th scope="col">Typical home value</th><th scope="col">Year-over-year change</th></tr></thead>
      <tbody>
{table_rows}
      </tbody>
    </table>
  </div>
</section>
""".format(
        direction=direction,
        first_value=_money(first["value"]),
        last_value=_money(last["value"]),
        first_month=first_month,
        last_month=last_month,
        width=width,
        height=height,
        chart_title=chart_title,
        left=left,
        top=top,
        axis_bottom=height - bottom,
        axis_right=width - right,
        points_attr=points_attr,
        endpoint_dots=endpoint_dots,
        high_value=_money(max(values)),
        low_value=_money(min(values)),
        safe_name=safe_name,
        table_rows=table_rows,
    )
