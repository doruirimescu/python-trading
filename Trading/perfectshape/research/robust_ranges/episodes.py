"""Episodes after the scan (the Trade Lab's "After the scan" backtest) on the end-to-end replay. Needs concentration.py output."""
import sys
from pathlib import Path
import numpy as np
import pandas as pd
sys.path.insert(0, str(Path(__file__).parent))
from stops import rows_from  # noqa: E402


def episode(Y, N, D, lo, hi, H, max_swings, mode="pair", bps=5.0, stop=0.0):
    mid = (lo + hi) / 2
    Y, N, D = Y[:H + 1], N[:H + 1], D[:H + 1]
    e = len(Y) - 1
    c = bps / 1e4
    cash, pos, pending, swings, wins, trades = 1.0, None, None, 0, 0, []
    legs = 2 if mode == "pair" else 1

    def value(t):
        if pos is None:
            return cash
        n, d = N[t] / pos["N0"], D[t] / pos["D0"]
        if mode == "pair":
            return pos["E"] * (1 + pos["side"] * (n - d))
        return pos["E"] * (n if pos["side"] > 0 else d)

    first_entry = None
    for t in range(e + 1):
        if pending:
            act = pending
            pending = None
            if act[0] == "close" or t == e:
                if pos:
                    v = value(t)
                    gross = pos["E"] * ((N[t] / pos["N0"] + D[t] / pos["D0"]) if mode == "pair" else v / pos["E"])
                    cash = v - c * gross
                    r = cash / pos["eb"] - 1
                    trades.append((act[1], r))
                    if act[1] == "median":
                        swings += 1
                        wins += r > 0
                    pos = None
            elif act[0] == "open":
                pos = {"side": act[1], "N0": N[t], "D0": D[t], "E": cash * (1 - c * legs), "eb": cash}
                first_entry = t if first_entry is None else first_entry
        if t == e:
            break
        y = Y[t]
        if pos:
            r = value(t) / pos["eb"] - 1
            if stop and r <= -stop:
                pending = ("close", "stop")
            elif (pos["side"] > 0 and y >= mid) or (pos["side"] < 0 and y <= mid):
                pending = ("close", "median")
        elif swings < max_swings and not any(k == "stop" for k, _ in trades):
            if y <= lo:
                pending = ("open", 1)
            elif y >= hi:
                pending = ("open", -1)
    if pos:   # still open at the horizon: closed at the last bar
        v = value(e)
        cash = v * (1 - c)
        trades.append(("horizon", cash / pos["eb"] - 1))
    return {"ret": cash - 1, "swings": swings, "wins": wins, "traded": first_entry is not None,
            "days_to_entry": first_entry if first_entry is not None else np.nan, "open_at_end": any(k == "horizon" for k, _ in trades)}


H_ = Path(__file__).parent
e = pd.read_pickle(H_ / "e2e2520_conc.pkl")
rows = []
for robust in (True, False):
    df = e[e.robust == robust]
    paths = rows_from(df, 2520, 21)
    bp = df.loc[[p[0] for p in paths], "band_pos"].to_numpy()
    yrs = df.loc[[p[0] for p in paths], "asof"].str[:4].astype(int).to_numpy()
    groups = {"at an extreme now (outside the band)": (bp <= 0) | (bp >= 1),
              "near an edge (outer 15% or outside)": (bp <= 0.15) | (bp >= 0.85),
              "inside the band (15-85%)": (bp > 0.15) & (bp < 0.85), "all listed": np.ones(len(bp), bool)}
    for H in (126, 252, 378):
        for ms in (1, 2):
            for mode in ("pair", "rotation"):
                R = pd.DataFrame([episode(Y, N, D, lo, hi, H, ms, mode) for _, Y, N, D, lo, hi, _a, _b in paths])
                for g, m in groups.items():
                    r = R[m]
                    rows.append({"robust": robust, "H_years": H / 252, "max_swings": ms, "mode": mode, "group": g, "n": int(m.sum()),
                                 "traded": r.traded.mean(), "got_max_swings": (r.swings >= ms).mean(),
                                 "all_swings_won": ((r.wins >= ms)).mean(), "ret": r.ret.mean(), "med": r.ret.median(),
                                 "loss10": (r.ret < -0.10).mean(), "loss20": (r.ret < -0.20).mean(), "open_end": r.open_at_end.mean(),
                                 "ret_15_19": r.ret[yrs[m] <= 2019].mean(), "ret_20_24": r.ret[yrs[m] >= 2020].mean()})
out = pd.DataFrame(rows)
out.to_pickle(H_ / "episodes.pkl")
pd.set_option("display.width", 260); pd.set_option("display.max_rows", 400)
print(out[(out["mode"] == "pair")].round(3).to_string(index=False))
