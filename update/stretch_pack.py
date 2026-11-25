"""Pack one regular season's stints for the site's stretch Chip Equity (Chip Equity over any run of games, worked out
in the browser): dist/stretch/<season>.bin.

Layout (little-endian): header Uint32 x5 [magic 0x54534543 'CEST', version 1, players, games, stints] + Float32 era,
then Int32[players] site player index (-1 = the pooled low-minute column, always index 0), Uint16[games] game day
(days since 1970-01-01), Uint16[stints] game, Uint16[stints*10] players (5 home then 5 away), Uint8[games] home team,
Uint8[games] away team (site team index), Uint8[stints] x4: home possessions, away possessions, home points, away points.
Garbage time is dropped (same rule as the model). era = REF / that season's points per 100, like the model's scaling.
usage: python update/stretch_pack.py <stints csv or csv.xz> ... [--data site/data.json] [--force]"""
import sys, os, json, lzma, struct, argparse, numpy as np, pandas as pd
ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."); sys.path.insert(0, ROOT)
import rapm_engine as E
REF = 105.0                     # points per 100 the stretch files scale every season to (only sets the scale of the numbers)
MINP = 150                      # players under this many possessions in the season share one column, like the model
ap = argparse.ArgumentParser(); ap.add_argument("files", nargs="+"); ap.add_argument("--data", default=os.path.join(ROOT, "site/data.json"))
ap.add_argument("--out", default=os.path.join(ROOT, "dist/stretch")); ap.add_argument("--force", action="store_true"); a = ap.parse_args()
D = json.load(lzma.open(a.data) if a.data.endswith(".xz") else open(a.data))
kidx = {int(p): k for k, p in enumerate(D["ids"])}; S = D["seasons"]; P = D["P"]
os.makedirs(a.out, exist_ok=True)
for f in a.files:
    season = os.path.basename(f).split("_")[1]; dst = os.path.join(a.out, f"{season}.bin")
    if os.path.exists(dst) and not a.force: print(season, "exists"); continue
    df = pd.read_csv(lzma.open(f) if f.endswith(".xz") else f, dtype={"game_id": str})
    tmp = f"/tmp/_st_{season}.csv"; df.to_csv(tmp, index=False); df = E.load([tmp]); os.remove(tmp)
    df = E.mark_starters_and_fatigue(df); df = df[~E.garbage_time(df)].copy()
    df = df[df.game_date.notna()].copy()
    lg = (df.home_pts.sum() + df.away_pts.sum()) / (df.home_poss.sum() + df.away_poss.sum()) * 100
    # players
    on = {}
    for col in ("home_players", "away_players"):
        for pls, ps in zip(df[col], df.poss):
            for q in pls.split("-"): on[q] = on.get(q, 0) + ps
    keep = sorted((q for q, v in on.items() if v >= MINP), key=lambda q: -on[q]); pl = {q: i + 1 for i, q in enumerate(keep)}
    site = [-1] + [kidx.get(int(q), -1) for q in keep]
    # teams: NBA team id -> the site's abbreviation used that season
    si = S.index(season) if season in S else -1
    used = {P["tm"][j] for j in range(len(P["s"])) if P["s"][j] == si} if si >= 0 else set(range(len(D["abbrs"])))
    tmap = {tid: ai for ai, tid in enumerate(D["teamIds"]) if ai in used}
    for ai, tid in enumerate(D["teamIds"]): tmap.setdefault(tid, ai)
    games = list(dict.fromkeys(df.sort_values(["game_date", "game_id"]).game_id)); gi = {g: i for i, g in enumerate(games)}
    gd = df.drop_duplicates("game_id").set_index("game_id")
    day = np.array([(pd.Timestamp(gd.game_date[g]) - pd.Timestamp("1970-01-01")).days for g in games], np.uint16)
    ht = np.array([tmap.get(int(gd.home_team[g]), 255) for g in games], np.uint8); at = np.array([tmap.get(int(gd.away_team[g]), 255) for g in games], np.uint8)
    sg = df.game_id.map(gi).values.astype(np.uint16)
    pp = np.array([[pl.get(q, 0) for q in h.split("-")][:5] + [pl.get(q, 0) for q in w.split("-")][:5] for h, w in zip(df.home_players, df.away_players)], np.uint16)
    if pp.shape[1] != 10: raise SystemExit(f"{season}: a stint without 10 players")
    u8 = lambda c: np.clip(df[c].values, 0, 255).astype(np.uint8)
    with open(dst, "wb") as o:
        o.write(struct.pack("<5If", 0x54534543, 1, len(site), len(games), len(df), REF / lg))
        o.write(np.array(site, np.int32).tobytes()); o.write(day.tobytes()); o.write(sg.tobytes()); o.write(pp.tobytes())
        o.write(ht.tobytes()); o.write(at.tobytes())
        for c in ("home_poss", "away_poss", "home_pts", "away_pts"): o.write(u8(c).tobytes())
    print(f"{season}: {len(games)} games, {len(df)} stints, {len(site) - 1} players, era {REF / lg:.3f}, {os.path.getsize(dst) / 1e6:.2f} MB")
