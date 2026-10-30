"""Small repairs to NBA.com live play-by-play before pbpstats reads it (shared by build_live_json.py and
box_from_live.py):
- a rebound must point back to an earlier missed 2PT / 3PT / free throw. Since 2025-26 an end-of-quarter heave is
  its own action type ("heave"), and some 2026-27 rebounds point to a shot pbpstats can't find; pbpstats then
  crashes on the game, so those few rebounds are dropped.
- 2026-27 files leave personId out of period / game records (it was 0 before).
- plays entered late by the scorer (e.g. two free throws from 2:55 logged after plays at 1:45) are put back in game
  order: within each period, a stable sort by game clock (counting down). A file already in order is unchanged.
- a violation with no subType (seen in 2026-27) gets "unspecified": none of the special kinds pbpstats checks for
  (goaltending, lane, kicked ball...), so it's read as an ordinary violation instead of crashing the game."""
import re
_CLK = re.compile(r"PT(\d+)M([\d.]+)S")


def _secs(c):
    m = _CLK.match(c or ""); return float(m.group(1)) * 60 + float(m.group(2)) if m else None
SHOTS = {"2pt", "3pt", "freethrow"}


def fix(actions):
    # stable sort by (period, clock counting down); actions without a readable clock keep the previous one's place
    key, last = [], (0, 0.0)
    for a in actions:
        sc = _secs(a.get("clock")); last = (a.get("period", last[0]), -sc if sc is not None else last[1]); key.append(last)
    actions = [a for _, _, a in sorted(zip(key, range(len(actions)), actions), key=lambda x: (x[0], x[1]))]
    seen, out, dropped = set(), [], 0
    for a in actions:
        if a.get("personId") in (None, ""): a["personId"] = 0
        if a.get("actionType") == "violation" and not a.get("subType"): a["subType"] = "unspecified"
        if a.get("actionType") == "rebound" and a.get("shotActionNumber") not in seen:
            dropped += 1; continue
        if a.get("actionType") in SHOTS and a.get("actionNumber") is not None: seen.add(a["actionNumber"])
        out.append(a)
    return out, dropped
