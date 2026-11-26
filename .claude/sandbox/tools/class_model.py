"""Longitudinal model of a kart (Moorhuhn) on the flat: gearing factor s and pull factor p.

usage: class_model.py                      table for the stock classes and some candidates
       class_model.py match <top speed> <pull>     gearing that gives this top speed with this pull

Thrust per unit of torque in top gear C = 16.15 units/s2, resistance 2.81 * (v / 57.57)^2,
traction limit 22.2 units/s2 (the launch acceleration measured in every class), gears
1.0 / 1.0 / 0.75 / 0.5 with a change at 4000 rpm, engine speed 143.27 * v * (gear / 0.5) / s.
The pull factor multiplies thrust and traction limit, like the game's power-ups do.
Fitted to runs of 2026-11-18; see .claude/memory/mhk2-powerups-and-class-factors.md.
"""
import sys

C, R0, VREF, TRACTION = 16.15, 2.81, 57.57, 22.2
GEARS = (1.0, 1.0, 0.75, 0.5)


def torque(rpm):
    pts = [(0, 1.4), (2000, 1.0), (4000, 0.6), (6000, 0.0)]
    if rpm >= 6000:
        return 0.0
    for (r0, t0), (r1, t1) in zip(pts, pts[1:]):
        if rpm <= r1:
            return t0 + (t1 - t0) * (rpm - r0) / (r1 - r0)


def top_speed(s, p=1.0):
    lo, hi = 20.0, 200.0
    for _ in range(60):
        mid = (lo + hi) / 2
        if p * C * torque(143.27 * mid / s) - R0 * (mid / VREF) ** 2 > 0:
            lo = mid
        else:
            hi = mid
    return lo


def match(v, p):
    """Gearing factor that gives top speed v with pull p."""
    lo, hi = 0.5, 4.0
    for _ in range(60):
        mid = (lo + hi) / 2
        if top_speed(mid, p) < v:
            lo = mid
        else:
            hi = mid
    return lo


def start(s, p=1.0, t_end=4.0, dt=0.001):
    v, t, gear = 0.0, 0.0, 0
    marks, reach = {}, {}
    while t < t_end:
        rpm = 143.27 * v * (GEARS[gear] / 0.5) / s
        if rpm > 4000 and gear < 3:
            gear += 1
            continue
        thrust = min(C * (GEARS[gear] / 0.5) * torque(rpm), TRACTION) * p
        v += (thrust - R0 * (v / VREF) ** 2) * dt
        t += dt
        for m in (0.5, 1.0, 2.0, 3.0):
            if m not in marks and t >= m:
                marks[m] = v
        for target in (30.0, 40.0, 50.0):
            if target not in reach and v >= target:
                reach[target] = t
    return marks, reach


def row(name, s, p):
    marks, reach = start(s, p)
    print("%-22s s %.3f p %.2f | top %5.1f | v after 0.5/1/2/3 s: %s | time to 30/40/50: %s"
          % (name, s, p, top_speed(s, p), " ".join("%5.1f" % marks[m] for m in (0.5, 1.0, 2.0, 3.0)),
             " ".join("%5.2f" % reach[v] if v in reach else "  -  " for v in (30.0, 40.0, 50.0))))


def main():
    if len(sys.argv) > 1 and sys.argv[1] == "match":
        v, p = float(sys.argv[2]), float(sys.argv[3])
        print("top speed %.2f with pull %.2f: gearing factor %.4f" % (v, p, match(v, p)))
        return
    for name, s in (("50 cc", 0.9), ("100 cc", 1.1), ("150 cc", 1.3), ("200 cc (1.3)", 1.52), ("250 cc (1.3)", 1.64)):
        row(name, s, 1.0)
    print()
    for p in (1.25, 1.5, 1.75, 2.0):
        row("200 cc, pull %.2f" % p, match(57.59, p), p)
    print()
    for p in (1.5, 2.0, 2.5, 3.0):
        row("250 cc, pull %.2f" % p, match(61.25, p), p)
    print()
    row("150 cc + siren", 1.3 * 1.10, 2.5)
    row("150 cc + power can", 1.3 * 1.15, 5.0)


if __name__ == "__main__":
    main()
