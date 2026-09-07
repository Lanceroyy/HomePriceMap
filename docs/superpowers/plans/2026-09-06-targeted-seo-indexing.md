# Targeted SEO and Indexing Improvements Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Improve search relevance and indexability of HomePriceMap's map, city, county, and state pages without redesigning the site or hand-editing generated pages.

**Architecture:** Keep `counties.html` and `cities.html` as static map landing pages, change map selection state from crawlable query strings to URL fragments, and make all generated-page changes in the Python builders. Extend the state-page builder with compact complete directories, improve city FAQ language without mislabeling Zillow's metric, add an evidence-backed original analysis article, and regenerate only in an isolated temporary output tree for verification. The production GitHub Action remains responsible for publishing generated pages.

**Tech Stack:** Static HTML/CSS/JavaScript, Python 3 standard library builders, JSON/CSV source data, GitHub Actions.

**Spec:** User-approved scope in the September 6, 2026 Codex task, informed by the attached Search Console exports.

---

### Task 1: Lock in regression checks for the diagnosed indexing causes

**Files:**
- Inspect: `C:/Users/chron/AppData/Local/Temp/Chart (2).csv`
- Inspect: `C:/Users/chron/AppData/Local/Temp/Metadata (1).csv`
- Inspect: `C:/Users/chron/AppData/Local/Temp/Table.csv`
- Test: one-off Python assertions against `counties.html`, `cities.html`, `scripts/seo_pages_builder.py`, `scripts/city_pages_builder.py`, and `scripts/state_pages_builder.py`

**Step 1: Run a failing baseline check**

Assert that the two map pages have the requested titles and visible H1s, builders no longer emit `?fips=` or `?city=` map links, and the state builder contains complete county/city directory support.

**Step 2: Confirm failures match the current implementation**

Expected failures are the generic map titles, missing map-page H1s, crawlable query-string links, and incomplete state-page link coverage.

### Task 2: Improve the map landing pages and eliminate crawlable selection URLs

**Files:**
- Modify: `counties.html`
- Modify: `cities.html`
- Modify: `js/counties.js`
- Modify: `js/cities.js`
- Modify: `scripts/seo_pages_builder.py`
- Modify: `scripts/city_pages_builder.py`

**Step 1: Update landing-page metadata and headings**

Use the exact requested 2026 titles, keep Open Graph and Twitter titles consistent, and replace the introductory H2 on each page with a matching visible H1.

**Step 2: Change selected-map state to fragments**

Generate and share `#fips=...` and `#city=...&county=...` URLs. Continue reading legacy query parameters so existing links do not break, but normalize them to fragments after a selection loads.

**Step 3: Change generated detail-page map links**

Make county and city builders emit fragment deep links so Google does not discover each map selection as a separate page URL.

**Step 4: Re-run the focused checks**

Verify titles, H1s, fragment links, sharing behavior, and backward-compatible query parsing.

### Task 3: Improve city search-language coverage accurately

**Files:**
- Modify: `scripts/city_pages_builder.py`

**Step 1: Update the first FAQ question**

Use “What is the average home price in {City}, {State}?” while explicitly explaining that the displayed Zillow Home Value Index is a typical home value, not an arithmetic average.

**Step 2: Verify the generated visible FAQ uses the approved wording**

Render a representative city page to a temporary directory and assert the question uses the approved wording and explanation. Do not add rich-result schema solely because Search Appearance is empty.

### Task 4: Add complete detail-page directories to state pages

**Files:**
- Modify: `scripts/state_pages_builder.py`
- Modify: `css/style.css`

**Step 1: Add compact directory markup**

Add accessible `<details>` directories containing alphabetized links to every generated county and city detail page. Avoid redundant directory blocks when the existing ranked section already displays every item.

**Step 2: Add responsive directory styling**

Use the existing visual language and a compact multi-column link grid that collapses cleanly on narrow screens.

**Step 3: Validate full link coverage**

Generate state pages into a temporary tree and compare their internal links to all eligible county and published-city records for every state.

### Task 5: Complete city income data if the official export is obtainable

**Files:**
- Add, if downloaded: `data/IncomeData/ACSDT5Y2024.B19013-Place-Data.csv`
- Generate, if source is available: `data/income_data_city.json`
- Use: `scripts/process_income_data.py`

**Step 1: Retrieve the official ACS 2024 five-year B19013 Place export**

Use the Census source for Geography “Place — All Places” and save it under the distinct filename above. Do not use the Census API and do not substitute estimated or fabricated values.

**Step 2: Process and validate the export**

Run the existing income processor, require income for roughly 4,000 eligible city pages, omit normalized-name collisions that cannot be matched unambiguously, handle ACS open-ended median sentinels as bounds, and spot-check multiple records against the source CSV before accepting the JSON.

**Step 3: Record an exact manual fallback if retrieval is blocked**

If Census prevents automated download, leave the existing safe processor intact and report the precise export selections and destination filename needed from the user; do not overwrite county data or create an empty city file.

### Task 6: Publish an original data analysis and strengthen internal authority signals

**Files:**
- Add: `home-price-trends-by-state-2026.html`
- Modify: `index.html`
- Modify: `scripts/state_pages_builder.py`

**Step 1: Compute one defensible finding from repository data**

Calculate county year-over-year price changes and unweighted state medians from the current Zillow county data, then save the exact calculation used for every number displayed.

**Step 2: Build a first-person analysis page**

Include an accessible text-labeled chart, methodology, source links, limitations, publication date, canonical metadata, and links to the relevant state pages.

**Step 3: Add internal discovery links**

Feature the analysis on the homepage and add its canonical URL to the sitemap source list in the state builder.

**Step 4: Validate every factual claim**

Recompute all displayed rankings, percentages, sample sizes, dates, and source labels from the committed data.

### Task 7: Run isolated generation and final verification

**Files:**
- Verify: all modified source and builder files
- Do not stage: locally generated `counties/`, `cities/`, `states/`, `states.html`, `sitemap.xml`, or `robots.txt`

**Step 1: Run syntax and focused regression checks**

Compile all modified Python builders and run the targeted assertions from Task 1.

**Step 2: Generate representative and full outputs outside tracked destinations**

Redirect city, county, and state builder output to temporary directories. Check canonical URLs, FAQ JSON-LD, fragment links, complete state link coverage, duplicate links, missing targets, and sitemap membership.

**Step 3: Inspect the working files for accidental generated output**

Provide the user an exact staging list limited to source files, data files, the article, CSS/JS, and this plan. The user will commit and push; the GitHub Action will regenerate production pages in the required order.

**Step 4: Request a code review and address findings**

Have a reviewer inspect the final changes for correctness, regressions, SEO accuracy, and unnecessary complexity, then rerun verification after any fix.
