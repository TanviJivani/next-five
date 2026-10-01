"""
make_race_calendar.py — create or update data/race_dates.csv

The race data has no dates, only season, location and year. This writes one
row per race edition with an empty 'month' column (1-12) to fill in from the
HYROX website or results pages. Months you've already filled in are kept.

Once filled:
  - the app shows races as 'Mumbai · Sep 2026'
  - repeat_analysis.py can order races within the same season and measure
    improvement per month between races

Run:  python make_race_calendar.py
"""

from pathlib import Path

import pandas as pd

index = pd.read_parquet("data/athlete_index.parquet")
editions = (index.groupby(["season", "location", "year"], observed=True).size()
            .rename("finishers").reset_index())
editions["location"] = editions["location"].astype(str)

path = Path("data/race_dates.csv")
if path.exists():
    old = pd.read_csv(path)[["season", "location", "year", "month"]]
    editions = editions.merge(old, on=["season", "location", "year"], how="left")
else:
    editions["month"] = pd.NA

editions = editions.sort_values(["year", "season", "location"])[["season", "location", "year", "month", "finishers"]]
editions.to_csv(path, index=False)
done = editions["month"].notna().sum()
print(f"{path}: {len(editions)} race editions, {done} with a month, {len(editions) - done} to fill in")
