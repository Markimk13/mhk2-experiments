"""Regression drive: full throttle from a standing start, speed after 2 and 3 seconds per engine class.

usage: regress_drive.py <test exe> <out dir> [class ...]      (default classes: 2 3 = 150 cc, 200 cc)

Uses drive.py (keyboard-free). Waits until no other test game is running before each launch.
"""
import csv
import math
import os
import subprocess
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import ghostlib as G

HERE = os.path.dirname(os.path.abspath(__file__))


def speed_at(rows, t):
    row = min(rows, key=lambda r: abs(float(r["t"]) - t))
    return math.sqrt(float(row["vx"]) ** 2 + float(row["vy"]) ** 2 + float(row["vz"]) ** 2)


def main():
    exe, out = sys.argv[1], sys.argv[2]
    classes = [int(x) for x in sys.argv[3:]] or [2, 3]
    os.makedirs(out, exist_ok=True)
    for cls in classes:
        G.wait_free()
        path = os.path.join(out, "regress_cls%d.csv" % cls)
        r = subprocess.run([sys.executable, os.path.join(HERE, "drive.py"), exe, path, "--plan", "0.5:1:0:0,3.2", "--cls", str(cls)],
                           capture_output=True, text=True)
        print((r.stdout + r.stderr).strip(), flush=True)
        if r.returncode != 0 or not os.path.exists(path):
            print("class %d: drive failed" % cls, flush=True)
            continue
        rows = list(csv.DictReader(open(path)))
        print("class %d: v(2.0 s) = %.2f   v(3.0 s) = %.2f   (%d frames)" % (cls, speed_at(rows, 2.0), speed_at(rows, 3.0), len(rows)), flush=True)


if __name__ == "__main__":
    main()
