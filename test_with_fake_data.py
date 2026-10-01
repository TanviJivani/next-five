"""Checks the logic on made-up race data, no internet needed.
Run: python test_with_fake_data.py"""
import numpy as np
import pandas as pd
from analysis import (RACE_ORDER, add_realistic_gain, fmt, find_peers, gap_report, parse_time, placing,
                      race_plan, search_athlete, top_opportunities)


def fake_race(n=400, seed=0):
    rng = np.random.default_rng(seed)
    typical = {c: 5.0 for c in RACE_ORDER}
    typical["wallBalls_time"], typical["roxzone_time"] = 7.0, 8.0
    fitness = rng.normal(1.0, 0.12, n)
    race = pd.DataFrame({c: typical[c] * fitness * rng.normal(1, 0.05, n) for c in RACE_ORDER})
    race["total_time"] = race[list(RACE_ORDER)].sum(axis=1)
    race["name"] = [f"Athlete{i}, Person" for i in range(n)]
    race["gender"], race["division"] = "female", "open"
    race["age_group"] = rng.choice(["25-29", "30-34", "35-39"], n)
    return race


if __name__ == "__main__":
    race = fake_race()
    race.loc[0, "name"] = "Jivani, Tanvi"
    race.loc[0, "wallBalls_time"] += 3
    race.loc[0, "total_time"] = race.loc[0, list(RACE_ORDER)].sum()

    # formatting
    assert fmt(72.5667) == "1:12:34", fmt(72.5667)
    assert fmt(2.0083) == "2:00" and fmt(2.0083, signed=True) == "+2:00"
    assert fmt(-0.5, signed=True) == "-0:30"
    assert parse_time("1:15:30") == 75.5 and parse_time("75") == 75.0 and parse_time("abc") is None

    # search: typed "Tanvi Jivani" must find "Jivani, Tanvi"
    assert len(search_athlete(race, "tanvi jivani")) == 1

    me = race.iloc[0]
    rank, size = placing(race, me["total_time"])
    report = add_realistic_gain(gap_report(me, find_peers(race, me["total_time"])))
    top = top_opportunities(report)
    plan, n = race_plan(race, 85)

    print("Finish:", fmt(me["total_time"]), f"| rank {rank} of {size}")
    print(top[["segment", "gap_min", "trainability"]].to_string())
    print("Plan for 1:25:00 from", n, "athletes; Run 1 target:", fmt(plan.iloc[0]["target_min"]))
    assert top.iloc[0]["segment"] == "Wall Balls"
    assert list(report["segment"][:3]) == ["Run 1", "SkiErg", "Run 2"], "race order"
    print("\nAll checks passed ✅")
