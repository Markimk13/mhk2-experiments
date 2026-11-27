"""What is near each sudden speed loss, on any track (issue #32).

usage (from .claude/sandbox): py tools/loss_context.py <level 01..08> <recording.csv> [...] [--kart N] [--min 25] [--list]

Losses come from loss_kinds.py (default: kart 0 in race_recorder.py files, the computer karts in
ai_race.py files). Respawns, drops and losses in the air are left out. For each loss:
  wall   distance in x/z to the nearest wall (|ny| < 0.3, covering the kart's height) of the three
         collision meshes the exe loads: collision_objects, collision_border, collision_drop
         (0x442952..0x442CE3; collision.dff is never loaded)
  step   largest rise of level.bsp's ground between samples 0.05 apart along the kart's path in
         the 0.3 s before, on the centre line and 0.6 / 1.2 to each side, counted only from
         ground less than 1 below the kart (a side line that leaves the deck is no step)
  clear  the kart's height above level.bsp's ground right before (normal: about 0.21)
  kart   distance to the nearest other kart
  jolt   largest speed drop within 1/60 s in the 0.3 s from the loss; 10 units/s or more is a
         hit, less is sliding or braking. For a hit, every other column (and x y z, lat) is
         taken at the hit frame, not at the start of the loss window
  flush  a steep level.bsp triangle whose top edge is at road level (0.4 below to 0.3 above the
         ground under the kart), with the kart in front of it, moving towards it, within
         1.5 units of the kart (hit frame or the 0.05 s before): the hidden side face of a road
         piece, invisible from above, that the kart's front can run into; distance and top - ground
  bsp    distance to the nearest steep (|ny| < 0.5) triangle of level.bsp at the kart's height
         (y - 0.3 .. y + 1.0): a visible wall, fence, rock or post
Environment LOSS_BSP=<file> takes another level.bsp (for example one from bsp_hidden_faces.py).
Meshes: work/lNN/data/mk2/levelNN/objects/ (datextract.py mhk2-00.dat work/lNN "levelNN.objects.(level\\.bsp|collision.*\\.dff)$").
The summary sorts each loss into the first that fits: flush < 1.5, wall < 1.5, bsp < 1.5, kart < 3,
step >= 0.1, none.
"""
import argparse
import bisect
import collections
import csv
import math
import os
import subprocess
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import rwmesh  # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))


def load_level(lv):
    base = os.path.join(HERE, "..", "work", "l" + lv, "data", "mk2", "level" + lv, "objects")
    walls = collections.defaultdict(list)
    for f in ("collision_objects", "collision_border", "collision_drop"):
        p = os.path.join(base, f + ".dff")
        if not os.path.exists(p):
            continue
        for _, ts in rwmesh.load(p):
            for t in ts:
                P = t[:3]
                if abs(rwmesh.normal(*P)[1]) < 0.3:
                    xs = [q[0] for q in P]
                    zs = [q[2] for q in P]
                    for gx in range(int(min(xs) // 8), int(max(xs) // 8) + 1):
                        for gz in range(int(min(zs) // 8), int(max(zs) // 8) + 1):
                            walls[(gx, gz)].append((f, P))
    ground = collections.defaultdict(list)
    steep = collections.defaultdict(list)
    for _, ts in rwmesh.load(os.environ.get("LOSS_BSP") or os.path.join(base, "level.bsp")):
        for t in ts:
            P = t[:3]
            ny = rwmesh.normal(*P)[1]
            if abs(ny) < 0.5:
                xs = [q[0] for q in P]
                zs = [q[2] for q in P]
                for gx in range(int(min(xs) // 4), int(max(xs) // 4) + 1):
                    for gz in range(int(min(zs) // 4), int(max(zs) // 4) + 1):
                        steep[(gx, gz)].append(P)
            if ny <= 0.2:
                continue
            xs = [q[0] for q in P]
            zs = [q[2] for q in P]
            for gx in range(int(min(xs) // 2), int(max(xs) // 2) + 1):
                for gz in range(int(min(zs) // 2), int(max(zs) // 2) + 1):
                    ground[(gx, gz)].append(P)
    return walls, ground, steep


def seg_dist(px, pz, a, b):
    ax, az, bx, bz = a[0], a[2], b[0], b[2]
    dx, dz = bx - ax, bz - az
    L = dx * dx + dz * dz
    u = 0 if L == 0 else max(0, min(1, ((px - ax) * dx + (pz - az) * dz) / L))
    return math.hypot(px - (ax + u * dx), pz - (az + u * dz))


def wall_dist(walls, x, y, z):
    best = (99.0, "-")
    for gx in range(int(x // 8) - 1, int(x // 8) + 2):
        for gz in range(int(z // 8) - 1, int(z // 8) + 2):
            for f, P in walls[(gx, gz)]:
                if not (min(q[1] for q in P) - 1 < y < max(q[1] for q in P) + 1):
                    continue
                d = min(seg_dist(x, z, P[i], P[(i + 1) % 3]) for i in range(3))
                if d < best[0]:
                    best = (d, f)
    return best


def pt_tri(q, P):
    """distance from point q to triangle P"""
    a, b, c = P
    sub = lambda u, v: [u[k] - v[k] for k in range(3)]
    dot = lambda u, v: sum(u[k] * v[k] for k in range(3))
    best = 1e9
    for u, v in ((a, b), (b, c), (c, a)):
        d = sub(v, u)
        L = dot(d, d)
        w = 0 if L == 0 else max(0, min(1, dot(sub(q, u), d) / L))
        best = min(best, math.dist(q, [u[k] + w * d[k] for k in range(3)]))
    n = rwmesh.normal(*P)
    h = dot(sub(q, a), n)
    pr = [q[k] - h * n[k] for k in range(3)]
    v0, v1, v2 = sub(c, a), sub(b, a), sub(pr, a)
    d00, d01, d02, d11, d12 = dot(v0, v0), dot(v0, v1), dot(v0, v2), dot(v1, v1), dot(v1, v2)
    den = d00 * d11 - d01 * d01
    if den:
        u = (d11 * d02 - d01 * d12) / den
        v = (d00 * d12 - d01 * d02) / den
        if u >= 0 and v >= 0 and u + v <= 1:
            best = min(best, abs(h))
    return best


def steep_dist(steep, x, y, z):
    best = 99.0
    for gx in range(int((x - 3) // 4), int((x + 3) // 4) + 1):
        for gz in range(int((z - 3) // 4), int((z + 3) // 4) + 1):
            for P in steep[(gx, gz)]:
                if min(q[1] for q in P) < y + 1.0 and max(q[1] for q in P) > y - 0.3:
                    best = min(best, pt_tri((x, y, z), P))
    return best


def flush_dist(steep, ground, rows, i):
    """nearest steep triangle whose top edge lies at road level (-0.4 .. +0.3 around the ground
    under the kart) and whose front side faces the kart's horizontal velocity, over the hit frame
    and the frames of the 0.05 s before it -> (distance, top - ground)"""
    best = (99.0, 0.0)
    k0 = i
    while k0 > 0 and rows[i]["t"] - rows[k0 - 1]["t"] <= 0.05 + 1e-4:
        k0 -= 1
    for k in range(k0, i + 1):
        r = rows[k]
        x, y, z, vx, vz = r["x"], r["y"], r["z"], r["vx"], r["vz"]
        g = ground_at(ground, x, z, y + 1.0)
        if g is None:
            continue
        for gx in range(int((x - 3) // 4), int((x + 3) // 4) + 1):
            for gz in range(int((z - 3) // 4), int((z + 3) // 4) + 1):
                for P in steep[(gx, gz)]:
                    top = max(q[1] for q in P)
                    if not -0.4 < top - g < 0.3:
                        continue
                    n = rwmesh.normal(*P)
                    if n[0] * vx + n[2] * vz >= 0:
                        continue
                    if n[0] * (x - P[0][0]) + n[2] * (z - P[0][2]) <= 0:   # the kart must be in front of it
                        continue
                    d = pt_tri((x, g + 0.2, z), P)
                    if d < best[0]:
                        best = (d, top - g)
    return best


def ground_at(ground, x, z, ytop):
    best = None
    for P in ground[(int(x // 2), int(z // 2))]:
        (ax, ay, az), (bx, by, bz), (cx, cy, cz) = P
        d = (bz - cz) * (ax - cx) + (cx - bx) * (az - cz)
        if abs(d) < 1e-12:
            continue
        l1 = ((bz - cz) * (x - cx) + (cx - bx) * (z - cz)) / d
        l2 = ((cz - az) * (x - cx) + (ax - cx) * (z - cz)) / d
        l3 = 1 - l1 - l2
        if min(l1, l2, l3) < -1e-6:
            continue
        y = l1 * ay + l2 * by + l3 * cy
        if y < ytop and (best is None or y > best):
            best = y
    return best


def max_step(ground, rows, i0, i1):
    worst = 0.0
    for i in range(i0, i1):
        a, b = rows[i], rows[i + 1]
        dx, dz = b["x"] - a["x"], b["z"] - a["z"]
        L = math.hypot(dx, dz)
        if L < 1e-6:
            continue
        sx, sz = -dz / L, dx / L
        n = max(1, int(L / 0.05))
        for off in (-1.2, -0.6, 0, 0.6, 1.2):
            prev = None
            for k in range(n + 1):
                x = a["x"] + dx * k / n + sx * off
                z = a["z"] + dz * k / n + sz * off
                y = a["y"] + (b["y"] - a["y"]) * k / n
                g = ground_at(ground, x, z, y + 1.0)
                if g is not None and prev is not None and prev > y - 1.0:
                    worst = max(worst, g - prev)
                prev = g
    return worst


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("level")
    ap.add_argument("files", nargs="+")
    ap.add_argument("--kart", type=int)
    ap.add_argument("--min", type=float, default=25)
    ap.add_argument("--list", action="store_true")
    a = ap.parse_args()
    walls, ground, steep = load_level(a.level)
    cmd = [sys.executable, os.path.join(HERE, "loss_kinds.py"), *a.files, "--list", "--min", str(a.min)]
    if a.kart is not None:
        cmd += ["--kart", str(a.kart)]
    out = subprocess.run(cmd, capture_output=True, text=True).stdout
    losses = collections.defaultdict(list)
    for line in out.splitlines():
        w = line.split()
        try:
            losses[w[0]].append((int(w[1]), float(w[2]), float(w[3]), float(w[5]), w[-2], w[-1]))
        except (ValueError, IndexError):
            pass
    summary = collections.Counter()
    total = 0
    for path in a.files:
        karts = collections.defaultdict(list)
        with open(path) as f:
            for r in csv.DictReader(f):
                row = {}
                for k, v in r.items():
                    try:
                        row[k] = float(v) if v != "" else 0.0
                    except ValueError:
                        row[k] = 0.0
                karts[int(row["kart"])].append(row)
        times = {k: [r["t"] for r in rows] for k, rows in karts.items()}
        for kn, t, v0, v1, grd, kind in losses[os.path.basename(path)]:
            if kind.startswith(("respawn", "drop", "landing")) or kind.endswith("/air"):
                continue
            rows, ts = karts[kn], times[kn]
            i0 = bisect.bisect_left(ts, t)
            # the hit frame: the largest speed drop within 1/60 s in the 0.3 s from the window start
            win = list(range(max(0, i0 - 3), min(i0 + 90, len(rows))))
            win = [k for k in win if rows[k]["t"] <= t + 0.3]
            sp = {k: math.sqrt(rows[k]["vx"] ** 2 + rows[k]["vy"] ** 2 + rows[k]["vz"] ** 2) for k in win}
            jolt, i = 0.0, i0
            for x1 in range(len(win)):
                for x2 in range(x1 + 1, len(win)):
                    k, m = win[x1], win[x2]
                    if rows[m]["t"] - rows[k]["t"] > 1 / 60 + 1e-4:
                        break
                    if sp[k] - sp[m] > jolt:
                        jolt, i = sp[k] - sp[m], m
            hit = jolt >= 10
            if not hit:
                i = i0
            j = bisect.bisect_left(ts, rows[i]["t"] - 0.3)
            r = rows[i]
            wd, wf = wall_dist(walls, r["x"], r["y"], r["z"])
            st = max_step(ground, rows, j, min(i + 1, len(rows) - 1))
            g = ground_at(ground, r["x"], r["z"], r["y"] + 2)
            clear = r["y"] - g if g is not None else float("nan")
            tt = r["t"]
            kd = min((math.dist((r["x"], r["y"], r["z"]), (o[k2]["x"], o[k2]["y"], o[k2]["z"]))
                      for k, o in karts.items() if k != kn
                      for k2 in [min(bisect.bisect_left(times[k], tt), len(o) - 1)]), default=99)
            bd = steep_dist(steep, r["x"], r["y"], r["z"])
            fd, ftop = flush_dist(steep, ground, rows, i) if hit else (99.0, 0.0)
            lat = r.get("lat", 0.5)
            cat = "flush face" if fd < 1.5 else ("wall " + wf.replace("collision_", "")) if wd < 1.5 else "bsp wall" if bd < 1.5 else "kart" if kd < 3 else "step" if st >= 0.1 else "none"
            cat = ("hit, " if hit else "soft, ") + cat
            summary[cat] += 1
            total += 1
            if a.list:
                print("%-24s #%d t %7.2f %5.1f -> %5.1f %-14s %-12s wall %5.1f %-17s step %.3f clear %.2f kart %5.1f jolt %5.1f bsp %5.1f flush %5.1f %5.2f lat %5.2f  (%.1f %.1f %.1f)"
                      % (os.path.basename(path)[:24], kn, t, v0, v1, kind, grd[:12], wd, wf, st, clear, kd, jolt, bd, fd, ftop, lat, r["x"], r["y"], r["z"]))
    print("level%s: %d losses (no respawn / drop / air): %s" % (a.level, total, ", ".join("%s %d" % kv for kv in summary.most_common())))


if __name__ == "__main__":
    main()
