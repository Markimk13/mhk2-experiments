r"""Wheel load against speed in ai_race.py recordings: shows what the downforce does.

usage: load_by_speed.py <race.csv> [<race.csv> ...]

For the computer karts, frames with all four wheels on the ground: the median of the summed
wheel loads per 10 units/s of speed, divided by the kart's weight (mass * 20.4), so 1.0 is a
kart standing still. Also the share of frames in the air and the highest point reached.
"""
import csv
import math
import sys

GRAVITY = 20.4          # from the wheel loads of a standing kart


def main():
    for path in sys.argv[1:]:
        bins, air, total, high = {}, 0, 0, -1e9
        with open(path) as f:
            for r in csv.DictReader(f):
                if r["kart"] == "0":
                    continue
                total += 1
                high = max(high, float(r["y"]))
                if r["c0"] + r["c1"] + r["c2"] + r["c3"] == "0000":
                    air += 1
                if r["c0"] + r["c1"] + r["c2"] + r["c3"] != "1111":
                    continue
                v = math.hypot(float(r["vx"]), float(r["vz"]))
                load = sum(float(r["load%d" % i]) for i in range(4)) / (float(r["mass"]) * GRAVITY)
                bins.setdefault(int(v // 10) * 10, []).append(load)
        print(path)
        print("   in the air %.1f %% of the frames, highest point y = %.1f" % (100.0 * air / max(total, 1), high))
        print("   speed: load / weight   " + "   ".join("%d: %.1f" % (b, sorted(v)[len(v) // 2]) for b, v in sorted(bins.items()) if len(v) > 30))


if __name__ == "__main__":
    main()
