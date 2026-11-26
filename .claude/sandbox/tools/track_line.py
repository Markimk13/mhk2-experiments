r"""The centre line of a track from its road edges (objects\street_left/right*.spl), for speed profiles.

usage: track_line.py <track 0..7> [step]   -> prints length, width range, sharpest bends

Edges come from the archive (extracted once into work\spl by datextract.py); like TrackPath::Load
(fn 0x445290) the plain file is used if there, else the _rev file reversed with left and right
swapped. The control points are joined by Catmull-Rom pieces (the game's own spline type is not
traced), each left point is paired with the nearest right point and the midpoints are resampled
every `step` units. Curvature: signed, from the points +-h units away; height curvature the same
on (distance, y).
"""
import math
import os
import struct
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
SANDBOX = os.path.dirname(HERE)
SPL = os.path.join(SANDBOX, "work", "spl", "data", "mk2")


def load_spl(path):
    d = open(path, "rb").read()
    n = struct.unpack_from("<I", d, 44)[0]
    return [struct.unpack_from("<3f", d, 52 + 12 * i) for i in range(n)]


def edges(track):
    d = os.path.join(SPL, "level%02d" % (track + 1), "objects")
    if not os.path.isdir(d):
        subprocess.run([sys.executable, os.path.join(HERE, "datextract.py"), os.path.join(SANDBOX, "game", "data", "mhk2-00.dat"),
                        os.path.join(SANDBOX, "work", "spl"), r"street_(left|right).*\.spl$"], check=True, capture_output=True)
    if os.path.exists(os.path.join(d, "street_left.spl")):
        return load_spl(os.path.join(d, "street_left.spl")), load_spl(os.path.join(d, "street_right.spl"))
    left = load_spl(os.path.join(d, "street_left_rev.spl"))[::-1]
    right = load_spl(os.path.join(d, "street_right_rev.spl"))[::-1]
    return right, left


def catmull(pts, step):
    """closed Catmull-Rom through pts, about `step` units apart"""
    if math.dist(pts[0], pts[-1]) < 1e-3:
        pts = pts[:-1]
    n = len(pts)
    out = []
    for i in range(n):
        p0, p1, p2, p3 = pts[i - 1], pts[i], pts[(i + 1) % n], pts[(i + 2) % n]
        k = max(1, int(math.dist(p1, p2) / step))
        for j in range(k):
            t = j / k
            out.append(tuple(0.5 * (2 * p1[c] + (-p0[c] + p2[c]) * t + (2 * p0[c] - 5 * p1[c] + 4 * p2[c] - p3[c]) * t * t
                                    + (-p0[c] + 3 * p1[c] - 3 * p2[c] + p3[c]) * t ** 3) for c in range(3)))
    return out


def resample(pts, step):
    """closed polyline -> points every `step` units"""
    out = [pts[0]]
    need = step
    n = len(pts)
    for i in range(n):
        a, b = pts[i], pts[(i + 1) % n]
        seg = math.dist(a, b)
        pos = 0.0
        while seg - pos >= need:
            pos += need
            t = pos / seg
            out.append(tuple(a[c] + (b[c] - a[c]) * t for c in range(3)))
            need = step
        need -= seg - pos
    return out


class Line:
    def __init__(self, track, step=2.0, h=6.0):
        L, R = edges(track)
        L, R = catmull(L, 1.0), catmull(R, 1.0)
        mid, wid = [], []
        j = 0
        for p in L:                                     # nearest right point, searched near the last one
            best = min(range(len(R)), key=lambda k: (R[k][0] - p[0]) ** 2 + (R[k][2] - p[2]) ** 2) if not mid else \
                min(((j + d) % len(R) for d in range(-40, 41)), key=lambda k: (R[k][0] - p[0]) ** 2 + (R[k][2] - p[2]) ** 2)
            j = best
            q = R[best]
            mid.append(tuple((p[c] + q[c]) / 2 for c in range(3)))
            wid.append(math.hypot(p[0] - q[0], p[2] - q[2]))
        self.track, self.step = track, step
        self.pts = resample(mid, step)
        self.n = len(self.pts)
        self.length = self.n * step
        # width at each resampled point: nearest midpoint's
        self.width = []
        k = 0
        for p in self.pts:
            k = min(((k + d) % len(mid) for d in range(-5, 30)), key=lambda i: (mid[i][0] - p[0]) ** 2 + (mid[i][2] - p[2]) ** 2)
            self.width.append(wid[k])
        m = max(1, int(round(h / step)))
        self.kappa, self.kv = [], []
        for i in range(self.n):
            a, b, c = self.pts[i - m], self.pts[i], self.pts[(i + m) % self.n]
            ux, uz, wx, wz = b[0] - a[0], b[2] - a[2], c[0] - b[0], c[2] - b[2]
            la, lb, lc = math.hypot(ux, uz), math.hypot(wx, wz), math.hypot(c[0] - a[0], c[2] - a[2])
            self.kappa.append(2 * (ux * wz - uz * wx) / (la * lb * lc + 1e-9))
            s1, s2 = (b[1] - a[1]) / (la + 1e-9), (c[1] - b[1]) / (lb + 1e-9)
            self.kv.append((s2 - s1) / ((la + lb) / 2 + 1e-9))   # < 0: crest
        self._grid = {}
        for i, p in enumerate(self.pts):
            self._grid.setdefault((int(p[0] // 20), int(p[2] // 20)), []).append(i)

    def nearest(self, x, z):
        gx, gz = int(x // 20), int(z // 20)
        best, bd = None, 1e18
        for dx in (-1, 0, 1):
            for dz in (-1, 0, 1):
                for i in self._grid.get((gx + dx, gz + dz), ()):
                    p = self.pts[i]
                    d = (p[0] - x) ** 2 + (p[2] - z) ** 2
                    if d < bd:
                        best, bd = i, d
        if best is None:
            best = min(range(self.n), key=lambda i: (self.pts[i][0] - x) ** 2 + (self.pts[i][2] - z) ** 2)
            bd = (self.pts[best][0] - x) ** 2 + (self.pts[best][2] - z) ** 2
        return best, math.sqrt(bd)


def main():
    t = int(sys.argv[1])
    ln = Line(t, float(sys.argv[2]) if len(sys.argv) > 2 else 2.0)
    print("track %d: %d points, length %.0f, width %.0f..%.0f" % (t, ln.n, ln.length, min(ln.width), max(ln.width)))
    bends = sorted(range(ln.n), key=lambda i: -abs(ln.kappa[i]))
    shown = []
    for i in bends:
        if all(min(abs(i - j), ln.n - abs(i - j)) * ln.step > 30 for j in shown):
            shown.append(i)
            p = ln.pts[i]
            print("   at %5.0f (%.3f) (%6.0f, %6.0f): radius %5.1f, width %4.1f" % (i * ln.step, i / ln.n, p[0], p[2], 1 / abs(ln.kappa[i]), ln.width[i]))
        if len(shown) >= 8:
            break


if __name__ == "__main__":
    main()
