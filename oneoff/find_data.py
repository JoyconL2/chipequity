"""One-off (runs on your PC): look for the old play-by-play stints and the pbpstats download in your user folder.
Reports folders (relative to your home folder) and file counts only; reads no file contents."""
import json, os, re
home = os.path.expanduser("~"); out = {}
SKIP = {"appdata", "node_modules", ".git", "$recycle.bin", "windows", "program files", "_work", "actions-runner"}
want = {"stints": re.compile(r"^stints_(\d{4}-\d{2})_(rs|po)\.csv$"), "pbpstats": re.compile(r"^(Player|Team)_all_seasons\.csv$"),
        "features": re.compile(r"^features_(rs|po)\.csv$")}
for root, dirs, files in os.walk(home):
    dirs[:] = [d for d in dirs if d.lower() not in SKIP and not d.startswith(".")]
    if root[len(home):].count(os.sep) > 7: dirs[:] = []; continue
    for f in files:
        for kind, rx in want.items():
            m = rx.match(f)
            if m:
                rel = "~" + root[len(home):].replace("\\", "/"); e = out.setdefault(rel, {"kind": kind, "files": [], "mb": 0.0})
                e["files"].append(f); e["mb"] += os.path.getsize(os.path.join(root, f)) / 1e6
for v in out.values(): v["files"] = sorted(v["files"]); v["mb"] = round(v["mb"], 1)
os.makedirs("oneoff/out", exist_ok=True); json.dump(out, open("oneoff/out/found.json", "w"), indent=1)
print(json.dumps({k: (v["kind"], len(v["files"]), v["mb"]) for k, v in out.items()}, indent=1))
