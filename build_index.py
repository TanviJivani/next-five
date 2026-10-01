"""
build_index.py — run this ONCE on your laptop (and again after new races).

It downloads recent HYROX results and keeps a small "phone book":
who raced where, when, in which division and age group, and their finish
time. The app searches this file so people can find their races by name
without knowing the season.

Run:  python build_index.py
Output: data/athlete_index.parquet
"""

from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

import pandas as pd
import pyrox

from analysis import age_group_col

SEASONS = [7, 8, 9]          # recent seasons; add older ones if you like
KEEP = ["name", "gender", "division", "total_time"]

client = pyrox.PyroxClient()
races = client.list_races()
races = races[races["season"].isin(SEASONS)]
print(f"Downloading {len(races)} race editions from seasons {SEASONS}...")


def fetch(row):
    df = client.get_race(season=int(row.season), location=row.location, year=int(row.year))
    ag = age_group_col(df)
    cols = [c for c in KEEP if c in df.columns] + ([ag] if ag else [])
    out = df[cols].copy()
    if ag and ag != "age_group":
        out = out.rename(columns={ag: "age_group"})
    out["season"], out["location"], out["year"] = int(row.season), row.location, int(row.year)
    return out


frames, failed = [], []
with ThreadPoolExecutor(max_workers=8) as pool:
    jobs = {pool.submit(fetch, row): row for row in races.itertuples()}
    for i, job in enumerate(as_completed(jobs), 1):
        row = jobs[job]
        try:
            frames.append(job.result())
        except Exception as e:
            failed.append(f"{row.location} {row.year}: {e}")
        if i % 20 == 0:
            print(f"  {i}/{len(races)} done")

index = pd.concat(frames, ignore_index=True).dropna(subset=["name", "total_time"])
for c in ["gender", "division", "location"] + (["age_group"] if "age_group" in index else []):
    index[c] = index[c].astype("category")   # makes the file much smaller

Path("data").mkdir(exist_ok=True)
index.to_parquet("data/athlete_index.parquet", index=False)

size_mb = Path("data/athlete_index.parquet").stat().st_size / 1e6
print(f"\nSaved {len(index):,} results to data/athlete_index.parquet ({size_mb:.1f} MB)")
print("Columns:", list(index.columns))
if "age_group" not in index:
    print("NOTE: no age-group column found; age-group features will be hidden.")
if failed:
    print(f"{len(failed)} races failed (safe to ignore a few):")
    for f in failed[:10]:
        print("  ", f)
