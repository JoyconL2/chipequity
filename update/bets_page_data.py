"""Data file for the owner's private picks page: bets/bets.json without the props (games only), plus a small
summary of the recorded props. usage: python update/bets_page_data.py bets.json out.json"""
import json, sys
B = json.load(open(sys.argv[1]))
keep = ("day", "home", "away", "state", "hs", "as", "p", "q", "mlh", "mla", "spread", "total", "edge", "side", "flag", "at", "won", "units", "start", "closing")
games = sorted(({"id": k, **{f: g[f] for f in keep if f in g}} for k, g in B["games"].items() if "p" in g), key=lambda g: (g["day"], g.get("start", ""), g["id"]))
pr = [r for r in B.get("props", {}).values() if r.get("won") is not None and "side" in r]
json.dump({"updated": B.get("updated"), "games": games,
           "props": {"graded": len(pr), "won": sum(1 for r in pr if r["won"]), "units": round(sum(r["units"] for r in pr), 2)}},
          open(sys.argv[2], "w"), separators=(",", ":"))
print(f"{len(games)} games, updated {B.get('updated')}")
