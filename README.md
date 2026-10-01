# ⏱️ Next Five

**Where are my next 5 minutes in HYROX?**

Find your HYROX race and see exactly where athletes who finished about 5 minutes faster than you gained their time: which runs, which stations, and how much in the roxzone.

## Why I built this

I race HYROX. After every race I'd look at my splits and wonder where the time was actually going. Knowing I was "slow on wall balls" meant little without knowing what *slow* means compared with athletes at the level I'm aiming for. Results sites show your times, but not where the gap to the next level is. So I built something that does.

## What it does

**📊 Analyse a race.** Type your name (no need to know the HYROX season) and pick any race you've done. You get:
- your finish, overall rank and age-group rank, in plain English
- your **most impactful areas**: the segments with the most time you can realistically win back, based on your gap to athletes ~5 minutes ahead *and* how much of that kind of gap athletes typically close by their next race
- every segment ranked, and a chart of your whole race in order

**🌍 Compare races.** Where would your time place at other races? Your time is converted for each venue's course, then placed in that race's actual field, overall and in your age group. Each race shows whether its field is faster or slower than typical, which stations run harder there, and your priorities for that venue.

**🎯 Plan my next race.** Pick a race and a target time to see where it would have placed at previous editions (including in your age group), what top 10 needed, and the splits and run pace per km that target requires.

## The research behind it

- **Repeat-athlete analysis** (`repeat_analysis.py`): compares thousands of athletes' first and latest races to measure which weaknesses actually close. Times are made relative to each race's median (so venue differences cancel out) and to the athlete's own overall level (so general fitness gains don't count as closing a specific weakness).
- **Venue effects** (`venue_effects.py`): athletes who raced at several venues act as measuring sticks, so each venue's effect on each station can be separated from the strength of its field.
- **Method validation** (`validate_method.py`): simulates athletes with known, planted trainability and checks the analysis recovers it.
- **Backtesting** (`evaluate.py`): trains on 70% of repeat athletes and tests on the 30% the model never saw, comparing Next Five's predictions with random guessing and with "just pick the biggest gaps".
- **HYROX by the numbers** (`hyrox_by_the_numbers.ipynb`): a notebook testing published claims and new questions: where time goes by level, compromised running, pacing, venue difficulty, age, athlete types, and India vs the global field.

Known limitations: results show associations, not causes; repeat athletes are matched by name within gender and division; regression to the mean inflates improvement figures.

## Run it yourself

Requires Python 3.12 or newer.

```bash
git clone https://github.com/TanviJivani/next-five.git
cd next-five
python3 -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -r requirements.txt
python test_with_fake_data.py    # checks the app logic
python validate_method.py        # checks the research method
python build_index.py            # builds the name search index (slow, once)
python repeat_analysis.py        # measures trainability (slow, once)
python venue_effects.py          # venue course effects
python repeat_analysis.py        # rerun so it uses venue effects
python evaluate.py               # backtests accuracy
streamlit run app.py
```

On a Mac with Python from python.org, run **Install Certificates.command** (in Applications → Python 3.x) first, or downloads fail with a certificate error.

## Project structure

| File | What it does |
| --- | --- |
| `app.py` | The web app (Streamlit) |
| `analysis.py` | Core logic: search, peers, gaps, realistic gain, race plans |
| `build_index.py` | Builds the searchable index of who raced where |
| `repeat_analysis.py` | Repeat-athlete trainability analysis |
| `venue_effects.py` | Estimates each venue's effect on each station from shared athletes |
| `evaluate.py` | Backtests prediction accuracy on unseen athletes |
| `validate_method.py` | Checks the method on simulated data with known answers |
| `export_for_kaggle.py` | Writes the anonymised datasets for Kaggle |
| `hyrox_by_the_numbers.ipynb` | Kaggle analysis notebook |
| `test_with_fake_data.py` | Tests for the app logic |

## Data

Race results come from [pyrox-client](https://github.com/vmatei2/pyrox-client) by Vlad Matei (MIT licence). This is an independent project, not affiliated with or endorsed by HYROX.

## How this was built

Built with Claude as a coding partner. I defined the question and the analysis approach, made the product decisions, set up and debugged the project, and am testing it with athletes.

## What's next

- Race months for every edition, to measure improvement per month of training
- Feedback from athletes on whether the top opportunities match how their race felt
- See `CHANGELOG.md` for what changed in each version and why
