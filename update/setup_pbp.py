"""Get the pbpstats parser at the exact version the history was built with (pbplib/ at the repo root).
Kept between runs on a self-hosted runner, so it's only downloaded once. Works the same on Windows, Mac and Linux."""
import os, subprocess, sys
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LIB = os.path.join(ROOT, "pbplib"); REV = "e7ccf2fb6326da630a3cf1665aac964a1e108f4c"
git = lambda *a: subprocess.run(["git", *a], check=True)
if not os.path.isdir(os.path.join(LIB, ".git")):
    git("clone", "https://github.com/dblackrun/pbpstats.git", LIB)
have = subprocess.run(["git", "-C", LIB, "rev-parse", "HEAD"], capture_output=True, text=True).stdout.strip()
if have != REV:
    git("-C", LIB, "checkout", "-q", REV)
print("pbpstats parser ready at", REV[:7])
