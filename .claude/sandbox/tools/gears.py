import csv, sys, math
for p in sys.argv[1:]:
    rows = [{k: float(v) for k, v in r.items()} for r in csv.DictReader(open(p))]
    print("==", p.split("\\")[-1])
    last = None
    t0 = rows[0]["race_time"]
    nxt = 0.0
    for r in rows:
        g = (int(r["f320"]), int(r["f30c"]))
        t = r["race_time"] - t0
        if g != last or t >= nxt:
            v = math.hypot(r["vx"], r["vz"])
            mark = "  <- change" if g != last else ""
            print(f"   t=+{t:5.3f}  v={v:6.2f}  f320={g[0]}  f30c={g[1]}  f334={r['rpm']:8.1f}  y={r['y']:.3f} vy={r['vy']:6.2f}{mark}")
            last = g
            if t >= nxt: nxt += 0.25
