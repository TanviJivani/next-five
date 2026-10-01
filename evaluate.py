"""
evaluate.py — how accurate is Next Five, really?

Backtesting: pretend we're in the past, make predictions, then check them
against what actually happened. Crucially, the athletes we test on are
NEVER used to build the model (a train/test split), otherwise we'd be
marking our own homework.

Test A — "Most impactful areas"
  For each test athlete, use their FIRST race to predict which 3 segments
  they'll improve most. Then check against their NEXT race.
  We compare three approaches:
    - Random guess (the floor)
    - Biggest gap only (the obvious approach)
    - Next Five: gap x measured closability
  If Next Five doesn't beat "biggest gap only", the closability data isn't
  adding anything, and we should say so.

Test B — "Where would I place?"
  For each race held more than once, predict each athlete's placing from
  the PREVIOUS edition's field, then compare with where they actually placed.

Run:  python evaluate.py    (uses the download saved by repeat_analysis.py)
"""

import numpy as np
import pandas as pd

from analysis import RACE_ORDER, add_realistic_gain, find_peers, gap_report
from repeat_analysis import RACE_KEY, SEGS, download_all, first_and_last, summarise

SEED = 42


def test_opportunities(results: pd.DataFrame, max_test: int = 3000) -> dict:
    pairs = first_and_last(results)
    rng = np.random.default_rng(SEED)
    is_test = rng.random(len(pairs)) < 0.3
    train, test = pairs[~is_test], pairs[is_test]
    if len(test) > max_test:
        test = test.sample(max_test, random_state=SEED)
    closability = summarise(train)          # learned ONLY from training athletes

    fields = {k: g for k, g in results.groupby(RACE_KEY, observed=True)}
    labels = list(RACE_ORDER.values())
    hits = {"Random guess": [], "Biggest gap only": [], "Next Five": []}

    for _, a in test.iterrows():
        key = tuple(a[f"{k}_a"] for k in RACE_KEY)
        if key not in fields:
            continue
        me = pd.Series({c: a[f"{c}_a"] for c in SEGS + ["total_time"]})
        report = add_realistic_gain(gap_report(me, find_peers(fields[key], me["total_time"])), closability)
        if report.empty:
            continue
        # what actually happened: venue-adjusted minutes gained per segment
        actual = pd.Series({lab: (a[f"{c}_rel_a"] - a[f"{c}_rel_b"]) * a[f"{c}_med_b"]
                            for c, lab in RACE_ORDER.items()})
        actual_top3 = set(actual.nlargest(3).index)

        guesses = {
            "Random guess": set(rng.choice(labels, 3, replace=False)),
            "Biggest gap only": set(report.nlargest(3, "gap_min")["segment"]),
            "Next Five": set(report.nlargest(3, "realistic_gain")["segment"]),
        }
        for name, g in guesses.items():
            hits[name].append(len(g & actual_top3) / 3)

    return {name: float(np.mean(v)) for name, v in hits.items()} | {"athletes_tested": len(hits["Next Five"])}


def test_placing(results: pd.DataFrame) -> dict:
    df = results.dropna(subset=["total_time"])
    errors = []
    for (loc, g, d), grp in df.groupby(["location", "gender", "division"], observed=True):
        years = sorted(grp["year"].unique())
        for prev, cur in zip(years, years[1:]):
            P = grp[grp["year"] == prev]["total_time"].to_numpy()
            C = grp[grp["year"] == cur]["total_time"].to_numpy()
            if len(P) < 30 or len(C) < 30:
                continue
            predicted = np.searchsorted(np.sort(P), C) / len(P)        # share of last year's field ahead of you
            actual = np.searchsorted(np.sort(C), C) / len(C)            # share of this year's field ahead of you
            errors.extend(np.abs(predicted - actual) * 100)
    e = np.array(errors)
    if not len(e):
        return {"athletes_tested": 0}
    return {"athletes_tested": len(e), "median_error_pct_points": float(np.median(e)),
            "within_5_pct_points": float((e <= 5).mean()), "within_10_pct_points": float((e <= 10).mean())}


def report(a: dict, b: dict):
    print("\n=== Test A: predicting your most impactful areas ===")
    print(f"Athletes tested (never seen by the model): {a['athletes_tested']:,}")
    print("Share of predicted top-3 that were really among the 3 most-improved segments:")
    for name in ["Random guess", "Biggest gap only", "Next Five"]:
        print(f"  {name:<18} {a[name]:.0%}")
    lift = a["Next Five"] - a["Biggest gap only"]
    verdict = "adds value" if lift > 0.02 else "does NOT clearly add value — be honest about this"
    print(f"Closability weighting {verdict} ({lift:+.0%} vs biggest gap only).")

    print("\n=== Test B: predicting your placing from last year's field ===")
    if b["athletes_tested"]:
        print(f"Athletes tested: {b['athletes_tested']:,}")
        print(f"Typical error: {b['median_error_pct_points']:.1f} percentage points "
              f"(e.g. predicted top 30%, actually top {30 + b['median_error_pct_points']:.0f}%)")
        print(f"Within 5 points: {b['within_5_pct_points']:.0%}  ·  within 10 points: {b['within_10_pct_points']:.0%}")
    else:
        print("Not enough races held more than once.")


if __name__ == "__main__":
    results = download_all()
    report(test_opportunities(results), test_placing(results))
