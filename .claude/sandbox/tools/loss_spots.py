"""Issue #32: do the hard hits with nothing near (loss_context.py --list, category "hit, none")
repeat at the same places? Groups hits within --radius units (x/z) of each other and prints each
place with hits of 2 or more different karts / files.
usage: py tools/loss_spots.py <context_list.txt> [...] [--radius 5]
"""
import math
import re
import sys

radius = 5.0
files = []
args = sys.argv[1:]
while args:
    a = args.pop(0)
    if a == "--radius":
        radius = float(args.pop(0))
    else:
        files.append(a)
for path in files:
    hits = []
    for line in open(path):
        m = re.search(r"^(\S+)\s+#(\d+) t\s+(\S+)\s+(\S+) ->\s+(\S+) (\S+)\s.*wall\s+(\S+) \S+\s+step (\S+) clear \S+ kart\s+(\S+) jolt\s+(\S+) bsp\s+(\S+)\s+flush\s+\S+\s+\S+\s+lat\s+\S+\s+\((\S+) (\S+) (\S+)\)", line)
        if not m:
            continue
        f, k, t, v0, v1, kind, wd, st, kd, jolt, bd, x, y, z = m.groups()
        if float(jolt) >= 10 and float(wd) >= 1.5 and float(bd) >= 1.5 and float(kd) >= 3 and float(st) < 0.1:
            hits.append((f, int(k), float(t), float(v0), float(v1), kind, float(x), float(y), float(z)))
    used = set()
    places = []
    for i, h in enumerate(hits):
        if i in used:
            continue
        grp = [j for j, g in enumerate(hits) if j not in used and math.hypot(g[6] - h[6], g[8] - h[8]) < radius]
        used.update(grp)
        places.append([hits[j] for j in grp])
    multi = [p for p in places if len({(g[0], g[1]) for g in p}) >= 2]
    print("%s: %d hits with nothing near, %d places, %d places with 2+ karts (%d hits)" % (
        path, len(hits), len(places), len(multi), sum(len(p) for p in multi)))
    for p in sorted(multi, key=len, reverse=True)[:6]:
        print("   %2d hits at x %.0f y %.1f z %.0f: %s" % (len(p), sum(g[6] for g in p) / len(p), sum(g[7] for g in p) / len(p),
              sum(g[8] for g in p) / len(p), ", ".join("#%d %.0f->%.0f %s" % (g[1], g[3], g[4], g[5]) for g in p[:5])))
