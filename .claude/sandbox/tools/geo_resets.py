r"""What a computer kart did in the seconds before each reset (ai_race.py recording with driver columns).

usage: geo_resets.py <race.csv> [--kart N] [--before 2.0]

Per reset (jump > 4 units): time, place, kart, then every 0.25 s before it: speed, allowed speed
(controller +88h), throttle, brake, steering, lateral position is not recorded (progress is).
"""
import collections
import csv
import math
import sys


def main():
    a = sys.argv[1:]
    only = int(a[a.index("--kart") + 1]) if "--kart" in a else None
    before = float(a[a.index("--before") + 1]) if "--before" in a else 2.0
    karts = collections.defaultdict(list)
    for r in csv.DictReader(open(a[0])):
        k = int(r["kart"])
        if k and (only is None or k == only):
            karts[k].append(r)
    for k, rows in sorted(karts.items()):
        for i in range(1, len(rows)):
            p, q = rows[i - 1], rows[i]
            if math.hypot(float(q["x"]) - float(p["x"]), float(q["z"]) - float(p["z"])) <= 4.0:
                continue
            t = float(p["t"])
            print("kart %d reset at %.2f s, (%.0f, %.0f), progress %.3f" % (k, t, float(p["x"]), float(p["z"]), float(p["prog"])))
            mark = t - before
            for r in rows[max(0, i - 2000):i]:
                if float(r["t"]) >= mark:
                    v = math.sqrt(float(r["vx"]) ** 2 + float(r["vy"]) ** 2 + float(r["vz"]) ** 2)
                    print("   %6.2f  v %5.1f  allow %6.1f  thr %.2f  brk %.2f  steer %+.2f  prog %.4f" % (
                        float(r["t"]) - t, v, float(r["allow"]), float(r["thr"]), float(r["brk"]), float(r["steer"]), float(r["prog"])))
                    mark += 0.25


if __name__ == "__main__":
    main()
