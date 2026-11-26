r"""Compare the races of a geo_duel.py folder that ran with --odd "<arguments>": the even races
against the odd ones (for example the watch on against --watch off).

usage: watch_report.py <geo_duel dir> [--tracks 0,1,..]

Per track and over all: laps driven per kart race, seconds without progress beyond 5 s, seconds
standing (hang_spots.py), times the kart was set back, and the longest stretch without progress.
"""
import glob
import math
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import hang_spots as H
import no_progress as N


def main():
    a = sys.argv[1:]
    if not a:
        raise SystemExit(__doc__)
    out = a[0]
    tracks = [int(x) for x in a[a.index("--tracks") + 1].split(",")] if "--tracks" in a else list(range(8))
    tot = {0: [], 1: []}
    print("track   races   laps even / odd (gain of even, z)   s beyond 5 s    s standing    set back      longest s")
    for t in tracks + ["all"]:
        if t == "all":
            data = tot
        else:
            data = {0: [], 1: []}
            for f in sorted(glob.glob(os.path.join(out, "t%d_r*.csv" % t))):
                r = int(re.search(r"_r(\d+)\.csv$", f).group(1))
                prog = N.load(f)
                for kn, rows in H.load(f).items():
                    p = prog[kn]
                    st = N.stretches(p, 2.0)
                    data[r % 2].append(((p[-1][1] - p[0][1]) / (p[-1][0] - p[0][0]) * 120.0,
                                        sum(max(0.0, d - 5.0) for _, d, _ in st),
                                        sum(h["dur"] for h in H.hangs(rows, 5.0, 1.0)),
                                        sum(1 for i in range(1, len(rows)) if rows[i][0] > 8 and math.dist(rows[i - 1][1:4], rows[i][1:4]) > 4),
                                        max([d for _, d, _ in st] or [0.0])))
            for k in (0, 1):
                tot[k] += data[k]
        if not data[0] or not data[1]:
            continue
        m = [[sum(x[i] for x in data[k]) / len(data[k]) for i in range(4)] for k in (0, 1)]
        la, lb = [x[0] for x in data[0]], [x[0] for x in data[1]]
        var = (sum((x - m[0][0]) ** 2 for x in la) + sum((x - m[1][0]) ** 2 for x in lb)) / (len(la) + len(lb) - 2)
        z = (m[0][0] - m[1][0]) / math.sqrt(var * (1.0 / len(la) + 1.0 / len(lb))) if var else 0.0
        print("%-5s  %3d+%-3d  %.3f / %.3f (%+5.1f %%, z %4.1f)          %5.2f / %5.2f   %5.2f / %5.2f   %4.2f / %4.2f   %5.1f / %5.1f"
              % (t, len(la) // 6, len(lb) // 6, m[0][0], m[1][0], 100 * (m[0][0] / m[1][0] - 1), z, m[0][1], m[1][1], m[0][2], m[1][2],
                 m[0][3], m[1][3], max(x[4] for x in data[0]), max(x[4] for x in data[1])))


if __name__ == "__main__":
    main()
