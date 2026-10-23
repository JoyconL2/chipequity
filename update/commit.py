"""Commit the rebuilt site (dist/) and the updated history files (base/) and push them, if anything changed.
Works the same on Windows, Mac and Linux."""
import json, os, subprocess, sys
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
git = lambda *a, **k: subprocess.run(["git", "-C", ROOT, *a], **k)
git("config", "user.name", "daily-update[bot]", check=True)
git("config", "user.email", "41898282+github-actions[bot]@users.noreply.github.com", check=True)
git("add", "dist", "base", check=True)
if git("diff", "--cached", "--quiet").returncode == 0:
    print("no changes"); sys.exit(0)
u = json.load(open(os.path.join(ROOT, "dist", "update.json")))
git("commit", "-q", "-m", f"Daily update: {u['season']} through {u['through']} - {u['games']} games", check=True)
git("push", check=True)
print("pushed:", u["season"], "through", u["through"])
