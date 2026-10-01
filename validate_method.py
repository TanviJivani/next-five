"""
validate_method.py — does the analysis find the truth when we KNOW the truth?

We invent 4,000 athletes racing at venues with different station lengths,
secretly decide how trainable each station is, then run the real analysis
and evaluation on them. If the method can't recover answers we planted,
we shouldn't trust it on real data.

Run: python validate_method.py   (no internet needed)
"""

import numpy as np
import pandas as pd

from analysis import RACE_ORDER
import repeat_analysis
repeat_analysis.USE_SAVED_FILES = False   # test the method alone, never with your real data files
from evaluate import report, test_opportunities, test_placing
from repeat_analysis import first_and_last, summarise

SEGS = list(RACE_ORDER)
TRUTH = {c: 0.30 for c in SEGS}          # share of a weakness that closes by the next race
TRUTH.update({"wallBalls_time": 0.65, "burpeeBroadJump_time": 0.60, "roxzone_time": 0.55,
              "sledPush_time": 0.10, "sledPull_time": 0.10})


def simulate(n=4000, seed=1) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    base = {c: 5.0 for c in SEGS}
    base["wallBalls_time"], base["roxzone_time"] = 7.0, 8.0
    venues = [("london", 2025, 8), ("mumbai", 2025, 8), ("mumbai", 2026, 9), ("paris", 2026, 9)]
    venue_len = {v: {c: rng.normal(1, 0.08) for c in SEGS} for v in venues}   # e.g. long roxzone
    fit = rng.normal(1, 0.12, n)
    weak = {c: np.clip(rng.normal(0, 0.10, n), -0.1, 0.4) for c in SEGS}
    rows = []
    for i in range(n):
        picks = sorted(rng.choice(len(venues), 2 if i % 2 else 1, replace=False),
                       key=lambda k: (venues[k][1], k))
        for r, k in enumerate(picks):
            loc, yr, season = venues[k]
            row = {"name": f"A{i}, X", "gender": "female", "division": "open",
                   "season": season, "location": loc, "year": yr}
            for c in SEGS:
                w = weak[c][i] * (1 - TRUTH[c]) if r else weak[c][i]
                row[c] = base[c] * venue_len[venues[k]][c] * fit[i] * (0.96 if r else 1) * (1 + w) * rng.normal(1, 0.04)
            rows.append(row)
    df = pd.DataFrame(rows)
    df["total_time"] = df[SEGS].sum(axis=1)
    return df


if __name__ == "__main__":
    results = simulate()
    s = summarise(first_and_last(results)).sort_values("closability", ascending=False)
    found_top = set(s["segment"].head(3))
    found_bottom = set(s["segment"].tail(2))
    print("Measured closability (top 3):", ", ".join(f"{r.segment} {r.closability:.0%}" for r in s.head(3).itertuples()))
    print("Measured closability (bottom 2):", ", ".join(f"{r.segment} {r.closability:.0%}" for r in s.tail(2).itertuples()))
    assert found_top == {"Wall Balls", "Burpee Broad Jumps", "Roxzone"}, found_top
    assert found_bottom == {"Sled Push", "Sled Pull"}, found_bottom
    print("✅ Analysis recovers the planted trainability")
    report(test_opportunities(results), test_placing(results))


# ------------------------------------------------------------------ venues
def simulate_venues(n=6000, seed=7):
    """Venues with KNOWN course effects and DIFFERENT field strengths."""
    from venue_effects import SEGS as VSEGS
    rng = np.random.default_rng(seed)
    venues = {  # (location, year, season): (field strength multiplier, planted course effect per segment)
        ("london", 2025, 8): 0.97, ("mumbai", 2025, 8): 1.10, ("paris", 2026, 9): 0.95,
        ("mumbai", 2026, 9): 1.08, ("berlin", 2025, 8): 1.00, ("delhi", 2026, 9): 1.12,
    }
    course = {v: {c: rng.normal(0, 0.06) for c in SEGS} for v in venues}
    vlist = list(venues)
    rows = []
    for i in range(n):
        ability = rng.normal(1, 0.12)
        k = rng.choice(len(vlist), 2 if i % 3 == 0 else 1, replace=False)
        for r, vi in enumerate(sorted(k, key=lambda z: (vlist[z][1], z))):
            v = vlist[vi]
            # field strength describes WHO races there: it shifts one-off local athletes,
            # never the travelling athletes' own ability
            field = venues[v] if len(k) == 1 else 1.0
            row = {"name": f"V{i}, X", "gender": "female", "division": "open",
                   "location": v[0], "year": v[1], "season": v[2]}
            for c in SEGS:
                base = 7.0 if c == "wallBalls_time" else 8.0 if c == "roxzone_time" else 5.0
                row[c] = base * ability * field * (1 + course[v][c]) * (0.97 if r else 1) * rng.normal(1, 0.04)
            rows.append(row)
    df = pd.DataFrame(rows)
    df["total_time"] = df[SEGS].sum(axis=1)
    return df, course


def check_venues():
    from venue_effects import estimate
    df, course = simulate_venues()
    est = estimate(df, min_shared=20)
    errs_fe, errs_med = [], []
    for c in SEGS:
        truth = pd.Series({f"{l}|{y}": course[(l, y, s)][c] for (l, y, s) in course})
        truth = np.exp(np.log1p(truth) - np.log1p(truth).mean()) - 1       # same mean-zero scale
        fe = est[est["segment"] == c].assign(k=lambda d: d.location + "|" + d.year.astype(str)).set_index("k")["effect"]
        med = df.groupby(["location", "year"])[c].median()
        med.index = [f"{l}|{y}" for l, y in med.index]
        med = np.exp(np.log(med) - np.log(med).mean()) - 1
        errs_fe.append((fe - truth).abs().mean())
        errs_med.append((med - truth).abs().mean())
    fe_err, med_err = np.mean(errs_fe) * 100, np.mean(errs_med) * 100
    print("\n=== Venue effects: can we recover planted course differences? ===")
    print(f"Median-per-venue method: average error {med_err:.1f} percentage points (confuses field with course)")
    print(f"Shared-athlete method:   average error {fe_err:.1f} percentage points")
    assert fe_err < med_err / 2, "shared-athlete method should be far more accurate"
    print("✅ Shared-athlete method recovers venue effects; median method is biased by field strength")


if __name__ == "__main__":
    check_venues()
