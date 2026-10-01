"""
app.py — Next Five v2, the website.
Run locally with:  streamlit run app.py
"""

import altair as alt
import pandas as pd
import pyrox
import streamlit as st

from analysis import (LONG, QUICK, STEADY, add_realistic_gain, compare_venues, edition_label, field_label, fmt,
                      level_of, load_race_dates, next_race_outlook, venue_factor, find_peers, gap_report, pace,
                      parse_time, placing, race_plan, search_athlete,
                      summary_by_type, top_opportunities)

st.set_page_config(page_title="Next Five — HYROX", page_icon="⏱️")
client = pyrox.PyroxClient()
BADGE = {QUICK: "🟢 Quick win", STEADY: "🟡 Steady build", LONG: "🔵 Long game"}


@st.cache_data
def load_index():
    return pd.read_parquet("data/athlete_index.parquet")


@st.cache_data(ttl=3600)
def load_race(season, location, year, gender, division):
    race = client.get_race(season=int(season), location=location, year=int(year), gender=gender)
    return race[race["division"] == division] if "division" in race.columns else race


def race_label(r) -> str:
    ag = f" · {r.age_group}" if "age_group" in r._fields and pd.notna(r.age_group) else ""
    return f"{edition_label(r.season, r.location, r.year)} · {r.division}{ag} · {fmt(r.total_time)}"


@st.cache_data
def load_trainability():
    try:
        return pd.read_csv("data/segment_trainability.csv")
    except FileNotFoundError:
        return None


@st.cache_data
def load_improvement():
    try:
        return pd.read_csv("data/improvement_by_level.csv")
    except FileNotFoundError:
        return None


@st.cache_data
def load_venue_effects():
    try:
        return pd.read_csv("data/venue_effects.csv")
    except FileNotFoundError:
        return None


load_race_dates()
index = load_index()
trainability_data = load_trainability()
venue_effects = load_venue_effects()
improvement_data = load_improvement()
HAS_AG = "age_group" in index.columns

st.title("⏱️ Next Five")
st.write("Find your HYROX races, see where your time goes, and plan your next one.")
tab_analyse, tab_compare, tab_plan = st.tabs(["📊 Analyse a race", "🌍 Compare races", "🎯 Plan my next race"])
analysed = None   # filled in by the Analyse tab, reused by Compare

# =============================================================== ANALYSE
with tab_analyse:
    query = st.text_input("Your name", placeholder="e.g. Tanvi Jivani")
    if query:
        found = search_athlete(index, query).sort_values(["year", "season"], ascending=False)
        if found.empty:
            st.error("No results found. Try just your surname, or check the spelling on your results page.")
        else:
            rows = list(found.itertuples(index=False))
            if len(set(r.name for r in rows)) > 1:
                st.caption("Several athletes match. Pick the race that's yours.")
            choice = st.selectbox("Your race", rows, format_func=lambda r: f"{r.name} — {race_label(r)}")

            race = load_race(choice.season, choice.location, choice.year, choice.gender, choice.division)
            me_rows = race[(race["name"] == choice.name) & ((race["total_time"] - choice.total_time).abs() < 0.02)]
            if me_rows.empty:
                st.error("Couldn't load your splits for this race.")
                st.stop()
            me = me_rows.iloc[0]

            # ---- 1. The headline, in plain words
            rank, size = placing(race, me["total_time"])
            pct = rank / size
            st.markdown(f"### You finished in {fmt(me['total_time'])}")
            line = (f"**{rank:,} of {size:,}** in {str(choice.division).title()} {choice.gender}: "
                    f"faster than {100 - round(100 * pct)}% of the field.")
            if HAS_AG and "age_group" in race.columns and pd.notna(choice.age_group):
                ag_rank, ag_size = placing(race[race["age_group"] == choice.age_group], me["total_time"])
                line += f"  \nIn your age group ({choice.age_group}): **{ag_rank} of {ag_size}**."
            st.markdown(line)
            vf = venue_factor(venue_effects, choice.season, choice.location, choice.year, "total_time")
            if abs(vf - 1) >= 0.01:
                st.caption(f"This course was about {abs(vf - 1):.0%} {'slower' if vf > 1 else 'faster'} than an average "
                           f"HYROX venue, so at a typical venue you'd have finished around {fmt(me['total_time'] / vf)}.")

            # ---- 2. Where to focus
            st.divider()
            st.subheader("🎯 Where to focus first")
            gain = st.select_slider("Compare me with people who finished this much faster:",
                                    options=[2, 3, 5, 8, 10], value=5, format_func=lambda m: f"{m} min")
            peers = find_peers(race, me["total_time"], target_gain=gain)
            report = add_realistic_gain(gap_report(me, peers), trainability_data)
            analysed = {"time": me["total_time"], "source": (int(choice.season), str(choice.location), int(choice.year)),
                        "gender": str(choice.gender), "division": str(choice.division), "report": report,
                        "age_group": str(choice.age_group) if HAS_AG and pd.notna(choice.age_group) else None}
            st.write(f"We compared your race with **{len(peers)} athletes in the same race** who finished about "
                     f"{gain} minutes ahead of you. These are the three places you lost the most time to them:")
            top = top_opportunities(report)
            if top.empty:
                st.success("You were level with or ahead of this group everywhere. Try a bigger number above.")
            cols = st.columns(max(len(top), 1))
            for col, (_, row) in zip(cols, top.iterrows()):
                col.metric(row["segment"], f"{fmt(row['gap_min'])} slower")
                col.markdown(f"{BADGE[row['trainability']]}  \n{row['why']}")

            # ---- 3. Next race outlook
            st.divider()
            st.subheader("📈 Your next race")
            outlook = next_race_outlook(improvement_data, pct)
            if outlook is not None:
                horizons = sorted(set(improvement_data["horizon"]) - {"any"},
                                  key=["up to 3 months", "4–6 months", "7–12 months", "over a year"].index)
                if horizons:
                    h = st.radio("When is your next race?", horizons, horizontal=True)
                    chosen = next_race_outlook(improvement_data, pct, h)
                    if chosen is not None:
                        outlook = chosen
                typical = me["total_time"] * outlook["median_gain"]
                strong = me["total_time"] * outlook["p75_gain"]
                where = {"Top 10%": "in the top 10%", "10–25%": "in the top 10–25%", "25–50%": "in the top 25–50%",
                         "50–75%": "in the top 50–75%", "Bottom 25%": "in the bottom 25%"}[level_of(pct)]
                st.write(f"Athletes who finished {where} of their race, like you, and then raced again typically got "
                         f"**{fmt(typical)} faster**. One in four improved by **{fmt(strong)} or more**.")
                c1, c2 = st.columns(2)
                c1.metric("Realistic target", fmt(me["total_time"] - typical))
                c2.metric("Stretch target", fmt(me["total_time"] - strong))
                note = f"Based on {int(outlook['n']):,} athletes, with differences between venues removed."
                if outlook["p25_gain"] < 0:
                    note += " About one in four actually got slower, so training matters."
                if not horizons:
                    note += " Once race dates are added, this will show what's typical in 3, 6 or 12 months."
                st.caption(note)
            else:
                st.caption("Next-race estimates appear once the repeat-athlete analysis has been run.")

            # ---- 4. Detail, for those who want it
            st.divider()
            with st.expander("📋 See every station"):
                table = report.assign(
                    you=report["you_min"].map(fmt),
                    them=report["peers_min"].map(fmt),
                    difference=report["gap_min"].map(lambda m: f"{fmt(abs(m))} {'slower' if m > 0 else 'faster'}"),
                    type=report["trainability"].map(BADGE),
                )
                st.caption(f"'Them' = the typical athlete in the group about {gain} minutes ahead of you.")
                st.dataframe(table[["segment", "you", "them", "difference", "type"]],
                             hide_index=True, width="stretch")
                chart_df = report.assign(gap_s=(report["gap_min"] * 60).round(),
                                         where=report["gap_min"].map(lambda m: "You were slower" if m > 0 else "You were faster"))
                st.altair_chart(alt.Chart(chart_df).mark_bar().encode(
                    x=alt.X("gap_s:Q", title="Seconds slower (right) or faster (left) than the group ahead"),
                    y=alt.Y("segment:N", sort=list(chart_df["segment"]), title=None),
                    color=alt.Color("where:N", title=None, legend=alt.Legend(orient="bottom"),
                                    scale=alt.Scale(domain=["You were slower", "You were faster"],
                                                    range=["#d44b3b", "#2e9d5b"])),
                    tooltip=["segment"]).properties(height=420), width="stretch")

            with st.expander(f"🏃 What a {fmt(me['total_time'] - gain)} race looks like"):
                plan, n = race_plan(race, me["total_time"] - gain)
                st.caption(f"The typical split of {n} athletes who finished around that time in this race.")
                st.dataframe(plan.assign(target=plan["target_min"].map(fmt))[["segment", "target", "note"]]
                             .rename(columns={"note": "run pace"}), hide_index=True, width="stretch")

            with st.expander("🔍 How we worked this out"):
                st.markdown(
                    "- **Where to focus** compares your splits with athletes from your own race, so the course is "
                    "the same for everyone. We tested this on 3,000 athletes who raced again: it picked over half "
                    "of their three most-improved stations, about three times better than guessing.\n"
                    "- **One race can include an off day.** If a station went unusually badly, it may show up here "
                    "even if it isn't a real weakness.\n"
                    "- **Quick win / Steady build / Long game** describe how quickly that kind of gap usually closes, "
                    "based on HYROX research and coaching practice.\n"
                    "- **Your next race** uses tens of thousands of athletes who raced HYROX more than once. Some of "
                    "their improvement is luck (a bad first race), so treat the realistic target as typical, not guaranteed.\n"
                    "- **Course differences** come from athletes who raced at several venues, used as measuring sticks.")


# ================================================================== PLAN
with tab_plan:
    st.write("Pick a race and a target time. See where that would have placed at previous editions, "
             "and the splits and run pace that target needs.")
    c1, c2 = st.columns(2)
    locations = sorted(index["location"].astype(str).unique())
    location = c1.selectbox("Race", locations, format_func=lambda l: l.replace("-", " ").title(),
                            index=locations.index("mumbai") if "mumbai" in locations else 0)
    target_text = c2.text_input("Target finish (h:mm:ss)", "1:15:00")
    c3, c4, c5 = st.columns(3)
    at_race = index[index["location"].astype(str) == location]
    gender = c3.selectbox("Gender", sorted(at_race["gender"].dropna().astype(str).unique()))
    division = c4.selectbox("Division", sorted(at_race["division"].dropna().astype(str).unique()))
    field = at_race[(at_race["gender"].astype(str) == gender) & (at_race["division"].astype(str) == division)]
    age_group = None
    if HAS_AG:
        groups = ["All"] + sorted(field["age_group"].dropna().astype(str).unique())
        picked = c5.selectbox("Age group", groups)
        age_group = None if picked == "All" else picked

    target = parse_time(target_text)
    if target is None or field.empty:
        st.info("Enter a target like 1:15:00, and pick a race with results.")
    else:
        compare = field[field["age_group"].astype(str) == age_group] if age_group else field
        editions = (compare[["season", "year"]].drop_duplicates()
                    .sort_values(["year", "season"], ascending=False).itertuples(index=False))
        st.subheader(f"{fmt(target)} at {location.replace('-', ' ').title()}")
        for ed_season, yr in editions:
            ed = compare[(compare["year"] == yr) & (compare["season"] == ed_season)]
            rank, size = placing(ed, target)
            top10 = ed["total_time"].nsmallest(10).max() if len(ed) >= 10 else None
            line = f"**{edition_label(ed_season, location, yr)}:** would have placed **{rank} of {size}**"
            if top10:
                line += f" · top 10 needed **{fmt(top10)}**"
            st.markdown(line)
        st.caption("Based on published results from previous editions. Upcoming start lists aren't public data.")

        latest = field.sort_values(["year", "season"]).iloc[-1]
        race = load_race(latest.season, location, latest.year, gender, division)
        plan, n = race_plan(race, target)
        st.subheader("Your race plan")
        runs = plan[plan["note"] != ""]
        st.markdown(f"Run pace to aim for: **{pace(runs['target_min'].mean())}** average across the 8 runs "
                    f"(based on {n} athletes who finished near {fmt(target)} at "
                    f"{edition_label(latest.season, location, latest.year)}).")
        st.dataframe(plan.assign(target=plan["target_min"].map(fmt))[["segment", "target", "note"]],
                     hide_index=True, width="stretch")


# =============================================================== COMPARE
with tab_compare:
    st.write("Where would your time place at other races? Two things change: the **course** "
             "(the same effort gives a different time) and the **field** (who else turns up).")
    editions = (index.groupby(["season", "location", "year"], observed=True).size()
                .rename("n").reset_index().sort_values("n", ascending=False))
    editions = editions[editions["n"] >= 30]
    ed_tuples = [(int(r.season), str(r.location), int(r.year)) for r in editions.itertuples()]
    lab = lambda t: edition_label(*t)

    if analysed:
        st.success(f"Using your result from the Analyse tab: **{fmt(analysed['time'])}** at {lab(analysed['source'])}.")
        my_time, source = analysed["time"], analysed["source"]
        gender, division, age_group, report = (analysed["gender"], analysed["division"],
                                               analysed["age_group"], analysed["report"])
    else:
        st.caption("Tip: find your race in the Analyse tab first to also get venue-specific priorities.")
        c1, c2 = st.columns(2)
        my_time = parse_time(c1.text_input("Your finish time (h:mm:ss)", "1:20:00", key="cmp_time"))
        source = c2.selectbox("Where you ran it", ed_tuples, format_func=lab, key="cmp_src")
        c3, c4, c5 = st.columns(3)
        gender = c3.selectbox("Gender", sorted(index["gender"].dropna().astype(str).unique()), key="cmp_g")
        division = c4.selectbox("Division", sorted(index["division"].dropna().astype(str).unique()), key="cmp_d")
        age_group = (c5.selectbox("Age group", ["All"] + sorted(index["age_group"].dropna().astype(str).unique()),
                                  key="cmp_ag") if HAS_AG else "All")
        age_group = None if age_group == "All" else age_group
        report = None

    others = [t for t in ed_tuples if t != source]
    targets = st.multiselect("Compare with", others, default=others[:3], format_func=lab, key="cmp_targets")

    if my_time and targets:
        table = compare_venues(my_time, source, [source] + targets, index, venue_effects,
                               gender, division, age_group, report)
        show = pd.DataFrame({
            "race": table["race"],
            "your time there": [fmt(t) + ("" if k else " *") for t, k in zip(table["predicted"], table["course_known"])],
            "overall": [f"{int(r)} of {n} (top {max(1, round(p))}%)" if r and n and pd.notna(p) else "–"
                        for r, n, p in zip(table["rank"], table["size"], table["top_pct"])],
            "field": [f"{field_label(x)} ({x:+.0%})" if pd.notna(x) else "–" for x in table["field"]],
            "runs harder here": table["runs_harder"],
        })
        if "ag_rank" in table:
            show.insert(3, f"age group {age_group}", [f"{int(r)} of {n}" if r and n and pd.notna(r) else "–"
                                                      for r, n in zip(table["ag_rank"], table["ag_size"])])
        if "priorities" in table:
            show["your priorities here"] = table["priorities"]
        st.dataframe(show, hide_index=True, width="stretch")

        ranked = table.iloc[1:].dropna(subset=["top_pct"])
        best = ranked.sort_values("top_pct").iloc[0] if len(ranked) else None
        if best is not None:
            st.markdown(f"Your best placing among these would be **{best['race']}**: top {max(1, round(best['top_pct']))}% overall.")
        st.caption("Course effects come from athletes who raced at several venues. Field = how the typical athlete there "
                   "compares with a typical race, after removing the course. "
                   + ("* = not enough shared athletes to measure this course, so your time is shown unadjusted."
                      if not table["course_known"].all() else ""))

st.divider()
st.caption("Data: pyrox-client (HYROX results, MIT licence). Independent project, not affiliated with HYROX. "
           "Trainability labels are a guide based on published HYROX research and coaching practice.")

