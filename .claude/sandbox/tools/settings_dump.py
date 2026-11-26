"""Dump the interesting parts of a Moorhuhn Kart 2 settings.dat.

File = GameParameters object bytes [4, 0xFD10), so file offset = object offset - 4.
"""
import struct
import sys

HS_BASE, HS_SIZE = 0x234, 0xB4      # [3][64] time trial highscores
CH_BASE, CH_SIZE = 0x8934, 0x8C     # [3][20] championship highscores
PH_BASE, PH_SIZE = 0xAA04, 0x6C     # [3][64] phantom headers (+1 at 0xFB04)


def cstr(b):
    return b.split(b"\0")[0].decode("latin-1")


def main():
    data = open(sys.argv[1], "rb").read()
    obj = b"\0\0\0\0" + data  # so offsets match the in-memory object
    u32 = lambda o: struct.unpack_from("<I", obj, o)[0]
    i32 = lambda o: struct.unpack_from("<i", obj, o)[0]
    f32 = lambda o: struct.unpack_from("<f", obj, o)[0]
    print(f"size={len(data):#x} version={u32(4):#x}")
    print("head ints 0x08..0x58:", [i32(o) for o in range(0x08, 0x58, 4)])
    print("0x58..0xE4:", [i32(o) for o in range(0x58, 0xE4, 4)])
    for i in range(7):
        o = 0xE4 + i * 0x1C
        raw = obj[o:o + 0x1C]
        size, cap = struct.unpack_from("<II", raw, 0x14)
        print(f"  str[{i}] size={size} cap={cap} inline={cstr(raw[4:0x14])!r}")
    print("0x1A8..0x234:", [i32(o) for o in range(0x1A8, 0x234, 4)])
    print("tail 0xFB70:", "numTracks", i32(0xFB70), "numChamps", i32(0xFB74))
    print("  tracks:", [i32(0xFB78 + 4 * i) for i in range(16)])
    print("  champs:", [i32(0xFCB8 + 4 * i) for i in range(20)])
    print("  unlockedClass", i32(0xFD08), "unlockMask", bin(u32(0xFD0C)))
    # defaults
    def hs_default(e):
        times = struct.unpack_from("<5f", e, 0)
        return times == (360.0, 370.0, 380.0, 390.0, 400.0)
    print("== time trial highscores (non-default entries)")
    for c in range(3):
        for t in range(64):
            o = HS_BASE + (c * 64 + t) * HS_SIZE
            e = obj[o:o + HS_SIZE]
            if not hs_default(e):
                times = struct.unpack_from("<5f", e, 0)
                names = [cstr(e[0x50 + 16 * i:0x60 + 16 * i]) for i in range(5)]
                chars = struct.unpack_from("<5i", e, 0xA0)
                laps = [struct.unpack_from("<3f", e, 0x14 + 12 * i) for i in range(5)]
                print(f"  class {c} track {t}: times={[round(x, 2) for x in times]} names={names} chars={chars}")
                print(f"      laps0={[round(x, 2) for x in laps[0]]}")
    print("== championship highscores (non-default)")
    for c in range(3):
        for k in range(20):
            o = CH_BASE + (c * 20 + k) * CH_SIZE
            e = obj[o:o + CH_SIZE]
            times = struct.unpack_from("<5f", e, 0)
            pts = struct.unpack_from("<5i", e, 0x14)
            if times != (1440.0, 1480.0, 1520.0, 1560.0, 1600.0) or any(pts):
                names = [cstr(e[0x28 + 16 * i:0x38 + 16 * i]) for i in range(5)]
                print(f"  class {c} champ {k}: times={[round(x, 2) for x in times]} pts={pts} names={names}")
    print("== phantom headers (with track set)")
    for c in range(3):
        for t in range(64):
            o = PH_BASE + (c * 64 + t) * PH_SIZE
            e = obj[o:o + PH_SIZE]
            trk, cls, ch = struct.unpack_from("<3i", e, 0x4C)
            tot = struct.unpack_from("<4f", e, 0x58)
            ver = cstr(e[:0x20])
            if tot[0] < 639 or trk or cls:
                print(f"  slot class {c} track {t}: ver={ver!r} vt={u32(o+0x20)} dv={u32(o+0x24)} user={cstr(e[0x28:0x4C])!r} trk={trk} cls={cls} char={ch} times={[round(x, 2) for x in tot]} last={u32(o+0x68)}")
    o = 0xFB04
    e = obj[o:o + PH_SIZE]
    print("  extra phantom @FB04:", cstr(e[:0x20]), struct.unpack_from("<3i", e, 0x4C), struct.unpack_from("<4f", e, 0x58))


if __name__ == "__main__":
    main()
