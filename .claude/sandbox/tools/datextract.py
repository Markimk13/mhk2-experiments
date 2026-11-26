"""Extract entries (raw, still encrypted where applicable) from an MHK2 .dat archive.

usage: datextract.py <archive> <outdir> [regex]
"""
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from datlist import read_index


def main():
    arc, outdir = sys.argv[1], sys.argv[2]
    pat = re.compile(sys.argv[3], re.I) if len(sys.argv) > 3 else None
    magic, count, align, entries = read_index(arc)
    n = 0
    with open(arc, "rb") as f:
        for name, off, size, rest in entries:
            if pat and not pat.search(name):
                continue
            f.seek(off)
            data = f.read(size)
            dst = os.path.join(outdir, name.replace("\\", os.sep))
            os.makedirs(os.path.dirname(dst), exist_ok=True)
            with open(dst, "wb") as o:
                o.write(data)
            n += 1
    print(f"extracted {n} of {count} files to {outdir}")


if __name__ == "__main__":
    main()
