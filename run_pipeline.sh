#!/bin/bash
# Basketball Done Right - full pipeline, from raw play-by-play to the finished site.
# Run from the repo root. Steps are slow (stints ~20 min, each RAPM/CEPM batch 30-60 min on 2 cores);
# each step writes its outputs to disk, so you can comment out steps that are already done.
set -e
E=rapm_engine.py

# ---- 0. data ----------------------------------------------------------------------------------------
# NBA.com play-by-play archive (1996-97 on): ~1.2 GB
[ -d nbadata ] || git clone --depth 1 https://github.com/shufinskiy/nba_data.git nbadata
# pbpstats parser (or: pip install pbpstats)
[ -d pbplib ] || git clone --depth 1 https://github.com/dblackrun/pbpstats.git pbplib
# pbpstats.com season totals (2000-01 on) go in zip2/pbpstats_data/{Player,Team}_all_seasons.csv

# ---- 1. stints (steps 1-2): every game -> stretches with the same 10 players --------------------------
(cd stintbuild && bash run_all.sh)                                                  # 1996-97 .. 2024-25
(cd stintbuild && for T in "" po_; do tar -xJf ../nbadata/datasets/cdnnba_${T}2025.tar.xz -C . ; done
  python build_live.py cdnnba_2025.csv 2025-26 rs ../stints/stints_2025-26_rs.csv
  python build_live.py cdnnba_po_2025.csv 2025-26 po ../stints/stints_2025-26_po.csv; rm -f cdnnba_*.csv)

# ---- 2. box stats for 1996-97 .. 1999-00 (pbpstats.com starts in 2000-01) -----------------------------
(cd stintbuild && bash run_box.sh)                       # -> boxraw/box_<season>_<rs|po>.csv
python mymodel/make_src96.py                             # -> src96/ (pbpstats.com-style files, 1996-97 on)
(cd mymodel && python features.py ../src96/)             # -> mymodel/features_rs.csv (per-100, vs league)

# ---- 3. pure RAPM (regular season), 2- to 5-year windows + decades ------------------------------------
mkdir -p rapm_out; cd rapm_out
for W in 2 3 4 5; do python ../$E "../stints/stints_*_rs.csv" --cache stints_rs.pkl --window $W --decay 1 --out rw$W.csv > rw$W.log; done
cd ..

# ---- 4. CEPM: box component, then RAPM shrunk toward it ------------------------------------------------
cd cepm
python box_prior.py && python split_priors.py
# regular-season-only 3-year CEPM (used by the playoff model; picks its own ridge penalty by cross-validation)
python ../$E "../stints/stints_*_rs.csv" --cache ../rapm_out/stints_rs.pkl --window 3 --decay 1 --prior prior_w3.csv --out cepm3_rs.csv > cepm3_rs.log
for e in 1996-97 1997-98; do python ../$E "../stints/stints_*_rs.csv" --cache ../rapm_out/stints_rs.pkl --window 3 --decay 1 --prior prior_w3.csv --only-end $e --out part_$e.csv; done
python -c "import pandas as pd; pd.concat([pd.read_csv('part_1996-97.csv'),pd.read_csv('part_1997-98.csv'),pd.read_csv('cepm3_rs.csv')]).to_csv('cepm3_rs.csv',index=False)"
# displayed CEPM: regular season + playoffs, same penalties as above
ALL="../stints/stints_*.csv"; CA=../rapm_out/stints_all.pkl; L=cepm3_rs.csv   # same ridge penalty as the regular-season fit, window by window
for W in 2 3 4 5; do python ../$E "$ALL" --cache $CA --window $W --decay 1 --prior prior_w$W.csv --lambda-from $L --out disp$W.csv > disp$W.log; done
python ../$E "$ALL" --cache $CA --seasons 1996-97..1999-00 --window 4 --decay 1 --only-end 1999-00 --prior prior_dec1990.csv --lambda-from $L --out ddec1990.csv
python ../$E "$ALL" --cache $CA --seasons 2000-01..2009-10 --window 10 --decay 1 --only-end 2009-10 --prior prior_dec2000.csv --lambda-from $L --out ddec2000.csv
python ../$E "$ALL" --cache $CA --seasons 2010-11..2019-20 --window 10 --decay 1 --only-end 2019-20 --prior prior_dec2010.csv --lambda-from $L --out ddec2010.csv
python ../$E "$ALL" --cache $CA --seasons 2020-21..2025-26 --window 6 --decay 1 --only-end 2025-26 --prior prior_dec2020.csv --lambda-from $L --out ddec2020.csv
cp cepm3_rs.csv cepm3.csv && python evaluate.py cepm3.csv          # pure RAPM vs CEPM, next-season team net
cd ..

# ---- 5. site data ---------------------------------------------------------------------------------------
cd site
python extend_1996.py data_2000.json      # data_2000.json = site data for 2000-01 on (players, teams, series, league)
python make_cepm_data.py                  # -> data.json (CEPM windows, peaks, decades, model-only CEPM)
python rebuild_no_bbref.py                # records + playoff series from NBA.com play-by-play, league averages from pbpstats.com
cd ..

# ---- 6. playoff model -----------------------------------------------------------------------------------
cd pomodel
python team_feats.py                      # player minutes per game -> player_game.csv
python add_avail.py                       # availability CEPM -> site/data.json (T.late, series[6..7])
node export_series.js && python fit_playoffs.py   # leave-one-season-out test; copy weights into site/model.js PARAMS
cd ..

# ---- 6b. playoff series lines, playoff-only CEPM, title runs ----------------------------------------------
(cd stintbuild && bash run_boxgames.sh)           # per-game playoff box scores -> boxgames/
(cd cepm && python po_cepm.py)                     # playoff-only CEPM per postseason -> cepm/po_cepm.csv
(cd site && python team_games.py && python build_playoff_data.py)   # SRS + TS% allowed, series lines -> data.json

# ---- 6c. current-season model (kept separate from everything above) ---------------------------------------
(cd cur && python games_all.py && python fit_current.py && python export_current.py)   # -> cur_params.json, data.json "cur"

# ---- 7. build the pages -----------------------------------------------------------------------------------
(cd site && python build.py)                                  # -> site/Courtside_Stats.html (plain theme)
(cd loadout && python assemble.py ../Basketball_Done_Right.html)   # Loadout theme (needs loadout/orig.html)
