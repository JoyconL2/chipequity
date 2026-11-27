"""Who counts as the lead in a stint: highest score on the floor.
  r3      3-year regression (window ending that season; 1-year if none)
  c<k>    3-year regression + k x (shot creation / league - 1): the site's rule (c2, 1.1). Shot creation = self-created
          rim, mid and three attempts + rim, mid, three and transition shots assisted, per 75 (play types)
  u<k>    3-year regression + k x (usage / league usage - 1): the player running the offense breaks near-ties (before 1.1)
          (u15 = 1.5, u3 = 3). Usage is the regular-season possession-weighted usage rate from data.json."""
import json, pandas as pd
def lead_map(tag="u2", base="."):
    d1 = pd.read_csv(f"{base}/../cepm/disp1.csv"); d3 = pd.read_csv(f"{base}/../cepm/disp3.csv")
    m1 = {(int(p), s): r for p, s, r in zip(d1.player, d1.window_end, d1.rapm)}
    m3 = {(int(p), s): r for p, s, r in zip(d3.player, d3.window_end, d3.rapm)}
    out = {k: (m3[k] if k in m3 else v) for k, v in m1.items()}
    if tag == "r3": return out
    if tag.startswith("c"):          # creation: self-created shots + shots created for teammates (play types), per 75, vs league
        k_ = float(tag[1:]); F = pd.read_csv(f"{base}/../playtypes/pt_features.csv")
        F["cr"] = F.rim_self75 + F.mid_self75 + F.three_self75 + F.ast_rim75 + F.ast_mid75 + F.ast_three75 + F.ast_transition75
        lgc = (F.cr * F.pos).groupby(F.season).sum() / F.pos.groupby(F.season).sum()
        CR = {(int(p), s): c / lgc[s] for p, s, c in zip(F.p, F.season, F.cr)}
        return {k: v + k_ * (min(2.5, max(0.3, CR.get(k, 1.0))) - 1) for k, v in out.items()}
    k_ = {"u15": 1.5, "u3": 3.0, "u2": 2.0}[tag]
    D = json.load(open(f"{base}/../site/data.json")); S = D["seasons"]; ids = [int(x) for x in D["ids"]]
    P = pd.DataFrame({c: D["P"][c] for c in ("p", "s", "t", "pos", "usg")}); P = P[P.t == 0]; P["up"] = P.usg * P.pos
    g = P.groupby(["p", "s"])[["up", "pos"]].sum(); lg = (P.groupby("s").up.sum() / P.groupby("s").pos.sum()).to_dict()
    U = {(ids[k], S[s]): (r.up / r.pos) / lg[s] for (k, s), r in g.iterrows() if r.pos > 0}
    return {k: v + k_ * (min(2.0, max(0.5, U.get(k, 1.0))) - 1) for k, v in out.items()}
