"""Fit the medal model of the challenges to stretch_pace.py runs and print the patcher's tables (sandbox).

usage: pace_fit.py <pace dir> [--q 0.3] [--skip 8] [--check]

Model (challenge_medals in tools/patch_200cc.py): the flying time over a stretch of track t with
tuning set s and character c = CH_PACE_LAP[t] * CH_PACE_SET[s] * (share of the lap time over the
stretch, CH_PACE_SHAPE[t]), plus the standing start CH_PACE_LOSS[s], times CH_PACE_CHAR[c].
- Lap times L[s, t] from pace_table.analyse (the --q quantile of every 1/64 segment over all karts
  and laps). log L = log T[t] + log F[s], least squares over the runs there are; the geometric
  mean of F is 1.
- Shape per track: the mean of every run's segment shares on that track.
- Loss per set: the median of its runs' standing losses (the cleanest start of each run),
  at least 0.
- Character: per kart the median ratio of its flying segments to the run's table; per character
  the geometric mean over all karts, divided by the mean over the characters.
--check: leave-one-out over the tracks other than 0 and 4: each such run predicted with F fitted
without it, the error of the lap and of random stretches (share 0.3..0.7, as the draw).
Prints the Python lines CH_PACE_LAP, CH_PACE_SET, CH_PACE_LOSS, CH_PACE_CHAR, CH_PACE_SHAPE.
"""
import glob
import json
import math
import os
import random
import statistics
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import pace_table as PT

N = 64
SETS, TRACKS, CHARS = 64, 8, 7


def fit_factors(laps):
    """laps {(s, t): L}: T[t], F[s] with log L = log T + log F, mean log F = 0 (alternating
    least squares)."""
    T = {t: 1.0 for t in range(TRACKS)}
    F = {s: 1.0 for s in range(SETS)}
    for _ in range(200):
        for t in range(TRACKS):
            v = [math.log(L) - math.log(F[s]) for (s, tt), L in laps.items() if tt == t]
            if v:
                T[t] = math.exp(statistics.mean(v))
        for s in range(SETS):
            v = [math.log(L) - math.log(T[t]) for (ss, t), L in laps.items() if ss == s]
            if v:
                F[s] = math.exp(statistics.mean(v))
        have = [s for s in range(SETS) if any(ss == s for ss, _ in laps)]
        g = math.exp(statistics.mean(math.log(F[s]) for s in have))
        for s in have:
            F[s] /= g
        for t in T:
            T[t] *= g
    return T, F, have


def stretch(shares, start, share):
    """Share of the lap time over progress start .. start + share (cumulative shares)."""
    def c(p):
        j = min(max(int(p * N), 0), N - 1)
        return shares[j] + (p * N - j) * (shares[j + 1] - shares[j])
    e = start + share
    return (c(e - 1) + 1 if e >= 1 else c(e)) - c(start)


def cumulative(table):
    total, run, out = sum(table), 0.0, []
    for j in range(N + 1):
        out.append(run / total)
        if j < N:
            run += table[j]
    return out


def main():
    args = sys.argv[1:]
    q, skip, check = 0.3, 8, "--check" in args
    if check:
        args.remove("--check")
    if "--q" in args:
        i = args.index("--q"); q = float(args[i + 1]); del args[i:i + 2]
    if "--skip" in args:
        i = args.index("--skip"); skip = int(args[i + 1]); del args[i:i + 2]
    runs = {}
    partial, partial_loss = [], {}
    char_ratio = {c: [] for c in range(CHARS)}
    for path in sorted(glob.glob(os.path.join(args[0], "pace_s*_t*.json"))):
        run = json.load(open(path))
        a = PT.analyse(run, q, skip)
        if a is None:
            partial.append(run)
            continue
        runs[(run["set"], run["track"])] = a
        seg = {}
        for k in run["karts"]:
            cr = k["cross"]
            if not cr or k.get("char") is None:
                continue
            r = [(tb - ta) / a["table"][ka % N] for (ka, ta), (kb, tb) in zip(cr, cr[1:])
                 if kb == ka + 1 and ka >= cr[0][0] + skip]
            if len(r) >= 16:
                char_ratio[k["char"]].append(statistics.median(r))
    laps = {k: a["lap_q"] for k, a in runs.items()}
    # runs whose karts did not cover every segment (very slow sets): the lap from the segments
    # they have, against the track's mean shape of the complete runs (at least 32 segments; fewer: the karts were stuck)
    for run in partial:
        s, t = run["set"], run["track"]
        tabs = [a["table"] for (ss, tt), a in runs.items() if tt == t]
        seg = PT.segments(run, skip)
        have_j = [j for j in range(N) if j in seg]
        if not tabs or len(have_j) < 32:
            print("# no lap: set %d track %d (%d segments)" % (s, t, len(have_j)))
            continue
        shape = [statistics.mean(tab[j] / sum(tab) for tab in tabs) for j in range(N)]
        part = sum(PT.quantile([x for x, _ in seg[j]], q) for j in have_j)
        laps[(s, t)] = part / sum(shape[j] for j in have_j)
        table = [laps[(s, t)] * x for x in shape]
        losses = [k["cross"][skip][1] - PT.flying(table, k["p0"], k["cross"][skip][0] / N) for k in run["karts"]
                  if len(k["cross"]) > skip and k["cross"][skip][0] == k["cross"][0][0] + skip]
        partial_loss[(s, t)] = min(losses) if losses else None
        print("# partial: set %d track %d, %d segments, lap about %.1f s, loss %s" % (
            s, t, len(have_j), laps[(s, t)], partial_loss[(s, t)]))
    T, F, have = fit_factors(laps)
    print("# %d runs, %d sets with a factor, %d without" % (len(runs), len(have), SETS - len(have)))
    missing = [s for s in range(SETS) if s not in have]
    fmed = statistics.median(F[s] for s in have)
    for s in missing:
        F[s] = fmed
    # shape per track
    shapes = []
    for t in range(TRACKS):
        tabs = [a["table"] for (s, tt), a in runs.items() if tt == t]
        if not tabs:
            shapes.append([1.0] * N)
            continue
        shapes.append([statistics.mean(tab[j] / sum(tab) for tab in tabs) for j in range(N)])
    # loss per set
    loss = []
    for s in range(SETS):
        v = [a["loss"] for (ss, t), a in runs.items() if ss == s and a["loss"] is not None]
        v += [x for (ss, t), x in partial_loss.items() if ss == s and x is not None]
        loss.append(max(0.0, statistics.median(v)) if v else None)
    lmed = statistics.median(x for x in loss if x is not None)
    loss = [lmed if x is None else x for x in loss]
    # characters
    cf = {c: math.exp(statistics.mean(math.log(x) for x in v)) if v else 1.0 for c, v in char_ratio.items()}
    g = math.exp(statistics.mean(math.log(x) for x in cf.values()))
    cf = {c: x / g for c, x in cf.items()}
    print("# characters (karts):", ", ".join("%d %.3f (%d)" % (c, cf[c], len(char_ratio[c])) for c in range(CHARS)))
    if check:
        rnd = random.Random(1)
        errs_lap, errs_str = [], []
        for (s, t), a in runs.items():
            if t in (0, 4):
                continue
            rest = {k: v for k, v in laps.items() if k != (s, t)}
            if not any(tt == t for _, tt in rest):
                continue
            T2, F2, have2 = fit_factors(rest)
            if s not in have2:
                continue
            pred = T2[t] * F2[s]
            errs_lap.append(pred / a["lap_q"] - 1)
            if abs(errs_lap[-1]) > 0.15:
                print("# check: set %d track %d off by %+.0f %%" % (s, t, 100 * errs_lap[-1]))
            own = cumulative(a["table"])
            sh = cumulative(shapes[t])
            for _ in range(20):
                st, share = rnd.random(), rnd.uniform(0.3, 0.7)
                errs_str.append(pred * stretch(sh, st, share) / (a["lap_q"] * stretch(own, st, share)) - 1)
        if errs_lap:
            print("# check, lap: %d runs, error mean %+.1f %%, abs median %.1f %%, max %.1f %%" % (
                len(errs_lap), 100 * statistics.mean(errs_lap), 100 * statistics.median(abs(e) for e in errs_lap),
                100 * max(abs(e) for e in errs_lap)))
            ae = sorted(abs(e) for e in errs_str)
            print("# check, stretches: abs median %.1f %%, 90 %% below %.1f %%, max %.1f %%" % (
                100 * statistics.median(ae), 100 * ae[int(0.9 * len(ae))], 100 * ae[-1]))
    print("CH_PACE_LAP = (%s)" % ", ".join("%.2f" % T[t] for t in range(TRACKS)))
    print("CH_PACE_SET = (%s)" % ", ".join("%.3f" % F[s] for s in range(SETS)))
    print("CH_PACE_LOSS = (%s)" % ", ".join("%.2f" % x for x in loss))
    print("CH_PACE_CHAR = (%s)" % ", ".join("%.3f" % cf[c] for c in range(CHARS)))
    print("CH_PACE_SHAPE = (")
    for t in range(TRACKS):
        total = sum(shapes[t])
        print("    (%s)," % ", ".join(str(round(10000 * x / total)) for x in shapes[t]))
    print(")")


if __name__ == "__main__":
    main()
