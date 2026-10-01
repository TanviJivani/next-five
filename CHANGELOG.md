# Changelog

## v2.0
- **Find your race by name.** No need to know the HYROX season: type your name and pick from every race you've done (seasons 7–9).
- **Plain-English headline.** Your finish, overall rank, and age-group rank at the top.
- **Most impactful areas first**: top 3 segments by *realistic gain* (your gap × how much of that kind of gap athletes typically close by their next race), then every segment ranked below.
- **Repeat-athlete analysis** (`repeat_analysis.py`): compares thousands of athletes' first and latest races, normalised for venue differences and overall fitness gains, to measure which weaknesses actually close. Validated on simulated data with known answers. Falls back to research-based labels if not run.
- **Plan my next race.** Pick a race and target time: see where it would have placed at previous editions (incl. in your age group), what top 10 needed, and the splits and run pace per km that target requires.
- Times shown as h:mm:ss everywhere; chart in race order, in seconds, coloured by trainability.

## v1.0
- Compare your splits with athletes who finished ~5 minutes faster in the same race and division.

## v2.1
- **Venue effects** (`venue_effects.py`): uses athletes who raced at more than one venue as measuring sticks to estimate how each venue changes each station, separating the course from the strength of the field. On simulated data it recovers planted course effects within 0.2 percentage points, versus 2.3 for comparing venue medians.
- **Course-adjusted times**: the Analyse tab shows what your time would be at an average venue.
- **🌍 Compare races**: your time converted to other venues' courses and placed in their actual fields (overall and age group), with a field-strength label, stations that run harder there, and venue-specific priorities.
- **Field strength**: each race's typical athlete compared with a typical race, after removing the course, so a slower *field* is no longer mistaken for a slower *course*.
- Repeat-athlete analysis now uses venue effects instead of race medians when available.

## v2.2
- **Backtested on real data.** Placing predictions from the previous edition's field: median error 3.9 percentage points across 547,911 results (59% within 5 points, 85% within 10). Top-3 improvement areas on 3,000 held-out repeat athletes: 54% hit rate for "biggest gaps" vs 53% with trainability weighting and 17% for random guessing.
- **Simplified ranking.** Since trainability weighting didn't beat the simpler baseline, top areas are now ranked by gap alone. Trainability and typical closure are still shown as context, and used for the realistic total.

## v2.2
- **Ranking by gap, not trainability.** Backtesting on 3,000 athletes the model never saw: ranking by raw gap identified 54% of each athlete's top-3 most-improved segments; weighting by measured trainability got 53%; random guessing 17%. The weighting added nothing, so it was removed from the ranking. Trainability is still shown as context.
- Placing predictions validated on 547,911 results: median error 3.9 percentage points; 85% within 10 points.

## v2.3
- **Plain-language Analyse tab.** "You finished in 1:45:45 … faster than 62% of the field", three focus areas in plain words, and the technical detail moved into "See every station" and "How we worked this out".
- **📈 Your next race.** A realistic and a stretch target, from what athletes at the same level typically improved by their next race (venue-adjusted). Once race months are filled in, athletes can pick how far away their next race is (up to 3 months, 4–6, 7–12, over a year).
- **Fix:** the comparison group could shrink to a single athlete; it now always uses at least 15.
- Race months shown in labels ("Mumbai · Sep 2026") via `data/race_dates.csv` (`make_race_calendar.py`).
