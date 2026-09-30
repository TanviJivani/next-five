# ⏱️ Next Five

**Where are my next 5 minutes in HYROX?**

Find your HYROX race and see exactly where athletes who finished about 5 minutes faster than you gained their time: which runs, which stations, and how much in the roxzone.

## Why I built this

I race HYROX. After every race I'd look at my splits and wonder where the time was actually going. Knowing I was "slow on wall balls" meant little without knowing what *slow* means compared with athletes at the level I'm aiming for. Results sites show your times, but not where the gap to the next level is. So I built something that does.

## How it works

1. Pick a season, race, gender and division, and find yourself by name.
2. The tool finds your **peers**: athletes in the same race and division who finished roughly 5 minutes faster (adjustable from 2 to 15). If too few athletes fall in that range, the window widens so the comparison isn't based on a handful of people.
3. For every segment (8 runs, 8 stations, roxzone), it compares your time with the peers' **median**. The median is used rather than the average so one unusual athlete doesn't skew the result.
4. Segments are ranked by gap, so your biggest opportunity is at the top, with totals for running, stations and roxzone.

## Run it yourself

Requires Python 3.12 or newer.

```bash
git clone https://github.com/YOUR-USERNAME/next-five.git
cd next-five
python3 -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -r requirements.txt
python test_with_fake_data.py    # checks the logic on made-up data
streamlit run app.py
```

On a Mac with Python from python.org, run **Install Certificates.command** (in Applications → Python 3.x) first, or race downloads will fail with a certificate error.

## Project structure

| File | What it does |
| --- | --- |
| `analysis.py` | The logic: finding the athlete, choosing peers, calculating gaps |
| `app.py` | The web interface, built with Streamlit |
| `test_with_fake_data.py` | Tests the logic on 400 synthetic athletes with a planted weakness |

## Data

Race results come from [pyrox-client](https://github.com/vmatei2/pyrox-client) by Vlad Matei (MIT licence). This is an independent project, not affiliated with or endorsed by HYROX.

## How this was built

Built with Claude as a coding partner. I defined the question and the analysis approach, made the product decisions, set up and debugged the project, and am testing it with athletes.

## What's next

- Feedback from athletes on whether the biggest gap matches how their race felt
- Comparing against your age group, not just your division
- Turning gaps into training suggestions

**Try it:** https://next-five-ztte9qexhy6vhpfcpbe54j.streamlit.app
