"""Playoff play types for every postseason: the same rules as build_playtypes.py, run on the playoff play-by-play
archives (nbastats_po_<y>, shotdetail_po_<y>, cdnnba_po_2025). Output: playtypes_po.csv.
usage: python build_playtypes_po.py [years...]   (default 1996..2025)"""
import sys, pandas as pd
import build_playtypes as B
_read = B.read_tar
B.read_tar = lambda name: _read(name.replace("nbastats_", "nbastats_po_").replace("shotdetail_", "shotdetail_po_").replace("cdnnba_", "cdnnba_po_"))
years = [int(a) for a in sys.argv[1:]] or list(range(1996, 2026))
rows = []
for y in years:
    ev = B.events_cdn(y) if y == 2025 else B.events_nbastats(y)
    r = B.profile(ev, B.season_of(y)); rows += r; print(B.season_of(y), len(ev), "events", len(r), "players", flush=True)
pd.DataFrame(rows).fillna(0).to_csv("playtypes_po.csv", index=False)
