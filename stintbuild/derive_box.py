"""Turn raw pbpstats stat keys into the pbpstats.com column names that features.py uses."""
import pandas as pd, numpy as np

Z2 = ["AtRim", "ShortMidRange", "LongMidRange", "UnknownDistance2pt"]
Z3 = ["Arc3", "Corner3"]


def c(W, k):
    return W[k] if k in W else pd.Series(0.0, index=W.index)


def derive(W):
    o = pd.DataFrame(index=W.index)
    for k in ["EntityId", "TeamId", "Season", "season_type", "GamesPlayed", "OffPoss", "DefPoss"]: o[k] = c(W, k)
    o["SecondsPlayed"] = (c(W, "SecondsPlayedOff") + c(W, "SecondsPlayedDef"))
    fgm = lambda z: c(W, f"Assisted{z}") + c(W, f"Unassisted{z}")
    fga = lambda z: fgm(z) + c(W, f"Missed{z}") + c(W, f"{z}Blocked")
    o["AtRimFGA"] = fga("AtRim"); o["ShortMidRangeFGA"] = fga("ShortMidRange") + fga("UnknownDistance2pt") * 0.5
    o["LongMidRangeFGA"] = fga("LongMidRange") + fga("UnknownDistance2pt") * 0.5
    o["FG2A"] = sum(fga(z) for z in Z2); o["FG2M"] = sum(fgm(z) for z in Z2)
    o["FG3A"] = sum(fga(z) for z in Z3); o["FG3M"] = sum(fgm(z) for z in Z3)
    tech = c(W, "TechFtsMade")      # the parser files made technical FTs separately; misses stay in FtsMissed
    o["FTM"] = c(W, "FtsMade") + tech; o["FTA"] = c(W, "FtsMade") + tech + c(W, "FtsMissed")
    o["Points"] = 2 * o.FG2M + 3 * o.FG3M + o.FTM
    o["PtsUnassisted2s"] = 2 * sum(c(W, f"Unassisted{z}") for z in Z2)
    o["PtsUnassisted3s"] = 3 * sum(c(W, f"Unassisted{z}") for z in Z3)
    o["AtRimAssists"] = c(W, "AtRimAssists"); o["Arc3Assists"] = c(W, "Arc3Assists"); o["Corner3Assists"] = c(W, "Corner3Assists")
    o["Assists"] = sum(c(W, f"{z}Assists") for z in Z2 + Z3)
    o["LiveBallTurnovers"] = c(W, "LostBallTurnovers") + c(W, "BadPassTurnovers")
    o["DeadBallTurnovers"] = c(W, "DeadBallTurnovers")
    o["Steals"] = c(W, "LostBallSteals") + c(W, "BadPassSteals")
    o["Blocks"] = sum(c(W, f"Blocked{z}") for z in Z2 + Z3)
    off = [k for k in W.columns if k.endswith("OffRebounds")]; dfn = [k for k in W.columns if k.endswith("DefRebounds")]
    o["OffRebounds"] = W[off].sum(axis=1); o["DefRebounds"] = W[dfn].sum(axis=1)
    drawn = [k for k in W.columns if k.endswith(" Drawn") and "Offensive" not in k and "Charge" not in k]
    o["FoulsDrawn"] = W[drawn].sum(axis=1)
    o["Offensive Fouls"] = c(W, "Offensive Fouls")
    o["Charge Fouls Drawn"] = c(W, "Charge Fouls Drawn")
    fouls = [k for k in W.columns if k.endswith("Fouls") and not k.endswith("Drawn") and "Technical" not in k]
    o["Fouls"] = W[fouls].sum(axis=1)
    o["PlusMinus"] = c(W, "PlusMinus"); o["OpponentPoints"] = c(W, "OpponentPoints")
    return o
