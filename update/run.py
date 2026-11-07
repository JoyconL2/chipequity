"""Weekly update: add the season being played to the site, then rebuild the site into dist/.

History (1996-97 up to the last finished season) is frozen in base/ and never refit; only the newest season is
computed, with exactly the same scripts and settings as every earlier season:
   1  download finished games from NBA.com (update/fetch_season.py)
   2  stints and box totals from the play-by-play (stintbuild/build_live_json.py, box_from_live.py)
   3  site rows for the season: players, teams, records, league averages, playoff series (update/add_season.py)
   4  box-score features and priors for windows ending this season (update/features_season.py, cepm/box_prior*.py)
   5  regression for every window ending this season: 1-5 years, the 2020s so far, the regular-season-only
      3-year fit (rapm_engine.py --only-end)
   6  lead margin, teammate adjustment, competitive minutes (load/), then Chip Equity (load/chip_build.py)
   7  current-season model, on/off and WOWY, and the pages (cur/export_current.py, wowy/, site/, loadout/)
When the Finals are over, the finished season is folded into base/ so the next season builds on it.

usage: python update/run.py [--season 2026-27] [--skip-fetch] [--site-url https://...]
exit code 0 with "nothing to update" when no new games have been played."""
import argparse, glob, json, lzma, os, shutil, subprocess, sys, time
import pandas as pd

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BASE = os.path.join(ROOT, "base"); LIVE = os.path.join(ROOT, "live"); DIST = os.path.join(ROOT, "dist")
PY = sys.executable
T0 = time.time()

# base/ file -> where the pipeline scripts expect it
BASE_FILES = {
    "data.json": "site/data_base.json", "wowy.json": "wowy/wowy_base.json", "orig.html": "loadout/orig.html",
    "features_rs.csv": "mymodel/features_rs.csv", "rw3.csv": "rapm_out/rw3.csv", "player_game_last.csv": "pomodel/player_game.csv",
    **{f"{n}.csv": f"cepm/{n}.csv" for n in ("disp1", "disp2", "disp3", "disp4", "disp5", "cepm3_rs", "ddec1990", "ddec2000", "ddec2010", "ddec2020")},
    **{f"{n}.csv": f"load/{n}.csv" for n in ("margin_attr_od", "po_lead", "tm_sums", "comp_share")},
}
WINDOW_FILES = ["disp1", "disp2", "disp3", "disp4", "disp5", "cepm3_rs"]
LOAD_FILES = ["margin_attr_od", "po_lead", "tm_sums", "comp_share"]


def log(msg): print(f"[{time.time() - T0:6.0f}s] {msg}", flush=True)


def run(args, cwd=".", env=None, out=None):
    e = dict(os.environ, **(env or {}), PYTHONUNBUFFERED="1")
    log(f"$ ({cwd}) {' '.join(args)}")
    with open(out, "w") if out else open(os.devnull, "w") as f:
        r = subprocess.run(args, cwd=os.path.join(ROOT, cwd), env=e, stdout=f if out else None, stderr=subprocess.STDOUT if out else None)
    if out and os.path.exists(out):           # pass a step's warnings (e.g. games it couldn't read) up to the run page
        for ln in open(out, errors="replace"):
            if ln.startswith("::warning::"): print(ln.rstrip(), flush=True)
    if r.returncode != 0:
        if out: print(open(out).read()[-4000:])
        sys.exit(f"step failed: {' '.join(args)}")


def unxz(src, dst):
    os.makedirs(os.path.dirname(dst), exist_ok=True)
    with lzma.open(src) as a, open(dst, "wb") as b: shutil.copyfileobj(a, b)


def xz(src, dst):
    with open(src, "rb") as a, lzma.open(dst + ".tmp", "wb", preset=6) as b: shutil.copyfileobj(a, b)
    os.replace(dst + ".tmp", dst)


def restore_base():
    for name, dst in BASE_FILES.items():
        unxz(os.path.join(BASE, name + ".xz"), os.path.join(ROOT, dst))
    os.makedirs(os.path.join(ROOT, "stints"), exist_ok=True)
    for f in glob.glob(os.path.join(BASE, "stints", "*.csv.xz")):
        unxz(f, os.path.join(ROOT, "stints", os.path.basename(f)[:-3]))


def merge_rows(path, new_path, season, col):
    """history rows from path (every season but this one) + this season's rows from new_path -> path"""
    old = pd.read_csv(path); new = pd.read_csv(new_path)
    new = new[new[col] == season]
    pd.concat([old[old[col] != season], new], ignore_index=True).to_csv(path, index=False)
    return len(new)


def next_season(s): y = int(s[:4]) + 1; return f"{y}-{str(y + 1)[-2:]}"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--season"); ap.add_argument("--skip-fetch", action="store_true")
    ap.add_argument("--fold", action="store_true", help="fold the season into base/ even if the Finals are not over (testing)")
    ap.add_argument("--site-url", default=os.environ.get("SITE_URL", "https://YOUR-SITE.netlify.app"))
    a = ap.parse_args()
    restore_base(); log("base restored")
    base = json.load(open(os.path.join(ROOT, "site/data_base.json"))); last_done = base["seasons"][-1]
    CUR = a.season or next_season(last_done)
    if CUR != next_season(last_done): sys.exit(f"base ends {last_done}; the next season to add is {next_season(last_done)}, not {CUR}")
    wd = os.path.join(LIVE, CUR)

    # 1  games
    if not a.skip_fetch:
        r = subprocess.run([PY, "update/fetch_season.py", LIVE, CUR], cwd=ROOT, capture_output=True, text=True)
        print((r.stdout + r.stderr).strip()[-3000:])
        if r.returncode != 0:
            if "schedule is for" in r.stdout + r.stderr:
                print(f"nothing to update: NBA.com's schedule isn't on {CUR} yet"); return
            sys.exit("could not download games")
    if not os.path.exists(os.path.join(wd, "games.csv")): print("nothing to update: no", CUR, "games"); return
    G = pd.read_csv(os.path.join(wd, "games.csv"), dtype={"gid": str})
    if G.empty: print("nothing to update: no", CUR, "games played yet"); return

    # 2  stints + box totals (regular season, and playoffs once they start)
    tmp = os.path.join(ROOT, "update", "tmp"); os.makedirs(tmp, exist_ok=True)
    for st in ("rs", "po"):
        src = os.path.join(wd, f"pbp_{st}")
        if not glob.glob(os.path.join(src, "*.json")): continue
        run([PY, "build_live_json.py", src, CUR, st, f"../stints/stints_{CUR}_{st}.csv", os.path.join(tmp, f"boxgames_{st}.csv")], cwd="stintbuild", out=os.path.join(tmp, f"stints_{st}.log"))
        run([PY, "box_from_live.py", src, CUR, st, os.path.join(wd, f"box_{CUR}_{st}.csv")], cwd="stintbuild", out=os.path.join(tmp, f"box_{st}.log"))
        shutil.copy(os.path.join(ROOT, f"stints/stints_{CUR}_{st}.csv"), os.path.join(wd, f"stints_{CUR}_{st}.csv"))
    log("stints and box totals done")

    # 3  site rows
    run([PY, "update/add_season.py", "site/data_base.json", CUR, wd, "site/data.json"])
    D = json.load(open(os.path.join(ROOT, "site/data.json"))); inprog = D["inprog"]

    # 4  features + priors for windows ending this season
    run([PY, "update/features_season.py", os.path.join(wd, f"box_{CUR}_rs.csv"), CUR, "mymodel/features_rs.csv"])
    env = {"ONLY_END": CUR}
    run([PY, "box_prior.py"], cwd="cepm", env=env, out=os.path.join(tmp, "box_prior.log"))
    run([PY, "split_priors.py"], cwd="cepm", out=os.path.join(tmp, "split_priors.log"))
    run([PY, "box_prior1.py"], cwd="cepm", env=env, out=os.path.join(tmp, "box_prior1.log"))

    # 5  regression, windows ending this season only
    for f in glob.glob(os.path.join(ROOT, "rapm_out", "stints_*.pkl")): os.remove(f)
    E = "../rapm_engine.py"; RS = "../stints/stints_*_rs.csv"; ALL = "../stints/stints_*.csv"
    CRS = "../rapm_out/stints_rs.pkl"; CA = "../rapm_out/stints_all.pkl"; common = ["--decay", "1", "--only-end", CUR]
    run([PY, E, RS, "--cache", CRS, "--window", "3", "--prior", "prior_w3.csv", "--out", "new_cepm3_rs.csv", *common], cwd="cepm", out=os.path.join(tmp, "cepm3_rs.log"))
    merge_rows(os.path.join(ROOT, "cepm/cepm3_rs.csv"), os.path.join(ROOT, "cepm/new_cepm3_rs.csv"), CUR, "window_end")
    # single-season floor for the season being played: 50 possessions per game, counting 67% of the most games any team
    # has played (so a player who missed a game or two, or whose team is behind on its schedule, still qualifies),
    # at least 50 and up to the usual 1,000; still steadied 40% toward 3 years
    rsG = G[G.stype == "rs"]; most = int(pd.concat([rsG.home, rsG.away]).value_counts().max()) if len(rsG) else 0
    tg = 0.67 * most; mp1 = int(min(1000, max(50, round(50 * tg))))
    log(f"single-season floor {mp1} possessions (67% of {most} games, the most any team has played)")
    run([PY, E, ALL, "--cache", CA, "--window", "1", "--prior", "prior_w1.csv", "--out", "new_disp1.csv", "--min-poss", str(mp1), *common], cwd="cepm", out=os.path.join(tmp, "disp1.log"))
    jobs = []
    for w in (2, 3, 4, 5):
        args = [PY, E, ALL, "--cache", CA, "--window", str(w), "--prior", f"prior_w{w}.csv", "--lambda-from", "cepm3_rs.csv", "--out", f"new_disp{w}.csv", *common]
        jobs.append((args, f"disp{w}.log"))
    nd = len(D["seasons"]) - D["seasons"].index("2020-21")
    jobs.append(([PY, E, ALL, "--cache", CA, "--seasons", f"2020-21..{CUR}", "--window", str(nd), "--prior", "prior_dec2020.csv",
                  "--lambda-from", "cepm3_rs.csv", "--out", "new_ddec2020.csv", *common], "ddec2020.log"))
    par = max(1, min(3, (os.cpu_count() or 2) - 1)); running = []
    for args, lg in jobs:                       # a few fits at a time (each holds the stints in memory)
        while len(running) >= par:
            for p_ in running[:]:
                if p_[0].poll() is not None:
                    running.remove(p_)
                    if p_[0].returncode != 0: print(open(p_[1]).read()[-3000:]); sys.exit("regression failed")
            time.sleep(5)
        lp = os.path.join(tmp, lg); log(f"$ (cepm) {' '.join(args[1:])}")
        running.append((subprocess.Popen(args, cwd=os.path.join(ROOT, "cepm"), stdout=open(lp, "w"), stderr=subprocess.STDOUT), lp))
    for p_, lp in running:
        if p_.wait() != 0: print(open(lp).read()[-3000:]); sys.exit("regression failed")
    for w in (1, 2, 3, 4, 5):
        n = merge_rows(os.path.join(ROOT, f"cepm/disp{w}.csv"), os.path.join(ROOT, f"cepm/new_disp{w}.csv"), CUR, "window_end")
        log(f"{w}-year windows ending {CUR}: {n} players")
    shutil.copy(os.path.join(ROOT, "cepm/new_ddec2020.csv"), os.path.join(ROOT, "cepm/ddec2020.csv"))

    # 6  lead margin etc. on this season's stints only, then Chip Equity
    full = pd.read_pickle(os.path.join(ROOT, "rapm_out/stints_all.pkl"))
    full[full.season == CUR].to_pickle(os.path.join(ROOT, "rapm_out/stints_cur.pkl")); del full
    env = {"STINTS_PKL": "../rapm_out/stints_cur.pkl", "LEADBY": "u2"}   # u2 = the lead rule the site uses (load/lead_map.py)
    for n in LOAD_FILES: shutil.move(os.path.join(ROOT, f"load/{n}.csv"), os.path.join(ROOT, f"load/{n}_base.csv"))
    for n in LOAD_FILES:
        run([PY, f"{n}.py"], cwd="load", env=env, out=os.path.join(tmp, f"{n}.log"))
    for n in LOAD_FILES:
        new = pd.read_csv(os.path.join(ROOT, f"load/{n}.csv")); old = pd.read_csv(os.path.join(ROOT, f"load/{n}_base.csv"))
        pd.concat([old[old.season != CUR], new[new.season == CUR]], ignore_index=True).to_csv(os.path.join(ROOT, f"load/{n}.csv"), index=False)
    run([PY, "chip_build.py"], cwd="load", out=os.path.join(tmp, "chip_build.log"))
    print(open(os.path.join(tmp, "chip_build.log")).read()[-1500:])
    D = json.load(open(os.path.join(ROOT, "site/data.json"))); S = D["seasons"]; si = S.index(CUR); kidx = {int(p): k for k, p in enumerate(D["ids"])}
    rs3 = pd.read_csv(os.path.join(ROOT, "cepm/cepm3_rs.csv")); rs3 = rs3[rs3.window_end == CUR]
    D["rwm"] = [r for r in D["rwm"] if r[1] != si] + [[kidx[int(p)], si, round(v, 2)] for p, v in zip(rs3.player, rs3.rapm) if int(p) in kidx]
    json.dump(D, open(os.path.join(ROOT, "site/data.json"), "w"), separators=(",", ":"), allow_nan=False)

    # 7  current-season model, WOWY, pages
    run([PY, "export_current.py"], cwd="cur", out=os.path.join(tmp, "export_current.log"))
    run([PY, "wowy_build.py"], cwd="wowy", env=env, out=os.path.join(tmp, "wowy.log"))
    W = json.load(open(os.path.join(ROOT, "wowy/wowy_base.json"))); W.update(json.load(open(os.path.join(ROOT, "wowy/wowy.json"))))
    os.makedirs(DIST, exist_ok=True)
    json.dump(W, open(os.path.join(DIST, "wowy.json"), "w"), separators=(",", ":"))
    os.makedirs(os.path.join(DIST, "lineups"), exist_ok=True)       # history's lineup files are already in dist/lineups
    shutil.copy(os.path.join(ROOT, f"wowy/lineups/{CUR}.json"), os.path.join(DIST, "lineups", f"{CUR}.json"))
    run([PY, "build.py"], cwd="site")
    run([PY, "assemble.py", os.path.join(DIST, "index.html"), a.site_url], cwd="loadout")
    if os.path.exists(os.path.join(ROOT, "site/preview.png")): shutil.copy(os.path.join(ROOT, "site/preview.png"), os.path.join(DIST, "preview.png"))
    json.dump({"season": CUR, "games": inprog["games"], "through": inprog["through"], "team_games": inprog["team_games"],
               "built": time.strftime("%Y-%m-%d %H:%M UTC", time.gmtime())}, open(os.path.join(DIST, "update.json"), "w"), indent=1)
    log(f"site built: {CUR} through {inprog['through']} ({inprog['games']} games)")

    # season over: fold it into base/ so the next season builds on it
    if inprog.get("done") or a.fold:
        D.pop("inprog", None)
        json.dump(D, open(os.path.join(tmp, "data.json"), "w"), separators=(",", ":"), allow_nan=False)
        xz(os.path.join(tmp, "data.json"), os.path.join(BASE, "data.json.xz"))
        xz(os.path.join(DIST, "wowy.json"), os.path.join(BASE, "wowy.json.xz"))
        for name, dst in BASE_FILES.items():
            if name in ("data.json", "wowy.json", "orig.html", "rw3.csv", "player_game_last.csv"): continue
            xz(os.path.join(ROOT, dst), os.path.join(BASE, name + ".xz"))
        for st in ("rs", "po"):
            f = os.path.join(ROOT, f"stints/stints_{CUR}_{st}.csv")
            if os.path.exists(f): xz(f, os.path.join(BASE, "stints", f"stints_{CUR}_{st}.csv.xz"))
        run([PY, "team_feats.py"], cwd="pomodel", out=os.path.join(tmp, "team_feats.log"))
        x = pd.read_csv(os.path.join(ROOT, "pomodel/player_game.csv"), dtype={"game_id": str}); x = x[(x.season == CUR) & (x.stype == "rs")]
        x.to_csv(os.path.join(tmp, "pg.csv"), index=False); xz(os.path.join(tmp, "pg.csv"), os.path.join(BASE, "player_game_last.csv.xz"))
        log(f"{CUR} is over: folded into base/")


if __name__ == "__main__":
    main()
