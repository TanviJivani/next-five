"""
app.py — the website people actually use.

Streamlit turns this Python script into a web page. Every time someone
clicks something, Streamlit re-runs the script top to bottom.
Run locally with:  streamlit run app.py
"""

import pyrox
import streamlit as st

from analysis import find_athlete, find_peers, fmt, gap_report, summary_by_type

st.set_page_config(page_title="Next Five — HYROX", page_icon="⏱️")
st.title("⏱️ Where are my next 5 minutes?")
st.write(
    "Find your HYROX race, and see exactly where athletes who finished "
    "~5 minutes faster than you gained their time."
)

client = pyrox.PyroxClient()


# @st.cache_data = "remember this result", so we don't re-download
# the same race every time someone clicks a button.
@st.cache_data(ttl=3600)
def load_seasons():
    return client.list_seasons()


@st.cache_data(ttl=3600)
def load_locations(season):
    return client.list_locations(season=season)


@st.cache_data(ttl=3600)
def load_race(season, location, gender):
    return client.get_race(season=season, location=location, gender=gender)


# ---- 1. Pick the race ----
col1, col2, col3 = st.columns(3)
seasons = load_seasons()
season = col1.selectbox("Season", seasons, index=len(seasons) - 1)
location = col2.selectbox("Race", load_locations(season))
gender = col3.selectbox("Gender", ["female", "male"])

race = load_race(season, location, gender)

# Filter by division (Open, Pro, Doubles...) if the data has that column
if "division" in race.columns:
    divisions = sorted(race["division"].dropna().unique())
    division = st.selectbox("Division", divisions)
    race = race[race["division"] == division]

# ---- 2. Find the athlete ----
name = st.text_input("Your name as it appears in results")
if not name:
    st.stop()  # wait until they type something

matches = find_athlete(race, name)
if matches.empty:
    st.error("No athlete found with that name in this race. Check spelling or division.")
    st.stop()
if len(matches) > 1:
    pick = st.selectbox("Several matches — which one is you?", matches["name"].tolist())
    me = matches[matches["name"] == pick].iloc[0]
else:
    me = matches.iloc[0]

# ---- 3. Analyse ----
gain = st.slider("How many minutes faster do you want to be?", 2, 15, 5)
peers = find_peers(race, me["total_time"], target_gain=gain)

if len(peers) < 5:
    st.warning("Very few athletes finished in that range, so this comparison is rough.")

report = gap_report(me, peers)
biggest = report.iloc[0]

st.metric("Your finish", fmt(me["total_time"]))
st.subheader(f"Your biggest gap: {biggest['segment']}")
st.write(
    f"You were **{fmt(biggest['gap_min'])}** slower there than the typical athlete "
    f"who finished ~{gain} min faster than you ({len(peers)} athletes compared)."
)

st.write("**Where the time goes, by type**")
buckets = summary_by_type(report)
for _, row in buckets.iterrows():
    st.write(f"- {row['type']}: {fmt(row['gap_min'])}")

st.write("**Every segment** (positive = time you could win back)")
st.bar_chart(report.set_index("segment")["gap_min"])

table = report.assign(
    you=report["you_min"].map(fmt),
    peers=report["peers_min"].map(fmt),
    gap=report["gap_min"].map(fmt),
)[["segment", "you", "peers", "gap"]]
st.dataframe(table, hide_index=True)

st.caption(
    "Data: pyrox-client (HYROX results, MIT licence). Independent project, "
    "not affiliated with HYROX."
)
