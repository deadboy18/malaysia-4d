# Deadboy4D Analytics v3

Multi-operator 4D lottery analytics dashboard for Malaysia.

## Quick Start (Windows)

**Double-click `START.bat`** — it handles everything automatically:
1. Checks if Python is installed
2. Installs missing packages if needed
3. Starts the server
4. Opens your browser to http://localhost:8080

## Manual Start

```bash
pip install -r requirements.txt
python server.py
# Open http://localhost:8080
```

## Data Limits

| Operator | Earliest data | Source |
|----------|--------------|--------|
| Sport Toto | 1992 | sportstoto.com.my (HTML scrape) |
| Magnum 4D | 1985 | magnum4d.my (JSON API) |
| Da Ma Cai | 2005 | damacai.com.my (JSON API) |

## Scraping Commands

```bash
# Sport Toto
python scraper_sportstoto.py --from 1992    # ~2 min/year
python scraper_sportstoto.py --update       # latest draws only

# Magnum 4D
python scraper_magnum.py --all              # ~3 min total
python scraper_magnum.py --update

# Da Ma Cai
python scraper_damacai.py --all             # ~35 min total
python scraper_damacai.py --update
```

Or use the Scraper tab in the dashboard — no command line needed.

## Files

```
deadboy4d/
  server.py              <- Flask API (multi-operator)
  dashboard.html         <- Full dashboard with light/dark theme
  scraper_sportstoto.py  <- Sport Toto scraper (ready)
  scraper_magnum.py      <- Magnum scraper (needs Selenium)
  scraper_damacai.py     <- Da Ma Cai scraper (skeleton)
  requirements.txt
  data/
    sportstoto_draws.csv
    magnum_draws.csv
    damacai_draws.csv
```

## API Endpoints

All endpoints use operator prefix: sportstoto, magnum, damacai

```
GET  /api/operators           -> list all operators + data status
GET  /api/{op}/status         -> dataset stats
GET  /api/{op}/frequency      -> hot/cold numbers
GET  /api/{op}/digits         -> digit position counts
GET  /api/{op}/gaps           -> gap analysis
GET  /api/{op}/lookup?num=    -> number history
GET  /api/{op}/patterns       -> pattern distribution
GET  /api/{op}/export         -> download CSV
GET  /api/compare             -> cross-operator comparison
POST /api/scrape              -> start scraper
GET  /api/scrape/status       -> scrape progress
```

## Dashboard Features

- Light / Dark theme toggle (saved in localStorage)
- Operator tabs on every analysis page
- Cross-operator comparison view
- All existing analysis: hot/cold, digit positions, gaps, patterns, lookup
- Built-in scraper with live log
- CSV export per operator
