D=../nbadata/datasets
mkdir -p ../boxraw
for Y in 1996 1997 1998 1999; do S="$Y-$(printf %02d $(( (Y+1) % 100 )))"
 for T in rs po; do P=""; [ $T = po ] && P="po_"
  rm -rf tmpb; mkdir tmpb; tar -xJf $D/nbastats_${P}${Y}.tar.xz -C tmpb; tar -xJf $D/shotdetail_${P}${Y}.tar.xz -C tmpb 2>/dev/null
  python3 box_from_pbp.py tmpb/nbastats_${P}${Y}.csv tmpb/shotdetail_${P}${Y}.csv $S $T ../boxraw/box_${S}_${T}.csv
 done; done; rm -rf tmpb
# names for those seasons
