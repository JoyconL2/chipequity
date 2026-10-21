# Basketball Done Right: RAPM, CEPM and the playoff model

[![tests](https://github.com/JoyconL2/basketball-done-right/actions/workflows/tests.yml/badge.svg)](https://github.com/JoyconL2/basketball-done-right/actions/workflows/tests.yml)

Everything behind the site's numbers, built from raw play-by-play. No outside impact metric is used.

## What's here

| Step | Folder / file | What it does |
|---|---|---|
| 1-2 | `stintbuild/build_stints.py`, `run_all.sh` | Parses every game (1996-97 to 2024-25, NBA.com play-by-play archive) with the pbpstats parser, offline, into **stints**: stretches with the same 10 players, with possessions, points for each side, time and score margin. Handles old-feed quirks (missing period markers, rebound order, missing starters, Hornets/Pelicans id mix-ups). |
| 1-2 | `stintbuild/build_live.py` | Same for 2025-26, from the cdn.nba.com live-format archive. |
| 1-2b | `stintbuild/build_live_json.py` | Stints + playoff box scores from raw NBA.com live play-by-play JSON files (`playbyplay_<gameId>.json`), used for the 2025-26 playoffs the archive doesn't cover. |
| 1-2 | `stintbuild/get_stints.py` | Alternative: download games yourself from NBA.com (live feed works for 2019-20 on). |
| box | `stintbuild/box_from_pbp.py`, `derive_box.py`, `run_box.sh` | Season box totals per player from play-by-play + shot coordinates, in pbpstats.com's definitions (checked against pbpstats.com for 2000-01). Used for 1996-97 to 1999-00, which pbpstats.com doesn't cover. |
| box | `mymodel/make_src96.py`, `mymodel/features.py` | Per-100 box features relative to each season's league: scoring above league efficiency, shot diet, unassisted points, assists by shot created, live/dead-ball turnovers, offensive and defensive rebounds separately, steals, blocks, fouls, charges. |
| 3-4 | `rapm_engine.py` | Ridge regression on stints (+1 home players on the floor, -1 away, 0 bench), offense/defense split. Garbage time removed (Cleaning-the-Glass style); controls for home court, continuous minutes on court, minutes already played, back-to-backs, score state and clutch time; each season scaled to its scoring level; ridge penalty picked by cross-validating on held-out games; low-minute players pooled into a replacement column. `--prior` shrinks toward a box-score estimate instead of zero. |
| CEPM | `cepm/box_prior.py`, `split_priors.py` | **CEPM's box component.** Learns how the box features map to pure RAPM (ridge, cross-validated), then predicts a prior for every player in every window. The model for a window is trained only on RAPM windows sharing no season with it, so the box score never sees the results it's combined with. |
| CEPM | `cepm/evaluate.py` | Pure RAPM vs CEPM at predicting next season's team net rating. |
| odds | `pomodel/team_feats.py`, `add_avail.py`, `export_series.js`, `fit_playoffs.py` | Playoff series model. Inputs: net rating, top-3 CEPM x floor share, **available roster** (CEPM weighted by minutes in the last 15 games or earlier playoff rounds), and record vs. point differential. Tested leave-one-season-out on all 450 series since 1997. |
| playoffs | `stintbuild/box_games.py`, `cepm/po_cepm.py`, `site/team_games.py`, `site/build_playoff_data.py` | Per-game playoff box scores; playoff-only CEPM (one fit per postseason, pulled toward a playoff box-score estimate); SRS and defensive TS% allowed for every team-season from game results; per-series player lines (per 75, opponent-adjusted rTS, roRTG) and the title-run rankings. |
| site | `site/extend_1996.py`, `make_cepm_data.py`, `rebuild_no_bbref.py` (records, series and league averages from NBA.com / pbpstats.com only), `model.js`, `template.html`, `build.py`; `loadout/assemble.py` | Site data (adds 1996-97 to 1999-00 players, teams, records, series), the in-browser model, and the page builds. |

`run_pipeline.sh` runs it all in order, with comments.

## Results (as of Oct 2026)

- Stints: about 36,600 games parsed; 99.9% match the real final score. About 1.2 million stints.
- Box component alone explains about 50% of 3-year RAPM out of sample.
- Next-season team net rating, correlation: pure RAPM 0.773, CEPM 0.791.
- Playoff series, leave-one-season-out over 450 series: net rating alone 72.4%; full model 75.3%, log loss 0.496. Feeding the model who actually played in each series (hindsight) reaches only about 76%.

## What CEPM is

**CEPM (Chip Equity Plus-Minus)** is points added per 100 possessions compared with an average player.
It starts from adjusted plus-minus (who was on the floor and what the score did, after accounting for
teammates and opponents) and, where that evidence is thin, leans on a box-score estimate learned from the
plus-minus itself. Built to avoid the usual issues with EPM-style metrics:

- assisted vs. unassisted scoring is an input, and assists are valued by the shot they create
- offensive and defensive rebounds are separate inputs
- garbage time is removed; fatigue (continuous minutes, minutes played, back-to-backs) is controlled for
- seasons are scaled to their scoring level, not just pace
- every weight is fit from data and cross-validated; nothing is hand-tuned

The numbers on the site count regular season + playoffs. The playoff odds use a regular-season-only
version, so they never see the series they predict.

## Chip Equity (v3: the site's single impact stat)

The site now shows one impact number, **Chip Equity**. The ridge regression described above (CEPM in the scripts) is its core:

`Chip Equity = (0.65 x Regression + 0.35 x LeadMargin) x CompShare` (`load/chip_build.py`).

- LeadMargin: team margin per 100 when he is the best player on the floor (highest 3-year regression + 2 x (usage / league usage - 1) on the floor, `load/lead_map.py`; picking by the 1-year number let hot role players take stars' credit, e.g. Odom over Kobe in 2008-09, and the usage tiebreak keeps a lagging co-star from taking the lead from the player running the offense, e.g. Kyrie over Luka in 2023-24), garbage time out, shrunk n/(n+3000), split offense/defense vs league (`load/margin_attr_od.py`).
- CompShare: share of the team's non-garbage minutes in games he played (`load/comp_share.py`).
- Playoffs: his playoff lead stints count too (each playoff possession = 2 regular-season ones), with the margin adjusted for the opponent team's regular-season offense/defense vs league (`load/po_lead.py`; playoff opponents average +4.8). Playoff-only Chip Equity uses the same recipe on the playoff-only fit: (0.65 x fit + 0.35 x opp-adjusted playoff lead x n/(n+1000)) x playoff competitive share. The playoff model only sees earlier postseasons (`load/po_cerm.py`).
- Teammate adjustment: in his lead stints, 0.5 x his four teammates' 3-year o and d (centred on the season's average lead lineup) is taken out of lead margin, so stars on stacked teams don't get their teammates' credit and stars on thin rosters aren't marked down (`load/tm_sums.py`; strengths 0 / 0.25 / 0.5 / 0.75 / 1 tested, 0.5 kept).
- Single seasons are steadied 40% toward the 3-season window (first full window for 1996-98) and use lighter shrinkage below 3,000 possessions (`rapm_engine_lw.py`). Windows of 2-5 years and decades pool the inputs. The single-season board starts at 1997-98.
- Tests: playoff series 76.2%, log loss 0.4941, weights Net 0.66, Top3 0.41, Avail 0.38, Luck 0.31 (75.1% / 0.4937 before); next-season team wins MAE 6.91 (6.94 before, `cur/proj_lab26.py`). On-ball bonus, usage/stint-length load, plain on-court margin, teammate-adjusted margin, opponent adjustment, era minutes, season normalization and a lighter minutes exponent were tested and dropped (`load/big_search.py`).

## Projected net rating and record (Live Feed)

Built iteratively in `cur/proj_lab*.py`: every season from 1998-99 to 2025-26 is predicted using only what was known before it started (roster = players in the team's first 10 games), every coefficient is fit on the other seasons, and a change is kept only if it predicts better.

| Version (held-out) | Net rating RMSE | Avg wins miss (per 82) |
|---|---|---|
| Every team average | 4.84 | 10.2 |
| Last season's net, regressed | 3.88 | 7.8 |
| Roster 3-yr CEPM x minutes | 3.53 | 7.0 |
| + last season's net, league centered (3-yr CEPM, ties 2-yr) | 3.48 | 6.9 |
| Standings-first: last season's net + roster change (V_now − V_last) + roster level (final, `cur/proj_lab12.py`) | **3.44** | **6.85** |

Standings-first form: `Net_0 = a + 0.46 x Net_last + 0.34 x (V_now − V_last) + 0.26 x V_now − 2.25 x U`, where V_last is last season's roster rated with the same CEPM at its real minutes, so the change term is purely who came and went.

Shipped form: the site-priors version (core continuity, star + support bonus, returning stars at full value and judged on their team's record with them, top 5 keep their usual minutes, stretch x1.3), model only. The betting-market blend was removed; ESPN BPI projected wins are shown beside it for comparison (top 10 built in, all 30 loaded live when ESPN's feed answers). BPI's accuracy isn't tested: no archive of past preseason BPI projections.

Tried and dropped (no gain): concentrating minutes on stars, experience splits, roster continuity, a second CEPM window, returning-player minutes, playoff experience, experience on winning rosters (a newcomer's past team success adds ~0 beyond his CEPM; `cur/proj_lab5.py`, `proj_lab6.py`). In season the projection blends with the real net rating, `(n x actual + 20 x projection) / (n + 20)` (k = 20 learned); the projected final-wins miss drops from 6.9 (preseason) to 5.1 after 20 games, 3.6 at 41 and 2.3 at 60. `cur/proj_final.py` writes `proj_params.json`. Spread: plain regression bunched teams toward the middle (projection SD 8.2 wins vs market 10.2 vs actual 12.3), so centered projections are stretched: x1.15 is the most accurate (every held-out fold; wins MAE 6.84), and x1.3 is used so projected standings spread like real seasons (SD ~12.1 vs 12.3 actual; wins MAE 6.97). Healthy form: players with 5-49 games last season are rated on the 3-year window before that short season (`proj_lab9.py`; neutral on accuracy, 6.89 vs 6.92 wins). Two-way players (Yardbarker tracker) stay on rosters but get no projected minutes. Returning stars (missed last season; 28+ min and +2 CEPM the season before) count at 50% of their CEPM with their last healthy minutes (`proj_lab7.py`; best on the 16 past cases). Compared with preseason market win totals on 180 team-seasons (`cur/market/`, `proj_lab8.py`): market 7.1 wins MAE, model 7.4, held-out blend 7.2, so the market (Kalshi, 2026-07-29) is shown beside the projection rather than blended in. Single-game and series odds for the current season stay off until tested the same way.

## Tests

```
pytest -q tests
```
Runs in seconds on fake data, no downloads needed. They check that the ridge engine recovers known player
values from synthetic stints, that a prior pulls the solve toward it, the garbage-time rule, stint building
(points add up, lineup changes split stints, time is continuous), the box-stat definitions, the series math
(closed-form best-of-5/7, home court, symmetry), and that the site's `model.js` loads and backtests.
GitHub Actions runs them on every push.

## Setup

```
pip install -r requirements.txt
bash run_pipeline.sh
```
Needs about 3 GB of disk. You also need the pbpstats.com season totals in `zip2/pbpstats_data/` (`Player_all_seasons.csv`, `Team_all_seasons.csv`) and, for the Loadout theme, the original Loadout file at `loadout/orig.html` (it holds the embedded fonts). `site/data_2000.json` is the base site data for 2000-01 on (box stats, team records, series, league averages).

Data credits: NBA.com play-by-play via [shufinskiy/nba_data](https://github.com/shufinskiy/nba_data), parsed with [pbpstats](https://github.com/dblackrun/pbpstats) (CEPM, team records, playoff series); pbpstats.com season totals (box-score features, league averages).

## Disclaimer

Independent, non-commercial fan project. Not affiliated with or endorsed by the NBA, its teams, NBA.com, ESPN or pbpstats.com. Team names, logos and player photos are trademarks or property of their respective owners. Statistics are factual data compiled from the sources credited above.

## Play types (`playtypes/`)

`build_playtypes.py` sorts every regular-season shot since 1996-97 into play types using only signals present in every season (descriptive tags like "pullup" are too sparse before ~2010): transition / early offense (shot within 7 s of a defensive rebound or turnover), putbacks (within 3 s of an offensive rebound), and half-court shots by shot-chart zone (rim 0-4 ft, mid-range, three), each split into self-created vs set up by the unassisted share of his makes there (shrunk to the league rate). Assists are split by the shot they created. `pt_features.py` turns these into per-75 rates and points per shot vs league; (Not shown on the site.)

`pt_test.py`: added to this season's regression and box prior, play types improve the out-of-sample forecast of next-season offensive impact slightly (RMSE 1.356 to 1.340; total 1.829 to 1.819). Added to the box-score prior they made it slightly worse out of sample (error 3.278 to 3.285-3.340 depending on the set; `cepm/box_prior_pt.py`), so they are not used and were removed from the site. A creation-based lead tiebreak (`load/lead_map.py`, tags c1/c2) and proportional lead credit (`load/lead_prop.py`) were tested and not adopted (no gain on the playoff / next-season tests).

## Style matchups (`pomodel/style_test.py`)

Tested clash terms in the playoff series model (A's tendency vs league x B's matching weakness, antisymmetric): offensive vs defensive rebounding, turnover rate vs steal rate, rim share vs block rate, free-throw rate vs shooting fouls, plus tempo and three-point reliance. None improved the leave-one-season-out test (base 76.2% / log loss 0.4941; every addition 0.4954-0.5074), so none are used. Real style effects likely need defensive matchup data (2016-17 on).

## Method text

The site's Method page is a short plain-English summary. The full technical method with every equation, weight and test is `METHOD.txt` (also `site/METHOD_technical.txt`, which `site/build.py` embeds so the page can offer it as a download). Update it by hand when the model changes.

## On/off and WOWY (`wowy/wowy_build.py`)

For every team-season since 1996-97 (regular season and playoffs, garbage time out): team totals, each player's on-court possessions and points for/against, and every pair of the 12 most-used players together. Written to `wowy.json`, which the site loads the first time a team page is opened (so it must be deployed next to `index.html`). Every five-man lineup per team-season goes to `lineups/<season>.json` (also deployed next to `index.html`), so the team page can split any group of players (all on together, each one taken away, none of them, with chosen players sitting) and rank the best 2- to 5-man units. Off-court, "without" and "neither" splits follow by subtraction.

## Daily update (`update/run.py`, `.github/workflows/weekly.yml`)

Every morning a GitHub Action downloads the finished games of the season being played from NBA.com's public CDN
(schedule, play-by-play and box score files), adds that season to the site and commits the rebuilt site to `dist/`.

- History (1996-97 to the last finished season) is frozen in `base/` (xz-compressed: site data, Chip Equity
  windows, lead margin / teammate / competitive-minutes tables, box-score features, WOWY, the last six seasons of stints)
  and is never refit. Only the new season is computed, with the same scripts and settings as every earlier one:
  stints and box totals from play-by-play (`stintbuild/build_live_json.py`, `stintbuild/box_from_live.py`), site rows
  (`update/add_season.py`), box features and priors (`update/features_season.py`, `cepm/box_prior*.py` with `ONLY_END`),
  every regression window ending this season (`rapm_engine.py --only-end`, 1-5 years, the 2020s so far, the
  regular-season-only 3-year fit), lead margin etc. (`load/`, on this season's stints), Chip Equity (`load/chip_build.py`),
  the current-season model, WOWY and the pages.
- A player gets a window once he has 1,000 possessions in it (as always), so single-season numbers fill in after about
  three weeks. The site labels the season "in progress"; the home page, leaderboard and team defaults stay on the last
  finished season until teams have played 20 games.
- When the Finals end, the run folds the finished season into `base/`, so the next season builds on it.
- Playoff-only Chip Equity, playoff series lines and late-season availability for the new season are not computed
  weekly (they need the full postseason refit).

Setup (once):
1. Push this repo to GitHub (Actions must be enabled; the workflow needs "Read and write permissions" under
   Settings -> Actions -> General -> Workflow permissions).
2. Netlify: Site configuration -> Build & deploy -> Link repository, branch `main`, build command empty,
   publish directory `dist`.
3. Optional: Settings -> Secrets and variables -> Actions -> Variables -> `SITE_URL` = your Netlify address
   (used for link previews).
4. Actions tab -> "daily update" -> Run workflow, to run it right away.
Run locally: `python update/run.py` (needs `pbplib/`, a clone of dblackrun/pbpstats).
