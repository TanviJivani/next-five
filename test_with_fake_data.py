"""Checks the logic on made-up race data, no internet needed.
Run: python test_with_fake_data.py"""
import numpy as np
import pandas as pd
from analysis import ALL_SEGMENTS, find_athlete, find_peers, gap_report, summary_by_type, fmt

rng = np.random.default_rng(0)
n = 400
typical = {c: 5.0 for c in ALL_SEGMENTS}          # every segment ~5 min
typical["wallBalls_time"] = 7.0
typical["roxzone_time"] = 8.0
fitness = rng.normal(1.0, 0.12, n)                 # >1 means slower athlete
race = pd.DataFrame({c: typical[c] * fitness * rng.normal(1, 0.05, n) for c in ALL_SEGMENTS})
race["total_time"] = race[list(ALL_SEGMENTS)].sum(axis=1)
race["name"] = [f"Athlete {i}" for i in range(n)]

# Our test athlete: average overall, but terrible at wall balls
race.loc[0, "name"] = "Tanvi Test"
race.loc[0, "wallBalls_time"] += 3
race.loc[0, "total_time"] = race.loc[0, list(ALL_SEGMENTS)].sum()

me = find_athlete(race, "tanvi").iloc[0]
peers = find_peers(race, me["total_time"])
report = gap_report(me, peers)

print("My total:", fmt(me["total_time"]), "| peers:", len(peers),
      "| peer median total:", fmt(peers["total_time"].median()))
print(report.head(5).to_string())
print(summary_by_type(report).to_string())
assert report.iloc[0]["segment"] == "Wall Balls", "wall balls should be the biggest gap"
print("\nAll checks passed ✅")
