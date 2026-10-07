# Quality and Measurement Implementation Plan

> **For agentic workers:** Execute these tasks inline with checkpoints, then use the requesting-code-review skill for an independent read-only review.

**Goal:** Make the homepage lighter, improve two existing profiles, add a verifiable original analysis, and establish usable measurement.

**Architecture:** Extend the existing place-index builder to write a tiny independent stats summary. Keep generated profile changes in the city builder and original editorial content in a maintained HTML page with a frozen data snapshot. Reuse existing production-only events rather than collecting raw search terms.

**Tech Stack:** Python unittest, vanilla JavaScript/node:test, static HTML/CSS, GitHub Actions, existing GA4 UI.

**Spec:** `docs/superpowers/specs/2026-10-06-quality-and-measurement.md`

## Global Constraints

- Static HTML/CSS/JavaScript and Python only; no new runtime dependencies.
- Never edit checked-in generated profiles, sitemap, state pages, or robots.
- Generate test profiles under an ignored preview directory.
- Do not post promotional content externally, purchase a subscription, schedule monitoring, or enable Google signals.

### Task 1: Lightweight homepage statistics

**Files:** Modify `scripts/place_index_builder.py`, `.github/workflows/update-data.yml`, `index.html`; create `js/home-stats.js`, `tests/test_home_stats.py`, `tests/home-stats.test.js`, `data/site_summary.json`.

**Interfaces:** `build_summary(data_dir=DEFAULT_DATA_DIR) -> {county_count:int, city_count:int, updated:str}`; `--summary-output PATH` explicitly opts the catalog CLI into summary output. The frontend consumes `/data/site_summary.json` only.

- [x] Write tests with deliberately incorrect source `count` fields; assert `build_summary` counts actual priced records and writes compact JSON.
- [x] Run `rtk proxy python -m unittest discover -s tests -p test_home_stats.py -v`; confirm the missing implementation fails.
- [x] Implement summary counting with `len([r for r in records if r.get('value') is not None])`, preserve the source refresh timestamp, and use the existing `write_catalog` JSON serializer. Add explicit `--summary-output data/site_summary.json` to the workflow and its explicit staging list.
- [x] Replace inline stats fetching with `js/home-stats.js`: check HTTP status, nonnegative integer counts, and a complete UTC ISO timestamp with real calendar components before updating any elements; on failure render `Unavailable` for all three counters. Format refresh dates in UTC.
- [x] Run Python and Node stats tests, including HTTP error, malformed payload, unavailable fetch, zero counts, and time-zone boundary cases.

### Task 2: Targeted city context and descriptions

**Files:** Modify `scripts/city_pages_builder.py`, `tests/test_city_pilot.py`.

**Interfaces:** `targeted_context_section(city, income, county_record) -> str`; template gets a dedicated section. Only exact `(state,name)` keys for Beverly Hills and Aspen render it.

- [x] Write tests asserting real price/income arithmetic, capped-income wording, missing-income suppression, and omission of stale county comparisons.
- [x] Run the targeted tests to establish failure before implementation.
- [x] Add short date-specific, explicitly non-payment interpretation of the local ratio and county aggregate; link Beverly Hills to the new analysis. Keep the same-month county check and escape generated display text.
- [x] Remove the 158-character description fallback while preserving the existing distinctive income/crime text. Test long city names and top-coded incomes.
- [x] Run targeted and full Python tests; generate all profiles into `.codex/qa/quality-preview/cities/` for link and eligibility checks.

### Task 3: Original Los Angeles County analysis

**Files:** Create `los-angeles-county-home-price-gaps.html`, `data/analysis/los-angeles-county-2026-08.json`, `tests/test_local_analysis.py`; modify `index.html`, `css/style.css`, `scripts/state_pages_builder.py`, `tests/test_discovery_features.py`.

**Interfaces:** Frozen snapshot contains `as_of`, one county record and all published same-month city records in Los Angeles County. HTML chart rows carry exact integer values for verification; chart bar widths use `value / max_value * 100`.

- [x] Read current source datasets and verify the county, published city range, selected values, income ratios, and dates. Freeze only public source facts in the snapshot.
- [x] Write calculation tests for extreme-city ratio, selected chart/table values, date labels, links, and sitemap registration.
- [x] Build a first-person article with six selected cities, linear value bars with a zero baseline, readable amounts, caveats about non-neighboring cities and geography, and comparison links. Use existing article layout and loader/theme conventions.
- [x] Add a dated homepage article callout and final sitemap registration. Do not change earlier dated articles' claims.
- [x] Run tests; inspect desktop and 320/390px mobile layouts in both themes and follow an article comparison link.

### Task 4: Measurement and handoff

**Files:** Private `.codex/analytics/2026-10-06-measurement.md` and ignored QA artifacts only.

- [x] Inspect the connected GA4 property's existing custom definitions; add event-scoped `search_surface` and `place_type` only if absent. Do not register high-cardinality place IDs or raw queries.
- [x] Record a comparable pre-release baseline and the first full 28-day post-deploy window, excluding lagging Search Console days and reviewing US engaged sessions separately from all-country totals.
- [x] Run all Python and Node tests and preview generation; request an independent read-only review against this plan and fix material findings.
- [x] Report exact checks and remaining deployment/account steps. Do not stage, commit, push, or publish generated files without current authorization.
