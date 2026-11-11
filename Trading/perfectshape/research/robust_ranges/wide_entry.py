"""Entering further outside the scan-window band (in half-bands), with and without a 10% stop. Needs concentration.py output."""
import sys
from pathlib import Path
import pandas as pd
sys.path.insert(0, str(Path(__file__).parent))
from stops import rows_from, sim
H = Path(__file__).parent
w = pd.read_pickle(H / "w2520_conc.pkl")
w = w[(w.score >= 0.6) & (w.trades_per_year >= 1.5) & (w.band_over_vol <= 0.45) & (w.vol_last_ratio >= 1.0)]
e = pd.read_pickle(H / "e2e2520_conc.pkl")
res = []
for name, (df, W, hold) in {"study W2520 robust": (w, 2520, 0), "e2e listed robust": (e[e.robust], 2520, 21)}.items():
    paths = rows_from(df, W, hold)
    yrs = df.loc[[p[0] for p in paths], "asof"].str[:4].astype(int).to_numpy()
    for k in (0.0, 0.5, 1.0, 1.5):
        for stop in (0.0, 0.10):
            R = pd.DataFrame([sim(Y, N, D, lo - k * (hi - lo) / 2, hi + k * (hi - lo) / 2, stop=stop)
                              for _, Y, N, D, lo, hi, _a, _b in paths])
            R["succ"] = (R.n_med_win >= 2) & (R.ret > 0)
            res.append({"set": name, "enter beyond edge (hb)": k, "stop": stop, "succ": R.succ.mean(), "rev2": (R.n_med >= 2).mean(),
                        "rev1": (R.n_med >= 1).mean(), "ret": R.ret.mean(), "med": R.ret.median(), "loss20": (R.ret < -0.2).mean(),
                        "ret_tr": R.ret[yrs <= 2019].mean(), "ret_te": R.ret[yrs >= 2020].mean()})
pd.set_option("display.width", 250)
print(pd.DataFrame(res).round(3).to_string(index=False))
