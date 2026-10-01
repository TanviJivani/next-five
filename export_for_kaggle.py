"""
export_for_kaggle.py — prepare the files to upload to Kaggle.

Takes the full download saved by repeat_analysis.py and writes a
kaggle/ folder containing:
  hyrox_results_anonymised.parquet  every result, names removed
  repeat_athletes.csv               first vs latest race for repeat athletes,
                                    no names, venue-adjusted relative times,
                                    months between races where dates are known

Run:  python export_for_kaggle.py
"""

from pathlib import Path

import numpy as np
import pandas as pd

from analysis import RACE_ORDER, age_group_col
from repeat_analysis import CACHE, SEGS, add_dates, first_and_last

OUT = Path("kaggle")
OUT.mkdir(exist_ok=True)

results = pd.read_parquet(CACHE)

# 1. all results, anonymised
ag = age_group_col(results)
keep = ["season", "location", "year", "gender", "division"] + ([ag] if ag else []) + ["total_time"] + SEGS
anon = results[[c for c in keep if c in results.columns]].copy()
if ag and ag != "age_group":
    anon = anon.rename(columns={ag: "age_group"})
anon = add_dates(anon).drop(columns="when")          # adds 'month' where known
anon.to_parquet(OUT / "hyrox_results_anonymised.parquet", index=False)
print(f"Saved {len(anon):,} anonymised results")

# 2. repeat athletes
pairs = first_and_last(results)
cols = ["gender_a", "division_a"]
for side in "ab":
    cols += [f"season_{side}", f"location_{side}", f"year_{side}", f"month_{side}", f"total_time_{side}"]
    cols += [f"{c}_rel_{side}" for c in SEGS + ["total_time"]]
rep = pairs[[c for c in cols if c in pairs.columns]].rename(
    columns={"gender_a": "gender", "division_a": "division"}).reset_index(drop=True)
rep["months_between"] = np.where(
    rep["month_a"].notna() & rep["month_b"].notna(),
    (rep["year_b"] * 12 + rep["month_b"]) - (rep["year_a"] * 12 + rep["month_a"]), np.nan)
rep.insert(0, "athlete_id", range(1, len(rep) + 1))
rep.to_csv(OUT / "repeat_athletes.csv", index=False)
print(f"Saved {len(rep):,} repeat athletes "
      f"({rep['months_between'].notna().sum():,} with known months between races)")
