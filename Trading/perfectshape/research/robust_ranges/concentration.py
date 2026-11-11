"""Post-hoc member-concentration features for every study row (fixed-share legs drift; what is held at the scan end)."""
import sys
from pathlib import Path
import numpy as np
import pandas as pd
R0 = Path(__file__).resolve().parent
sys.path.insert(0, str(R0))
from harness import load_all  # noqa: E402

panel = load_all()
sym = {s: i for i, s in enumerate(panel.symbols)}


def feats(X, num, den, last):
    """X (T, n) normalised to 1 at window start, ending at the scan end; num/den (m, k) column indices."""
    k = num.shape[1]
    out = {}
    Xe = X[-1]
    for leg, idx in (("n", num), ("d", den)):
        w = Xe[idx] / Xe[idx].sum(1, keepdims=True)
        out[f"wmax_{leg}"] = w.max(1)
        out[f"neff_{leg}"] = 1 / (w ** 2).sum(1)
        g = np.log(Xe[idx])
        out[f"gdisp_{leg}"] = g.max(1) - g.min(1)
    out["w_end_max"] = np.maximum(out["wmax_n"], out["wmax_d"])
    out["neff_min"] = np.minimum(out["neff_n"], out["neff_d"])
    out["gdisp_max"] = np.maximum(out["gdisp_n"], out["gdisp_d"])
    R = np.diff(np.log(X), axis=0)
    for tag, s in (("full", 0), ("last", X.shape[0] - 1 - last)):
        Xs = X[s:-1]
        wn = Xs[:, num] / Xs[:, num].sum(2, keepdims=True)
        wd = Xs[:, den] / Xs[:, den].sum(2, keepdims=True)
        C = np.concatenate([wn * R[s:, num], -wd * R[s:, den]], axis=2)       # (t, m, 2k)
        r = C.sum(2)
        cov = ((C - C.mean(0)) * (r - r.mean(0))[:, :, None]).mean(0)
        sh = cov / np.maximum(r.var(0), 1e-18)[:, None]
        out[f"ts_{tag}"] = sh.max(1)
        out[f"vol_{tag}"] = r.std(0) * np.sqrt(252)
    out["vol_last_vs_full"] = out["vol_last"] / out["vol_full"]
    return out


def run(df, W, hold=0):
    rows = []
    for (sector, asof), g in df.groupby(["sector", "asof"]):
        ai = int(np.searchsorted(panel.dates, np.datetime64(asof[:10]), side="right") - 1)
        s0 = ai - hold - W + 1 if hold == 0 else ai - hold - W + 1
        tick = sorted(set(" ".join(g.num).split()) | set(" ".join(g.den).split()))
        loc = {t: j for j, t in enumerate(tick)}
        X = panel.close[s0:ai + 1][:, [sym[t] for t in tick]]
        X = X / X[0]
        num = np.array([[loc[t] for t in s.split()] for s in g.num])
        den = np.array([[loc[t] for t in s.split()] for s in g.den])
        f = feats(X, num, den, last=252)
        rows.append(pd.DataFrame(f, index=g.index))
    return pd.concat(rows)


if __name__ == "__main__":
    for tag, W, hold in (("w2520", 2520, 0), ("w1260", 1260, 0), ("e2e2520", 2520, 21)):
        df = pd.concat([pd.read_pickle(f) for f in sorted((R0 / "parts").glob(f"{tag}_*.pkl"))], ignore_index=True)
        f = run(df, W, hold)
        df = df.join(f)
        df.to_pickle(R0 / f"{tag}_conc.pkl")
        print(tag, df.shape, flush=True)
