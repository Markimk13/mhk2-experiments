"""List the placed objects of a track's objects.txt (decrypted: work/lNN/objects.txt) near a point.

usage: py tools/track_objects.py <NN> x z [radius 20]     (issue #32)
Reads "position", "Start Position" and "centre" lines of each object block.
"""
import math
import os
import re
import sys

lv, x0, z0 = sys.argv[1], float(sys.argv[2]), float(sys.argv[3])
r = float(sys.argv[4]) if len(sys.argv) > 4 else 20.0
path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "work", "l" + lv, "objects.txt")
txt = open(path, encoding="cp1252").read()
for blk in re.split(r"(?:DYNAMIC )?OBJECT START", txt)[1:]:
    m = re.search(r'class type: "class ([^"]+)"', blk)
    nm = re.search(r'\]\s*"([^"]*)"', blk)
    for p in re.finditer(r'"(position|Start Position|centre)" (\S+) (\S+) (\S+)', blk):
        x, y, z = map(float, p.groups()[1:])
        d = math.hypot(x - x0, z - z0)
        if d < r:
            print("%-22s %-28s %-15s (%.1f %.1f %.1f) dist %.1f" % (m.group(1) if m else "?", nm.group(1) if nm else "", p.group(1), x, y, z, d))
