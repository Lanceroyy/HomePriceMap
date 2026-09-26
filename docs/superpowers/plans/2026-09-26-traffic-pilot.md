# Targeted Traffic Pilot Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Exclude preview traffic from GA4, enrich two promising city profiles with verified local comparisons, verify the unpublished discovery feature batch, and release the approved city-identity correction.

**Architecture:** A shared vanilla-JavaScript loader gates GA4 by hostname; maintained pages and three Python templates reference it. The city builder assembles two curated, data-driven comparison sections only from already-eligible peer profiles. City identity is matched conservatively across the FBI, ACS, coordinates, and history datasets. Tests and isolated generation verify the changes before the user pushes source files.

**Tech Stack:** Python 3.11 standard library, vanilla HTML/CSS/JavaScript, Node.js for JS checks, `unittest`, GitHub Actions.

**Spec:** `docs/superpowers/specs/2026-09-26-traffic-pilot.md`

## Global Constraints

- Never hand-edit generated profile/state pages or push locally generated output.
- Do not run Git commands in the agent sandbox; give the user an explicit staging list.
- Keep the refresh workflow in dependency order: city pages, county pages, place catalog, then `state_pages_builder.py` last. County pages read existing city files to create internal links.
- Zillow ZHVI is a typical home value, not a simple arithmetic average or an individual sale price.
- Keep `trackEvent()` safe when `gtag` is absent, including on preview hosts and with ad blockers.
- Preserve the existing local discovery/comparison/history changes; do not recreate them.
- The site owner approved the 2024 FBI JSON regeneration and the resulting 112 removed/7 added city URLs on September 26, 2026.

---

### Task 1: Production-only GA4 loader

**Files:**
- Create: `js/analytics-loader.js`
- Create: `tests/analytics-loader.test.js`
- Modify: `index.html`, `counties.html`, `cities.html`, `compare.html`, `about.html`, `contact.html`, `methodology.html`, `privacy-policy.html`, `cheapest-counties-arent-the-most-affordable.html`, `home-price-trends-by-state-2026.html`
- Modify: `scripts/city_pages_builder.py`, `scripts/seo_pages_builder.py`, `scripts/state_pages_builder.py`
- Test: `tests/test_discovery_features.py`

**Interfaces:**
- Consumes: `window.location.hostname`, `document.head`, the existing GA4 measurement ID `G-2K8JWH5ZKY`.
- Produces: a global `window.gtag` and queued GA4 config only on the two production hosts; no `window.gtag` on other hosts.

- [ ] **Step 1: Write failing loader and integration tests.** In a Node VM, mock production and localhost locations. Assert that production appends exactly one GA script and queues `js` and `config`; localhost appends none and leaves `gtag` undefined. Extend the Python integration test to require the shared script in maintained pages and all three builder templates.
- [ ] **Step 2: Run the tests and confirm the expected missing-loader failures.** Run `rtk proxy node tests/analytics-loader.test.js` and `rtk proxy python -m unittest tests.test_discovery_features -v`.
- [ ] **Step 3: Implement the loader.** Use a hostname allowlist; append `https://www.googletagmanager.com/gtag/js?id=G-2K8JWH5ZKY` only on production; queue `gtag('js', new Date())` and `gtag('config', 'G-2K8JWH5ZKY')` there. Replace the repeated GA snippets with `<script src="/js/analytics-loader.js"></script>`.
- [ ] **Step 4: Run the focused checks.** Run `rtk proxy node tests/analytics-loader.test.js`, `rtk proxy node --check js/analytics-loader.js`, and `rtk proxy python -m unittest tests.test_discovery_features -v`.

### Task 2: Two verified city-profile pilots

**Files:**
- Modify: `scripts/city_pages_builder.py`
- Modify: `index.html`, `cities.html`
- Create: `tests/test_city_pilot.py`

**Interfaces:**
- Consumes: eligible `(city_record, crime_record)` pairs already selected by `city_pages_builder.build()`. `local_comparison_section(city: dict, eligible_by_location: dict) -> str` receives only the data needed for rendered links.
- Produces: a same-month, same-county local comparison section for Los Angeles, CA and Canton, GA; empty text for other cities or unavailable peers.

- [ ] **Step 1: Write failing unit tests.** Use small fixtures for Los Angeles/Long Beach/Pasadena/Santa Monica and Canton/Woodstock/Holly Springs. Assert accurate value deltas, links, same-county/month eligibility, HTML escaping, and empty output when peers vanish.
- [ ] **Step 2: Confirm the tests fail for the missing component.** Run `rtk proxy python -m unittest tests.test_city_pilot -v`.
- [ ] **Step 3: Implement the component in the city builder.** Build an eligible-location lookup once, use curated peer names only when those records qualify, format each current value and percentage relative to the subject city, and link to generated profile slugs. Insert the section after the existing state/county comparison.
- [ ] **Step 4: Add direct maintained-page links.** Put Los Angeles and Canton profile links near the homepage finder and in the city-map explanatory section, without altering map controls.
- [ ] **Step 5: Run focused tests and isolated output checks.** Run `rtk proxy python -m unittest tests.test_city_pilot tests.test_discovery_features -v`; point `city_pages_builder.OUT_DIR` at a temporary directory and compare all displayed numbers with `data/city_prices.json`.

### Task 3: Indexing and release-candidate verification

**Files:**
- Verify: `compare.html`, `js/place-search.js`, `js/compare.js`, `scripts/place_index_builder.py`, `scripts/profile_components.py`, maintained pages, tests, and `.github/workflows/update-data.yml`.
- Do not edit: generated `cities/`, `counties/`, `states/`, `states.html`, `sitemap.xml`, `robots.txt`.

**Interfaces:**
- Consumes: current Search Console URL inspections, the linked GA4/GSC baseline, and isolated local site output.
- Produces: a factual deployment handoff with an exact source-file staging list and the manual Action step.

- [ ] **Step 1: Inspect a small sample of stale 404, discovered, and crawled-not-indexed URLs.** Compare Google's last crawl/indexing result with current page status; report unresolved cases without bulk requests.
- [ ] **Step 2: Run the complete code suite.** Run `rtk proxy python -m unittest discover -s tests -v`, `rtk proxy python -m py_compile scripts/city_pages_builder.py scripts/seo_pages_builder.py scripts/state_pages_builder.py scripts/place_index_builder.py scripts/profile_components.py`, and `rtk proxy node --check` on all maintained JS files.
- [ ] **Step 3: Verify catalog/profile output in temporary directories.** Confirm unique place IDs, two pilot sections, profile history, comparison links, canonical URLs, and no generated-file writes in the working tree.
- [ ] **Step 4: Exercise local browser interactions at desktop and mobile widths.** Test finder keyboard selection, comparison add/remove/share/fragment restoration, history chart display, no horizontal overflow, and no GA4 request from localhost.
- [x] **Step 5: Review source edits and hand off deployment.** Provide explicit files to stage, the normal push instructions, and the "Daily home price data refresh" Action sequence. Do not claim production features are live until the user pushes and the live site is checked.

## Self-review

- [ ] Match each acceptance criterion in the spec to one tested task.
- [ ] Confirm all named function signatures and file paths above match implementation.
- [ ] Search this plan for unresolved placeholders before handoff.

### Task 4: Release-review data integrity correction

The independent review found that the legacy `STATE|suffix-stripped-name` key
can name several distinct Zillow places. Current data demonstrates wrong FBI,
Census, coordinate, and history joins. This correction is required before the
finder/history batch can be released.

- [x] Add focused failing tests for Hot Springs / Hot Springs Village, Royal Oak
  / Royal Oak Township, and same-named cities in different counties.
- [x] Centralize conservative source-name matching: accept a source record only
  when it identifies one Zillow place in that legacy-key group. Census `city`
  may be a formal suffix; do not treat `village` or `township` as interchangeable.
- [x] Suppress map coordinates when one legacy coordinate key is shared by
  multiple Zillow cities; keep those priced records for profiles and mark them
  as unavailable on the map. Make the map and page link skip missing locations.
- [x] Key new city history by state, county, and full name. Reuse legacy history
  only for a unique old key whose latest point matches the current city value;
  never display an ambiguous old series.
- [x] Apply the same crime/income matching to the profile builder, catalog, and
  interactive city map. Verify every current generated chart endpoint equals
  the page headline month/value, and that no catalog row shows a mismatched
  source name.
- [x] Recheck the dated affordability article's factual claims against the
  current data or identify it explicitly as a historical snapshot.

### Task 5: Approved derived-data release and URL audit

**Files:**
- Modify: `scripts/process_crime_data.py`, `scripts/build_city_coords.py`, `scripts/fetch_data.py`, `scripts/city_identity.py`, `js/city-identity.js`
- Regenerate: `data/crime_data_city.json`, `data/crime_data_county.json` from the existing 2024 Table 8 workbook
- Test: `tests/test_city_identity.py`, `tests/city-identity.test.js`

**Interfaces:**
- `match_city_source(city, source_by_key, candidates, allow_city_suffix=False)` accepts either one source record or a list of collision records under a legacy key, returning exactly one unambiguous full-name match or `None`.
- `matched_county_for_crime_row(row, city_candidates)` returns the Zillow county only when one full-name city match exists.
- `build_city_data(rows, cols, coords)` retains priced cities with an existing coordinate lookup but sets latitude/longitude to `None` when that lookup's name or key is ambiguous. Zillow cities with no Gazetteer lookup still follow the pre-existing exclusion rule.

- [x] **Step 1: Preserve and test FBI collisions.** Keep all 8,861 source rows in 8,782 legacy-key buckets, with lists for colliding keys. Assert Hot Springs and Hot Springs Village return distinct crime records; ambiguous same-name cities return no match.
- [x] **Step 2: Correct the county rollup.** Use `matched_county_for_crime_row` rather than a last-record-wins city-to-county dictionary. Regenerate both JSON outputs with `rtk proxy python scripts/process_crime_data.py`; spot-check Garland, Macomb, and Lenawee against raw Table 8 rows.
- [x] **Step 3: Reject untrusted coordinates and histories.** Require stored Gazetteer place names to match the Zillow place, mark future duplicate Gazetteer keys ambiguous, and retain history only when its latest month/value match the city. Exercise Ocean City, Park City, Royal Oak, and duplicate-key fixtures.
- [x] **Step 4: Verify the complete profile and catalog snapshot.** Generate city pages outside `cities/`, confirm the catalog has one entry per generated city URL, verify the two pilots and Hot Springs profiles, and compare filenames to the checked-in `cities/` snapshot. Expected at the current data snapshot: 3,907 generated city URLs, 112 removed, 7 added. Generate county pages afterward and assert every county-to-city link targets one of those 3,907 pages. The county builder also prunes one already-stale generated URL, `ak-valdez-cordova-borough.html`, leaving 3,071 county pages.
- [x] **Step 5: Review and hand off.** Run the full Python and JavaScript tests, syntax checks, and an independent read-only review. Give the site owner explicit source/data file staging instructions and the manual Action step. Do not push generated pages or claim the site is live before inspecting the deployed result.
