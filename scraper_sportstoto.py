"""
Sport Toto 4D Scraper (Deadboy4D)
======================================
Scrapes draw results from sportstoto.com.my
Falls back to check4d.com when the official site blocks datacenter IPs.
Outputs: data/sportstoto_draws.csv

Usage:
    python scraper_sportstoto.py              # scrape last 5 years
    python scraper_sportstoto.py --from 2015  # scrape from 2015
    python scraper_sportstoto.py --update     # only add missing draws to existing CSV
"""

import requests
import re
import time
import json
import random
import argparse
import os
import pandas as pd
from datetime import date, datetime, timedelta
from bs4 import BeautifulSoup

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/126.0.0.0 Safari/537.36"
    ),
    "Accept": (
        "text/html,application/xhtml+xml,application/xml;"
        "q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8"
    ),
    "Accept-Language": "en-US,en;q=0.9",
    "Accept-Encoding": "gzip, deflate",
    "Connection": "keep-alive",
}
BASE_URL = "https://www.sportstoto.com.my/results_past.asp"
FALLBACK_URL = "https://www.check4d.com/past-results"
OUTPUT_PATH = "data/sportstoto_draws.csv"
DELAY = 0.5  # seconds between requests
_use_fallback = None  # auto-detect on first call

# Persistent session
_session = None

def get_session():
    global _session
    if _session is None:
        _session = requests.Session()
        _session.headers.update(HEADERS)
    return _session


# ---------------------------------------------------------------------------
# Official site parser (sportstoto.com.my)
# ---------------------------------------------------------------------------

def parse_month_official(year: int, month: int) -> list[dict]:
    """Fetch and parse all 4D draws for a given month/year from official site."""
    session = get_session()
    url = f"{BASE_URL}?date={month}/15/{year}"
    try:
        r = session.get(url, headers={"Referer": "https://www.sportstoto.com.my/"}, timeout=15)
        if r.status_code != 200:
            return None  # return None to signal "blocked", [] means "no draws"
    except requests.RequestException:
        return None

    soup = BeautifulSoup(r.text, "html.parser")
    tables = soup.find_all("table")
    if len(tables) < 2:
        return []

    full_text = tables[1].get_text("\n")
    blocks = re.split(r"(\d+/\d{2}\s*Draw Date\s*:\s*\d+/\d+/\d+)", full_text)

    draws = []
    i = 1
    while i < len(blocks) - 1:
        header = blocks[i]
        body = blocks[i + 1]
        i += 2

        m_no = re.search(r"(\d+)/(\d{2})", header)
        m_date = re.search(r"Draw Date\s*:\s*(\d+)/(\d+)/(\d+)", header)
        if not m_no or not m_date:
            continue

        draw_seq = int(m_no.group(1))
        day_v = int(m_date.group(1))
        mon_v = int(m_date.group(2))
        yr_v = int(m_date.group(3))

        p_m = re.search(
            r"First Prize\s+Second Prize\s+Third Prize\s+(\d{4})\s+(\d{4})\s+(\d{4})",
            body,
        )
        if not p_m:
            continue
        p1, p2, p3 = p_m.group(1), p_m.group(2), p_m.group(3)

        sp_m = re.search(r"Special Prize\s+([\d\s]+?)Consolation Prize", body)
        specials = re.findall(r"\d{4}", sp_m.group(1))[:10] if sp_m else []

        cp_m = re.search(r"Consolation Prize\s+([\d\s]+?)TOTO 4D JACKPOT", body)
        consols = re.findall(r"\d{4}", cp_m.group(1))[:10] if cp_m else []

        record = {
            "draw_seq": draw_seq,
            "date": f"{yr_v:04d}-{mon_v:02d}-{day_v:02d}",
            "year": yr_v, "month": mon_v, "day": day_v,
            "prize_1": p1, "prize_2": p2, "prize_3": p3,
        }
        for idx, s in enumerate(specials):
            record[f"special_{idx + 1}"] = s
        for idx, c in enumerate(consols):
            record[f"consol_{idx + 1}"] = c

        draws.append(record)

    return draws


# ---------------------------------------------------------------------------
# Fallback parser (check4d.com) — works from datacenter IPs
# ---------------------------------------------------------------------------

def parse_date_check4d(draw_date_str: str) -> dict | None:
    """Parse Sport Toto 4D results from check4d.com for a single date (YYYY-MM-DD)."""
    session = get_session()
    url = f"{FALLBACK_URL}/{draw_date_str}"
    try:
        r = session.get(url, timeout=15)
        if r.status_code != 200 or len(r.text) < 5000:
            return None
    except requests.RequestException:
        return None

    soup = BeautifulSoup(r.text, "html.parser")

    for box in soup.find_all("div", class_="outerbox"):
        text = box.get_text(" ", strip=True)
        if "SportsToto 4D" not in text or "5D" in text[:50]:
            continue

        draw_match = re.search(r"Draw No:\s*(\d+)/(\d+)", text)
        draw_seq = int(draw_match.group(1)) if draw_match else 0

        date_match = re.search(r"Date:\s*(\d+)-(\d+)-(\d+)", text)
        if not date_match:
            continue
        day_v = int(date_match.group(1))
        mon_v = int(date_match.group(2))
        yr_v = int(date_match.group(3))

        p1 = p2 = p3 = ""
        specials = []
        consols = []
        section = None

        for td in box.find_all("td"):
            cls = " ".join(td.get("class", []))
            val = td.get_text(strip=True)

            if "resultprizelable" in cls:
                if "1st" in val:
                    section = "1st"
                elif "2nd" in val:
                    section = "2nd"
                elif "3rd" in val:
                    section = "3rd"
                elif "Special" in val:
                    section = "special"
                elif "Consolation" in val:
                    section = "consol"
                else:
                    section = "other"
            elif "resulttop" in cls:
                if section == "1st":
                    p1 = val
                elif section == "2nd":
                    p2 = val
                elif section == "3rd":
                    p3 = val
            elif "resultbottom" in cls and val != "****":
                if len(val) == 4 and val.isdigit():
                    if section == "special":
                        specials.append(val)
                    elif section == "consol":
                        consols.append(val)

        if not p1 or not p2 or not p3:
            continue

        record = {
            "draw_seq": draw_seq,
            "date": f"{yr_v:04d}-{mon_v:02d}-{day_v:02d}",
            "year": yr_v, "month": mon_v, "day": day_v,
            "prize_1": p1, "prize_2": p2, "prize_3": p3,
        }
        for i, sp in enumerate(specials[:10]):
            record[f"special_{i + 1}"] = sp
        for i, co in enumerate(consols[:10]):
            record[f"consol_{i + 1}"] = co

        return record
    return None


def parse_month_check4d(year: int, month: int) -> list[dict]:
    """Scrape a full month of Sport Toto draws via check4d.com, day by day."""
    today = date.today()
    draws = []

    # Generate all dates in this month
    first_day = date(year, month, 1)
    if month == 12:
        last_day = date(year + 1, 1, 1) - timedelta(days=1)
    else:
        last_day = date(year, month + 1, 1) - timedelta(days=1)

    # Don't go past today
    if last_day > today:
        last_day = today

    # Only check likely draw days (Wed=2, Sat=5, Sun=6) to save requests
    d = first_day
    while d <= last_day:
        if d.weekday() in (2, 5, 6):  # Wed, Sat, Sun
            record = parse_date_check4d(str(d))
            if record:
                draws.append(record)
            time.sleep(DELAY + random.uniform(0, 0.3))
        d += timedelta(days=1)

    return draws


# ---------------------------------------------------------------------------
# Smart dispatcher — auto-detects which source works
# ---------------------------------------------------------------------------

def parse_month(year: int, month: int) -> list[dict]:
    """Try official site first, fall back to check4d.com if blocked."""
    global _use_fallback

    # If we already know the official site is blocked, skip it
    if _use_fallback:
        return parse_month_check4d(year, month)

    # Try official site
    result = parse_month_official(year, month)
    if result is not None:
        # Official site worked (even if 0 draws for this month)
        if _use_fallback is None:
            _use_fallback = False
            print("  [INFO] Using official sportstoto.com.my")
        return result

    # Official site returned None (blocked / 403)
    if _use_fallback is None:
        print("  [INFO] Official site blocked, switching to check4d.com fallback")
        _use_fallback = True

    return parse_month_check4d(year, month)


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
            pct = round(((yi * 12 + mi) / (total_years * 12)) * 100)
            print(f"[PROGRESS] {pct}% | {year}-{month:02d} | year {yi+1}/{total_years}")
            time.sleep(DELAY)

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

    if df_new.empty:
        print("No data scraped.")
        return

    print(f"\nTotal draws: {len(df_new)}")
    print(f"Date range: {df_new['date'].min().date()} -> {df_new['date'].max().date()}")
    save(df_new)


if __name__ == "__main__":
    main()
