# Quality and measurement improvements

## Goal

Reduce homepage data overhead, add useful context to a small set of existing city profiles, publish one reproducible first-person analysis, and make discovery/comparison usage measurable.

## Scope

- Replace homepage price-dataset downloads with an automatically refreshed summary. Preserve coverage counts and the last-refresh date; distinguish refresh date from Zillow's observation month.
- Retain the existing local-comparison pilot. Add price-versus-income interpretation and data-date context only to Beverly Hills, CA and Aspen, CO. Do not invent nearby-city eligibility or expand the publication set.
- Preserve informative city descriptions instead of removing their distinctive information at an arbitrary character boundary.
- Publish an August 2026 Los Angeles County city-price analysis with a chart, exact source snapshot, calculation tests, methodological caveats, and profile/comparison links.
- Check GA4 custom definitions for the already-emitted search/comparison parameters. Register only low-cardinality event dimensions needed to distinguish search surfaces and place types if access permits. Preserve the production-only analytics loader and all analytics guards.
- Document the measurement baseline and evaluation procedure privately; do not publish traffic data or account details.

## Constraints

Static HTML/CSS/JavaScript and Python only; no new runtime dependencies. Never edit checked-in generated profiles, sitemap, state pages, or robots. Generate test profiles under an ignored preview directory. Add the new article to the final state builder's sitemap list. Do not post promotional content externally, purchase a subscription, schedule monitoring, enable Google signals, or claim that a release caused earlier traffic growth.

## Acceptance

- Homepage fetches one summary smaller than 512 bytes, not either price dataset. Counts are nonnegative integers. Network/parse/data failures leave readable unavailable text; full UTC ISO timestamp validation and formatting are deterministic across time zones.
- The daily workflow builds and commits the summary. CLI custom output paths cannot accidentally overwrite unrelated production outputs.
- Targeted profile facts come from each exact matched city and same-month county; no mortgage qualification or neighborhood safety claims.
- Every published analysis number and chart width is rechecked from its frozen source snapshot. Links resolve, with mobile/light/dark visual QA and semantic chart labels.
- Existing tests plus new summary, frontend failure-path, targeted-context, and analysis tests pass. Independent read-only code review is required before handoff.
- Handoff distinguishes local completion, GA4 settings changes, and deployment still required.
