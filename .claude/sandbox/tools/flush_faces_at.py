"""Issue #32: the flush faces (see loss_context.py) at the hard hits of a context list, with what
is in front of each face: material, normal, height of its top edge over the road under the kart,
and the ground 0.3 units in front of the face's top edge (none = nothing, the face looks into the air).
usage: [LOSS_BSP=<file>] py tools/flush_faces_at.py <NN> <recording.csv> <context_list.txt>
"""
import collections
import csv
import math
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import loss_context as LC  # noqa: E402
import rwmesh  # noqa: E402

lv, path, lst = sys.argv[1], sys.argv[2:-1], sys.argv[-1]
walls, ground, steep = LC.load_level(lv)
mat = {}
base = os.environ.get("LOSS_BSP") or os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "work", "l" + lv, "data", "mk2", "level" + lv, "objects", "level.bsp")
for _, ts in rwmesh.load(base):
    for t in ts:
        mat[tuple(t[:3])] = t[3]
karts = {}
for pth in path:
    kk = collections.defaultdict(list)
    for r in csv.DictReader(open(pth)):
        kk[int(float(r["kart"]))].append({k: float(v) if v else 0.0 for k, v in r.items()})
    karts[os.path.basename(pth)[:24]] = kk
kinds = collections.Counter()
for line in open(lst):
    m = re.search(r"^(\S+)\s+#(\d+) .*jolt\s+(\S+) bsp\s+\S+ flush\s+(\S+)\s+\S+ .*\((\S+) (\S+) (\S+)\)", line)
    if not m or float(m.group(3)) < 10 or float(m.group(4)) >= 1.5:
        continue
    rows = karts[m.group(1)][int(m.group(2))]
    x, y, z = map(float, m.groups()[4:])
    i = min(range(len(rows)), key=lambda k: (rows[k]["x"] - x) ** 2 + (rows[k]["z"] - z) ** 2 + (rows[k]["y"] - y) ** 2)
    r = rows[i]
    g = LC.ground_at(ground, r["x"], r["z"], r["y"] + 1.0)
    best = None
    for gx in range(int((r["x"] - 3) // 4), int((r["x"] + 3) // 4) + 1):
        for gz in range(int((r["z"] - 3) // 4), int((r["z"] + 3) // 4) + 1):
            for P in steep[(gx, gz)]:
                top = max(q[1] for q in P)
                n = rwmesh.normal(*P)
                if g is None or not -0.4 < top - g < 0.3 or n[0] * r["vx"] + n[2] * r["vz"] >= 0:
                    continue
                d = LC.pt_tri((r["x"], g + 0.2, r["z"]), P)
                if best is None or d < best[0]:
                    best = (d, P, n, top - g)
    if best is None:
        continue
    d, P, n, rel = best
    top2 = sorted(P, key=lambda q: -q[1])[:2]
    q = [(top2[0][k] + top2[1][k]) / 2 for k in range(3)]
    h = math.hypot(n[0], n[2])
    gf = LC.ground_at(ground, q[0] + n[0] / h * 0.3, q[2] + n[2] / h * 0.3, q[1] + 0.5)
    front = "none" if gf is None else "%+.2f" % (gf - q[1])
    kind = "front: air or far below" if gf is None or gf - q[1] < -0.5 else "front: road a bit lower" if gf - q[1] < -0.1 else "front: road at the top (hidden)"
    kinds[kind] += 1
    print("%s #%s (%.1f %.1f %.1f) face %.2f away, mat %d, n (%.2f %.2f %.2f), top %+.2f over the road, depth %.1f, ground in front %s"
          % (m.group(1), m.group(2), x, y, z, d, mat.get(tuple(P), -1), *n, rel, top2[0][1] - min(p[1] for p in P), front))
print(dict(kinds))
