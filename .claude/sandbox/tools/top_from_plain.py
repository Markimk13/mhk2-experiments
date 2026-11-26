r"""Top speed of a class from a plain standing start on track 3 (pu_run.py without power-up).

usage: top_from_plain.py <gearing factor> <run.csv> [<gearing factor> <run.csv> ...]

The start straight is too short to reach top speed. Behind the dip (x 94 .. 56) the kart is in
top gear and pulls against the resistance: a(v) = pull * C * T(143.27 * v / gearing) - R(v), with
C and R from class_model.py. This fits the pull to the measured accelerations there and solves
for the speed where a(v) = 0. Prints the measured and the fitted accelerations so the fit can be judged.
"""
import csv
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import class_model as M


def main():
    args = sys.argv[1:]
    for s, path in zip(args[0::2], args[1::2]):
        s = float(s)
        rows = [(float(r["t"]), float(r["x"]), float(r["v"]), int(r["gear"]), float(r["rpm"])) for r in csv.DictReader(open(path))]
        seg = [r for r in rows if 56.0 < r[1] < 94.0 and r[3] == 3]
        seg = seg[: next((i for i in range(1, len(seg)) if seg[i][2] < seg[i - 1][2] - 0.5), len(seg))]
        w = 6
        pts = []
        for i in range(w, len(seg) - w, 3):
            a = (seg[i + w][2] - seg[i - w][2]) / (seg[i + w][0] - seg[i - w][0])
            pts.append((seg[i][2], a, seg[i][4]))
        # a + R(v) = pull * C * T(rpm): least squares for pull
        num = sum((a + M.R0 * (v / M.VREF) ** 2) * M.C * M.torque(143.27 * v / s) for v, a, _ in pts)
        den = sum((M.C * M.torque(143.27 * v / s)) ** 2 for v, a, _ in pts)
        pull = num / den
        top = M.top_speed(s, pull)
        err = (sum((a - (pull * M.C * M.torque(143.27 * v / s) - M.R0 * (v / M.VREF) ** 2)) ** 2 for v, a, _ in pts) / len(pts)) ** 0.5
        ratio = sum(rpm / v for v, a, rpm in pts) / len(pts)
        print("%s: gearing %.3f (engine speed / v measured %.2f, expected %.2f) | %d samples, v %.1f .. %.1f, a %.2f .. %.2f"
              % (os.path.basename(path), s, ratio, 143.27 / s, len(pts), pts[0][0], pts[-1][0], pts[0][1], pts[-1][1]))
        print("   fitted pull %.3f (rms error %.3f units/s2) -> top speed %.2f" % (pull, err, top))


if __name__ == "__main__":
    main()
