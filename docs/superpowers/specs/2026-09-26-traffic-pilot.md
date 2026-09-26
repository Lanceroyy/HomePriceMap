# Targeted Traffic Pilot Spec

## Goal

Make production analytics trustworthy and improve two city pages that already have Google search demand, without a redesign or mass-generated copy. Correct the city-identity data errors found during release review.

## Scope

1. Load the production GA4 tag only on `homepricemap.us` and `www.homepricemap.us`; local files, localhost previews, and GitHub Pages previews must not send production events.
2. Add same-county, same-month Zillow home-value comparisons to the generated Los Angeles, CA and Canton, GA city profiles. Peer links must point only to city profiles that pass the existing publication eligibility rules.
3. Add visible direct links to those two pilot profiles from the maintained homepage and city map page.
4. Verify the existing local discovery/comparison/history feature batch before asking the user to stage and push source files. Generated profiles and state pages are published by the daily GitHub Action, not by a local bulk push.
5. Inspect representative indexing examples with current URL data and record a measurement baseline: exact Google query–page pairs, U.S. acquisition, and unique affiliate-click users.
6. Preserve distinct FBI city records that share a shortened name key, assign county crime only on an unambiguous full-name match, and suppress mismatched or ambiguous map coordinates and history. Regenerate the 2024 FBI JSON outputs from the checked-in workbook.
7. Accept the resulting change in eligible profile URLs. Against the checked-in 4,012-page snapshot, the corrected build has 3,907 pages: 112 old URLs are removed and 7 qualify for publication. This is a data-accuracy correction approved by the site owner, not a program to create thin pages.

## Non-goals

- No changes to the raw Zillow or ACS source files. The two derived 2024 FBI JSON datasets are explicitly in scope.
- No hand edits or local commits of generated `cities/`, `counties/`, `states/`, `states.html`, `sitemap.xml`, or `robots.txt`.
- No speculative city pages, ZIP pages, schema for its own sake, or visual redesign. The seven newly eligible city profiles must satisfy the existing FBI population rule.
- No assumption that a ranking or click change proves the pilot caused it.
- No handling or storage of a Bing Webmaster API key in the repository or this chat.

## Acceptance criteria

- Local and preview hosts enqueue no production GA4 config or events; the production host still queues page-view and delegated interaction events.
- Each pilot section uses current source values, accurately describes Zillow ZHVI as a typical value, lists only published same-county peers with the same data month, and omits itself safely if qualifying peers disappear.
- Direct pilot links are visible and resolve to published profile paths after the Action regenerates pages.
- Python and JavaScript tests pass; representative generated profiles are tested outside checked-in output directories; desktop/mobile browser QA covers the existing discovery feature batch.
- Indexing findings distinguish stale Google crawl records from presently failing URLs, and the handoff names every remaining account or deployment action.
- FBI rows sharing one shortened key remain distinct; county rollups, profile statistics, history, and map markers cannot borrow a different place's values. The derived JSON is regenerated, with the intentional 112 removed/7 added city URLs disclosed before deployment.
