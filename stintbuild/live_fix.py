"""Small repairs to NBA.com live play-by-play before pbpstats reads it (shared by build_live_json.py and
box_from_live.py):
- a rebound must point back to an earlier missed 2PT / 3PT / free throw. Since 2025-26 an end-of-quarter heave is
  its own action type ("heave"), and some 2026-27 rebounds point to a shot pbpstats can't find; pbpstats then
  crashes on the game, so those few rebounds are dropped.
- 2026-27 files leave personId out of period / game records (it was 0 before)."""
SHOTS = {"2pt", "3pt", "freethrow"}


def fix(actions):
    seen, out, dropped = set(), [], 0
    for a in actions:
        if a.get("personId") in (None, ""): a["personId"] = 0
        if a.get("actionType") == "rebound" and a.get("shotActionNumber") not in seen:
            dropped += 1; continue
        if a.get("actionType") in SHOTS and a.get("actionNumber") is not None: seen.add(a["actionNumber"])
        out.append(a)
    return out, dropped
