"""Dump ASCII strings of a PE file with their virtual addresses.

usage: pestrings.py <exe> [minlen]
"""
import re
import struct
import sys


def sections(data):
    pe = struct.unpack_from("<I", data, 0x3C)[0]
    nsec = struct.unpack_from("<H", data, pe + 6)[0]
    optsz = struct.unpack_from("<H", data, pe + 20)[0]
    imagebase = struct.unpack_from("<I", data, pe + 24 + 28)[0]
    secs = []
    o = pe + 24 + optsz
    for i in range(nsec):
        name = data[o:o + 8].rstrip(b"\0").decode("latin-1")
        vsize, va, rsize, roff = struct.unpack_from("<IIII", data, o + 8)
        chars = struct.unpack_from("<I", data, o + 36)[0]
        secs.append((name, va, vsize, roff, rsize, chars))
        o += 40
    return imagebase, secs


def off2va(imagebase, secs, off):
    for name, va, vsize, roff, rsize, chars in secs:
        if roff <= off < roff + rsize:
            return imagebase + va + (off - roff)
    return None


if __name__ == "__main__":
    data = open(sys.argv[1], "rb").read()
    minlen = int(sys.argv[2]) if len(sys.argv) > 2 else 4
    imagebase, secs = sections(data)
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    print(f"# imagebase={imagebase:#x}")
    for s in secs:
        print("# section %-8s va=%#x vsize=%#x roff=%#x rsize=%#x chars=%#x" % s)
    for m in re.finditer(rb"[\x20-\x7e\x80-\xff]{%d,}" % minlen, data):
        va = off2va(imagebase, secs, m.start())
        txt = m.group().decode("latin-1")
        print(f"{va if va is None else format(va, '08x')} {m.start():08x} {txt}")
