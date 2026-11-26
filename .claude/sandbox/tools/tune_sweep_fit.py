r"""Looks at the results of tune_sweep.py: which values make a race bad, which ones make it different.

usage: tune_sweep_fit.py <out dir> [<out dir> ...]

Per race, relative to the default values on the same track (mean of those runs):
  extra still   = seconds nearly still minus the track's default
  extra resets  = resets minus the track's default
  speed         = computer karts' mean speed / the track's default
A race is "bad" when the karts stood still for long, were reset often, or crawled (see BAD below).
Prints the bad share per value of every row, and the races sorted by badness.
"""
import json
import os
import sys
from collections import defaultdict

ROW_NAMES = ("Ueber", "Motor", "Haft", "Gew", "Brems", "Lenk", "Anpr", "Schw", "Gegner")


def load(dirs):
    recs = []
    for d in dirs:
        for line in open(os.path.join(d, "results.jsonl")):
            r = json.loads(line)
            if "error" not in r:
                recs.append(r)
    base = defaultdict(list)
    for r in recs:
        if r["id"].startswith("default"):
            base[r["track"]].append(r)
    b = {t: {k: sum(x[k] for x in rs) / len(rs) for k in ("stuck", "resets", "mean", "air")} for t, rs in base.items()}
    for r in recs:
        bt = b[r["track"]]
        r["xstill"] = r["stuck"] - bt["stuck"]
        r["xreset"] = r["resets"] - bt["resets"]
        r["speed"] = r["mean"] / bt["mean"]
        r["slowr"] = r["slowest"] / bt["mean"]
    return recs, b


def badness(r):
    """0 = like the defaults; 1 = clearly hardly a race."""
    s = max(0.0, r["xstill"]) / 15.0 + max(0.0, r["xreset"]) / 12.0
    if r["runaway"] is not None:
        s += 2
    return s


def main():
    recs, b = load(sys.argv[1:])
    print("defaults per track:")
    for t in sorted(b):
        print("  t%d: still %.1f resets %.1f mean %.1f air %.2f" % (t, b[t]["stuck"], b[t]["resets"], b[t]["mean"], b[t]["air"]))
    print("%d races" % len(recs))
    for k, name in enumerate(ROW_NAMES):
        groups = defaultdict(list)
        for r in recs:
            groups[r["v"][k]].append(r)
        line = []
        for v in sorted(groups):
            g = groups[v]
            line.append("%d:%d/%.1f/%.2f" % (v, len(g), sum(badness(x) for x in g) / len(g), sum(x["speed"] for x in g) / len(g)))
        print("%-6s %s" % (name, "  ".join(line)))
    recs.sort(key=badness)
    for r in recs:
        print("%-22s %-48s t%d bad %.2f xstill %5.1f xreset %3.0f speed %.2f slow %.2f air %.2f" % (
            r["id"], r["v"], r["track"], badness(r), r["xstill"], r["xreset"], r["speed"], r["slowr"], r["air"]))


if __name__ == "__main__":
    main()


# --- model ---------------------------------------------------------------------------------
import math  # noqa: E402

DEF = (155, 200, 100, 100, 100, 100, 100, 100, 100)


def lg(k, v):
    """Log2 distance of value v of row k from its default (Anpressdruck shifted by 25, Gegner by 150)."""
    if k == 6:
        return math.log2((v + 25) / 125.0)
    if k == 8:
        return math.log2((v + 150) / 250.0)
    return math.log2(v / DEF[k])


def features(v, inter=True):
    f = []
    for k in range(9):
        x = lg(k, v[k])
        f += [max(0.0, x), max(0.0, -x)]
    if inter:
        speed = max(0.0, lg(0, v[0])) + 0.5 * max(0.0, lg(1, v[1]))
        grip = max(0.0, -lg(2, v[2])) + max(0.0, -lg(6, v[6]))
        f += [speed * grip, max(0.0, lg(3, v[3])) * max(0.0, lg(1, v[1]))]
    return f


def solve(A, b):
    n = len(b)
    M = [row[:] + [b[i]] for i, row in enumerate(A)]
    for c in range(n):
        p = max(range(c, n), key=lambda r: abs(M[r][c]))
        M[c], M[p] = M[p], M[c]
        for r in range(n):
            if r != c and M[c][c]:
                q = M[r][c] / M[c][c]
                M[r] = [x - q * y for x, y in zip(M[r], M[c])]
    return [M[i][n] / M[i][i] for i in range(n)]


def ridge(X, y, lam=1.0):
    n = len(X[0]) + 1
    Xb = [[1.0] + x for x in X]
    A = [[sum(r[i] * r[j] for r in Xb) + (lam if i == j and i else 0) for j in range(n)] for i in range(n)]
    b = [sum(r[i] * t for r, t in zip(Xb, y)) for i in range(n)]
    return solve(A, b)


def predict(w, v, inter=True):
    return w[0] + sum(a * x for a, x in zip(w[1:], features(v, inter)))


def fit_report(recs, inter=True, lam=1.0, folds=5):
    y = [min(3.0, badness(r)) for r in recs]
    X = [features(r["v"], inter) for r in recs]
    w = ridge(X, y, lam)
    # cross-validated error
    err = 0.0
    for f in range(folds):
        tr = [i for i in range(len(recs)) if i % folds != f]
        te = [i for i in range(len(recs)) if i % folds == f]
        wf = ridge([X[i] for i in tr], [y[i] for i in tr], lam)
        err += sum((predict(wf, recs[i]["v"], inter) - y[i]) ** 2 for i in te)
    base = sum((t - sum(y) / len(y)) ** 2 for t in y)
    return w, 1 - err / base


def bad2(r):
    """Continuous badness: airtime, extra still time and extra resets above what the defaults scatter."""
    # (no term for "runaway": in these sets it only came from a speed spike while a kart was reset)
    s = max(0.0, r["air"] - 0.12) / 0.25 + max(0.0, r["xstill"] - 5) / 25.0 + max(0.0, r["xreset"] - 3) / 15.0
    return min(3.0, s)


def hinge(v):
    h = {}
    for k, n in enumerate(ROW_NAMES):
        x = lg(k, v[k])
        h[n + "+"], h[n + "-"] = max(0.0, x), max(0.0, -x)
    return h


PAIRS = [("Motor+", "Gew+"), ("Motor+", "Haft+"), ("Ueber+", "Anpr-"), ("Ueber+", "Haft-"), ("Gew+", "Haft+"),
         ("Motor+", "Anpr-"), ("Ueber+", "Motor+"), ("Gegner+", "Motor+"), ("Schw+", "Gew+"), ("Schw-", "Ueber+")]


def feats2(v, pairs=PAIRS):
    h = hinge(v)
    names = sorted(h)
    return [h[n] for n in names] + [h[a] * h[b] for a, b in pairs], names + ["%s*%s" % p for p in pairs]


def fit2(recs, lam=1.0, pairs=PAIRS, folds=5, target=bad2):
    X = [feats2(r["v"], pairs)[0] for r in recs]
    names = feats2(recs[0]["v"], pairs)[1]
    y = [target(r) for r in recs]
    w = ridge(X, y, lam)
    err = 0.0
    for f in range(folds):
        tr = [i for i in range(len(recs)) if i % folds != f]
        te = [i for i in range(len(recs)) if i % folds == f]
        wf = ridge([X[i] for i in tr], [y[i] for i in tr], lam)
        err += sum((wf[0] + sum(a * x for a, x in zip(wf[1:], X[i])) - y[i]) ** 2 for i in te)
    base = sum((t - sum(y) / len(y)) ** 2 for t in y)
    return w, names, 1 - err / base


# --- knot model (the form the game uses: per-row hinge terms plus products of two sums) ----------
KNOTS = (0.0, 0.75, 1.5)


def knot_feats(v):
    f, names = [], []
    for k, n in enumerate(ROW_NAMES):
        x = lg(k, v[k])
        for side, sname in ((1, "+"), (-1, "-")):
            for kn in KNOTS:
                f.append(max(0.0, side * x - kn))
                names.append("%s%s%.2f" % (n, sname, kn))
    h = hinge(v)
    speed = h["Ueber+"] + 0.5 * h["Motor+"]
    slide = h["Haft-"] + h["Anpr-"]
    pairs = {"Motor+*Gew+": h["Motor+"] * h["Gew+"], "speed*slide": speed * slide,
             "Motor+*Haft+": h["Motor+"] * h["Haft+"], "Gegner+*Motor+": h["Gegner+"] * h["Motor+"],
             "Ueber+*Lenk-": h["Ueber+"] * h["Lenk-"], "Gew+*Schw+": h["Gew+"] * h["Schw+"],
             "Motor+*Anpr+": h["Motor+"] * h["Anpr+"], "Ueber+*Anpr+": h["Ueber+"] * h["Anpr+"],
             "Ueber+*Haft+": h["Ueber+"] * h["Haft+"]}   # Haft-*Anpr- was tried: weight 0.06, left out
    for n in sorted(pairs):
        f.append(pairs[n])
        names.append(n)
    return f, names


FREE = ("Motor+*Anpr+", "Motor+*Haft+", "Ueber+*Anpr+", "Ueber+*Haft+")    # may get a negative weight


def nn_fit(recs, lam=2.0, target=bad2):
    """Ridge on the knot features, dropping features with a negative weight until none is left
    (risk points never go below zero for a value further from the default)."""
    X = [knot_feats(r["v"])[0] for r in recs]
    names = knot_feats(recs[0]["v"])[1]
    y = [target(r) for r in recs]
    keep = list(range(len(names)))
    while True:
        Xk = [[x[i] for i in keep] for x in X]
        w = ridge(Xk, y, lam)
        neg = [keep[j] for j, c in enumerate(w[1:]) if c < 0 and names[keep[j]] not in FREE]
        if not neg:
            break
        keep = [i for i in keep if i not in neg]
    full = [0.0] * len(names)
    for j, i in enumerate(keep):
        full[i] = w[1 + j]
    return w[0], full, names


def nn_cv(recs, lam=2.0, folds=5, target=bad2):
    err = 0.0
    y = [target(r) for r in recs]
    for f in range(folds):
        tr = [r for i, r in enumerate(recs) if i % folds != f]
        c, w, _ = nn_fit(tr, lam, target)
        for i, r in enumerate(recs):
            if i % folds == f:
                p = c + sum(a * b for a, b in zip(w, knot_feats(r["v"])[0]))
                err += (p - y[i]) ** 2
    base = sum((t - sum(y) / len(y)) ** 2 for t in y)
    return 1 - err / base


# --- the patcher's LIMIT_POINTS from a fit ---------------------------------------------------
PUSH = (  # set by hand, see the patcher
    "((UP, 0, 1.0), (DOWN, 0, -1.0))", "((UP, 0, 0.5), (DOWN, 0, -0.5))", "((DOWN, 0, 1.0), (UP, 0, -0.25))",
    "((UP, 0, 0.25), (DOWN, 0, 0.25))", "((DOWN, 0, 0.5),)", "((DOWN, 0, 0.75), (UP, 0, -0.25))",
    "((DOWN, 0, 0.5), (UP, 0, -0.15))", "((UP, 0, 0.5), (DOWN, 0, 0.5))", "((UP, 0, 2.0), (DOWN, 0, -1.0))")
PATCH_ROWS = ("Übersetzung", "Motorkraft", "Haftung", "Gewicht", "Bremsen", "Lenkung", "Anpressdruck",
              "Schwerkraft", "Gegner")
# pair features -> (first channel, its row term), (second channel, its row term)
PAIR_CH = {"Gegner+*Motor+": ("opp", "power"), "Motor+*Gew+": ("power", "mstab"), "Motor+*Anpr+": ("power", "mstab"),
           "Motor+*Haft+": ("power", "mstab"), "Ueber+*Lenk-": ("gear", "ustab"), "Ueber+*Anpr+": ("gear", "ustab"),
           "Ueber+*Haft+": ("gear", "ustab"), "Haft-*Anpr-": ("slip", "slipd")}


def emit(w, names):
    """Python source of LIMIT_POINTS for the patcher."""
    chans = ("risk", "push", "power", "gear", "opp", "mstab", "ustab", "slip", "slipd")
    terms = {k: {ch: [] for ch in chans if ch != "push"} for k in range(9)}
    idx = {n: k for k, n in enumerate(ROW_NAMES)}
    for n, x in zip(names, w):
        if not x:
            continue
        if "*" in n:
            a, b = n.split("*")
            first, second = PAIR_CH[n]
            # the first factor is a channel with slope 1 (power, gear) or carries the weight (opp)
            if first == "opp":
                terms[idx[a[:-1]]]["opp"] = [(1, 0, round(x, 2))]
                terms[idx[b[:-1]]]["power"] = [(1, 0, 1.0)]
            else:
                terms[idx[a[:-1]]][first] = [(1 if a[-1] == "+" else -1, 0, 1.0)]
                side = 1 if b[-1] == "+" else -1
                terms[idx[b[:-1]]][second].append((side, 0, round(x, 2)))
        else:
            row, side, kn = n[:-5], 1 if n[-5] == "+" else -1, float(n[-4:])
            terms[idx[row]]["risk"].append((side, kn, round(x, 2)))
    out = ["LIMIT_POINTS = (     # per row: channel -> terms (side, knot, slope)"]
    for k in range(9):
        parts = []
        for ch in chans:
            if ch == "push":
                parts.append('"push": %s' % PUSH[k])
                continue
            t = terms[k][ch]
            if t:
                parts.append('"%s": (%s)' % (ch, "".join("(%s, %s, %s), " % ("UP" if s > 0 else "DOWN", ("%g" % kn), "%g" % sl)
                                                         for s, kn, sl in t).rstrip(", ") + ("," if len(t) == 1 else "")))
        out.append("    {%s},   # %s" % (",\n     ".join(parts), PATCH_ROWS[k]))
    out.append(")")
    return "\n".join(out)


def speed_fit(recs, lam=2.0):
    """log2 of the computer karts' mean speed against the defaults, on races that worked (badness < 0.5)."""
    good = [r for r in recs if bad2(r) < 0.5 and r["speed"] > 0]
    X = [[h for h in hinge(r["v"]).values()] for r in good]
    names = list(hinge(good[0]["v"]).keys())
    y = [math.log2(r["speed"]) for r in good]
    return ridge(X, y, lam), names


def speed_pred(w, v):
    return 2 ** (w[0] + sum(a * x for a, x in zip(w[1:], hinge(v).values())))
