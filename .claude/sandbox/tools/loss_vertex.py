"""Issue #32: do the hard hits with nothing near happen where the kart passes a corner (vertex)
of the road mesh? For each such hit (loss_context.py --list: jolt >= 10, no wall / bsp / flush /
kart / step), the x/z distance from the kart's path in the 1/60 s before the hit frame to the
nearest vertex of level.bsp's ground triangles (ny > 0.2, within 1 unit below .. 0.3 above the
kart's ground); the same for 300 random frames above 45 units/s as a control.
usage: py tools/loss_vertex.py <NN> <recording.csv> <context_list.txt>
"""
import bisect
import collections
import csv
import math
import os
import random
import re
import statistics
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import loss_context as LC  # noqa: E402
import rwmesh  # noqa: E402

lv, path, lst = sys.argv[1], sys.argv[2], sys.argv[3]
base = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "work", "l" + lv, "data", "mk2", "level" + lv, "objects", "level.bsp")
verts = collections.defaultdict(set)
for _, ts in rwmesh.load(base):
    for t in ts:
        if rwmesh.normal(*t[:3])[1] > 0.2:
            for q in t[:3]:
                verts[(int(q[0] // 4), int(q[2] // 4))].add(q)
walls, ground, steep = LC.load_level(lv)


def seg_point(a, b, q):
    dx, dz = b[0] - a[0], b[2] - a[2]
    L = dx * dx + dz * dz
    u = 0 if L == 0 else max(0, min(1, ((q[0] - a[0]) * dx + (q[2] - a[2]) * dz) / L))
    return math.hypot(q[0] - a[0] - u * dx, q[2] - a[2] - u * dz)


def vdist(a, b):
    g = LC.ground_at(ground, b[0], b[2], b[1] + 1.0)
    if g is None:
        return None
    best = 99.0
    for gx in range(int(min(a[0], b[0]) // 4) - 1, int(max(a[0], b[0]) // 4) + 2):
        for gz in range(int(min(a[2], b[2]) // 4) - 1, int(max(a[2], b[2]) // 4) + 2):
            for q in verts[(gx, gz)]:
                if g - 1.0 < q[1] < g + 0.3:
                    best = min(best, seg_point(a, b, q))
    return best


karts = collections.defaultdict(list)
for r in csv.DictReader(open(path)):
    karts[int(float(r["kart"]))].append({k: float(v) if v else 0.0 for k, v in r.items()})
times = {k: [r["t"] for r in v] for k, v in karts.items()}
hits = []
for line in open(lst):
    m = re.search(r"^(\S+)\s+#(\d+) .*wall\s+(\S+) .*step (\S+) .*kart\s+(\S+) jolt\s+(\S+) bsp\s+(\S+) flush\s+(\S+) .*\((\S+) (\S+) (\S+)\)", line)
    if not m or os.path.basename(path)[:24] != m.group(1):
        continue
    kn = int(m.group(2))
    wd, st, kd, jolt, bd, fd = map(float, m.groups()[2:8])
    if jolt < 10 or wd < 1.5 or bd < 1.5 or fd < 1.5 or kd < 3 or st >= 0.1:
        continue
    x, y, z = map(float, m.groups()[8:])
    rows = karts[kn]
    i = min(range(len(rows)), key=lambda k: (rows[k]["x"] - x) ** 2 + (rows[k]["z"] - z) ** 2 + (rows[k]["y"] - y) ** 2)
    k0 = i
    while k0 > 0 and rows[i]["t"] - rows[k0 - 1]["t"] <= 1 / 60 + 1e-4:
        k0 -= 1
    d = vdist((rows[k0 - 1]["x"], rows[k0 - 1]["y"], rows[k0 - 1]["z"]), (rows[i]["x"], rows[i]["y"], rows[i]["z"])) if k0 > 0 else None
    if d is not None:
        hits.append(d)
random.seed(3)
ctrl = []
allrows = [(k, j) for k, v in karts.items() for j in range(1, len(v))]
while len(ctrl) < 300:
    k, j = random.choice(allrows)
    r = karts[k][j]
    if math.sqrt(r["vx"] ** 2 + r["vz"] ** 2) < 45 or not all(r["c%d" % w] for w in range(4)):
        continue
    j0 = j
    while j0 > 0 and r["t"] - karts[k][j0 - 1]["t"] <= 1 / 60 + 1e-4:
        j0 -= 1
    if j0 == 0:
        continue
    p = karts[k][j0 - 1]
    d = vdist((p["x"], p["y"], p["z"]), (r["x"], r["y"], r["z"]))
    if d is not None:
        ctrl.append(d)


def share(v, lim):
    return 100.0 * sum(1 for x in v if x < lim) / len(v) if v else 0


print("level%s %s: %d hits with nothing near, path to the nearest road vertex: median %.2f, within 0.5: %.0f %%, within 1.0: %.0f %% | random frames: median %.2f, within 0.5: %.0f %%, within 1.0: %.0f %%"
      % (lv, os.path.basename(path), len(hits), statistics.median(hits) if hits else -1, share(hits, 0.5), share(hits, 1.0),
         statistics.median(ctrl), share(ctrl, 0.5), share(ctrl, 1.0)))
