E=../rapm_engine.py; ALL="../stints/stints_*.csv"; CA=../rapm_out/stints_all.pkl; L=cepm3_rs.csv
for W in 2 3 4 5; do python3 $E "$ALL" --cache $CA --window $W --decay 1 --prior prior_w$W.csv --lambda-from $L --only-end 2025-26 --out fix26_w$W.csv > fix26_w$W.log 2>&1; done
python3 $E "$ALL" --cache $CA --seasons 2020-21..2025-26 --window 6 --decay 1 --only-end 2025-26 --prior prior_dec2020.csv --lambda-from $L --out ddec2020.csv > ddec2020.log 2>&1
echo done
