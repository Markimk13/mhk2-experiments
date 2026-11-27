"""Issue #32: for the hard hits of loss_context.py --list that have a steep level.bsp triangle
within 1.5 units ("bsp wall"): how high that triangle reaches above the road under the kart, its
material index, and the kart's lat. Low (top < 0.5 above the road) = an edge or slope of the
ground itself (a kerb, the bevelled edge of a bridge deck); tall = a visible wall, rock or post.
usage: py tools/loss_walls.py <NN> <context_list.txt> [--list]
"""
import collections
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import loss_context as LC  # noqa: E402
import rwmesh  # noqa: E402

lv, path = sys.argv[1], sys.argv[2]
show = "--list" in sys.argv
walls, ground, steep = LC.load_level(lv)
mats = collections.Counter()
kinds = collections.Counter()
for line in open(path):
    m = re.search(r"#(\d+) t\s+(\S+)\s+(\S+) ->\s+(\S+) (\S+).*wall\s+(\S+) .*kart\s+(\S+) jolt\s+(\S+) bsp\s+(\S+)\s+flush\s+\S+\s+\S+\s+lat\s+(\S+)\s+\((\S+) (\S+) (\S+)\)", line)
    if not m or float(m.group(8)) < 10 or float(m.group(9)) >= 1.5 or float(m.group(6)) < 1.5 or float(m.group(7)) < 3:
        continue
    x, y, z = map(float, m.groups()[10:])
    lat = float(m.group(10))
    best = None
    for gx in range(int((x - 3) // 4), int((x + 3) // 4) + 1):
        for gz in range(int((z - 3) // 4), int((z + 3) // 4) + 1):
            for P in steep[(gx, gz)]:
                if min(q[1] for q in P) < y + 1.0 and max(q[1] for q in P) > y - 0.3:
                    d = LC.pt_tri((x, y, z), P)
                    if best is None or d < best[0]:
                        best = (d, P)
    if best is None:
        continue
    g = LC.ground_at(ground, x, z, y + 2)
    top = max(q[1] for q in best[1]) - (g if g is not None else y - 0.21)
    kind = ("low" if top < 0.5 else "tall") + (", on the road" if 0.1 < lat < 0.9 else ", road edge or off")
    kinds[kind] += 1
    if show:
        print("t %7s %5s -> %5s lat %5.2f  steep %.2f away, top %.2f above the road, n (%.2f %.2f %.2f)  (%.1f %.1f %.1f)"
              % (m.group(2), m.group(3), m.group(4), lat, best[0], top, *rwmesh.normal(*best[1]), x, y, z))
print("level%s %s: %s" % (lv, os.path.basename(path), dict(kinds)))
