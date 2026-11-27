"""Remove hidden side faces from a level.bsp (issue #32: "invisible pixels").

usage: bsp_hidden_faces.py <level.bsp> <out.bsp> [--list] [--offset 0.3] [--tol 0.1]

A hidden side face is a steep triangle (|ny| < 0.5) whose front side looks into the road: at
three points along its top edge, the ground --offset units in front of it (along its horizontal
normal) lies no more than --tol below the top edge and less than 0.3 above it. The road covers
such a face, so nobody can see it, but the kart's body can run into its top edge, for example
where a road slab ends and the next piece lies a little lower (level07 x -212.5 z 61: slab top
58.0, next piece 57.9, side face 7 units deep facing back onto the slab).
Removal: the triangle's three vertex indices are set to its first one (zero area). Vertices stay,
so neighbouring triangles do not change. The file keeps its size. Test archive:
datpack.py <game>\\data\\mhk2-02.dat data\\mk2\\levelNN\\objects\\level.bsp=<out.bsp>
"""
import argparse
import collections
import math
import struct

import rwmesh


def sectors(data):
    """yields (tri offset, ntri, vertex offset, nvert, material base) per atomic sector"""
    t, s, v, body = next(rwmesh.chunks(data, 0, len(data)))
    assert t == 0x0B, "not a world"
    st = list(rwmesh.chunks(data, body, body + s))[0]
    flags = struct.unpack_from("<I", data, st[3] + 0x24)[0]
    out = []

    def walk(off, end):
        for t2, s2, v2, b2 in rwmesh.chunks(data, off, end):
            if t2 == 0x0A:
                walk(b2, b2 + s2)
            elif t2 == 0x09:
                p = list(rwmesh.chunks(data, b2, b2 + s2))[0][3]
                base, ntri, nvert = struct.unpack_from("<III", data, p)
                p += 12 + 24 + 8
                vpos = p
                p += 12 * nvert
                if flags & 0x10:
                    p += 4 * nvert
                if flags & 0x08:
                    p += 4 * nvert
                nsets = (flags >> 16 & 0xFF) or (2 if flags & 0x80 else 1 if flags & 0x04 else 0)
                p += 8 * nvert * nsets
                out.append((p, ntri, vpos, nvert, base))
    walk(body, body + s)
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("src")
    ap.add_argument("out")
    ap.add_argument("--offset", type=float, default=0.3)
    ap.add_argument("--tol", type=float, default=0.1)
    ap.add_argument("--list", action="store_true")
    a = ap.parse_args()
    data = bytearray(open(a.src, "rb").read())
    secs = sectors(data)
    tris = []      # (tri offset, P, material)
    for toff, ntri, vpos, nvert, base in secs:
        verts = [struct.unpack_from("<3f", data, vpos + 12 * i) for i in range(nvert)]
        for i in range(ntri):
            v1, v2, v3, m = struct.unpack_from("<4H", data, toff + 8 * i)
            tris.append((toff + 8 * i, (verts[v1], verts[v2], verts[v3]), m + base))
    ground = collections.defaultdict(list)
    for _, P, m in tris:
        if rwmesh.normal(*P)[1] > 0.2:
            xs = [q[0] for q in P]
            zs = [q[2] for q in P]
            for gx in range(int(min(xs) // 2), int(max(xs) // 2) + 1):
                for gz in range(int(min(zs) // 2), int(max(zs) // 2) + 1):
                    ground[(gx, gz)].append(P)

    def heights(x, z):
        out = []
        for P in ground[(int(x // 2), int(z // 2))]:
            (ax, ay, az), (bx, by, bz), (cx, cy, cz) = P
            d = (bz - cz) * (ax - cx) + (cx - bx) * (az - cz)
            if abs(d) < 1e-12:
                continue
            l1 = ((bz - cz) * (x - cx) + (cx - bx) * (z - cz)) / d
            l2 = ((cz - az) * (x - cx) + (ax - cx) * (z - cz)) / d
            l3 = 1 - l1 - l2
            if min(l1, l2, l3) >= -1e-6:
                out.append(l1 * ay + l2 * by + l3 * cy)
        return out

    removed = collections.Counter()
    for off, P, m in tris:
        n = rwmesh.normal(*P)
        if abs(n[1]) >= 0.5:
            continue
        h = math.hypot(n[0], n[2])
        if h < 1e-6:
            continue
        nx, nz = n[0] / h, n[2] / h
        top2 = sorted(P, key=lambda q: -q[1])[:2]
        if math.dist(top2[0], top2[1]) < 0.05:
            continue
        ok = True
        for f in (0.1, 0.5, 0.9):
            q = [top2[0][k] + f * (top2[1][k] - top2[0][k]) for k in range(3)]
            hs = heights(q[0] + nx * a.offset, q[2] + nz * a.offset)
            if not any(q[1] - a.tol <= y < q[1] + 0.3 for y in hs):
                ok = False
                break
        if not ok:
            continue
        v1 = struct.unpack_from("<H", data, off)[0]
        struct.pack_into("<3H", data, off, v1, v1, v1)
        removed[m] += 1
        if a.list:
            print("mat %3d n(%5.2f %5.2f %5.2f) top (%.2f %.2f %.2f)-(%.2f %.2f %.2f) bottom y %.2f"
                  % (m, *n, *top2[0], *top2[1], min(q[1] for q in P)))
    open(a.out, "wb").write(data)
    print("%d of %d triangles removed (hidden side faces), by material: %s" % (sum(removed.values()), len(tris), dict(removed.most_common())))


if __name__ == "__main__":
    main()
