import sys, os, struct
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import harness as H
h = H.open_proc(0x0410)
gp = H.u32(h, 0x5E84EC)
used = []
for slot in range(192):
    e = H.read(h, gp + 0xAA04 + slot * 0x6C, 0x6C)
    trk, cls, ch = struct.unpack_from("<3i", e, 0x4C)
    tot = struct.unpack_from("<f", e, 0x58)[0]
    if tot < 639:
        used.append((slot, trk, cls, round(tot, 2)))
print("phantom slots in use:", len(used))
print("  slots >= 128:", [u for u in used if u[0] >= 128])
tail = H.read(h, gp + 0xFB04, 0x6C + 16)
print("  entry behind the table (0xFB04): track/class", struct.unpack_from("<2i", tail, 0x4C), "numTracks", struct.unpack_from("<i", tail, 0x6C)[0])
