"""Moorhuhn Kart 2 .txt cipher (as implemented at 0x00450360 in MHK2-XXL.exe).

Every *.txt entry inside the mhk2-XX.dat archives is stored encrypted:
    key = 0x1234
    plain[i] = swap_adjacent_bits(cipher[i] ^ (key & 0xFF)); key = (key * 3 + 2) & 0xFFFF
The transform is an involution apart from the order of the two steps.

usage: mhk2crypt.py dec|enc <infile> <outfile>
"""
import sys


def _swap(b):
    return ((b >> 1) & 0x55) | ((b << 1) & 0xAA)


def decrypt(data: bytes) -> bytes:
    key = 0x1234
    out = bytearray(len(data))
    for i, c in enumerate(data):
        out[i] = _swap(c ^ (key & 0xFF))
        key = (key * 3 + 2) & 0xFFFF
    return bytes(out)


def encrypt(data: bytes) -> bytes:
    key = 0x1234
    out = bytearray(len(data))
    for i, p in enumerate(data):
        out[i] = _swap(p) ^ (key & 0xFF)
        key = (key * 3 + 2) & 0xFFFF
    return bytes(out)


if __name__ == "__main__":
    mode, src, dst = sys.argv[1:4]
    data = open(src, "rb").read()
    res = decrypt(data) if mode == "dec" else encrypt(data)
    open(dst, "wb").write(res)
