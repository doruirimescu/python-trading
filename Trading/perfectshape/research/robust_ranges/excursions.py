"""How often the forward ratio leaves the scan window's own 10-year extremes (listed robust ranges). Needs concentration.py output."""
import sys
from pathlib import Path
import numpy as np
import pandas as pd
sys.path.insert(0, str(Path(__file__).parent))
from stops import rows_from, sim
H = Path(__file__).parent
e = pd.read_pickle(H / "e2e2520_conc.pkl")
e = e[e.robust]
paths = rows_from(e, 2520, 21)
out = []
for i, Y, N, D, lo, hi, ymin, ymax in paths:
    half = (hi - lo) / 2
    Yf = Y[1:]
    out.append({"ext_lo_hb": (lo - ymin) / half, "ext_hi_hb": (ymax - hi) / half,
                "broke_ext": bool((Yf < ymin).any() or (Yf > ymax).any()),
                "max_out_hb": max(0, (lo - Yf.min()) / half, (Yf.max() - hi) / half),
                "n_stop10": sim(Y, N, D, lo, hi, stop=0.10)["n_stop"]})
R = pd.DataFrame(out)
print(R.describe().round(2).to_string())
print("share breaking the 10y extreme within 2y:", R.broke_ext.mean())
