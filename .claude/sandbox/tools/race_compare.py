"""Compare the player with the computer karts in a race_recorder.py recording.

usage: race_compare.py <race.csv> [...] [--parts N] [--all]

Per race: finishing times (progress 4 = three laps after the start line), the player's lap times,
resets of every kart (a jump of more than 4 units between frames), and then the lap in N parts
(default 40): the player's and the computer karts' mean speed, how often they brake, lift
(throttle below 0.5) and steer at full lock, and the computer karts' resets in that part.
Without --all only the parts with resets or a speed difference of 5 units/s or more are listed.
"""
import collections
import csv
import math
import sys


def load(path):
    by = collections.defaultdict(list)
    with open(path) as f:
        for r in csv.DictReader(f):
            by[int(r["kart"])].append(r)
    return by


def f(r, key):
    v = r[key]
    return float(v) if v else 0.0


def main():
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    n = int(sys.argv[sys.argv.index("--parts") + 1]) if "--parts" in sys.argv else 40
    args = [a for a in args if a != str(n)] if "--parts" in sys.argv else args
    show_all = "--all" in sys.argv
    for path in args:
        by = load(path)
        print("== %s (start of kart 0: %.0f, %.0f)" % (path, f(by[0][0], "x"), f(by[0][0], "z")))
        fin = {}
        for k, v in sorted(by.items()):
            fin[k] = next((f(r, "t") for r in v if f(r, "prog") >= 4.0), None)
        order = sorted(by, key=lambda k: (fin[k] is None, fin[k] or 0, -f(by[k][-1], "prog")))
        print("   order: " + ", ".join("%s %s" % ("you" if k == 0 else "kart %d" % k,
              "%.1f s" % fin[k] if fin[k] else "(progress %.2f)" % f(by[k][-1], "prog")) for k in order))
        v = by[0]
        laps = [next((f(r, "t") for r in v if f(r, "prog") >= lap), None) for lap in (1, 2, 3, 4)]
        print("   your laps: " + ", ".join("%.1f" % (b - a) for a, b in zip(laps, laps[1:]) if a is not None and b is not None))
        stats = {0: collections.defaultdict(lambda: [0, 0.0, 0, 0, 0]), 1: collections.defaultdict(lambda: [0, 0.0, 0, 0, 0])}
        resets = collections.Counter()
        per_kart = {}
        for k, v in by.items():
            grp = stats[0 if k == 0 else 1]
            count = 0
            for i, r in enumerate(v):
                p = f(r, "prog")
                if i and math.hypot(f(r, "x") - f(v[i - 1], "x"), f(r, "z") - f(v[i - 1], "z")) > 4.0:
                    count += 1
                    if k:
                        resets[int((f(v[i - 1], "prog") % 1) * n)] += 1
                if p < 1 or p >= 4:
                    continue
                e = grp[int((p % 1) * n)]
                e[0] += 1
                e[1] += math.hypot(f(r, "vx"), f(r, "vz"))
                e[2] += f(r, "brk") > 0
                e[3] += f(r, "thr") < 0.5
                e[4] += abs(f(r, "steer")) > 0.95
            per_kart[k] = count
        print("   resets: " + ", ".join("%s %d" % ("you" if k == 0 else "kart %d" % k, c) for k, c in sorted(per_kart.items()))
              + "; computer karts together %d" % sum(c for k, c in per_kart.items() if k))
        print("   part | you: speed brake lift lock | computer karts: speed brake lift lock | resets")
        for i in range(n):
            a, b = stats[0][i], stats[1][i]
            if not a[0] or not b[0]:
                continue
            ya, yb = a[1] / a[0], b[1] / b[0]
            if not show_all and not resets[i] and abs(ya - yb) < 5:
                continue
            print("   %4.2f | %5.1f %4.0f%% %4.0f%% %4.0f%% | %5.1f %4.0f%% %4.0f%% %4.0f%% | %s" % (
                i / n, ya, 100 * a[2] / a[0], 100 * a[3] / a[0], 100 * a[4] / a[0],
                yb, 100 * b[2] / b[0], 100 * b[3] / b[0], 100 * b[4] / b[0], "#" * resets[i]))


if __name__ == "__main__":
    main()
