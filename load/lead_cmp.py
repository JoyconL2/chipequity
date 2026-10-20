import os, numpy as np, pandas as pd
g = {}; exec(open("po_test.py").read().split('if __name__ == "__main__":')[0], g); nm = g["nm"]; pid = {v: k for k, v in nm.items()}
r = [g["match"](g["board"](w, 2, "t", "rs"))[0] for w in (1, 3, 5)]
print(os.environ["LEADBY"], "rank match", round(np.mean(r), 3))
B1 = g["board"](1, 2, "t", "rs").sort_values("v", ascending=False).reset_index(drop=True)
for who, s in (("Kobe Bryant", "2008-09"), ("Lamar Odom", "2008-09"), ("Luka Dončić", "2023-24"), ("Kyrie Irving", "2023-24"), ("LeBron James", "2017-18"), ("Kevin Garnett", "2003-04")):
    x = B1[(B1.p == pid[who]) & (B1.s == s)]; print(f"   {who} {s}: {x.v.iloc[0]:+.2f} (#{x.index[0] + 1})")
B5 = g["board"](5, 2, "t", "rs").sort_values("v", ascending=False).drop_duplicates("p").reset_index(drop=True)
print("   5y:", "; ".join(f"{nm[p].split()[-1]} #{i+1}" for i, p in enumerate(B5.p) if nm[p] in ("Luka Dončić", "Kyrie Irving", "Kevin Garnett", "Michael Jordan", "Stephen Curry", "James Harden", "Russell Westbrook")))
print("   5y top10:", ", ".join(nm[p].split()[-1] for p in B5.p[:10]))
