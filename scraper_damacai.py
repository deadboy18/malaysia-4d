"""
Da Ma Cai 1+3D Scraper (Deadboy4D)
====================================
Scrapes draw results from damacai.com.my using their JSON API.
No Selenium needed!

API flow:
  1. /ListPastResult -> all available draw dates (3500+)
  2. /callpassresult?pastdate=YYYYMMDD -> Azure blob SAS URL
  3. Fetch blob URL -> full draw result JSON

Outputs: data/damacai_draws.csv

Data available from: January 2005

Usage:
    python scraper_damacai.py              # scrape last 5 years
    python scraper_damacai.py --from 2005  # scrape from 2005
    python scraper_damacai.py --update     # only add new draws
    python scraper_damacai.py --all        # scrape everything (2005-now)
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
    "cookiesession": "301",
}
BASE_URL = "https://www.damacai.com.my"
OUTPUT_PATH = "data/damacai_draws.csv"
DELAY = 0.3


def get_all_draw_dates():
    """Fetch all available draw dates from Damacai."""
    url = f"{BASE_URL}/ListPastResult"
    try:
        r = requests.get(url, headers=HEADERS, timeout=15)
        if r.status_code == 200:
            data = r.json()
            dates = data.get("drawdate", "").split()
            return sorted(dates)  # YYYYMMDD format, sorted ascending
    except Exception as e:
        print(f"[ERROR] Failed to get draw dates: {e}")
    return []


def fetch_draw_result(date_str):
    """
    Fetch results for a specific date.
    Step 1: Get Azure blob SAS URL
    Step 2: Fetch actual results from blob
    """
    try:
        # Step 1: Get the blob link
        r = requests.get(
            f"{BASE_URL}/callpassresult?pastdate={date_str}",
            headers=HEADERS, timeout=10
        )
        if r.status_code != 200:
            return None

        data = r.json()
        link = data.get("link", "")
        if not link:
            return None

        # Step 2: Fetch the actual results
        r2 = requests.get(link, timeout=10)
        if r2.status_code != 200:
            return None

        return r2.json()

    except Exception as e:
        print(f"  [WARN] Failed for {date_str}: {e}")
        return None


def parse_draw(result, date_str):
    """Convert Damacai API response to our standard format."""
    if not result:
        return None

    p1 = result.get("p1", "")
    p2 = result.get("p2", "")
    p3 = result.get("p3", "")

    if not p1 or not p2 or not p3:
        return None

    # Parse draw number: "6070/26" -> 6070
    draw_no = result.get("drawNo", "")
    seq_match = re.match(r"(\d+)/(\d+)", draw_no)
    draw_seq = int(seq_match.group(1)) if seq_match else 0

    # Date from YYYYMMDD string
    yr = int(date_str[:4])
    mon = int(date_str[4:6])
    day = int(date_str[6:8])

    record = {
        "draw_seq": draw_seq,
        "date": f"{yr:04d}-{mon:02d}-{day:02d}",
        "year": yr,
        "month": mon,
        "day": day,
        "prize_1": str(p1).zfill(4),
        "prize_2": str(p2).zfill(4),
        "prize_3": str(p3).zfill(4),
    }

    # Starter prizes = Special (10 numbers)
    starters = result.get("starterList", [])
    for i, s in enumerate(starters[:10]):
        record[f"special_{i + 1}"] = str(s).zfill(4)

    # Consolidate prizes = Consolation (10 numbers)
    consols = result.get("consolidateList", [])
    for i, c in enumerate(consols[:10]):
        record[f"consol_{i + 1}"] = str(c).zfill(4)

    return record


def scrape_range(from_year, to_year):
    """Scrape all Damacai draws in the given year range."""
    print("Fetching all available draw dates from Damacai...")
    all_dates = get_all_draw_dates()

    if not all_dates:
        print("[ERROR] Could not get draw dates. Check your internet connection.")
        return pd.DataFrame()

    print(f"Total dates available: {len(all_dates)}")
    print(f"Range: {all_dates[0]} -> {all_dates[-1]}")

    # Filter to requested year range
    from_str = f"{from_year}0101"
    to_str = f"{to_year}1231"
    filtered = [d for d in all_dates if from_str <= d <= to_str]

    print(f"Dates in {from_year}-{to_year}: {len(filtered)}")
    print()

    all_draws = []
    errors = 0
    total = len(filtered)

    for i, date_str in enumerate(filtered):
        result = fetch_draw_result(date_str)

        if result:
            record = parse_draw(result, date_str)
            if record:
                all_draws.append(record)
        else:
            errors += 1

        # Progress
        pct = round((i + 1) / total * 100)
        if (i + 1) % 50 == 0 or pct % 10 == 0:
            yr = date_str[:4]
            print(f"  {i+1}/{total} ({pct}%) | {yr}-{date_str[4:6]}-{date_str[6:8]} | {len(all_draws)} draws OK, {errors} errors")
            print(f"[PROGRESS] {pct}% | {yr}-{date_str[4:6]}")

        time.sleep(DELAY)

    # Save everything at the end
    if all_draws:
        save_final(all_draws)
        print(f"\nDone! {len(all_draws)} draws scraped ({errors} errors).")
    else:
        print("\nNo draws found.")

    return load_existing()


def load_existing():
    if os.path.exists(OUTPUT_PATH):
        return pd.read_csv(OUTPUT_PATH, parse_dates=["date"])
    return pd.DataFrame()


def save_final(new_draws):
    """Save all scraped draws, merging with any existing CSV."""
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
    parser = argparse.ArgumentParser(description="Scrape Da Ma Cai results")
    parser.add_argument("--from", dest="from_year", type=int, default=date.today().year - 5)
    parser.add_argument("--to", dest="to_year", type=int, default=date.today().year)
    parser.add_argument("--update", action="store_true")
    parser.add_argument("--all", action="store_true", help="Scrape from 2005")
    args = parser.parse_args()

    if args.all:
        args.from_year = 2005

    if args.update:
        existing = load_existing()
        if existing.empty:
            print("No existing data. Running full scrape...")
            scrape_range(args.from_year, args.to_year)
        else:
            last_date = existing["date"].max()
            print(f"Existing: {len(existing)} draws, latest: {last_date.date()}")
            print("Fetching recent draws...")
            # Scrape current year only
            scrape_range(date.today().year, date.today().year)
    else:
        print(f"Scraping Da Ma Cai: {args.from_year}-{args.to_year}")
        scrape_range(args.from_year, args.to_year)


if __name__ == "__main__":
    main()
