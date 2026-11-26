"""Print texts as the running sandbox game resolves them (text.csv merged with text-NN.csv).

usage: text_test.py [id ...]        (default: the ids the patch adds or moves)

Asks the game's own TextManager::GetText through the test build's command slot.
"""
import os
import struct
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import harness as H
import remote_test as R

GET_TEXT = 0x00490C70       # std::string* TextManager::GetText(std::string* out, int id, int line)
SCRATCH = 0x00884FA0        # 1Ch unused, zero-initialised, writable bytes for the result string


def text(r, tid):
    tm = H.u32(r.h, 0x5E8518)          # TextManager instance
    r.write(SCRATCH, b"\0" * 0x1C)
    r.call(GET_TEXT, ecx=tm, args=(SCRATCH, tid, 0))
    raw = H.read(r.h, SCRATCH, 0x1C)
    size, cap = struct.unpack_from("<II", raw, 0x14)
    ptr = struct.unpack_from("<I", raw, 4)[0] if cap >= 16 else SCRATCH + 4
    return H.read(r.h, ptr, size).decode("cp1252")


def main():
    ids = [int(a) for a in sys.argv[1:]] or [221, 222, 223, 323, 332, 333, 334, 335, 336, 337, 338, 339, 583, 584, 585, 586, 587, 588]
    r = R.Remote()
    for tid in ids:
        print("  text %d: %r" % (tid, text(r, tid)))


if __name__ == "__main__":
    main()
