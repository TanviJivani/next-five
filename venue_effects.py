"""
venue_effects.py — how does each venue change each station's time?

The idea: athletes who raced at more than one venue act as measuring
sticks. We model every segment time as

    log(time) = athlete ability + venue effect + experience effect + noise

and solve for all three at once using only athletes who raced 2+ times.
  - athlete ability absorbs how good each person is
  - experience (1st race, 2nd race, 3rd+) absorbs people getting better
  - what's left, consistently across hundreds of shared athletes, is the venue

Why not just compare each venue's median time? Because that mixes up the
COURSE with the FIELD: a venue with a slower field of athletes would look like
a slower course. validate_method.py demonstrates this bias.

Run:    python venue_effects.py      (uses the download saved by repeat_analysis.py)
Output: data/venue_effects.csv
        e.g. "Mumbai 2026, Sled Push, +8%" = the same athlete would be ~8% slower
        on sled push there than at an average venue.
"""

from pathlib import Path

import numpy as np
import pandas as pd

from analysis import RACE_ORDER

SEGS = list(RACE_ORDER) + ["total_time"]
RACE = ["season", "location", "year"]
SINGLES = {"open", "pro"}


def prepare(results: pd.DataFrame) -> pd.DataFrame:
    """Repeat athletes only, one row per athlete per race, with experience count."""
    df = results[results["division"].astype(str).isin(SINGLES)].dropna(subset=SEGS).copy()
    # Real results sometimes record a missing split as 0:00, and log(0) breaks the
    # model. Keep only results where every split is positive and the splits add up
    # to the finish time (within 3%).
    parts = [c for c in SEGS if c != "total_time"]
    clean = (df[SEGS] > 0).all(axis=1) & ((df[parts].sum(axis=1) - df["total_time"]).abs() / df["total_time"] < 0.03)
    print(f"Using {clean.sum():,} of {len(df):,} results ({(~clean).sum():,} had missing or inconsistent splits)")
    df = df[clean]
    df["key"] = (df["name"].astype(str).str.casefold().str.strip() + "|"
                 + df["gender"].astype(str) + "|" + df["division"].astype(str))
    df = df[~df.duplicated(RACE + ["key"], keep=False)]           # ambiguous namesakes
    df["race"] = df["season"].astype(str) + "|" + df["location"].astype(str) + "|" + df["year"].astype(str)
    order_cols = ["year", "month", "season"] if "month" in df.columns else ["year", "season"]
    df = df.sort_values(order_cols)
    df["experience"] = df.groupby("key").cumcount().clip(upper=2)   # 0 = first race seen, 1, 2+
    races_per = df.groupby("key")["race"].transform("nunique")
    return df[races_per >= 2]


def fit_segment(y: pd.Series, athlete: pd.Series, race: pd.Series, exp: pd.Series, iters: int = 60):
    """
    Solve log(time) = athlete + race + experience by alternating averages
    (each step: hold two factors fixed, set the third to the average leftover).
    Returns race effects (mean zero across races) and experience effects.
    """
    v = pd.Series(0.0, index=race.unique())
    x = pd.Series(0.0, index=sorted(exp.unique()))
    for _ in range(iters):
        a = (y - race.map(v) - exp.map(x)).groupby(athlete).mean()
        v = (y - athlete.map(a) - exp.map(x)).groupby(race).mean()
        v -= v.mean()
        x = (y - athlete.map(a) - race.map(v)).groupby(exp).mean()
        x -= x.iloc[0]
    return v, x


def estimate(results: pd.DataFrame, min_shared: int = 30) -> pd.DataFrame:
    df = prepare(results)
    shared = df.groupby("race")["key"].nunique()
    df = df[df["race"].isin(shared[shared >= min_shared].index)]
    df = df[df.groupby("key")["race"].transform("nunique") >= 2]   # re-check after dropping races
    rows = []
    for col in SEGS:
        v, x = fit_segment(np.log(df[col]), df["key"], df["race"], df["experience"])
        if v.isna().any():
            print(f"WARNING: {col} has {int(v.isna().sum())} races with no estimate")
        for race_id, eff in v.dropna().items():
            s, loc, yr = race_id.split("|")
            rows.append({"season": int(s), "location": loc, "year": int(yr), "segment": col,
                         "effect": float(np.exp(eff) - 1), "shared_athletes": int(shared[race_id])})
        if col == "total_time":
            print("Experience effect on total time: "
                  + ", ".join(f"race {int(k)+1}{'+' if k == 2 else ''}: {np.exp(val)-1:+.1%}" for k, val in x.items()))
    return pd.DataFrame(rows)


def print_findings(eff: pd.DataFrame):
    tot = eff[eff["segment"] == "total_time"].sort_values("effect")
    lab = lambda r: f"{r.location.title()} {r.year}"
    print(f"\n{len(tot)} race editions with enough shared athletes.")
    print("Fastest courses (same athlete, vs average venue):")
    for r in tot.head(5).itertuples():
        print(f"  {lab(r):<20} {r.effect:+.1%}   ({r.shared_athletes} shared athletes)")
    print("Slowest courses:")
    for r in tot.tail(5).itertuples():
        print(f"  {lab(r):<20} {r.effect:+.1%}")
    st = eff[eff["segment"] != "total_time"].copy()
    st["abs"] = st["effect"].abs()
    print("\nBiggest single-station venue quirks:")
    for r in st.nlargest(8, "abs").itertuples():
        print(f"  {lab(r):<20} {RACE_ORDER[r.segment]:<20} {r.effect:+.0%}")
    spread = st.groupby("segment")["effect"].std().rename(RACE_ORDER).sort_values(ascending=False)
    print("\nWhich segments vary most between venues:")
    for seg, sd in spread.head(5).items():
        print(f"  {seg:<20} ±{sd:.0%}")


if __name__ == "__main__":
    from repeat_analysis import CACHE, add_dates
    results = add_dates(pd.read_parquet(CACHE))
    eff = estimate(results)
    Path("data").mkdir(exist_ok=True)
    eff.to_csv("data/venue_effects.csv", index=False)
    print_findings(eff)
    print("\nSaved data/venue_effects.csv")
