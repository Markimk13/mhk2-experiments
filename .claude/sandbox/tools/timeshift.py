import csv, math, sys
def load(p):
    rows = [{k: float(v) for k, v in r.items()} for r in csv.DictReader(open(p))]
    t0 = rows[0]["race_time"]
    return [(r["race_time"], math.hypot(r["vx"], r["vz"])) for r in rows]
def at(series, t):
    for (t0, v0), (t1, v1) in zip(series, series[1:]):
        if t0 <= t <= t1:
            return v0 + (v1 - v0) * (t - t0) / max(t1 - t0, 1e-9)
    return None
a = load(sys.argv[1]); b = load(sys.argv[2])     # a = 60 FPS, b = compensated 200 FPS
ts = [0.6 + 0.05 * i for i in range(48)]          # race time 0.6 .. 2.95 s (on the road)
best = None
for shift_ms in range(-10, 81, 2):
    sh = shift_ms / 1000.0
    err = []
    for t in ts:
        va, vb = at(a, t + sh), at(b, t)
        if va is not None and vb is not None:
            err.append((vb - va) ** 2)
    rms = math.sqrt(sum(err) / len(err))
    if best is None or rms < best[1]:
        best = (shift_ms, rms)
    if shift_ms in (0, 20, 30, 40):
        print(f"  60 FPS curve shifted by {shift_ms:3d} ms: rms speed difference {rms:.3f} units/s")
print(f"best match: the 60 FPS run lags the compensated 200 FPS run by {best[0]} ms (remaining rms difference {best[1]:.3f} units/s)")
