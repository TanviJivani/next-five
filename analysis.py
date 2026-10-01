"""
analysis.py — the "brain" of Next Five (v2).

Pure logic, no website code. Everything here works on pandas DataFrames
where every time is in MINUTES (e.g. 4.5 = 4 min 30 s), which is how
pyrox-client delivers race data.
"""

import numpy as np
import pandas as pd

# ---------------------------------------------------------------- segments
STATIONS = {
    "skiErg_time": "SkiErg",
    "sledPush_time": "Sled Push",
    "sledPull_time": "Sled Pull",
    "burpeeBroadJump_time": "Burpee Broad Jumps",
    "rowErg_time": "Row",
    "farmersCarry_time": "Farmers Carry",
    "sandbagLunges_time": "Sandbag Lunges",
    "wallBalls_time": "Wall Balls",
}
RUNS = {f"run{i}_time": f"Run {i}" for i in range(1, 9)}
ROXZONE = {"roxzone_time": "Roxzone"}
# Race order: Run 1, SkiErg, Run 2, Sled Push, ... then Roxzone at the end
RACE_ORDER = {}
for (run_col, run_label), (st_col, st_label) in zip(RUNS.items(), STATIONS.items()):
    RACE_ORDER[run_col] = run_label
    RACE_ORDER[st_col] = st_label
RACE_ORDER.update(ROXZONE)

# ------------------------------------------------------------ trainability
# How quickly a gap here usually closes with focused training.
# Based on published HYROX research (running is the biggest share of race
# time; strength stations cost slower athletes disproportionately) plus
# coaching consensus. A guide, not a personal assessment.
QUICK, STEADY, LONG = "Quick win", "Steady build", "Long game"
TRAINABILITY = {
    "Roxzone": (QUICK, "Pure efficiency: knowing the layout, moving with purpose, no dawdling. Free time."),
    "Wall Balls": (QUICK, "Rep pacing and planned short breaks improve fast, often within weeks."),
    "Burpee Broad Jumps": (QUICK, "Rhythm and jump distance respond quickly to practice."),
    "Sandbag Lunges": (QUICK, "Muscular endurance and steady pacing build within weeks."),
    "Farmers Carry": (QUICK, "Grip endurance and not putting the handles down; trains quickly."),
    "SkiErg": (STEADY, "Technique comes fast; the engine behind it takes months."),
    "Row": (STEADY, "Technique comes fast; the engine behind it takes months."),
    "Sled Push": (STEADY, "Needs real leg strength, which builds over months. Surfaces also vary by venue."),
    "Sled Pull": (STEADY, "Strength plus technique; builds over months. Surfaces also vary by venue."),
}
for label in RUNS.values():
    TRAINABILITY[label] = (LONG, "Running is the biggest share of race time. The biggest lever, but the aerobic engine takes months.")


# -------------------------------------------------------------- formatting
def fmt(minutes, signed=False) -> str:
    """Minutes -> '1:12:34' (over an hour) or '4:30'. signed=True adds +/-."""
    if minutes is None or pd.isna(minutes):
        return "–"
    sign = ("+" if minutes > 0 else "-" if minutes < 0 else "") if signed else ("-" if minutes < 0 else "")
    s = round(abs(minutes) * 60)
    h, m, sec = s // 3600, (s % 3600) // 60, s % 60
    return f"{sign}{h}:{m:02d}:{sec:02d}" if h else f"{sign}{m}:{sec:02d}"


def pace(minutes_per_km) -> str:
    """Each HYROX run is 1 km, so a run time is also a pace per km."""
    return f"{fmt(minutes_per_km)} /km"


# ------------------------------------------------------------- data helpers
AGE_GROUP_CANDIDATES = ["age_group", "agegroup", "age_category", "age_class", "ag"]


def age_group_col(df: pd.DataFrame):
    """Return the name of the age-group column, if the data has one."""
    for c in AGE_GROUP_CANDIDATES:
        if c in df.columns:
            return c
    return None


def search_athlete(index: pd.DataFrame, query: str) -> pd.DataFrame:
    """
    Names in HYROX results look like 'Surname, Firstname'. People type
    'Firstname Surname'. So: every word typed must appear somewhere in
    the name, in any order.
    """
    words = [w for w in query.replace(",", " ").casefold().split() if w]
    if not words:
        return index.iloc[0:0]
    names = index["name"].astype(str).str.casefold()
    mask = pd.Series(True, index=index.index)
    for w in words:
        mask &= names.str.contains(w, regex=False)
    return index[mask]


def placing(field: pd.DataFrame, time_min: float):
    """Where would this time rank in this field? Returns (rank, field size); rank is None if unknown."""
    times = field["total_time"].dropna()
    times = times[times > 0]
    if time_min is None or not np.isfinite(time_min):
        return None, int(len(times))
    return int((times < time_min).sum()) + 1, int(len(times))


def find_peers(race: pd.DataFrame, my_total: float, target_gain: float = 5.0,
               window: float = 1.5, min_peers: int = 15) -> pd.DataFrame:
    """Athletes who finished roughly `target_gain` minutes faster (window widens if too few)."""
    target = my_total - target_gain
    band = race.iloc[0:0]
    for w in (window, window * 2, window * 3):
        band = race[(race["total_time"] >= target - w) & (race["total_time"] <= target + w)]
        if len(band) >= min_peers:
            break
    if len(band) < min_peers:
        # Still too few (e.g. near the front or back of the field): use the
        # min_peers athletes ahead of you whose times are closest to the target.
        faster = race[race["total_time"] < my_total]
        band = faster.iloc[(faster["total_time"] - target).abs().argsort()[:min_peers]]
    return band


def gap_report(me: pd.Series, peers: pd.DataFrame) -> pd.DataFrame:
    """Per segment: my time, peers' median, gap (positive = time to win back), trainability."""
    rows = []
    for col, label in RACE_ORDER.items():
        if col not in peers.columns or pd.isna(me.get(col)):
            continue
        peer_median = peers[col].median()
        level, why = TRAINABILITY.get(label, (QUICK, ""))
        rows.append({
            "segment": label,
            "type": "Run" if col in RUNS else ("Station" if col in STATIONS else "Roxzone"),
            "you_min": me[col],
            "peers_min": peer_median,
            "gap_min": me[col] - peer_median,
            "trainability": level,
            "why": why,
        })
    return pd.DataFrame(rows)


def add_realistic_gain(report: pd.DataFrame, trainability_data: pd.DataFrame = None) -> pd.DataFrame:
    """
    realistic_gain = your gap x how much of such a gap typically closes.

    If we have our own repeat-athlete analysis (data/segment_trainability.csv),
    use the measured closability per segment. Otherwise fall back to the
    research-based labels: Quick win 60%, Steady build 40%, Long game 30%.
    """
    fallback = {QUICK: 0.6, STEADY: 0.4, LONG: 0.3}
    r = report.copy()
    r["closability"] = r["trainability"].map(fallback)
    r["evidence"] = "research"
    if trainability_data is not None:
        measured = trainability_data.set_index("segment")
        has = r["segment"].isin(measured.index)
        r.loc[has, "closability"] = r.loc[has, "segment"].map(measured["closability"]).clip(0, 1)
        r.loc[has, "athletes"] = r.loc[has, "segment"].map(measured["athletes_weak_here"])
        r.loc[has, "evidence"] = "data"
    r["realistic_gain"] = r["gap_min"].clip(lower=0) * r["closability"]
    return r


def top_opportunities(report: pd.DataFrame, n: int = 3) -> pd.DataFrame:
    """
    Your biggest gaps. Backtesting on 3,000 unseen repeat athletes showed that
    ranking by gap alone predicts next-race improvement as well as weighting by
    trainability (54% vs 53% top-3 hit rate; random 17%), so we keep it simple.
    Trainability is still shown as context.
    """
    r = report[report["gap_min"] > 0]
    return r.sort_values("gap_min", ascending=False).head(n)


def summary_by_type(report: pd.DataFrame) -> pd.DataFrame:
    return report.groupby("type", as_index=False)["gap_min"].sum().sort_values("gap_min", ascending=False)


def race_plan(field: pd.DataFrame, target_min: float, window: float = 2.0, min_n: int = 10):
    """
    What does a target finish time actually look like? Take athletes who
    finished within +/- `window` minutes of the target and use their median
    split for every segment. Returns (plan table, number of athletes used).
    """
    band = field.iloc[0:0]
    for w in (window, window * 2, window * 3):
        band = field[(field["total_time"] - target_min).abs() <= w]
        if len(band) >= min_n:
            break
    rows = []
    for col, label in RACE_ORDER.items():
        if col in band.columns:
            t = band[col].median()
            rows.append({"segment": label, "target_min": t,
                         "note": pace(t) if col in RUNS else ""})
    return pd.DataFrame(rows), len(band)


def parse_time(text: str):
    """'1:15:30' -> 75.5, '58:20' -> 58.33, '75' -> 75.0. None if unreadable."""
    try:
        parts = [float(p) for p in str(text).strip().split(":")]
    except ValueError:
        return None
    if len(parts) == 3:
        return parts[0] * 60 + parts[1] + parts[2] / 60
    if len(parts) == 2:
        return parts[0] + parts[1] / 60
    if len(parts) == 1:
        return parts[0]
    return None


# ------------------------------------------------------------ venue effects
def venue_factor(effects, season, location, year, col) -> float:
    """1.08 = this venue makes that segment ~8% slower than average. 1.0 if unknown."""
    if effects is None:
        return 1.0
    m = effects[(effects["season"] == int(season)) & (effects["location"] == str(location))
                & (effects["year"] == int(year)) & (effects["segment"] == col)]
    if not len(m) or not np.isfinite(m["effect"].iloc[0]):
        return 1.0                      # unknown or broken estimate: no adjustment
    return 1.0 + float(m["effect"].iloc[0])


MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
RACE_DATES: dict = {}   # (season, location, year) -> month number; filled by load_race_dates()


def load_race_dates(path="data/race_dates.csv") -> dict:
    """Read the race calendar (season, location, year, month) if it exists."""
    RACE_DATES.clear()
    try:
        d = pd.read_csv(path).dropna(subset=["month"])
        for r in d.itertuples():
            RACE_DATES[(int(r.season), str(r.location), int(r.year))] = int(r.month)
    except (FileNotFoundError, ValueError, KeyError):
        pass
    return RACE_DATES


def edition_label(season, location, year) -> str:
    """'Mumbai · Sep 2026' when the month is known, otherwise 'Mumbai 2026'."""
    name = str(location).replace("-", " ").title()
    month = RACE_DATES.get((int(season), str(location), int(year)))
    return f"{name} · {MONTHS[month - 1]} {int(year)}" if month else f"{name} {int(year)}"


def field_strength(index: pd.DataFrame, effects, gender: str, division: str) -> pd.DataFrame:
    """
    How strong is each race's FIELD, with the course taken out?
    Each edition's median finish is divided by its course effect, then compared
    with the typical edition. +6% = the typical athlete there is 6% slower
    than at a typical race: a less competitive field.
    """
    f = index[(index["gender"].astype(str) == gender) & (index["division"].astype(str) == division)]
    g = f.groupby(["season", "location", "year"], observed=True)["total_time"].agg(["median", "size"]).reset_index()
    g = g[g["size"] >= 30]
    g["course"] = [venue_factor(effects, r.season, r.location, r.year, "total_time") for r in g.itertuples()]
    g["adjusted"] = g["median"] / g["course"]
    g["field_vs_typical"] = g["adjusted"] / g["adjusted"].median() - 1
    return g


def field_label(x) -> str:
    if pd.isna(x):
        return "–"
    return "Faster field" if x < -0.02 else "Slower field" if x > 0.02 else "Typical field"


def compare_venues(my_time, source, targets, index, effects, gender, division,
                   age_group=None, report=None) -> pd.DataFrame:
    """
    "I ran my_time at `source`. What would that be at each target race, and where would I place?"
      1. Course: convert the time with the two venues' course effects.
      2. Field: place the converted time among that race's actual finishers.
      3. Priorities: a station that runs harder at a venue costs more there, so
         your realistic gains (from `report`) are scaled by that venue's effect.
    source/targets are (season, location, year) tuples.
    """
    strength = field_strength(index, effects, gender, division).set_index(["season", "location", "year"])
    src_total = venue_factor(effects, *source, "total_time")
    rows = []
    for t in targets:
        tgt_total = venue_factor(effects, *t, "total_time")
        known = effects is not None and tgt_total != 1.0 and src_total != 1.0 or t == tuple(source)
        predicted = my_time / src_total * tgt_total
        field = index[(index["season"] == t[0]) & (index["location"].astype(str) == t[1]) & (index["year"] == t[2])
                      & (index["gender"].astype(str) == gender) & (index["division"].astype(str) == division)]
        rank, size = placing(field, predicted)
        row = {"race": edition_label(*t), "predicted": predicted, "course_known": known,
               "rank": rank, "size": size, "top_pct": 100 * rank / size if size and rank else None,
               "field": strength["field_vs_typical"].get(t, float("nan"))}
        if age_group is not None and "age_group" in field.columns:
            ag = field[field["age_group"].astype(str) == str(age_group)]
            row["ag_rank"], row["ag_size"] = placing(ag, predicted) if len(ag) else (None, 0)
        # stations that run hardest here
        seg_eff = {lab: venue_factor(effects, *t, col) - 1 for col, lab in RACE_ORDER.items()}
        harder = sorted(((v, k) for k, v in seg_eff.items() if v > 0.02), reverse=True)[:2]
        row["runs_harder"] = ", ".join(f"{k} {v:+.0%}" for v, k in harder) or "–"
        if report is not None and "realistic_gain" in report:
            cols = {lab: col for col, lab in RACE_ORDER.items()}
            scale = report["segment"].map(lambda lab: venue_factor(effects, *t, cols[lab])
                                          / venue_factor(effects, *source, cols[lab]))
            here = pd.Series((report["realistic_gain"] * scale).to_numpy(), index=report["segment"].to_numpy())
            row["priorities"] = ", ".join(f"{k} ~{fmt(v)}" for k, v in here[here > 0].nlargest(3).items()) or "–"
        rows.append(row)
    return pd.DataFrame(rows)


# ---------------------------------------------------------- next-race outlook
LEVEL_BANDS = [(0.00, 0.10, "Top 10%"), (0.10, 0.25, "10–25%"), (0.25, 0.50, "25–50%"),
               (0.50, 0.75, "50–75%"), (0.75, 1.01, "Bottom 25%")]


def level_of(pct: float) -> str:
    """Percentile within your race (0 = winner) -> level band label."""
    return next(label for lo, hi, label in LEVEL_BANDS if lo <= pct < hi)


def next_race_outlook(table: pd.DataFrame, pct: float, horizon: str = "any"):
    """What athletes at your level typically improved by their next race. None if no data."""
    if table is None:
        return None
    m = table[(table["level"] == level_of(pct)) & (table["horizon"] == horizon)]
    return m.iloc[0] if len(m) else None
