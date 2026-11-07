import subprocess, sys
g = lambda *a: subprocess.run(["git", *a], check=False)
g("config", "user.name", "hist80[bot]"); g("config", "user.email", "41898282+github-actions[bot]@users.noreply.github.com")
g("add", "-A", "hist80/raw")
if subprocess.run(["git", "diff", "--cached", "--quiet"]).returncode == 0: print("nothing to commit"); sys.exit(0)
g("commit", "-m", "hist80: raw NBA.com season totals"); sys.exit(subprocess.run(["git", "push"]).returncode)
