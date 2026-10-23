"""On a failed run: show the end of the update's output (and of the last step log) as an error on the run's
summary page, so it can be read without downloading the logs."""
import glob, os
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
def show(path, title, n=40):
    if not os.path.exists(path): return
    lines = open(path, errors="replace").read().strip().splitlines()[-n:]
    msg = "%0A".join(l.replace("%", "%25").replace("\r", "") for l in lines)
    print(f"::error title={title}::{msg}")
show(os.path.join(ROOT, "update", "tmp", "run_out.txt"), "update output (last lines)")
logs = sorted(glob.glob(os.path.join(ROOT, "update", "tmp", "*.log")), key=os.path.getmtime)
if logs: show(logs[-1], f"last step log: {os.path.basename(logs[-1])}", 30)
