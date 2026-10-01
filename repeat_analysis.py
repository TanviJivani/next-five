"""
repeat_analysis.py — what actually improves when people race HYROX again?

The idea: thousands of athletes have raced more than once. For each of them,
compare their FIRST and MOST RECENT race, station by station. Across all of
them, we learn which segments people really improve, and, crucially, how much
of a WEAKNESS usually closes by the next race.

Two problems we have to handle, and how:

1. Venues differ. Roxzone at one venue can be twice as long as another, and
   sled carpets vary. So we never compare raw times across races. Instead,
   each time becomes "relative to that race's median" (1.10 = 10% slower
   than the typical athlete in that race, gender and division).

2. General fitness. If someone gets fitter overall, every segment improves.
   To see whether a specific weakness closed, we measure each segment
   relative to the athlete's OWN overall level:
       weakness = segment relative time - total relative time
   If that gap shrinks between races, the weakness genuinely closed.

Run:    python repeat_analysis.py        (downloads full race data; slow)
Output: data/segment_trainability.csv   (read by the app)
        and a printed summary of the findings
"""

from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

import numpy as np
import pandas as pd

from analysis import RACE_ORDER, RUNS

SEASONS = [7, 8, 9]
SINGLES = {"open", "pro"}          # doubles/relay names are teams, skip them
WEAK = 0.10                        # "weak" = segment 10%+ slower than your own overall level
RACE_KEY = ["season", "location", "year", "gender", "division"]
SEGS = list(RACE_ORDER)


CACHE = Path("data/all_results.parquet")   # big, contains names: gitignored

# When True, use the saved race calendar and venue effects from data/ if they exist.
# validate_method.py switches this off so its made-up athletes aren't adjusted
# with real venues' numbers.
USE_SAVED_FILES = True


def download_all(seasons=SEASONS) -> pd.DataFrame:
    if CACHE.exists():
        print(f"Using saved download {CACHE} (delete it to re-download)")
        return pd.read_parquet(CACHE)
    import pyrox
    client = pyrox.PyroxClient()
    races = client.list_races()
    races = races[races["season"].isin(seasons)]
    print(f"Downloading {len(races)} race editions...")

    def fetch(row):
        df = client.get_race(season=int(row.season), location=row.location, year=int(row.year))
        df["season"], df["location"], df["year"] = int(row.season), row.location, int(row.year)
        return df

    frames = []
    with ThreadPoolExecutor(max_workers=8) as pool:
        jobs = [pool.submit(fetch, r) for r in races.itertuples()]
        for i, job in enumerate(as_completed(jobs), 1):
            try:
                frames.append(job.result())
            except Exception as e:
                print("  skipped a race:", e)
            if i % 25 == 0:
                print(f"  {i}/{len(races)}")
    results = pd.concat(frames, ignore_index=True)
    CACHE.parent.mkdir(exist_ok=True)
    results.to_parquet(CACHE, index=False)
    return results


def add_dates(df: pd.DataFrame) -> pd.DataFrame:
    """
    Order races by (year, month) when we know the month, else by (year, season).
    Months come from an optional hand-filled file data/race_dates.csv with
    columns season, location, year, month.
    """
    df = df.copy()
    df["month"] = np.nan
    dates = Path("data/race_dates.csv")
    if USE_SAVED_FILES and dates.exists():
        d = pd.read_csv(dates).dropna(subset=["month"])
        df = df.drop(columns="month").merge(d[["season", "location", "year", "month"]],
                                            on=["season", "location", "year"], how="left")
    # without a month, all races in a season+year share one slot (can't be ordered)
    df["when"] = np.where(df["month"].notna(),
                          df["year"] * 1000 + df["month"] * 10,
                          df["year"] * 1000 + df["season"])
    return df


def first_and_last(results: pd.DataFrame) -> pd.DataFrame:
    """One row per repeat athlete: their first race (_a) and latest race (_b), in relative terms."""
    df = results[results["division"].astype(str).isin(SINGLES)].copy()
    df = df.dropna(subset=SEGS + ["total_time"])
    parts_ok = (df[SEGS + ["total_time"]] > 0).all(axis=1)
    adds_up = (df[SEGS].sum(axis=1) - df["total_time"]).abs() / df["total_time"] < 0.03
    df = df[parts_ok & adds_up]

    # 1. make times comparable across venues.
    # Best: shared-athlete venue effects (data/venue_effects.csv, from venue_effects.py),
    # which separate the COURSE from the FIELD. Fallback: each race's median.
    effects_file = Path("data/venue_effects.csv")
    effects = pd.read_csv(effects_file) if USE_SAVED_FILES and effects_file.exists() else None
    for c in SEGS + ["total_time"]:
        med = df.groupby(RACE_KEY, observed=True)[c].transform("median")
        if effects is not None:
            e = effects[effects["segment"] == c][["season", "location", "year", "effect"]]
            f = df[["season", "location", "year"]].astype({"location": str}).merge(
                e, on=["season", "location", "year"], how="left")["effect"].to_numpy()
            overall = df.groupby(["gender", "division"], observed=True)[c].transform("median").to_numpy()
            course_based = overall * (1 + f)
            med = pd.Series(np.where(np.isnan(f), med.to_numpy(), course_based), index=df.index)
        df[c + "_med"] = med
        df[c + "_rel"] = df[c] / med

    # identify athletes by name + gender + division; drop names that appear
    # twice in the SAME race (can't tell those people apart)
    df["pct"] = df.groupby(RACE_KEY, observed=True)["total_time"].rank(pct=True)
    df["key"] = (df["name"].astype(str).str.casefold().str.strip() + "|"
                 + df["gender"].astype(str) + "|" + df["division"].astype(str))
    df = df[~df.duplicated(RACE_KEY + ["key"], keep=False)]

    df = add_dates(df)
    df = df.sort_values("when")
    races_per = df.groupby("key").size()
    counts = df.groupby("key")["when"].nunique()
    lost = df[df["key"].isin(races_per[(races_per >= 2) & (counts < 2)].index)]
    if len(lost) and USE_SAVED_FILES:
        need = lost[lost["month"].isna()][["season", "location", "year"]].drop_duplicates()
        Path("data").mkdir(exist_ok=True)
        need.assign(month="").to_csv("data/race_dates_needed.csv", index=False)
        print(f"{lost['key'].nunique():,} repeat athletes skipped: their races can't be ordered "
              f"without dates. Races needing a month: data/race_dates_needed.csv ({len(need)} races)")
    df = df[df["key"].isin(counts[counts >= 2].index)]

    first = df.groupby("key").first()
    last = df.groupby("key").last()
    return first.join(last, lsuffix="_a", rsuffix="_b")


def summarise(pairs: pd.DataFrame) -> pd.DataFrame:
    rows = []
    improvers = pairs[(pairs["total_time_rel_a"] - pairs["total_time_rel_b"]) > 0]
    total_gain = ((improvers["total_time_rel_a"] - improvers["total_time_rel_b"])
                  * improvers["total_time_med_b"]).sum()

    for col, label in RACE_ORDER.items():
        rel_a, rel_b = pairs[f"{col}_rel_a"], pairs[f"{col}_rel_b"]
        # weakness relative to the athlete's own overall level
        weak_a = rel_a - pairs["total_time_rel_a"]
        weak_b = rel_b - pairs["total_time_rel_b"]
        was_weak = weak_a > WEAK
        closed = ((weak_a - weak_b) / weak_a)[was_weak].clip(-1, 1.5)

        gain_min = ((improvers[f"{col}_rel_a"] - improvers[f"{col}_rel_b"]) * improvers[f"{col}_med_b"])
        rows.append({
            "segment": label,
            "type": "Run" if col in RUNS else ("Station" if col != "roxzone_time" else "Roxzone"),
            "athletes_weak_here": int(was_weak.sum()),
            "closability": float(closed.median()) if was_weak.sum() else np.nan,
            "pct_who_improved": float((rel_b < rel_a).mean()),
            "share_of_improvement": float(gain_min.sum() / total_gain) if total_gain > 0 else np.nan,
            "avg_gain_min": float(gain_min.mean()),
        })
    return pd.DataFrame(rows)


def print_findings(summary: pd.DataFrame, pairs: pd.DataFrame):
    print(f"\nRepeat athletes analysed: {len(pairs):,}")
    s = summary.sort_values("closability", ascending=False)
    print("\nWhen athletes were WEAK at a segment, how much of that weakness closed by their next race:")
    for r in s.itertuples():
        print(f"  {r.segment:<20} {r.closability:>5.0%} closed   ({r.athletes_weak_here:,} athletes were weak here)")
    by_type = summary.groupby("type")["share_of_improvement"].sum().sort_values(ascending=False)
    print("\nWhere improvers' time savings came from:")
    for t, v in by_type.items():
        print(f"  {t:<8} {v:.0%}")
    print("\nCaveat: an unusually bad day in race 1 looks like 'improvement' in race 2")
    print("(regression to the mean), so all closability numbers are somewhat inflated,")
    print("most for noisy segments. Compare segments with each other, not as absolutes.")


HORIZONS = [(0, 3, "up to 3 months"), (4, 6, "4–6 months"), (7, 12, "7–12 months"), (13, 999, "over a year")]


def improvement_table(pairs: pd.DataFrame) -> pd.DataFrame:
    """
    How much faster did athletes get by their next race, by level (and by
    months between races where dates are known)? Gains are venue-adjusted and
    expressed as a share of the athlete's own time.
    """
    from analysis import LEVEL_BANDS
    gain = (pairs["total_time_rel_a"] - pairs["total_time_rel_b"]) / pairs["total_time_rel_a"]
    months = pd.Series(np.nan, index=pairs.index)
    if "month_a" in pairs.columns:
        months = (pairs["year_b"] * 12 + pairs["month_b"]) - (pairs["year_a"] * 12 + pairs["month_a"])
    rows = []
    for lo, hi, level in LEVEL_BANDS:
        at_level = (pairs["pct_a"] >= lo) & (pairs["pct_a"] < hi)
        groups = [("any", at_level)] + [(h, at_level & months.between(a, b)) for a, b, h in HORIZONS]
        for horizon, mask in groups:
            g = gain[mask]
            if len(g) >= 50:
                rows.append({"level": level, "horizon": horizon, "n": int(len(g)),
                             "median_gain": float(g.median()), "p75_gain": float(g.quantile(0.75)),
                             "p25_gain": float(g.quantile(0.25))})
    return pd.DataFrame(rows)


def export_anonymised(pairs: pd.DataFrame):
    """For Kaggle: one row per repeat athlete, NO names, relative times only."""
    keep = ["gender_a", "division_a"]
    for side in "ab":
        keep += [f"season_{side}", f"location_{side}", f"year_{side}", f"total_time_{side}"]
        keep += [f"{c}_rel_{side}" for c in SEGS + ["total_time"]]
    out = pairs[keep].rename(columns={"gender_a": "gender", "division_a": "division"}).reset_index(drop=True)
    out.insert(0, "athlete_id", range(1, len(out) + 1))
    out.to_csv("data/kaggle_repeat_athletes.csv", index=False)
    print(f"Saved anonymised dataset for Kaggle: data/kaggle_repeat_athletes.csv ({len(out):,} athletes)")


if __name__ == "__main__":
    results = download_all()
    pairs = first_and_last(results)
    summary = summarise(pairs)
    Path("data").mkdir(exist_ok=True)
    summary.to_csv("data/segment_trainability.csv", index=False)
    outlook = improvement_table(pairs)
    outlook.to_csv("data/improvement_by_level.csv", index=False)
    print("\nTypical improvement by next race (share of own time), by level:")
    for r in outlook[outlook["horizon"] == "any"].itertuples():
        print(f"  {r.level:<11} median {r.median_gain:+.1%}   top quarter {r.p75_gain:+.1%}   ({r.n:,} athletes)")
    if (outlook["horizon"] != "any").any():
        print("  (also saved by months between races)")
    export_anonymised(pairs)
    print_findings(summary, pairs)
    print("\nSaved data/segment_trainability.csv")
