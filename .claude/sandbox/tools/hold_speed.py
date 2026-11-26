"""Speed a kart holds at the end of the long start straight, from pu_run.py runs on track 3.

usage: hold_speed.py <run.csv> [<run.csv> ...]

The start straight of track 3 ("Ägypten") is too short to reach top speed from a standing start.
So the kart is pushed with the power can and the push is cut near the speed of interest
(pu_run.py --boost 7 --cut V, optionally --then 2 for the siren). This prints what it does
afterwards between x = 94 (a dip at x 95..103 costs 2 to 3 units/s, so start behind it) and the
end of the straight at x = 52: first and last speed, the mean and the slope. A slope near zero
means the kart sits at its top speed; a run cut too low climbs with about 0.5 units/s per second
for every unit/s it is short.
"""
import csv
import sys


def segment(path):
    rows = list(csv.DictReader(open(path)))
    last_state = rows[-1]["state"]
    tail = [r for r in rows if r["state"] == last_state]
    seg = []
    for r in tail:
        if float(r["x"]) >= 94.0:
            continue
        if seg and float(r["v"]) < float(seg[-1]["v"]) - 0.5:
            break                      # the end of the straight
        seg.append(r)
    return rows, seg


def approach(t, v):
    """Fit v(t) = v_eq + b * exp(-k (t - t0)): the speed the run is heading for."""
    import math
    best = None
    for ki in range(5, 600):
        k = ki / 100.0
        e = [math.exp(-k * (a - t[0])) for a in t]
        n, se, see = len(t), sum(e), sum(x * x for x in e)
        sv, sve = sum(v), sum(a * b for a, b in zip(v, e))
        det = n * see - se * se
        if abs(det) < 1e-12:
            continue
        veq = (sv * see - se * sve) / det
        b = (n * sve - se * sv) / det
        res = sum((y - veq - b * x) ** 2 for y, x in zip(v, e))
        if best is None or res < best[0]:
            best = (res, k, veq)
    res, k, veq = best
    return k, veq, math.sqrt(res / len(t))


def main():
    for path in sys.argv[1:]:
        rows, seg = segment(path)
        if len(seg) < 5:
            print("%s: no frames behind the dip" % path)
            continue
        t = [float(r["t"]) for r in seg]
        v = [float(r["v"]) for r in seg]
        n = len(seg)
        tm, vm = sum(t) / n, sum(v) / n
        slope = sum((a - tm) * (b - vm) for a, b in zip(t, v)) / sum((a - tm) ** 2 for a in t)
        r0 = seg[0]
        print("%s: %s, accel factor %.2f, speed factor %.2f | %d frames, %.2f s | v %.2f -> %.2f, mean %.2f, slope %+.2f per s | rpm %.0f"
              % (path, r0["state"], float(r0["accf"]), float(r0["spdf"]), n, t[-1] - t[0], v[0], v[-1], vm, slope, float(seg[-1]["rpm"])))
        if abs(v[-1] - v[0]) > 0.15:
            k, veq, rms = approach(t, v)
            print("   approach fitted as v = %.2f + offset * exp(-%.2f t), rms error %.3f" % (veq, k, rms))


if __name__ == "__main__":
    main()
