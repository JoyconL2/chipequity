D=../nbadata/datasets; mkdir -p ../boxgames
for Y in $(seq 1996 2024); do S="$Y-$(printf %02d $(( (Y+1) % 100 )))"
  [ -f ../boxgames/po_$S.csv ] && continue
  rm -rf tmpg; mkdir tmpg; tar -xJf $D/nbastats_po_${Y}.tar.xz -C tmpg
  python3 box_games.py tmpg/nbastats_po_${Y}.csv $S po ../boxgames/po_$S.csv
done
rm -rf tmpg; mkdir tmpg; tar -xJf $D/cdnnba_po_2025.tar.xz -C tmpg
python3 box_games.py --live tmpg/cdnnba_po_2025.csv 2025-26 po ../boxgames/po_2025-26.csv; rm -rf tmpg
