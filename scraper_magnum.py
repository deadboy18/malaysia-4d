"""
Magnum 4D Scraper (Deadboy4D)
==============================
Scrapes draw results from magnum4d.my using their JSON API.
No Selenium needed!

Outputs: data/magnum_draws.csv

Usage:
    python scraper_magnum.py                  # scrape last 5 years
    python scraper_magnum.py --from 1985      # scrape from 1985
    python scraper_magnum.py --update         # only add new draws
    python scraper_magnum.py --all            # scrape everything (1985-now)
"""

import requests
import re
import time
import os
import argparse
import pandas as pd
from datetime import date, datetime

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 Chrome/120.0.0.0 Safari/537.36"
    ),
    "Accept": "application/json",
    "Referer": "https://www.magnum4d.my/results/draw-results",
}
BASE_URL = "https://www.magnum4d.my/results/past/between-dates"
OUTPUT_PATH = "data/magnum_draws.csv"
PAGE_SIZE = 50
DELAY = 0.4


def fetch_page(end_date, count=PAGE_SIZE):
    """Fetch a page of results ending at end_date (YYYY-MM-DD format)."""
    url = f"{BASE_URL}/null/{end_date}/{count}"
    try:
        r = requests.get(url, headers=HEADERS, timeout=15)
        if r.status_code == 200:
            return r.json()
        else:
            print(f"  [WARN] HTTP {r.status_code} for {url}")
            return []
    except Exception as e:
        print(f"  [ERROR] {e}")
        return []


def parse_draw(item):
    """Convert a Magnum API response item to our standard format."""
    dd = item.get("DrawDate", "")
    if not dd:
        return None
    parts = dd.split("/")
    if len(parts) != 3:
        return None

    day_v, mon_v, yr_v = int(parts[0]), int(parts[1]), int(parts[2])

    draw_id = item.get("DrawID", "")
    seq_match = re.match(r"(\d+)/(\d+)", draw_id)
    draw_seq = int(seq_match.group(1)) if seq_match else 0

    record = {
        "draw_seq": draw_seq,
        "date": f"{yr_v:04d}-{mon_v:02d}-{day_v:02d}",
        "year": yr_v,
        "month": mon_v,
        "day": day_v,
        "prize_1": item.get("FirstPrize", ""),
        "prize_2": item.get("SecondPrize", ""),
        "prize_3": item.get("ThirdPrize", ""),
    }
    for i in range(1, 11):
        record[f"special_{i}"] = item.get(f"Special{i}", "")
    for i in range(1, 11):
        record[f"consol_{i}"] = item.get(f"Console{i}", "")

    return record


def scrape_range(from_year, to_year):
    """Scrape all Magnum draws by paginating through the API."""
    today = date.today()
    end_date = str(today)
    from_date = f"{from_year}-01-01"

    all_draws = []
    seen_ids = set()
    page = 0

    print(f"Scraping Magnum 4D: {from_year} -> {to_year}")
    print(f"Paginating backwards from {end_date}...")
    print()

    while True:
        items = fetch_page(end_date)
        if not items:
            print("  No more results.")
            break

        new_count = 0
        for item in items:
            draw_id = item.get("DrawID", "")
            if draw_id in seen_ids:
                continue
            seen_ids.add(draw_id)

            record = parse_draw(item)
            if record and record["date"] >= from_date:
                all_draws.append(record)
                new_count += 1

        page += 1

        last_item = items[-1]
        last_dd = last_item.get("DrawDate", "")
        parts = last_dd.split("/")
        if len(parts) == 3:
            last_api_date = f"{parts[2]}-{parts[1]}-{parts[0]}"
        else:
            break

        if last_api_date < from_date:
            print(f"  Reached {last_api_date}, stopping.")
            break

        if len(items) < PAGE_SIZE:
            print(f"  Last page ({len(items)} items).")
            break

        end_date = last_api_date

        first_dd = items[0].get("DrawDate", "?")
        print(f"  Page {page}: {first_dd} -> {last_dd} | +{new_count} new | total: {len(all_draws)}")
        pct = min(99, page * 3)
        print(f"[PROGRESS] {pct}% | {last_api_date}")

        time.sleep(DELAY)

    # Save everything at the end in one shot
    if all_draws:
        save_final(all_draws)
        print(f"\nDone! {len(all_draws)} draws scraped.")
    else:
        print("\nNo draws found.")

    return load_existing()


def load_existing():
    if os.path.exists(OUTPUT_PATH):
        return pd.read_csv(OUTPUT_PATH, parse_dates=["date"])
    return pd.DataFrame()


def save_final(new_draws):
    """Save all scraped draws, merging with any existing CSV data."""
    os.makedirs("data", exist_ok=True)
    df_new = pd.DataFrame(new_draws)
    df_new["date"] = pd.to_datetime(df_new["date"])

    existing = load_existing()
    if not existing.empty:
        before = len(existing)
        df_all = pd.concat([existing, df_new], ignore_index=True)
        df_all = df_all.drop_duplicates(subset="date")
        df_all = df_all.sort_values("date").reset_index(drop=True)
        added = len(df_all) - before
        print(f"Merged with existing {before} draws (+{added} new)")
    else:
        df_all = df_new.drop_duplicates(subset="date")
        df_all = df_all.sort_values("date").reset_index(drop=True)

    df_all.to_csv(OUTPUT_PATH, index=False)
    print(f"[OK] Saved {len(df_all)} draws -> {OUTPUT_PATH}")


def main():
    parser = argparse.ArgumentParser(description="Scrape Magnum 4D results")
    parser.add_argument("--from", dest="from_year", type=int, default=date.today().year - 5)
    parser.add_argument("--to", dest="to_year", type=int, default=date.today().year)
    parser.add_argument("--update", action="store_true")
    parser.add_argument("--all", action="store_true", help="Scrape from 1985")
    args = parser.parse_args()

    if args.all:
        args.from_year = 1985

    if args.update:
        existing = load_existing()
        if existing.empty:
            print("No existing data. Running full scrape...")
            scrape_range(args.from_year, args.to_year)
        else:
            print(f"Existing: {len(existing)} draws, latest: {existing['date'].max().date()}")
            items = fetch_page(str(date.today()), 50)
            if items:
                new_draws = [parse_draw(item) for item in items if parse_draw(item)]
                save_final(new_draws)
            else:
                print("No new draws found.")
    else:
        scrape_range(args.from_year, args.to_year)


if __name__ == "__main__":
    main()
