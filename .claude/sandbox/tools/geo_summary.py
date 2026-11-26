r"""Summary of ai_race.py recordings with the driver columns (knum, prog, allow, thr, brk, steer).

usage: geo_summary.py <race.csv> [...]

Per computer kart: laps driven (progress at the end minus at the start), resets (jumps > 4 units; "moving": faster than 5
units/s 1.5 s before), seconds nearly still
(speed < 3 after 5 s), share of frames braking and at full lock, mean speed; then the mean of the
six. With several files the per-file means are listed and averaged.
"""
import collections
import csv
import math
import sys


def summary(path):
    karts = collections.defaultdict(list)
    with open(path) as f:
        for r in csv.DictReader(f):
            karts[int(r["kart"])].append(r)
    out = {}
    for k, rows in sorted(karts.items()):
        if k == 0:
            continue
        t = [float(r["t"]) for r in rows]
        x = [float(r["x"]) for r in rows]
        z = [float(r["z"]) for r in rows]
        v = [math.sqrt(float(r["vx"]) ** 2 + float(r["vy"]) ** 2 + float(r["vz"]) ** 2) for r in rows]
        jumps = [i for i in range(1, len(rows)) if math.hypot(x[i] - x[i - 1], z[i] - z[i - 1]) > 4.0]
        resets = len(jumps)
        moving = 0                                     # resets with speed > 5 at 1.5 s before
        for i in jumps:
            j = i - 1
            while j > 0 and t[j] > t[i - 1] - 1.5:
                j -= 1
            moving += v[j] > 5.0
        still = sum(t[i] - t[i - 1] for i in range(1, len(rows)) if t[i] > 5 and v[i] < 3.0)
        brk = sum(1 for r in rows if float(r["brk"]) > 0) / len(rows)
        lock = sum(1 for r in rows if abs(float(r["steer"])) >= 0.999) / len(rows)
        out[int(rows[0]["knum"])] = dict(prog=float(rows[-1]["prog"]) - float(rows[0]["prog"]), resets=resets, moving=moving, still=still, brk=brk, lock=lock,
                                         mean=sum(v) / len(v))
    return out


def main():
    means = []
    for path in sys.argv[1:]:
        s = summary(path)
        print(path)
        for kn, d in sorted(s.items()):
            print("   kart %d: %.3f laps, %d resets, still %4.1f s, brake %4.1f %%, full lock %4.1f %%, mean %.1f" % (
                kn, d["prog"], d["resets"], d["still"], 100 * d["brk"], 100 * d["lock"], d["mean"]))
        m = {key: sum(d[key] for d in s.values()) / len(s) for key in ("prog", "resets", "still", "brk", "lock", "mean")}
        means.append(m)
        print("   mean:   %.3f laps, %.1f resets, still %4.1f s, brake %4.1f %%, full lock %4.1f %%, mean %.1f" % (
            m["prog"], m["resets"], m["still"], 100 * m["brk"], 100 * m["lock"], m["mean"]))


if __name__ == "__main__":
    main()
