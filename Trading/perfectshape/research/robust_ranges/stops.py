"""Do Trade Lab stops (loss %, max days) cut the breaks of robust ranges without killing the reversions?
Replays trade.js 'bandscan': fixed scan-window p10 band, enter beyond an edge, exit at the median, decide on the
close / fill next close, 5 bps per leg, pair mode (long one leg, short the other, equal notional), start flat."""
import sys
from pathlib import Path
import numpy as np
import pandas as pd
R0 = Path(__file__).resolve().parent
sys.path.insert(0, str(R0))
sys.path.insert(0, str(R0.parents[1] / "src"))
from harness import load_all  # noqa: E402
from perfectshape.shapes import range_band  # noqa: E402

panel = load_all()
sym = {s: i for i, s in enumerate(panel.symbols)}


def sim(Y, N, D, lo, hi, stop=0.0, maxdays=0, bps=5.0, brk_lo=None, brk_hi=None, dead=False):
    """Y/N/D from the scan end (index 0) to the end of the final test."""
    mid = (lo + hi) / 2
    cash, pos, pending, blocked = 1.0, None, None, {1: False, -1: False}
    trades = []
    e = len(Y) - 1
    c = bps / 1e4

    def value(t):
        return cash if pos is None else pos["E"] * (1 + pos["side"] * (N[t] / pos["N0"] - D[t] / pos["D0"]))

    def do(t, act):
        nonlocal cash, pos
        if act[0] in ("close", "reverse"):
            v = value(t)
            gross = pos["E"] * (N[t] / pos["N0"] + D[t] / pos["D0"])
            cash = v - c * gross
            trades.append((pos["side"], pos["t0"], t, cash / pos["eb"] - 1, act[1]))
            pos = None
        if act[0] in ("open", "reverse"):
            side = act[2]
            pos = {"side": side, "t0": t, "N0": N[t], "D0": D[t], "E": cash * (1 - c * 2), "eb": cash}

    off = False
    for t in range(e + 1):
        if pending:
            if t == e:
                if pending[0] in ("close", "reverse"):
                    do(t, ("close", pending[1]))
            else:
                do(t, pending)
            pending = None
        if t == e:
            break
        y = Y[t]
        sig = 1 if y <= lo else (-1 if y >= hi else 0)
        broke = brk_lo is not None and (y < brk_lo or y > brk_hi)
        if broke and dead:
            off = True
        if off:
            sig = 0
        for s_ in (1, -1):
            if sig != s_:
                blocked[s_] = False
        act = None
        if pos:
            r = value(t) / pos["eb"] - 1
            why = None
            if stop > 0 and r <= -stop:
                why = "stop"
            elif broke and ((pos["side"] > 0 and y < brk_lo) or (pos["side"] < 0 and y > brk_hi)):
                why = "stop"
            elif maxdays > 0 and t - pos["t0"] >= maxdays:
                why = "days"
            elif pos["side"] > 0 and y >= mid:
                why = "median"
            elif pos["side"] < 0 and y <= mid:
                why = "median"
            if why:
                if why == "stop":
                    blocked[pos["side"]] = True
                again = sig != 0 and sig != pos["side"] and not blocked[sig]
                act = ("reverse", why, sig) if again else ("close", why, 0)
        elif sig != 0 and not blocked[sig]:
            act = ("open", "signal", sig)
        if act:
            pending = act
    if pos:
        do(e, ("close", "end"))
    n_med = sum(1 for tr in trades if tr[4] == "median")
    n_med_win = sum(1 for tr in trades if tr[4] == "median" and tr[3] > 0)
    worst = min([tr[3] for tr in trades], default=0.0)
    return {"ret": cash - 1, "n_med": n_med, "n_med_win": n_med_win, "worst": worst,
            "n_stop": sum(1 for tr in trades if tr[4] in ("stop", "days"))}


def rows_from(df, W, hold, F=504):
    out = []
    for (sector, asof), g in df.groupby(["sector", "asof"]):
        ai = int(np.searchsorted(panel.dates, np.datetime64(asof[:10]), side="right") - 1)
        s0 = ai - hold - W + 1
        for i, r in g.iterrows():
            nu, de = r.num.split(), r.den.split()
            X = panel.close[s0:ai + F + 1][:, [sym[t] for t in nu + de]]
            X = X / X[0]
            N, D = X[:, :3].mean(1), X[:, 3:].mean(1)
            Y = np.log(N) - np.log(D)
            lo, _, hi = range_band(Y[:W], 10)
            a = ai - s0
            out.append((i, Y[a:], N[a:], D[a:], lo, hi, Y[:W].min(), Y[:W].max()))
    return out


if __name__ == "__main__":
    H = Path(__file__).parent
    w = pd.read_pickle(H / "w2520_conc.pkl")
    w = w[(w.score >= 0.6) & (w.trades_per_year >= 1.5) & (w.band_over_vol <= 0.45) & (w.vol_last_ratio >= 1.0)]
    e = pd.read_pickle(H / "e2e2520_conc.pkl")
    w12 = pd.read_pickle(H / "w1260_conc.pkl")
    w12 = w12[(w12.score >= 0.6) & (w12.trades_per_year >= 1.5) & (w12.band_over_vol <= 0.45) & (w12.vol_last_ratio >= 1.0)]
    w12 = w12.sample(3000, random_state=0)
    sets = {"study W2520 robust": (w, 2520, 0), "e2e listed robust": (e[e.robust], 2520, 21),
            "e2e listed plain": (e[~e.robust], 2520, 21), "study W1260 robust (3000)": (w12, 1260, 0)}
    res = []
    for name, (df, W, hold) in sets.items():
        paths = rows_from(df, W, hold)
        yrs = df.loc[[p[0] for p in paths], "asof"].str[:4].astype(int).to_numpy()
        variants = [("none", {}), ("stop 10%", {"stop": 0.10})]
        for m in (0.0, 0.5, 1.0):
            for dead in (False, True):
                variants.append((f"extreme+{m}hb{' dead' if dead else ''}", {"brk": m, "dead": dead}))
        for k in (1.0, 1.5, 2.0):
            variants.append((f"edge+{k}hb dead", {"edge": k, "dead": True}))
        for vname, v in variants:
            out = []
            for _, Y, N, D, lo, hi, ymin, ymax in paths:
                half = (hi - lo) / 2
                kw = {"stop": v.get("stop", 0.0), "dead": v.get("dead", False)}
                if "brk" in v:
                    kw.update(brk_lo=ymin - v["brk"] * half, brk_hi=ymax + v["brk"] * half)
                if "edge" in v:
                    kw.update(brk_lo=lo - v["edge"] * half, brk_hi=hi + v["edge"] * half)
                out.append(sim(Y, N, D, lo, hi, **kw))
            R = pd.DataFrame(out)
            R["succ"] = (R.n_med_win >= 2) & (R.ret > 0)
            res.append({"set": name, "rule": vname, "n": len(R), "succ": R.succ.mean(),
                        "rev2": (R.n_med >= 2).mean(), "ret": R.ret.mean(), "med": R.ret.median(),
                        "loss20": (R.ret < -0.2).mean(), "loss35": (R.ret < -0.35).mean(), "p10": R.ret.quantile(.1),
                        "ret_tr": R.ret[yrs <= 2019].mean(), "ret_te": R.ret[yrs >= 2020].mean(),
                        "l20_tr": (R.ret[yrs <= 2019] < -0.2).mean(), "l20_te": (R.ret[yrs >= 2020] < -0.2).mean(),
                        "stopped": (R.n_stop > 0).mean()})
        print(name, "done", flush=True)
    pd.set_option("display.width", 250)
    print(pd.DataFrame(res).round(3).to_string(index=False))
