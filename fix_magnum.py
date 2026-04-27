"""Run this once to get all 6752 Magnum draws in one shot."""
from scraper_magnum import fetch_page, parse_draw
import pandas as pd, time, os

all_draws = []
seen = set()
end_date = "2026-04-27"
page = 0

while True:
    items = fetch_page(end_date)
    if not items:
        break
    for item in items:
        did = item.get("DrawID", "")
        if did in seen:
            continue
        seen.add(did)
        d = parse_draw(item)
        if d:
            all_draws.append(d)
    last = items[-1]["DrawDate"].split("/")
    end_date = f"{last[2]}-{last[1]}-{last[0]}"
    page += 1
    print(f"Page {page}: {len(all_draws)} draws, at {end_date}")
    if len(items) < 50:
        break
    time.sleep(0.4)

os.makedirs("data", exist_ok=True)
df = pd.DataFrame(all_draws)
df["date"] = pd.to_datetime(df["date"])
df = df.sort_values("date").reset_index(drop=True)
df.to_csv("data/magnum_draws.csv", index=False)
print(f"\nDONE: {len(df)} draws saved to data/magnum_draws.csv")
