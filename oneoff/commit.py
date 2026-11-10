import subprocess
g = lambda *a: subprocess.run(["git", *a], check=True)
g("config", "user.name", "oneoff[bot]"); g("config", "user.email", "41898282+github-actions[bot]@users.noreply.github.com")
g("add", "oneoff/out"); g("commit", "-qm", "one-off: NBA.com game ids 1996-2026 + video probe"); g("push")
