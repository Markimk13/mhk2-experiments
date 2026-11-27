"""Lower the posts of one material in a level.bsp (issue #32: Insel's bamboo posts).

usage: bsp_posts.py <level.bsp> <out.bsp> [--mat 22] [--width 1.5] [--height 1.5]

The triangles of material --mat are split into connected parts (shared vertices, per sector). A
part at most --width wide (x and z) and more than --height tall is a post's side; a narrow part
whose x/z box overlaps a post's is its cap (the cap has vertices of its own). Both go down to the
post's lowest y, so the post ends there. Vertices shared with other materials stay (count
printed). Insel: material 22 `Bambus2_UV` is the deck of the bridges AND the posts beside it
(583 narrow tall parts, about 0.5 wide, from the water to 0.1..1.5 above the deck, plus caps);
lowering the whole material removes the decks.
Writes a copy; the file layout stays the same (only vertex floats change). For a test archive:
datpack.py <game>\\data\\mhk2-02.dat data\\mk2\\level03\\objects\\level.bsp=<out.bsp>
"""
import argparse
import struct

import rwmesh


def parts_of(data, mat):
    """-> list of (vertex offsets, lo xyz, hi xyz) per connected part of material mat, and the
    number of vertices shared with other materials (those offsets are left out)"""
    t, s, v, body = next(rwmesh.chunks(data, 0, len(data)))
    assert t == 0x0B, "not a world"
    st = list(rwmesh.chunks(data, body, body + s))[0]
    flags = struct.unpack_from("<I", data, st[3] + 0x24)[0]
    out = []
    shared = 0

    def walk(off, end):
        nonlocal shared
        for t2, s2, v2, b2 in rwmesh.chunks(data, off, end):
            if t2 == 0x0A:
                walk(b2, b2 + s2)
            elif t2 != 0x09:
                continue
            else:
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
                other, par = set(), {}

                def root(x):
                    while par[x] != x:
                        par[x] = par[par[x]]
                        x = par[x]
                    return x
                for i in range(ntri):
                    v1, v2_, v3, m = struct.unpack_from("<4H", data, p + 8 * i)
                    if m + base == mat:
                        for x in (v1, v2_, v3):
                            par.setdefault(x, x)
                        par[root(v2_)] = root(v1)
                        par[root(v3)] = root(v1)
                    else:
                        other.update((v1, v2_, v3))
                groups = {}
                for x in par:
                    groups.setdefault(root(x), []).append(x)
                for vs in groups.values():
                    pts = [struct.unpack_from("<3f", data, vpos + 12 * i) for i in vs]
                    lo = [min(q[k] for q in pts) for k in range(3)]
                    hi = [max(q[k] for q in pts) for k in range(3)]
                    shared += sum(1 for i in vs if i in other)
                    out.append(([vpos + 12 * i for i in vs if i not in other], lo, hi))
    walk(body, body + s)
    return out, shared


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("src")
    ap.add_argument("out")
    ap.add_argument("--mat", type=int, default=22)
    ap.add_argument("--width", type=float, default=1.5)
    ap.add_argument("--height", type=float, default=1.5)
    a = ap.parse_args()
    data = bytearray(open(a.src, "rb").read())
    parts, shared = parts_of(data, a.mat)

    def narrow(lo, hi):
        return max(hi[0] - lo[0], hi[2] - lo[2]) <= a.width

    posts = [(lo, hi) for offs, lo, hi in parts if narrow(lo, hi) and hi[1] - lo[1] > a.height]
    cell = {}
    for k, (lo, hi) in enumerate(posts):
        cell.setdefault((int(lo[0] // 4), int(lo[2] // 4)), []).append(k)
    moved = caps = 0
    for offs, lo, hi in parts:
        if not narrow(lo, hi):
            continue
        bottom = None
        cx, cz = int(lo[0] // 4), int(lo[2] // 4)
        for dx in (-1, 0, 1):
            for dz in (-1, 0, 1):
                for k in cell.get((cx + dx, cz + dz), []):
                    plo, phi = posts[k]
                    if plo[0] - 0.1 <= hi[0] and lo[0] <= phi[0] + 0.1 and plo[2] - 0.1 <= hi[2] and lo[2] <= phi[2] + 0.1:
                        bottom = plo[1] if bottom is None else min(bottom, plo[1])
        if bottom is None:
            continue
        if hi[1] - lo[1] <= a.height:
            caps += 1
        for o in offs:
            struct.pack_into("<f", data, o + 4, bottom)
            moved += 1
    open(a.out, "wb").write(data)
    print("material %d: %d parts, %d posts, %d caps, %d vertices lowered, %d shared with other materials (kept)"
          % (a.mat, len(parts), len(posts), caps, moved, shared))


if __name__ == "__main__":
    main()
