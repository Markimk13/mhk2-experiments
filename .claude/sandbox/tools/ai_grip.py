"""Cornering grip and vertical kicks from recorded races.  usage: ai_grip.py <csv> [...]

grip:   for the same cornering demand (lateral acceleration, from how fast the direction of travel
        turns) how far does the kart point away from its direction of travel (slip angle)?
kicks:  sudden upward changes of vertical speed within ~20 ms while the kart was on its wheels.
"""
import csv
import math
import os
import sys
from collections import defaultdict


def series(rows, win):
    """per-sample: speed, lateral acceleration, slip angle, upward kick"""
    out = []
    n = len(rows)
    ts = [r["t"] for r in rows]
    j0 = 0
    for i, r in enumerate(rows):
        # symmetric window of +-win seconds
        while ts[i] - ts[j0] > win:
            j0 += 1
        j1 = i
        while j1 + 1 < n and ts[j1 + 1] - ts[i] <= win:
            j1 += 1
        if j1 == j0:
            continue
        a, b = rows[j0], rows[j1]
        dt = b["t"] - a["t"]
        s = math.hypot(r["vx"], r["vz"])
        if s < 1 or dt <= 0:
            continue
        h0, h1 = math.atan2(a["vz"], a["vx"]), math.atan2(b["vz"], b["vx"])
        dh = (h1 - h0 + math.pi) % (2 * math.pi) - math.pi
        alat = abs(s * dh / dt)
        v_long = r["vx"] * r["fx"] + r["vy"] * r["fy"] + r["vz"] * r["fz"]
        v_lat = r["vx"] * r["sx"] + r["vy"] * r["sy"] + r["vz"] * r["sz"]
        slip = math.degrees(math.atan2(abs(v_lat), abs(v_long)))
        out.append((r["t"], s, alat, slip))
    return out


def kicks(rows, span=0.02, thresh=1.5):
    """count upward vertical-speed jumps > thresh within `span` seconds, starting with all wheels down"""
    count = 0
    last_t = -1.0
    j = 0
    for i, r in enumerate(rows):
        while r["t"] - rows[j]["t"] > span:
            j += 1
        a = rows[j]
        if j < i and r["vy"] - a["vy"] > thresh and all(a[f"c{k}"] for k in range(4)) and r["t"] - last_t > 0.25:
            count += 1
            last_t = r["t"]
    return count


def main():
    bands = [(5, 10), (10, 15), (15, 20), (20, 25), (25, 35)]
    speed_bands = [(20, 30), (30, 45)]
    res = {}
    for p in sys.argv[1:]:
        karts = defaultdict(list)
        for r in csv.DictReader(open(p)):
            karts[int(r["kart"])].append({k: float(v) for k, v in r.items()})
        acc = defaultdict(list)
        nk, dist = 0, 0.0
        for k, rows in karts.items():
            if k == 0:
                continue
            rows = [r for r in rows if r["t"] >= 5.0]
            for t, s, alat, slip in series(rows, 0.05):
                for slo, shi in speed_bands:
                    if slo <= s < shi:
                        for lo, hi in bands:
                            if lo <= alat < hi:
                                acc[(slo, lo)].append(slip)
            nk += kicks(rows)
            dist += sum(math.hypot(b["x"] - a["x"], b["z"] - a["z"]) for a, b in zip(rows, rows[1:]))
        res[os.path.basename(p).replace(".csv", "")] = (acc, nk, dist)
    names = list(res)
    print("mean slip angle (deg) at equal cornering demand   [samples]")
    print("%-34s" % "" + "".join("%22s" % n for n in names))
    for slo, shi in speed_bands:
        for lo, hi in bands:
            cells = []
            for n in names:
                v = res[n][0].get((slo, lo), [])
                cells.append("%22s" % ("%.2f  [%d]" % (sum(v) / len(v), len(v)) if len(v) >= 30 else "-"))
            print("%-34s" % f"speed {slo}-{shi}, lat. accel {lo}-{hi}" + "".join(cells))
    print()
    print("%-34s" % "upward kicks per 1000 units driven" + "".join("%22s" % ("%.1f  (%d)" % (res[n][1] / res[n][2] * 1000, res[n][1])) for n in names))


if __name__ == "__main__":
    main()
