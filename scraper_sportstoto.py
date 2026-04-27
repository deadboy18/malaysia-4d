"""
Sport Toto 4D Scraper (Deadboy4D)
======================================
Scrapes draw results from sportstoto.com.my
Outputs: data/sportstoto_draws.csv

Usage:
    python scraper.py              # scrape last 5 years
    python scraper.py --from 2015  # scrape from 2015
    python scraper.py --update     # only add missing draws to existing CSV
"""

import requests
import re
import time
import json
import argparse
import os
import pandas as pd
from datetime import date, datetime
from bs4 import BeautifulSoup

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 Chrome/120.0.0.0 Safari/537.36"
    )
}
BASE_URL = "https://www.sportstoto.com.my/results_past.asp"
OUTPUT_PATH = "data/sportstoto_draws.csv"
DELAY = 0.4  # seconds between requests (be polite)


# ---------------------------------------------------------------------------
# Core parser
# ---------------------------------------------------------------------------

def parse_month(year: int, month: int) -> list[dict]:
    """Fetch and parse all 4D draws for a given month/year."""
    url = f"{BASE_URL}?date={month}/15/{year}"
    try:
        r = requests.get(url, headers=HEADERS, timeout=15)
        if r.status_code != 200:
            print(f"  [WARN] HTTP {r.status_code} for {year}-{month:02d}")
            return []
    except requests.RequestException as e:
        print(f"  [ERROR] {year}-{month:02d}: {e}")
        return []

    soup = BeautifulSoup(r.text, "html.parser")
    tables = soup.find_all("table")
    if len(tables) < 2:
        return []

    full_text = tables[1].get_text("\n")

    # Split into individual draw blocks
    # Each block starts with "DrawSeq/YY  Draw Date : D/M/YYYY"
    blocks = re.split(
        r"(\d+/\d{2}\s*Draw Date\s*:\s*\d+/\d+/\d+)", full_text
    )

    draws = []
    i = 1
    while i < len(blocks) - 1:
        header = blocks[i]
        body = blocks[i + 1]
        i += 2

        # --- Draw metadata ---
        m_no = re.search(r"(\d+)/(\d{2})", header)
        m_date = re.search(r"Draw Date\s*:\s*(\d+)/(\d+)/(\d+)", header)
        if not m_no or not m_date:
            continue

        draw_seq = int(m_no.group(1))
        day_v = int(m_date.group(1))
        mon_v = int(m_date.group(2))
        yr_v = int(m_date.group(3))

        # --- Top 3 prizes ---
        p_m = re.search(
            r"First Prize\s+Second Prize\s+Third Prize\s+(\d{4})\s+(\d{4})\s+(\d{4})",
            body,
        )
        if not p_m:
            continue
        p1, p2, p3 = p_m.group(1), p_m.group(2), p_m.group(3)

        # --- Special prizes (10 numbers) ---
        sp_m = re.search(r"Special Prize\s+([\d\s]+?)Consolation Prize", body)
        specials = re.findall(r"\d{4}", sp_m.group(1))[:10] if sp_m else []

        # --- Consolation prizes (10 numbers) ---
        cp_m = re.search(r"Consolation Prize\s+([\d\s]+?)TOTO 4D JACKPOT", body)
        consols = re.findall(r"\d{4}", cp_m.group(1))[:10] if cp_m else []

        record = {
            "draw_seq": draw_seq,
            "date": f"{yr_v:04d}-{mon_v:02d}-{day_v:02d}",
            "year": yr_v,
            "month": mon_v,
            "day": day_v,
            "prize_1": p1,
            "prize_2": p2,
            "prize_3": p3,
        }
        for idx, s in enumerate(specials):
            record[f"special_{idx + 1}"] = s
        for idx, c in enumerate(consols):
            record[f"consol_{idx + 1}"] = c

        draws.append(record)

    return draws


# ---------------------------------------------------------------------------
# Orchestration
# ---------------------------------------------------------------------------

def scrape_range(from_year: int, to_year: int) -> pd.DataFrame:
    """Scrape all draws, saving incrementally after each year completes."""
    today = date.today()
    total_years = to_year - from_year + 1
    cumulative_new = 0

    for yi, year in enumerate(range(from_year, to_year + 1)):
        year_draws = []
        months_in_year = 12 if year < today.year else today.month

        for month in range(1, 13):
            if year == today.year and month > today.month:
                break
            mi = month
            draws = parse_month(year, month)
            print(f"  {year}-{month:02d}: {len(draws)} draws fetched")
            year_draws.extend(draws)
            # Print month-level progress
            pct = round(((yi * 12 + mi) / (total_years * 12)) * 100)
            print(f"[PROGRESS] {pct}% | {year}-{month:02d} | year {yi+1}/{total_years}")
            time.sleep(DELAY)

        # -- Save after each year so dashboard can show partial data ------
        if year_draws:
            df_year = pd.DataFrame(year_draws)
            df_year["date"] = pd.to_datetime(df_year["date"])
            existing = load_existing()
            if not existing.empty:
                before = len(existing)
                df_merged = pd.concat([existing, df_year], ignore_index=True)
                df_merged = df_merged.drop_duplicates(subset="draw_seq")
                df_merged = df_merged.sort_values("draw_seq").reset_index(drop=True)
                added = len(df_merged) - before
                cumulative_new += added
            else:
                df_merged = df_year.drop_duplicates(subset="draw_seq")
                df_merged = df_merged.sort_values("draw_seq").reset_index(drop=True)
                cumulative_new += len(df_merged)
            save(df_merged)

        print(f"[YEAR_DONE] {year} | +{len(year_draws)} draws | total {cumulative_new} new")

    return load_existing()


def load_existing() -> pd.DataFrame:
    if os.path.exists(OUTPUT_PATH):
        df = pd.read_csv(OUTPUT_PATH, parse_dates=["date"])
        return df
    return pd.DataFrame()


def save(df: pd.DataFrame):
    os.makedirs("data", exist_ok=True)
    df.to_csv(OUTPUT_PATH, index=False)
    print(f"\n[OK] Saved {len(df)} draws -> {OUTPUT_PATH}")


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description="Scrape Sport Toto 4D results")
    parser.add_argument("--from", dest="from_year", type=int, default=date.today().year - 5,
                        help="Start year (default: 5 years ago)")
    parser.add_argument("--to", dest="to_year", type=int, default=date.today().year,
                        help="End year (default: current year)")
    parser.add_argument("--update", action="store_true",
                        help="Only fetch draws newer than what's already saved")
    args = parser.parse_args()

    if args.update:
        existing = load_existing()
        if existing.empty:
            print("No existing data found. Running full scrape...")
            df_new = scrape_range(args.from_year, args.to_year)
        else:
            last_seq = existing["draw_seq"].max()
            last_date = existing["date"].max()
            print(f"Existing data: {len(existing)} draws, latest draw #{last_seq} on {last_date.date()}")
            print("Fetching updates for current + previous month...")
            today = date.today()
            months_to_check = [(today.year, today.month)]
            if today.month == 1:
                months_to_check.append((today.year - 1, 12))
            else:
                months_to_check.append((today.year, today.month - 1))

            new_draws = []
            for yr, mo in months_to_check:
                draws = parse_month(yr, mo)
                new_draws.extend(draws)
                time.sleep(DELAY)

            df_new_raw = pd.DataFrame(new_draws)
            if df_new_raw.empty:
                print("No new draws found.")
                return
            df_new_raw["date"] = pd.to_datetime(df_new_raw["date"])
            df_new_raw = df_new_raw[df_new_raw["draw_seq"] > last_seq]
            print(f"Found {len(df_new_raw)} new draws.")
            df_new = pd.concat([existing, df_new_raw], ignore_index=True)
            df_new = df_new.drop_duplicates(subset="draw_seq")
            df_new = df_new.sort_values("draw_seq").reset_index(drop=True)
    else:
        print(f"Scraping Sport Toto 4D results: {args.from_year}-{args.to_year}")
        df_new = scrape_range(args.from_year, args.to_year)
        # scrape_range saves incrementally after each year and merges with existing

    if df_new.empty:
        print("No data scraped.")
        return

    print(f"\nTotal draws: {len(df_new)}")
    print(f"Date range: {df_new['date'].min().date()} -> {df_new['date'].max().date()}")
    save(df_new)


if __name__ == "__main__":
    main()
