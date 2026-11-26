r"""Speed signs learned from races: where computer karts crash, and the entry speed that separates
clean passes from crashes there.

usage: speed_signs.py <batch dir> [...] [--min 4] [--before 120]

Per track (lines from track_line.py): moving resets (speed > 5 1.5 s before the jump) grouped by
the place on the centre line where the kart was 0.5 s before (within 40 units); for each group of at
least --min resets every pass of every kart through the --before units ahead of that place: its
highest speed and whether it was reset within 3 s. Printed: the place (lap share, x, z), resets,
passes, and the speed limit that best separates them (sign), with how many passes it would have
slowed (clean ones too) and how many resets it would have caught.
"""
import collections
import csv
import math
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from track_line import Line  # noqa: E402


def load(batch_dirs):
    """track -> list of kart runs: [(t, line index, distance from centre, speed, jumped)]"""
    runs = collections.defaultdict(list)
    lines = {}
    for b in batch_dirs:
        for f in sorted(os.listdir(b)):
            if not (f.endswith(".csv") and f.startswith("t")):
                continue
            track = int(f[1:f.index("_")])
            ln = lines.setdefault(track, Line(track))
            karts = collections.defaultdict(list)
            for r in csv.DictReader(open(os.path.join(b, f))):
                if r["kart"] != "0":
                    karts[r["kart"]].append(r)
            for rows in karts.values():
                run, last, px, pz = [], -1.0, None, None
                for r in rows:
                    t, x, z = float(r["t"]), float(r["x"]), float(r["z"])
                    jump = px is not None and math.hypot(x - px, z - pz) > 4
                    px, pz = x, z
                    if t - last >= 0.05 or jump:
                        idx, d = ln.nearest(x, z)
                        run.append((t, idx, d, math.hypot(float(r["vx"]), float(r["vz"])), jump))
                        last = t
                runs[track].append(run)
    return lines, runs


def main():
    a = sys.argv[1:]
    mn = int(a[a.index("--min") + 1]) if "--min" in a else 4
    before = float(a[a.index("--before") + 1]) if "--before" in a else 120.0
    dirs = [x for i, x in enumerate(a) if not x.startswith("--") and (i == 0 or not a[i - 1].startswith("--"))]
    lines, runs = load(dirs)
    for track in sorted(runs):
        ln = lines[track]
        step = ln.step
        places = []
        for run in runs[track]:
            for k, e in enumerate(run):
                if not e[4]:
                    continue
                t0 = run[k - 1][0]
                v15 = [q[3] for q in run[:k] if t0 - 1.6 < q[0] <= t0 - 1.4]
                p05 = [q for q in run[:k] if t0 - 0.6 < q[0] <= t0 - 0.4 and q[2] < 15]
                if v15 and v15[0] > 5 and p05:
                    places.append(p05[0][1])
        groups = []
        for idx in sorted(places):
            if groups and (idx - groups[-1][-1]) * step <= 40:
                groups[-1].append(idx)
            else:
                groups.append([idx])
        print("track %d: %d moving resets with a place, length %.0f" % (track, len(places), ln.length))
        for g in groups:
            if len(g) < mn:
                continue
            spot = g[len(g) // 2]
            lo = spot - int(before / step)
            passes = []
            for run in runs[track]:
                inwin, vmax = False, 0.0
                for k, e in enumerate(run):
                    rel = (e[1] - lo) % ln.n
                    inside = rel * step <= before + 40 * 0 and e[2] < 15 and not e[4]
                    if inside:
                        inwin, vmax = True, max(vmax, e[3])
                    elif inwin:
                        reset = any(q[4] for q in run[k:] if q[0] <= e[0] + 3.0)
                        passes.append((vmax, reset))
                        inwin, vmax = False, 0.0
            if not passes:
                continue
            best = None
            for v, _ in passes:                              # sign = v: passes above it are slowed
                caught = sum(1 for w, r in passes if w > v and r)
                slowed = sum(1 for w, r in passes if w > v)
                missed = sum(1 for w, r in passes if w <= v and r)
                cost = missed + 0.5 * (slowed - caught)
                if best is None or cost < best[0]:
                    best = (cost, v, caught, slowed, missed)
            p = ln.pts[spot]
            nres = sum(1 for _, r in passes if r)
            print("   lap %.3f (%5.0f, %5.0f) radius %5.1f: %2d resets, %3d passes (%2d reset)  sign %5.1f: catches %2d, slows %3d, misses %2d"
                  % (spot / ln.n, p[0], p[2], 1 / max(abs(ln.kappa[spot]), 1e-4), len(g), len(passes), nres, best[1], best[2], best[3], best[4]))


if __name__ == "__main__":
    main()
