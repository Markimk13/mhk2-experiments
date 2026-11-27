"""Reduce stretch_pace.py runs to flying segment times and standing-start losses (sandbox).

usage: pace_table.py <pace dir> [--q 0.3] [--skip 8] [--json out.json]

Per run (set, track): the segment j (1/64 lap from progress j/64) takes the time between two
crossings of a kart. Crossings in the first --skip segments after the grid are the standing start
and stay out. The flying time of a segment is the --q quantile over all karts and laps (crashes,
item hits and pile-ups only make segments slower). The standing loss of a kart = its race time
(the clock starts at "go") at grid point first + skip, minus the flying time of the same
distance; the run's loss is the lowest (the cleanest start: karts behind wait for traffic).
Prints per run: lap time (q and median), the spread of the segments, samples, standing losses.
"""
import glob
import json
import math
import os
import statistics
import sys

N = 64


def quantile(xs, q):
    xs = sorted(xs)
    if not xs:
        return None
    pos = q * (len(xs) - 1)
    lo = int(math.floor(pos))
    hi = min(lo + 1, len(xs) - 1)
    return xs[lo] + (xs[hi] - xs[lo]) * (pos - lo)


def segments(run, skip):
    """{j: [(time, char), ...]} of the flying segments."""
    seg = {}
    for k in run["karts"]:
        cr = k["cross"]
        if not cr:
            continue
        first = cr[0][0]
        for (a, ta), (b, tb) in zip(cr, cr[1:]):
            # tb > ta: several crossings in one frame (a reset jump) give no segment time
            if b == a + 1 and a >= first + skip and tb > ta:
                seg.setdefault(a % N, []).append((tb - ta, k.get("char")))
    return seg


def flying(table, p_from, p_to):
    """Time over progress p_from .. p_to (laps, unwrapped) with per-segment times table[j]."""
    t, p = 0.0, p_from
    while p < p_to - 1e-12:
        j = int(math.floor(p * N))
        end = min((j + 1) / N, p_to)
        t += table[j % N] * (end - p) * N
        p = end
    return t


def analyse(run, q, skip):
    seg = segments(run, skip)
    if len(seg) < N:
        return None
    table = [quantile([x for x, _ in seg[j]], q) for j in range(N)]
    med = [statistics.median([x for x, _ in seg[j]]) for j in range(N)]
    spread = statistics.mean((quantile([x for x, _ in seg[j]], 0.75) - quantile([x for x, _ in seg[j]], 0.25)) / med[j]
                             for j in range(N))
    losses = []
    for k in run["karts"]:
        cr = k["cross"]
        if len(cr) <= skip or k["t_move"] is None:
            continue
        a, ta = cr[skip]
        if a != cr[0][0] + skip:
            continue
        losses.append((k["kart"], k.get("char"), ta - flying(table, k["p0"], a / N)))
    return {"table": table, "lap_q": sum(table), "lap_med": sum(med), "spread": spread,
            "samples": min(len(seg[j]) for j in range(N)), "losses": losses,
            "loss": min(l[2] for l in losses) if losses else None}


def main():
    args = sys.argv[1:]
    q, skip, out = 0.3, 8, None
    if "--q" in args:
        i = args.index("--q"); q = float(args[i + 1]); del args[i:i + 2]
    if "--skip" in args:
        i = args.index("--skip"); skip = int(args[i + 1]); del args[i:i + 2]
    if "--json" in args:
        i = args.index("--json"); out = args[i + 1]; del args[i:i + 2]
    res = {}
    for path in sorted(glob.glob(os.path.join(args[0], "pace_s*_t*.json"))):
        run = json.load(open(path))
        a = analyse(run, q, skip)
        name = "s%02d t%d" % (run["set"], run["track"])
        if a is None:
            print("%s: too few segments" % name)
            continue
        res[name] = dict(a, set=run["set"], track=run["track"])
        print("%s: lap %.2f s (median %.2f), spread %.1f %%, min samples %d, loss %.2f: %s" % (
            name, a["lap_q"], a["lap_med"], 100 * a["spread"], a["samples"], a["loss"],
            " ".join("k%d/c%s %.2f" % l for l in a["losses"])))
    if out:
        json.dump(res, open(out, "w"))


if __name__ == "__main__":
    main()
