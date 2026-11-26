"""Summary of a batch of ai_race.py recordings named t<track>_<setting>_<repeat>.csv.

usage: ai_batch_summary.py <dir>

Per track and setting, the mean over the repeats of: resets of the six computer karts (a jump of
more than 4 units between frames), their mean speed and the seconds they stood nearly still
(speed below 2 after the first 3 s), with the single races in brackets.
"""
import collections
import csv
import glob
import math
import os
import re
import sys


def race(path):
    karts = collections.defaultdict(list)
    with open(path) as f:
        for r in csv.DictReader(f):
            karts[int(r["kart"])].append((float(r["t"]), float(r["x"]), float(r["z"]),
                                          math.hypot(float(r["vx"]), float(r["vz"]))))
    resets, speeds, still = 0, [], 0.0
    for k, rows in karts.items():
        if k == 0:
            continue
        for a, b in zip(rows, rows[1:]):
            if math.hypot(b[1] - a[1], b[2] - a[2]) > 4.0:
                resets += 1
            elif b[0] > 3.0 and b[3] < 2.0:
                still += b[0] - a[0]
        speeds += [q[3] for q in rows]
    return resets, sum(speeds) / len(speeds), still


def main():
    groups = collections.defaultdict(list)
    for path in sorted(glob.glob(os.path.join(sys.argv[1], "t*_*_*.csv"))):
        m = re.match(r"t(\d+)_(.+)_(\d+)\.csv$", os.path.basename(path))
        if m:
            groups[(int(m.group(1)), m.group(2))].append(race(path))
    for (trk, name), runs in sorted(groups.items()):
        n = len(runs)
        print("track %d %-8s %d races: resets %5.1f (%s)  speed %5.1f (%s)  still %5.1f s" % (
            trk, name, n, sum(r[0] for r in runs) / n, " ".join(str(r[0]) for r in runs),
            sum(r[1] for r in runs) / n, " ".join("%.1f" % r[1] for r in runs), sum(r[2] for r in runs) / n))


if __name__ == "__main__":
    main()
