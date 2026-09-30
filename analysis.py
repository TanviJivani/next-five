"""
analysis.py — the "brain" of Next Five.

Given one athlete's race and everyone else in that race, it answers:
"Compared with people who finished about 5 minutes faster than me,
where exactly am I losing that time?"

No website code lives here, just the logic. Keeping logic separate from
the interface makes it easy to test and reuse.
"""

import pandas as pd

# Column names come from the pyrox-client library.
# Every time is already converted to MINUTES (e.g. 4.5 = 4 min 30 s).
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
ROXZONE = {"roxzone_time": "Roxzone (transitions)"}

ALL_SEGMENTS = {**RUNS, **STATIONS, **ROXZONE}


def find_athlete(race: pd.DataFrame, name: str) -> pd.DataFrame:
    """Return every row whose name contains the text typed (case-insensitive)."""
    mask = race["name"].astype(str).str.casefold().str.contains(name.strip().casefold())
    return race[mask]


def find_peers(race: pd.DataFrame, my_total: float, target_gain: float = 5.0,
               window: float = 1.5, min_peers: int = 15) -> pd.DataFrame:
    """
    Peers = athletes who finished roughly `target_gain` minutes faster.

    We look in a band around (my time - 5 min). If fewer than `min_peers`
    athletes are in that band, we widen it, because comparing against
    3 people would be noise, not insight.
    """
    target = my_total - target_gain
    for w in (window, window * 2, window * 3):
        band = race[(race["total_time"] >= target - w) & (race["total_time"] <= target + w)]
        if len(band) >= min_peers:
            return band
    return band  # best we could do; the app warns if this is small


def gap_report(me: pd.Series, peers: pd.DataFrame) -> pd.DataFrame:
    """
    For each segment: my time, the peers' MEDIAN time, and the gap.

    We use the median (the middle person) rather than the average,
    so one athlete who walked the wall balls doesn't skew everything.
    Positive gap = I'm slower than the peers there = time to win back.
    """
    rows = []
    for col, label in ALL_SEGMENTS.items():
        if col not in peers.columns or pd.isna(me.get(col)):
            continue
        peer_median = peers[col].median()
        rows.append({
            "segment": label,
            "type": "Run" if col in RUNS else ("Station" if col in STATIONS else "Roxzone"),
            "you_min": me[col],
            "peers_min": peer_median,
            "gap_min": me[col] - peer_median,
        })
    report = pd.DataFrame(rows)
    return report.sort_values("gap_min", ascending=False).reset_index(drop=True)


def summary_by_type(report: pd.DataFrame) -> pd.DataFrame:
    """Add up gaps into three buckets: running, stations, roxzone."""
    return report.groupby("type", as_index=False)["gap_min"].sum().sort_values(
        "gap_min", ascending=False)


def fmt(minutes: float) -> str:
    """4.5 -> '4:30'. Negative values get a minus sign."""
    sign = "-" if minutes < 0 else ""
    total_seconds = round(abs(minutes) * 60)
    return f"{sign}{total_seconds // 60}:{total_seconds % 60:02d}"
