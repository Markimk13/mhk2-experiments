"""Issue #32: which hard hits of loss_context.py --list lie in a RotatedBoxArea of the track
(objects.txt: "speed limit", "respawn", "start", ...). Tests both turning directions of the box's
rotation (y axis), because the sign the game uses is not traced; size = across (x), height, along (z).
usage: py tools/loss_boxes.py <NN> <context_list.txt> [...]
"""
import math
import os
import re
import sys

lv = sys.argv[1]
txt = open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "work", "l" + lv, "objects.txt"), encoding="cp1252").read()
boxes = []
for blk in re.split(r"(?:DYNAMIC )?OBJECT START", txt)[1:]:
    if "class RotatedBoxArea" not in blk:
        continue
    nm = re.search(r'\]\s*"([^"]*)"', blk).group(1)
    pos = list(map(float, re.search(r'"position" (\S+) (\S+) (\S+)', blk).groups()))
    w, x, y, z = map(float, re.search(r'"rotation" (\S+) (\S+) (\S+) (\S+)', blk).groups())
    sz = list(map(float, re.search(r'"size" (\S+) (\S+) (\S+)', blk).groups()))
    msg = re.search(r'"message" "([^"]*)"', blk)
    msg = msg.group(1) if msg else ""
    par = re.search(r'"parameters" "([^"]*)"', blk)
    par = par.group(1) if par else ""
    boxes.append((nm, msg + " " + par, pos, 2 * math.atan2(y, w), sz))


def inside(p, b, sign):
    nm, msg, pos, ang, sz = b
    dx, dz = p[0] - pos[0], p[2] - pos[2]
    a = sign * ang
    lx = dx * math.cos(a) - dz * math.sin(a)
    lz = dx * math.sin(a) + dz * math.cos(a)
    return abs(lx) <= sz[0] / 2 and abs(lz) <= sz[2] / 2 and abs(p[1] - pos[1]) <= sz[1] / 2 + 5


for path in sys.argv[2:]:
    n = 0
    cnt = {1: {}, -1: {}}
    for line in open(path):
        m = re.search(r"jolt\s+(\S+) bsp\s+\S+\s+flush\s+\S+\s+\S+\s+lat\s+\S+\s+\((\S+) (\S+) (\S+)\)", line)
        if not m or float(m.group(1)) < 10:
            continue
        n += 1
        p = tuple(map(float, m.groups()[1:]))
        for sign in (1, -1):
            for b in boxes:
                if inside(p, b, sign):
                    cnt[sign][b[0] + " " + b[1]] = cnt[sign].get(b[0] + " " + b[1], 0) + 1
    print("%s: %d hard hits; in a box, rotation +: %d %s | rotation -: %d %s" % (
        path, n, sum(cnt[1].values()), cnt[1], sum(cnt[-1].values()), cnt[-1]))
