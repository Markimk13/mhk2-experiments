"""Compare recorded kart runs.  usage: analyze.py <csv> [csv...]"""
import csv
import math
import os
import sys


def load(path):
    rows = []
    with open(path) as f:
        for r in csv.DictReader(f):
            rows.append({k: float(v) for k, v in r.items()})
    return rows


def interp(rows, key, t):
    """value of `key` at race time t (linear interpolation)"""
    for i in range(1, len(rows)):
        a, b = rows[i - 1], rows[i]
        if a["race_time"] <= t <= b["race_time"]:
            w = (t - a["race_time"]) / max(b["race_time"] - a["race_time"], 1e-9)
            if callable(key):
                return key(a) + w * (key(b) - key(a))
            return a[key] + w * (b[key] - a[key])
    return float("nan")


def speed(r):
    return math.sqrt(r["vx"] ** 2 + r["vz"] ** 2)


def main():
    runs = [(os.path.basename(p), load(p)) for p in sys.argv[1:]]
    for name, rows in runs:
        dts = [b["race_time"] - a["race_time"] for a, b in zip(rows, rows[1:])]
        dts_sorted = sorted(dts)
        t0 = rows[0]["race_time"]
        print(f"== {name}: {len(rows)} frames, race time {t0:.3f}..{rows[-1]['race_time']:.3f}")
        print(f"   frame dt: min {dts_sorted[0]*1000:.3f} ms, median {dts_sorted[len(dts)//2]*1000:.3f} ms, "
              f"max {dts_sorted[-1]*1000:.3f} ms, mean {sum(dts)/len(dts)*1000:.3f} ms")
        wall = rows[-1]["wall"] - rows[0]["wall"]
        game = rows[-1]["race_time"] - rows[0]["race_time"]
        print(f"   game time / wall time = {game / wall:.4f}")
    t_base = max(rows[0]["race_time"] for _, rows in runs)
    print("\nrace time | " + " | ".join(f"{n:>22}" for n, _ in runs))
    print("  speed (horizontal units/s), distance from first sample, height y, vertical speed vy")
    for dt in [0.25, 0.5, 0.75, 1.0, 1.5, 2.0, 2.5, 3.0, 3.5, 4.0, 4.5, 5.0, 6.0, 7.0, 8.0]:
        t = t_base + dt
        cells = []
        for n, rows in runs:
            if t > rows[-1]["race_time"]:
                cells.append(" " * 22)
                continue
            s = interp(rows, speed, t)
            x0, z0 = interp(rows, "x", t_base), interp(rows, "z", t_base)
            d = math.hypot(interp(rows, "x", t) - x0, interp(rows, "z", t) - z0)
            cells.append(f"v={s:6.2f} d={d:7.2f} y={interp(rows, 'y', t):5.2f}")
        print(f"  +{dt:4.2f}s | " + " | ".join(cells))
    print("\nvertical motion (vy) per run:")
    for name, rows in runs:
        vys = [r["vy"] for r in rows]
        mean = sum(vys) / len(vys)
        rms = math.sqrt(sum((v - mean) ** 2 for v in vys) / len(vys))
        print(f"   {name}: vy min {min(vys):6.2f} max {max(vys):6.2f} rms {rms:5.2f}; "
              f"max speed {max(speed(r) for r in rows):6.2f}; rpm max {max(r['rpm'] for r in rows):7.1f}")


if __name__ == "__main__":
    main()
