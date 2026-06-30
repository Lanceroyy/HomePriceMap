# Home Price Map

Interactive map of median U.S. home prices — one view for counties, one for cities — refreshed daily from Zillow's free Research data. Pure static site (HTML/CSS/JS, Leaflet), no backend server, no API keys.

## How it works

A Python script (`scripts/fetch_data.py`) downloads Zillow's public ZHVI (Zillow Home Value Index) CSVs for counties and cities, extracts the latest median value and year-over-year change per region, and writes two small JSON files:

- `data/county_prices.json` — keyed by 5-digit county FIPS code
- `data/city_prices.json` — list of cities with lat/lon

The frontend (`index.html`, `counties.html`, `cities.html`) is a static site that reads those JSON files directly — no server-side code at runtime. County boundaries are loaded client-side from the free `us-atlas` TopoJSON package via CDN; city markers are plotted from lat/lon resolved against the U.S. Census Gazetteer.

A GitHub Actions workflow (`.github/workflows/update-data.yml`) runs the fetch script once a day and commits the refreshed JSON automatically, so once it's hosted you don't have to touch it again. Zillow only republishes ZHVI around the 16th of each month, so most daily runs are a no-op — that's expected.

## First-time setup

1. **Build the city coordinate lookup (one time only).** This downloads the Census Gazetteer Places file and only needs to be re-run if you want fresher coordinates (roughly once a year):

   ```
   python scripts/build_city_coords.py
   ```

   This writes `data/city_coords.json`.

2. **Run the daily fetch script once locally** to pull real data (this repo ships with small sample data so you can preview the site immediately, but it's not live data):

   ```
   python scripts/fetch_data.py
   ```

   This overwrites `data/county_prices.json` and `data/city_prices.json` with real Zillow numbers.

3. **Preview locally:**

   ```
   python -m http.server 8000
   ```

   Then open `http://localhost:8000`.

No dependencies beyond the Python standard library — nothing to `pip install`.

## Hosting on GitHub Pages (free)

1. Push this folder to a new GitHub repo.
2. In the repo, go to **Settings → Pages** and set the source to the `main` branch, root folder.
3. Go to **Settings → Actions → General → Workflow permissions** and make sure "Read and write permissions" is selected (the daily workflow needs to commit data updates).
4. That's it — the site is live at `https://<you>.github.io/<repo>/`, and the data refreshes daily on its own. You can also trigger a refresh manually from the **Actions** tab ("Run workflow").

Any other static host (Netlify, Vercel, Cloudflare Pages) works the same way — just make sure the daily GitHub Action still has permission to push commits back to whichever repo triggers your host's deploy.

## Data notes & limitations

- **Coverage**: county data covers essentially all ~3,000 U.S. counties. City coverage depends on how well Zillow's city names match the Census Gazetteer's official place names — the fetch script logs a match rate each run; a small percentage of cities (mostly ones with ambiguous or unincorporated names) won't have coordinates and are skipped.
- **Update cadence**: ZHVI is a monthly metric. Polling daily doesn't get you new numbers daily — it just guarantees you pick up the new month within 24 hours of Zillow publishing it.
- **Not real-time market data**: ZHVI is a smoothed index of typical home values, not individual sale prices. It's the standard free benchmark used across the industry, but it lags live listing data by design.
- **Attribution**: Zillow's data is free to use but Zillow asks that you not present it as your own proprietary dataset — credit "Zillow Research" (already done in the footer and in the JSON `source` field). Census Gazetteer data is public domain.

## Project structure

```
HomePriceMap/
├── index.html              landing page
├── counties.html           county choropleth map
├── cities.html              city marker map
├── css/style.css
├── js/
│   ├── common.js           shared color scale / formatting helpers
│   ├── counties.js
│   └── cities.js
├── data/
│   ├── county_prices.json  daily-refreshed
│   ├── city_prices.json    daily-refreshed
│   └── city_coords.json    built once from Census Gazetteer
├── scripts/
│   ├── fetch_data.py       daily data refresh
│   └── build_city_coords.py  one-time/yearly coordinate builder
└── .github/workflows/update-data.yml
```

(`MONETIZATION.md` exists locally as a private planning doc but is gitignored — not pushed to the repo.)
