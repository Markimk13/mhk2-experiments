"""Write a Moorhuhn Kart 2 .dat archive (the format datlist.py reads).

usage: datpack.py <out.dat> <name>=<file> [<name>=<file> ...]
  name: the path inside the archive, e.g. data\\mk2\\level01\\settings\\objects\\objects.txt
  file: the local file, stored as it is (encrypt .txt entries first: mhk2crypt.py enc)

The game mounts data\\mhk2-00..99.dat, newest first, so an entry in mhk2-02.dat replaces the
same name in mhk2-00.dat / mhk2-01.dat. Only for sandbox game folders.
"""
import struct
import sys

MAGIC = b"Moorhuhn Kart 2"
ALIGN = 0x100


def pack(out, entries):
    """entries: list of (name, bytes)."""
    head_size = 0x40 + 0x80 * len(entries)
    pos = (head_size + ALIGN - 1) // ALIGN * ALIGN
    index = b""
    blobs = []
    for name, data in entries:
        raw = name.encode("latin-1")
        if len(raw) >= 0x68:
            raise SystemExit(f"name too long: {name}")
        index += raw.ljust(0x68, b"\0") + struct.pack("<II", pos, len(data)) + b"\0" * 0x10
        blobs.append((pos, data))
        pos = (pos + len(data) + ALIGN - 1) // ALIGN * ALIGN
    head = MAGIC.ljust(0x20, b"\0") + struct.pack("<II", len(entries), ALIGN) + b"\0" * 0x18
    with open(out, "wb") as f:
        f.write(head + index)
        for off, data in blobs:
            f.write(b"\0" * (off - f.tell()))
            f.write(data)
        f.write(b"\0" * (pos - f.tell()))


def main():
    out = sys.argv[1]
    entries = []
    for arg in sys.argv[2:]:
        name, path = arg.split("=", 1)
        entries.append((name, open(path, "rb").read()))
    pack(out, entries)
    print(f"{out}: {len(entries)} entries")


if __name__ == "__main__":
    main()
