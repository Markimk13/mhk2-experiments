r"""Physics speed signs: a speed profile per track from the centre line, checked against recorded races.

usage: speed_profile.py fit <batch dir> [...]      grid over the model values, how well the profile
                                                     tells the seconds before a reset from the rest
       speed_profile.py show <track> [C RW D]      the profile's slow places

Model: corner speed C * (R + RW) (sideways grip grows with speed, measured: about 1.4 * v at full
lock), R = radius of the centre line (track_line.py); then backwards around the lap
v(s) = min(corner(s), sqrt(v(s + ds)^2 + 2 D ds)) (braking at D units/s^2), like the game's speed
limit boxes but at every point. Optional crest limit sqrt(G / height curvature).
Check: per recorded kart frame the ratio speed / profile at its place; per moving reset (speed > 5
1.5 s before) the highest ratio in the 3 s before it, against the same for 3 s windows far from any
reset; AUC = chance that a reset window has the higher ratio.
"""
import collections
import csv
import json
import math
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from track_line import Line  # noqa: E402

_lines = {}


def line(t):
    if t not in _lines:
        _lines[t] = Line(t)
    return _lines[t]


def profile(ln, C, RW, D, G=None):
    n = ln.n
    v = [C * (1 / max(abs(k), 1e-4) + RW) for k in ln.kappa]
    if G:
        v = [min(a, math.sqrt(G / -kv)) if kv < -1e-4 else a for a, kv in zip(v, ln.kv)]
    v = [max(a, 5.0) for a in v]
    for _ in range(2):
        for i in range(n - 1, -1, -1):
            j = (i + 1) % n
            v[i] = min(v[i], math.sqrt(v[j] ** 2 + 2 * D * ln.step))
    return v


def windows(batch_dirs):
    """per track: list of (indices along the line, speeds, is_reset_window)"""
    out = collections.defaultdict(list)
    for b in batch_dirs:
        for f in sorted(os.listdir(b)):
            if not (f.endswith(".csv") and f.startswith("t")):
                continue
            track = int(f[1:f.index("_")])
            ln = line(track)
            karts = collections.defaultdict(list)
            for r in csv.DictReader(open(os.path.join(b, f))):
                if r["kart"] != "0":
                    karts[r["kart"]].append(r)
            for rows in karts.values():
                T = [float(r["t"]) for r in rows]
                X = [float(r["x"]) for r in rows]
                Z = [float(r["z"]) for r in rows]
                jumps = [i for i in range(1, len(rows)) if math.hypot(X[i] - X[i - 1], Z[i] - Z[i - 1]) > 4]
                # frames every 0.05 s
                keep, last = [], -1
                for i, t in enumerate(T):
                    if t - last >= 0.05:
                        keep.append(i)
                        last = t
                fr = {}
                for i in keep:
                    idx, _ = ln.nearest(X[i], Z[i])
                    fr[i] = (T[i], idx, math.hypot(float(rows[i]["vx"]), float(rows[i]["vz"])))
                reset_t = [T[i - 1] for i in jumps]
                for i in jumps:
                    t0 = T[i - 1]
                    before = [fr[k] for k in keep if t0 - 1.6 < T[k] <= t0 - 1.4]
                    if not before or before[0][2] <= 5:
                        continue
                    w = [fr[k] for k in keep if t0 - 3.0 < T[k] <= t0 - 0.3]
                    out[track].append(([e[1] for e in w], [e[2] for e in w], True))
                t = 8.0
                while t + 3 < T[-1]:
                    if all(abs(t + 1.5 - r) > 5 for r in reset_t):
                        w = [fr[k] for k in keep if t < T[k] <= t + 3]
                        if w:
                            out[track].append(([e[1] for e in w], [e[2] for e in w], False))
                    t += 3.0
    return out


def auc(pos, neg):
    allv = sorted([(x, 1) for x in pos] + [(x, 0) for x in neg])
    rank, s = 0, 0.0
    np_ = len(pos)
    for r, (x, lab) in enumerate(allv, 1):
        if lab:
            s += r
    return (s - np_ * (np_ + 1) / 2) / (np_ * len(neg))


def score(W, C, RW, D, G=None):
    pos, neg = [], []
    over = 0
    nf = 0
    for track, lst in W.items():
        prof = profile(line(track), C, RW, D, G)
        for idx, v, is_reset in lst:
            m = max(a / prof[i] for i, a in zip(idx, v))
            (pos if is_reset else neg).append(m)
            if not is_reset:
                over += sum(a > prof[i] for i, a in zip(idx, v))
                nf += len(v)
    return auc(pos, neg), over / max(nf, 1), len(pos), len(neg)


def main():
    a = sys.argv[1:]
    if a[0] == "fit":
        cache = os.path.join(a[1], "speed_profile_windows.json")
        dirs = a[1:]
        W = windows(dirs)
        print("reset windows %d, other windows %d" % (sum(1 for l in W.values() for e in l if e[2]), sum(1 for l in W.values() for e in l if not e[2])))
        res = []
        for C in (1.2, 1.4, 1.6, 1.8, 2.0, 2.2):
            for RW in (-4, 0, 4, 8):
                for D in (15, 25, 40):
                    s, over, npos, nneg = score(W, C, RW, D)
                    res.append((s, C, RW, D, over))
        res.sort(reverse=True)
        for s, C, RW, D, over in res[:12]:
            print("AUC %.3f  C %.1f RW %+d D %d  normal frames above the profile %4.1f %%" % (s, C, RW, D, 100 * over))
        s, C, RW, D, over = res[0]
        for G in (50, 100, 200, 400):
            print("with crest G %d: AUC %.3f" % (G, score(W, C, RW, D, G)[0]))
        print("driver now (C 2.2 RW 4 D 25): AUC %.3f, normal frames above %4.1f %%" % (score(W, 2.2, 4, 25)[0], 100 * score(W, 2.2, 4, 25)[1]))
    else:
        t = int(a[1])
        C, RW, D = (float(x) for x in a[2:5]) if len(a) >= 5 else (1.6, 0, 25)
        ln = line(t)
        prof = profile(ln, C, RW, D)
        mins = [i for i in range(ln.n) if prof[i] <= prof[i - 1] and prof[i] <= prof[(i + 1) % ln.n] and prof[i] < 60]
        for i in mins:
            p = ln.pts[i]
            print("lap %.3f (%6.0f, %6.0f): %5.1f units/s, radius %5.1f" % (i / ln.n, p[0], p[2], prof[i], 1 / max(abs(ln.kappa[i]), 1e-4)))


if __name__ == "__main__":
    main()
