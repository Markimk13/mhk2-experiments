"""How often the computer karts fire their power-ups, from race_recorder.py recordings.

usage: item_rate.py <recording.csv or a folder of them> [...]

Per recording: uses per minute of the six computer karts (the held item, car+270h, goes from a
power-up to none), the mean seconds an item was held before it was used, and the seconds the
karts stood still (speed below 0.5 after the first 3 s) in a hit state (car+29Ch 15, 20 or 24;
recordings from before that column have none).
"""
import collections
import csv
import glob
import math
import os
import sys


def one(path):
    karts = collections.defaultdict(list)
    with open(path) as f:
        rows = csv.DictReader(f)
        if "item" not in (rows.fieldnames or ()):
            return 0, 0.0, 0.0, 0.0                    # not a race_recorder.py file
        for r in rows:
            karts[int(r["kart"])].append(r)
    uses, held, dur, frozen = 0, 0.0, 0.0, 0.0
    for k, v in karts.items():
        if k == 0:
            continue
        dur = float(v[-1]["t"]) - float(v[0]["t"])
        for a, b in zip(v, v[1:]):
            ta, tb = float(a["t"]), float(b["t"])
            if int(a["item"]) >= 0:
                held += tb - ta
                if int(b["item"]) < 0:
                    uses += 1
            if (tb > 3 and a.get("cstate") in ("15", "20", "24")
                    and math.hypot(float(a["vx"]), float(a["vz"])) < 0.5):
                frozen += tb - ta
    return uses, dur, held, frozen


def main():
    paths = []
    for arg in sys.argv[1:]:
        paths += sorted(glob.glob(os.path.join(arg, "**", "*.csv"), recursive=True)) if os.path.isdir(arg) else [arg]
    for path in paths:
        uses, dur, held, frozen = one(path)
        if dur:
            print("%-60s %5.1f uses per minute, items held %5.1f s, frozen after hits %5.1f s"
                  % (path, uses * 60 / dur, held / max(uses, 1), frozen))


if __name__ == "__main__":
    main()
