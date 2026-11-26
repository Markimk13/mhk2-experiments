"""Ride height / wheel load of the kart standing still on the grid.  usage: rest.py <csv> [...]"""
import csv
import os
import sys

for p in sys.argv[1:]:
    rows = [{k: float(v) for k, v in r.items()} for r in csv.DictReader(open(p))]
    n = len(rows)
    dts = sorted(b["race_time"] - a["race_time"] for a, b in zip(rows, rows[1:]))
    ys = [r["y"] for r in rows]
    loads = [sum(r[f"load{i}"] for r in rows) / n for i in range(4)]
    contact = [sum(1 for r in rows if r[f"c{i}"] != 0) / n for i in range(4)]
    print(f"{os.path.basename(p):18s} step {dts[len(dts)//2]*1000:6.2f} ms | y mean {sum(ys)/n:.4f} min {min(ys):.4f} max {max(ys):.4f} | "
          f"wheel load FL FR RL RR {' '.join('%6.1f' % l for l in loads)} sum {sum(loads):6.1f} | contact {' '.join('%3.0f%%' % (c*100) for c in contact)}")
