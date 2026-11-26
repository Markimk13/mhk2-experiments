"""Statistics over computer-driven karts in recorded races.  usage: ai_stats.py <csv> [...]

Per variant (averaged over the 6 computer karts, from race second 5 on):
  pace      distance covered, mean and top speed
  contact   share of time with at least one wheel off the ground / all four off, hop count
  chassis   share of (weight + downforce) that the four wheels do NOT carry while all are down
  sliding   sideways speed and slip angle (angle between where the kart points and where it moves)
"""
import csv
import math
import os
import sys
from collections import defaultdict

G = 19.62
DOWNFORCE = 0.5


def pct(vals, q):
    s = sorted(vals)
    return s[min(len(s) - 1, int(q * len(s)))] if s else float("nan")


def kart_stats(rows):
    n = len(rows)
    sp = [math.hypot(r["vx"], r["vz"]) for r in rows]
    out = {}
    out["dist"] = sum(math.hypot(b["x"] - a["x"], b["z"] - a["z"]) for a, b in zip(rows, rows[1:]))
    out["mean_v"] = sum(sp) / n
    out["top_v"] = pct(sp, 0.99)
    out["any_off"] = sum(1 for r in rows if not all(r[f"c{i}"] for i in range(4))) / n
    out["all_off"] = sum(1 for r in rows if not any(r[f"c{i}"] for i in range(4))) / n
    hops, longest, start = 0, 0.0, None
    for r in rows:
        off = not any(r[f"c{i}"] for i in range(4))
        if off and start is None:
            start = r["t"]
        elif not off and start is not None:
            d = r["t"] - start
            hops += d >= 0.10
            longest = max(longest, d)
            start = None
    out["hops"], out["longest"] = hops, longest
    # chassis share by speed band (all four wheels down)
    for lo, hi in ((0, 20), (20, 30), (30, 40), (40, 99)):
        sel = [(r, s) for r, s in zip(rows, sp) if lo <= s < hi and all(r[f"c{i}"] for i in range(4))]
        if len(sel) > 20:
            need = sum(r["mass"] * G + DOWNFORCE * s * s for r, s in sel)
            have = sum(sum(r[f"load{i}"] for i in range(4)) for r, s in sel)
            out[f"chassis_{lo}"] = 1 - have / need
    # sliding: lateral speed relative to the kart's own axes (fwd = model x axis, side = model z axis)
    slips, lats = [], []
    for r, s in zip(rows, sp):
        if s < 15:
            continue
        v_long = r["vx"] * r["fx"] + r["vy"] * r["fy"] + r["vz"] * r["fz"]
        v_lat = r["vx"] * r["sx"] + r["vy"] * r["sy"] + r["vz"] * r["sz"]
        slips.append(math.degrees(math.atan2(abs(v_lat), abs(v_long))))
        lats.append(abs(v_lat))
    out["slip_mean"] = sum(slips) / len(slips) if slips else float("nan")
    out["slip_p90"] = pct(slips, 0.90)
    out["slip_over10"] = sum(1 for a in slips if a > 10) / len(slips) if slips else float("nan")
    out["lat_mean"] = sum(lats) / len(lats) if lats else float("nan")
    out["vy_rms"] = math.sqrt(sum(r["vy"] ** 2 for r in rows) / n)
    return out


def main():
    table = {}
    for p in sys.argv[1:]:
        karts = defaultdict(list)
        for r in csv.DictReader(open(p)):
            karts[int(r["kart"])].append({k: float(v) for k, v in r.items()})
        stats = [kart_stats([r for r in rows if r["t"] >= 5.0]) for k, rows in sorted(karts.items()) if k != 0]
        keys = sorted({k for s in stats for k in s})
        avg = {k: sum(s[k] for s in stats if k in s) / max(1, sum(1 for s in stats if k in s)) for k in keys}
        avg["hops"] = sum(s["hops"] for s in stats)
        avg["longest"] = max(s["longest"] for s in stats)
        table[os.path.basename(p)] = avg
    names = list(table)
    rowspec = [
        ("distance covered (units)", "dist", "%.0f"), ("mean speed", "mean_v", "%.2f"), ("top speed (99th pct)", "top_v", "%.2f"),
        ("time with >=1 wheel in the air", "any_off", "pct"), ("time fully airborne", "all_off", "pct"),
        ("hops >= 0.1 s (all 6 karts)", "hops", "%.0f"), ("longest hop (s)", "longest", "%.2f"),
        ("load NOT on wheels, v < 20", "chassis_0", "pct"), ("load NOT on wheels, v 20-30", "chassis_20", "pct"),
        ("load NOT on wheels, v 30-40", "chassis_30", "pct"), ("load NOT on wheels, v > 40", "chassis_40", "pct"),
        ("mean slip angle (deg), v > 15", "slip_mean", "%.2f"), ("90th pct slip angle (deg)", "slip_p90", "%.2f"),
        ("time sliding > 10 deg", "slip_over10", "pct"), ("mean sideways speed", "lat_mean", "%.2f"),
        ("vertical speed rms", "vy_rms", "%.2f"),
    ]
    print("%-34s" % "" + "".join("%18s" % n.replace(".csv", "") for n in names))
    for label, key, fmt in rowspec:
        cells = []
        for n in names:
            v = table[n].get(key, float("nan"))
            cells.append("%17.1f%%" % (v * 100) if fmt == "pct" else "%18s" % (fmt % v))
        print("%-34s" % label + "".join(cells))


if __name__ == "__main__":
    main()
