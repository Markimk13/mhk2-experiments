r"""Show the frames before a kart's speed runs away in an ai_race.py recording.

usage: runaway_look.py <race.csv> [limit] [frames before] [frames after]

For every kart that got faster than the limit (default 150): the time, and for the first two of
them the frames around it: position, velocity, the y part of the kart's up axis (1 = upright),
which wheels touch the ground and the wheel loads. Shows whether the kart was on the ground or
tumbling in the air when it took off.
"""
import csv
import math
import sys


def main():
    path = sys.argv[1]
    limit = float(sys.argv[2]) if len(sys.argv) > 2 else 150.0
    before = int(sys.argv[3]) if len(sys.argv) > 3 else 14
    after = int(sys.argv[4]) if len(sys.argv) > 4 else 5
    rows = {}
    with open(path) as f:
        for r in csv.DictReader(f):
            rows.setdefault(int(r["kart"]), []).append(r)
    shown = 0
    for k in sorted(rows):
        rs = rows[k]
        sp = [math.sqrt(float(r["vx"]) ** 2 + float(r["vy"]) ** 2 + float(r["vz"]) ** 2) for r in rs]
        first = next((i for i, s in enumerate(sp) if not s <= limit), None)
        air = sum(1 for r in rs if r["c0"] + r["c1"] + r["c2"] + r["c3"] == "0000") / len(rs)
        print("kart %d: mass %s, in the air %.0f %% of the time, %s" % (
            k, rs[0]["mass"], 100 * air, "never above %.0f (top %.1f)" % (limit, max(sp)) if first is None
            else "above %.0f at t = %s" % (limit, rs[first]["t"])))
        if first is None or shown >= 2:
            continue
        shown += 1
        for i in range(max(0, first - before), min(len(rs), first + after)):
            r = rs[i]
            print("   t %8s pos %8.2f %7.2f %8.2f  v %8.1f %8.1f %8.1f |%7.1f|  up.y %5.2f  wheels %s%s%s%s loads %6.0f %6.0f %6.0f %6.0f" % (
                r["t"], float(r["x"]), float(r["y"]), float(r["z"]), float(r["vx"]), float(r["vy"]), float(r["vz"]), sp[i],
                float(r["sy"]), r["c0"], r["c1"], r["c2"], r["c3"],
                float(r["load0"]), float(r["load1"]), float(r["load2"]), float(r["load3"])))


if __name__ == "__main__":
    main()
