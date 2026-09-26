# Discovery, Comparison, and History Feature Spec

## Goal

Help visitors find a useful local page quickly, compare locations without opening multiple tabs, and understand how each location's home value is changing over time.

## Scope

1. Generate one compact catalog containing every published county profile and every city profile that passes the existing city-page eligibility rules.
2. Add a homepage place finder and a dedicated `compare.html` experience using that catalog.
3. Let visitors compare two or three places on home value, year-over-year change, income/affordability, crime, and reporting coverage when those fields are available.
4. Encode selections in a URL fragment so comparisons can be shared without creating crawlable URL variants. The comparison page has one canonical URL; fragments are not indexed separately.
5. Add a static, accessible historical price chart to generated county and city profiles when at least two monthly observations exist.
6. Add direct comparison links to generated profiles and a Compare navigation link to maintained and generated pages.
7. Keep CARTO/OpenStreetMap attribution, current data definitions, and the builder-only generation workflow intact.

## Non-goals

- No ZIP-code pages.
- No redesign of the map pages.
- No client-side charting dependency.
- No hand edits to files under `cities/`, `counties/`, or `states/`.
- No server, database, account system, or saved comparisons.

## Acceptance criteria

- The catalog builder emits deterministic JSON with unique stable IDs and only valid profile URLs.
- Search supports keyboard navigation, escape-to-close, visible empty/error states, and links directly to profiles.
- Comparison supports two or three places, add/remove, copy/share URL, graceful missing values, and responsive rendering at 375px.
- Profile history is rendered as semantic HTML plus inline SVG, with a tabular fallback for screen readers and no JavaScript dependency.
- Builders safely omit history when data is missing or malformed.
- The refresh workflow builds and commits the catalog before the state builder runs last.
- Automated tests cover catalog eligibility/deduplication, chart rendering/escaping, HTML wiring, canonical URL hygiene, and mobile layout. Browser QA covers the homepage finder, comparison interaction, fragment restoration, profile chart rendering, desktop, and mobile.
