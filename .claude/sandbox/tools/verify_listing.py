"""Compare the patcher's intended listing against dumpbin's disassembly of the patched exe.

usage: verify_listing.py <payload.lst> <dumpbin disasm of .mod200>
"""
import re
import sys

LINE = re.compile(r"^  ([0-9A-F]{8}): ((?:[0-9A-F]{2} )+)\s*(.*)$")


def norm(t):
    return re.sub(r"\s+", " ", t.strip())


def main():
    want = {}
    data_ranges = []
    order = []
    for line in open(sys.argv[1], encoding="utf-8"):
        line = line.rstrip("\n")
        if not line.strip():
            break
        va, text = line.split(": ", 1)
        va = int(va, 16)
        order.append(va)
        if text.startswith(";"):
            data_ranges.append(va)
        else:
            want[va] = norm(text)
    got = {}
    for line in open(sys.argv[2], encoding="latin-1"):
        m = LINE.match(line.rstrip("\n"))
        if m:
            got[int(m.group(1), 16)] = norm(m.group(3))
    bad = 0
    for va in order:
        if va in want:
            g = got.get(va)
            if g != want[va]:
                bad += 1
                print(f"MISMATCH {va:08X}: want '{want[va]}' got '{g}'")
    print(f"{len(want)} instructions checked, {bad} mismatches, data at {[hex(x) for x in data_ranges]}")


if __name__ == "__main__":
    main()
