"""Triangles of RenderWare .dff / .bsp files of Moorhuhn Kart 2 (collision meshes, level.bsp).

usage: rwmesh.py tree <file> [depth]
       rwmesh.py near <file> x y z [radius]      triangles with a vertex within radius (default 3)
       rwmesh.py tris <file>                       count of triangles per geometry / sector

Chunks: 12-byte header (type, size, version). Containers walked: Clump 0x10, FrameList 0x0E,
GeometryList 0x1A, Geometry 0x0F, World 0x0B, PlaneSector 0x0A, AtomicSector 0x09,
Extension 0x03, MaterialList 0x08, Atomic 0x14.

Geometry (0x0F) struct: flags u16, num tex sets u8, native u8, numTris, numVerts, numMorph;
(version < 0x34000: ambient, specular, diffuse floats); prelit colours if flag 0x08; tex sets
(numVerts * 2 floats each, count from the byte, or 1/2 from flags 0x04 / 0x80); triangles
numTris * (u16 v2, v1, material, v3); per morph target: sphere 4 floats, hasVerts, hasNormals,
vertices, normals. Frames are applied when an atomic links frame -> geometry.

AtomicSector (0x09) struct: matListWindowBase, numTris, numVerts, bbox max 3f, min 3f,
collSectorPresent, unused; vertices 3f; normals (4 bytes each) if the world has flag 0x10;
prelit if 0x08; tex coords per set (count in flags >> 16); triangles numTris * (u16 v1, v2,
v3, material), material last (checked on Insel's level.bsp, 28 bytes per vertex).
"""
import math
import struct
import sys

CONTAINERS = {0x10, 0x0E, 0x1A, 0x0F, 0x0B, 0x0A, 0x09, 0x03, 0x08, 0x14, 0x07}


def chunks(data, off, end):
    while off + 12 <= end:
        t, s, v = struct.unpack_from("<III", data, off)
        yield t, s, v, off + 12
        off += 12 + s


def tree(data, off=0, end=None, depth=0, maxd=6):
    end = len(data) if end is None else end
    for t, s, v, body in chunks(data, off, end):
        print("  " * depth + "%04X size %d ver %X at %X" % (t, s, v, body - 12))
        if t in CONTAINERS and depth < maxd:
            tree(data, body, body + s, depth + 1, maxd)


def rw_version(v):
    if v & 0xFFFF0000:
        return ((v >> 14 & 0x3FF00) + 0x30000) | (v >> 16 & 0x3F)
    return v << 8


def geometry(data, body, size, ver):
    """-> (vertices, triangles [(a, b, c, mat)]) of a Geometry chunk"""
    st = list(chunks(data, body, body + size))[0]
    p = st[3]
    flags, ntex, native, ntri, nvert, nmorph = struct.unpack_from("<HBBIII", data, p)
    p += 16
    if rw_version(ver) < 0x34000:
        p += 12
    if native:
        return [], []
    if flags & 0x08:
        p += 4 * nvert
    nsets = ntex or (2 if flags & 0x80 else 1 if flags & 0x04 else 0)
    p += nsets * nvert * 8
    tris = []
    for i in range(ntri):
        v2, v1, mat, v3 = struct.unpack_from("<4H", data, p + 8 * i)
        tris.append((v1, v2, v3, mat))
    p += 8 * ntri
    p += 16
    has_v, has_n = struct.unpack_from("<II", data, p)
    p += 8
    verts = [struct.unpack_from("<3f", data, p + 12 * i) for i in range(nvert)] if has_v else []
    return verts, tris


def frames(data, body, size):
    st = list(chunks(data, body, body + size))[0]
    p = st[3]
    n = struct.unpack_from("<I", data, p)[0]
    p += 4
    out = []
    for i in range(n):
        rot = struct.unpack_from("<9f", data, p)
        pos = struct.unpack_from("<3f", data, p + 36)
        parent = struct.unpack_from("<i", data, p + 48)[0]
        out.append((rot, pos, parent))
        p += 56
    return out


def apply(fr, i, v):
    while i >= 0:
        rot, pos, parent = fr[i]
        x, y, z = v
        # RW matrix rows: right, up, at; world = x*right + y*up + z*at + pos
        v = (x * rot[0] + y * rot[3] + z * rot[6] + pos[0],
             x * rot[1] + y * rot[4] + z * rot[7] + pos[1],
             x * rot[2] + y * rot[5] + z * rot[8] + pos[2])
        i = parent
    return v


def dff_triangles(data):
    """-> list of (name, [(p1, p2, p3, mat)]) in world coordinates"""
    out = []
    for t, s, v, body in chunks(data, 0, len(data)):
        if t != 0x10:
            continue
        fr, geos, atoms = [], [], []
        for t2, s2, v2, b2 in chunks(data, body, body + s):
            if t2 == 0x0E:
                fr = frames(data, b2, s2)
            elif t2 == 0x1A:
                for t3, s3, v3, b3 in chunks(data, b2, b2 + s2):
                    if t3 == 0x0F:
                        geos.append(geometry(data, b3, s3, v3))
            elif t2 == 0x14:
                st = list(chunks(data, b2, b2 + s2))[0]
                fi, gi = struct.unpack_from("<II", data, st[3])
                atoms.append((fi, gi))
        if not atoms:
            atoms = [(-1, i) for i in range(len(geos))]
        for fi, gi in atoms:
            verts, tris = geos[gi]
            w = [apply(fr, fi, p) if fi >= 0 else p for p in verts]
            out.append(("geometry %d frame %d" % (gi, fi), [(w[a], w[b], w[c], m) for a, b, c, m in tris]))
    return out


def bsp_triangles(data):
    out = []
    t, s, v, body = next(chunks(data, 0, len(data)))
    assert t == 0x0B, "not a world"
    st = list(chunks(data, body, body + s))[0]
    flags = struct.unpack_from("<I", data, st[3] + 0x24)[0]   # rootIsSector, origin 3f, tris, verts, planes, atomics, colsize, flags
    ver = rw_version(v)

    def walk(off, end):
        for t2, s2, v2, b2 in chunks(data, off, end):
            if t2 == 0x0A:
                walk(b2, b2 + s2)
            elif t2 == 0x09:
                sub = list(chunks(data, b2, b2 + s2))
                p = sub[0][3]
                base, ntri, nvert = struct.unpack_from("<III", data, p)
                p += 12 + 24 + 8
                verts = [struct.unpack_from("<3f", data, p + 12 * i) for i in range(nvert)]
                p += 12 * nvert
                if flags & 0x10:
                    p += 4 * nvert
                if flags & 0x08:
                    p += 4 * nvert
                nsets = (flags >> 16 & 0xFF) or (2 if flags & 0x80 else 1 if flags & 0x04 else 0)
                p += 8 * nvert * nsets
                tris = []
                for i in range(ntri):
                    a, b, c, m = struct.unpack_from("<4H", data, p + 8 * i)   # MHK2's 3.6 files: material last
                    tris.append((verts[a], verts[b], verts[c], m + base))
                out.append(("sector at %X" % (b2 - 12), tris))
    walk(body, body + s)
    return out, flags


def load(path):
    data = open(path, "rb").read()
    if path.lower().endswith(".bsp"):
        return bsp_triangles(data)[0]
    return dff_triangles(data)


def normal(p1, p2, p3):
    u = [p2[i] - p1[i] for i in range(3)]
    w = [p3[i] - p1[i] for i in range(3)]
    n = (u[1] * w[2] - u[2] * w[1], u[2] * w[0] - u[0] * w[2], u[0] * w[1] - u[1] * w[0])
    ln = math.sqrt(sum(c * c for c in n)) or 1
    return tuple(c / ln for c in n)


def main():
    cmd, path = sys.argv[1], sys.argv[2]
    if cmd == "tree":
        tree(open(path, "rb").read(), maxd=int(sys.argv[3]) if len(sys.argv) > 3 else 6)
    elif cmd == "tris":
        for name, tris in load(path):
            print(name, len(tris))
    elif cmd == "near":
        x, y, z = map(float, sys.argv[3:6])
        r = float(sys.argv[6]) if len(sys.argv) > 6 else 3.0
        for name, tris in load(path):
            for t in tris:
                if any(math.dist(p, (x, y, z)) < r for p in t[:3]):
                    n = normal(*t[:3])
                    print("%s mat %d  n(%5.2f %5.2f %5.2f)  " % (name, t[3], *n)
                          + "  ".join("(%.3f %.3f %.3f)" % p for p in t[:3]))


if __name__ == "__main__":
    main()
