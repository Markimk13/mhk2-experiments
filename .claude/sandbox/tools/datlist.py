"""List the entries of a Moorhuhn Kart 2 .dat archive."""
import struct
import sys


def read_index(path):
    with open(path, "rb") as f:
        head = f.read(0x40)
        magic = head[:0x20].split(b"\0")[0].decode("latin-1")
        count, align = struct.unpack_from("<II", head, 0x20)
        entries = []
        for i in range(count):
            e = f.read(0x80)
            name = e[:0x68].split(b"\0")[0].decode("latin-1")
            off, size = struct.unpack_from("<II", e, 0x68)
            rest = e[0x70:]
            entries.append((name, off, size, rest))
    return magic, count, align, entries


if __name__ == "__main__":
    magic, count, align, entries = read_index(sys.argv[1])
    print(f"magic={magic!r} count={count} align={align:#x}")
    for name, off, size, rest in entries:
        extra = "" if not any(rest) else " extra=" + rest.hex()
        print(f"{off:#010x} {size:>10} {name}{extra}")
