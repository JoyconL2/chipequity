#!/bin/bash
# builds stints for every season from the archive
D=../nbadata/datasets; OUT=../stints; mkdir -p $OUT tmp
for Y in $(seq 1996 2024); do
  S="$Y-$(printf %02d $(( (Y+1) % 100 )))"
  for T in rs po; do
    P=""; [ $T = po ] && P="po_"
    [ -f $OUT/stints_${S}_${T}.csv ] && continue
    rm -rf tmp/*; tar -xJf $D/nbastats_${P}${Y}.tar.xz -C tmp || continue
    tar -xJf $D/shotdetail_${P}${Y}.tar.xz -C tmp 2>/dev/null
    python3 -c "
import pandas as pd, json, glob
f=glob.glob('tmp/shotdetail*.csv'); m={}
if f:
    d=pd.read_csv(f[0], usecols=['GAME_ID','GAME_DATE'], dtype=str).drop_duplicates('GAME_ID')
    m={g.zfill(10): f'{x[:4]}-{x[4:6]}-{x[6:8]}' for g,x in zip(d.GAME_ID,d.GAME_DATE)}
json.dump(m, open('tmp/dates.json','w'))"
    python3 build_stints.py tmp/nbastats_${P}${Y}.csv $S $T $OUT/stints_${S}_${T}.csv --dates tmp/dates.json
  done
done
rm -rf tmp
