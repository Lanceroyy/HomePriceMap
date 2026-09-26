# Discovery, Comparison, and History Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a searchable place catalog, shareable side-by-side comparisons, and accessible historical charts to published profiles.

**Architecture:** A Python builder joins existing price, income, and crime datasets into a compact browser catalog. Reusable vanilla JavaScript powers an accessible search widget and the comparison page, while a small Python component renders historical profile charts as static HTML/SVG during the existing page-generation workflow.

**Tech Stack:** Python 3.11 standard library, vanilla HTML/CSS/JavaScript, `unittest`, GitHub Actions.

**Spec:** `docs/superpowers/specs/2026-09-17-discovery-comparison-history.md`

## Global Constraints

- Do not hand-edit generated files under `cities/`, `counties/`, `states/`, `states.html`, `sitemap.xml`, or `robots.txt`.
- Do not add a JavaScript framework, chart library, server, database, or new package dependency.
- Keep state page generation last because it produces the final sitemap.
- Use URL fragments for comparison state; do not create indexable query-string variants.
- Keep all display labels technically accurate: Zillow ZHVI is a typical home value, not an arithmetic average.
- Do not run Git commands; provide a staging list for the user after verification.

---

### Task 1: Compact published-place catalog

**Files:**
- Create: `scripts/place_index_builder.py`
- Create: `tests/test_place_index_builder.py`
- Modify: `.github/workflows/update-data.yml`

**Interfaces:**
- Consumes: `data/county_prices.json`, `data/city_prices.json`, county/city income JSON, county/city crime JSON.
- Produces: `build_catalog(data_dir: Path) -> dict`, `write_catalog(catalog: dict, output_path: Path) -> None`, and `data/place_index.json` with `{updated, count, places}`.

- [ ] **Step 1: Write failing catalog tests**

  Cover county joins, city eligibility at population 5,000, duplicate city slug removal, stable `county:<fips>` / `city:<profile-slug>` IDs, deterministic sorting, computed price-to-income ratios, and URLs beginning with `/counties/` or `/cities/`.

- [ ] **Step 2: Run the focused test and confirm the missing module failure**

  Run: `python -m unittest tests.test_place_index_builder -v`

- [ ] **Step 3: Implement the pure builder and command-line output option**

  The CLI defaults to `data/place_index.json` and accepts `--output PATH` for isolated verification. Optional supporting datasets produce `null` fields rather than aborting; missing price datasets fail loudly.

- [ ] **Step 4: Run the focused tests**

  Run: `python -m unittest tests.test_place_index_builder -v`

- [ ] **Step 5: Wire the builder into the refresh workflow**

  Run it after both profile builders and before the state builder; add `data/place_index.json` to the bot's explicit `git add` list.

### Task 2: Accessible profile history component

**Files:**
- Create: `scripts/profile_components.py`
- Create: `tests/test_profile_components.py`
- Modify: `scripts/city_pages_builder.py`
- Modify: `scripts/seo_pages_builder.py`
- Modify: `css/style.css`

**Interfaces:**
- Consumes: `render_history_section(points: list[dict], place_name: str) -> str` and the existing history JSON `series` dictionaries.
- Produces: a `.history-section` containing a responsive inline SVG and a screen-reader-accessible monthly data table, or `""` for fewer than two valid observations.

- [ ] **Step 1: Write failing chart tests**

  Verify chronological sorting, invalid-row filtering, escaped labels, finite SVG coordinates for flat series, first/last value labels, table rows, and empty output with fewer than two points.

- [ ] **Step 2: Run the focused test and confirm the missing module failure**

  Run: `python -m unittest tests.test_profile_components -v`

- [ ] **Step 3: Implement the static renderer**

  Use an SVG `viewBox`, a polyline, endpoint dots, labeled min/max context, a plain-language change summary, and a table hidden visually but available to assistive technology.

- [ ] **Step 4: Load history once per builder and insert it into each profile template**

  County lookup key is FIPS. City lookup key is `<STATE>|<normalize_place(name)>`. Missing/malformed history files must not stop page generation.

- [ ] **Step 5: Add responsive chart styling and rerun focused tests**

  Run: `python -m unittest tests.test_profile_components tests.test_mobile_layout -v`

### Task 3: Homepage finder and comparison experience

**Files:**
- Create: `js/place-search.js`
- Create: `js/compare.js`
- Create: `compare.html`
- Create: `tests/test_discovery_features.py`
- Modify: `index.html`
- Modify: `css/style.css`

**Interfaces:**
- Consumes: `/data/place_index.json` and `HomePriceSearch.attach(input, results, options)`.
- Produces: keyboard-accessible search results, direct profile navigation, two-to-three-place comparison cards/table, and fragment format `#places=<encoded-id>,<encoded-id>`.

- [ ] **Step 1: Write failing static integration tests**

  Assert the canonical comparison URL, no query-driven canonical variants, required ARIA wiring, homepage finder, external script loading, share control, empty/error states, and responsive CSS hooks.

- [ ] **Step 2: Run the focused test and confirm failures**

  Run: `python -m unittest tests.test_discovery_features -v`

- [ ] **Step 3: Implement the shared search controller**

  Load the catalog lazily, normalize accents/case/punctuation, rank prefix matches before substring matches, cap results at eight, support ArrowUp/ArrowDown/Enter/Escape, and expose selected place objects through a callback.

- [ ] **Step 4: Build the comparison page**

  Restore valid fragment IDs, reject duplicates, enforce three selections, render honest `n/a` values, allow removal, copy a share URL with Clipboard API fallback, and record optional analytics events through `window.trackEvent` when present.

- [ ] **Step 5: Add the homepage finder and responsive styles**

  The homepage widget navigates directly to the selected profile. The comparison layout stacks at 700px and never causes horizontal viewport overflow at 375px.

- [ ] **Step 6: Run focused tests and JavaScript syntax checks**

  Run: `python -m unittest tests.test_discovery_features -v`
  Run: `node --check js/place-search.js`
  Run: `node --check js/compare.js`

### Task 4: Site integration and discoverability

**Files:**
- Modify: `scripts/city_pages_builder.py`
- Modify: `scripts/seo_pages_builder.py`
- Modify: `scripts/state_pages_builder.py`
- Modify: `about.html`
- Modify: `cheapest-counties-arent-the-most-affordable.html`
- Modify: `cities.html`
- Modify: `contact.html`
- Modify: `counties.html`
- Modify: `home-price-trends-by-state-2026.html`
- Modify: `index.html`
- Modify: `methodology.html`
- Modify: `privacy-policy.html`

**Interfaces:**
- Consumes: stable catalog IDs from Task 1 and `/compare.html#places=<encoded-id>`.
- Produces: Compare navigation links, profile comparison calls-to-action, and a canonical sitemap entry for `/compare.html`.

- [ ] **Step 1: Extend integration tests for every maintained/template navigation source**

  Confirm Compare is present in maintained HTML and all three page-builder templates, profile links use fragments rather than queries, and the state sitemap includes `/compare.html` exactly once.

- [ ] **Step 2: Add navigation and profile calls-to-action in sources only**

  Do not modify generated pages. Preserve the existing map header height on mobile by hiding the redundant Home nav item below 700px while retaining the visible brand.

- [ ] **Step 3: Add `/compare.html` to the final sitemap builder and run integration tests**

  Run: `python -m unittest tests.test_discovery_features tests.test_seo_url_hygiene tests.test_mobile_layout -v`

### Task 5: Full verification and visual QA

**Files:**
- Verify all files above; do not edit generated output.

**Interfaces:**
- Consumes: all feature outputs.
- Produces: evidence that the batch is safe to push and regenerate.

- [ ] **Step 1: Run the complete automated suite and compile checks**

  Run: `python -m unittest discover -s tests -v`
  Run: `python -m py_compile scripts/place_index_builder.py scripts/profile_components.py scripts/city_pages_builder.py scripts/seo_pages_builder.py scripts/state_pages_builder.py`
  Run: `node --check js/place-search.js`
  Run: `node --check js/compare.js`

- [ ] **Step 2: Generate the catalog to an isolated temporary path and inspect it**

  Verify count, unique IDs/URLs, absence of query strings, representative county/city joins, and deterministic output from two runs.

- [ ] **Step 3: Render representative city and county pages in temporary directories**

  Verify history, Compare links, canonical URLs, and no unresolved template placeholders without changing checked-in generated directories.

- [ ] **Step 4: Browser-test desktop and mobile**

  At 1440px and 375px, exercise homepage search, keyboard selection, comparison add/remove/share/fragment restore, missing-data rendering, and a representative history chart. Check console errors, viewport overflow, focus visibility, and readable labels.

- [ ] **Step 5: Perform a focused code review and rerun any affected verification**

  Review for correctness, accessibility, SEO/canonical behavior, accidental generated-file edits, and regressions in the daily workflow. Resolve findings before reporting completion.
