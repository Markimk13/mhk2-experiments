"""Navigation helper over a dumpbin /disasm listing of MHK2-XXL.exe.

usage:
  dis.py index                      build the pickle index
  dis.py xref <hexaddr> [...]       list instructions referencing the address(es)
  dis.py func <hexaddr> [maxlines]  print the function containing the address
  dis.py range <hexstart> <hexend>  print the instructions in [start, end)
  dis.py callers <hexaddr>          list call sites of a function (with their function start)
  dis.py str <regex>                find strings in the image and list xrefs to them
  dis.py grep <regex> [maxhits]     regex over instruction text
"""
import bisect
import os
import pickle
import re
import struct
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
WORK = os.path.join(os.path.dirname(HERE), "work")
EXE = os.environ.get("MHK2_EXE", os.path.join(WORK, "MHK2-XXL.orig.exe"))
DIS = os.path.join(WORK, "disasm.txt")
IDX = os.path.join(WORK, "disasm.pickle")

LINE = re.compile(r"^  ([0-9A-F]{8}): ((?:[0-9A-F]{2} )+)\s*(.*)$")
CONT = re.compile(r"^\s{12}((?:[0-9A-F]{2} ?)+)\s*$")
HEXIMM = re.compile(r"\b0*([0-9A-F]{5,8})h\b")


class Image:
    def __init__(self, path):
        self.data = open(path, "rb").read()
        d = self.data
        pe = struct.unpack_from("<I", d, 0x3C)[0]
        nsec = struct.unpack_from("<H", d, pe + 6)[0]
        optsz = struct.unpack_from("<H", d, pe + 20)[0]
        self.base = struct.unpack_from("<I", d, pe + 24 + 28)[0]
        self.secs = []
        o = pe + 24 + optsz
        for i in range(nsec):
            name = d[o:o + 8].rstrip(b"\0").decode("latin-1")
            vsize, va, rsize, roff = struct.unpack_from("<IIII", d, o + 8)
            self.secs.append((name, self.base + va, vsize, roff, rsize))
            o += 40

    def off(self, va):
        for name, sva, vsize, roff, rsize in self.secs:
            if sva <= va < sva + max(vsize, rsize):
                if va - sva < rsize:
                    return roff + (va - sva)
                return None
        return None

    def sec(self, va):
        for name, sva, vsize, roff, rsize in self.secs:
            if sva <= va < sva + max(vsize, rsize):
                return name
        return None

    def read(self, va, n):
        o = self.off(va)
        if o is None:
            return None
        return self.data[o:o + n]

    def u32(self, va):
        b = self.read(va, 4)
        return None if b is None or len(b) < 4 else struct.unpack("<I", b)[0]

    def f32(self, va):
        b = self.read(va, 4)
        return None if b is None or len(b) < 4 else struct.unpack("<f", b)[0]

    def f64(self, va):
        b = self.read(va, 8)
        return None if b is None or len(b) < 8 else struct.unpack("<d", b)[0]

    def cstr(self, va, maxlen=120):
        o = self.off(va)
        if o is None:
            return None
        end = self.data.find(b"\0", o, o + maxlen + 1)
        if end < 0:
            end = o + maxlen
        raw = self.data[o:end]
        if len(raw) < 3:
            return None
        if all(32 <= c < 127 or c in (9, 10, 13) or c >= 0xA0 for c in raw):
            return raw.decode("latin-1")
        return None


def build_index():
    addrs, texts, raws = [], [], []
    with open(DIS, "r", encoding="latin-1") as f:
        for line in f:
            m = LINE.match(line.rstrip("\n"))
            if m:
                addrs.append(int(m.group(1), 16))
                raws.append(m.group(2).strip())
                texts.append(m.group(3).strip())
            else:
                c = CONT.match(line.rstrip("\n"))
                if c and raws:
                    raws[-1] += " " + c.group(1).strip()
    # function starts: call targets + first instruction after int3 padding
    starts = set()
    callre = re.compile(r"^call\s+([0-9A-F]{8})$")
    prev_int3 = True
    for a, t in zip(addrs, texts):
        m = callre.match(t)
        if m:
            starts.add(int(m.group(1), 16))
        if t == "int         3":
            prev_int3 = True
        else:
            if prev_int3:
                starts.add(a)
            prev_int3 = False
    starts = sorted(s for s in starts)
    with open(IDX, "wb") as f:
        pickle.dump((addrs, texts, raws, starts), f, protocol=pickle.HIGHEST_PROTOCOL)
    print(f"indexed {len(addrs)} instructions, {len(starts)} function starts")


_cache = None


def load():
    global _cache
    if _cache is None:
        with open(IDX, "rb") as f:
            _cache = pickle.load(f)
    return _cache


def annotate(img, text):
    notes = []
    for m in HEXIMM.finditer(text):
        v = int(m.group(1), 16)
        sec = img.sec(v)
        if sec in (".rdata", ".data"):
            s = img.cstr(v)
            if s is not None:
                notes.append('"' + s.replace("\r", "\\r").replace("\n", "\\n") + '"')
            else:
                if re.search(r"(dword ptr|qword ptr|real4|real8)", text):
                    if "qword" in text:
                        d = img.f64(v)
                        if d is not None:
                            notes.append(f"f64={d:.9g}")
                    else:
                        fl = img.f32(v)
                        u = img.u32(v)
                        if fl is not None and u is not None:
                            notes.append(f"u32={u:#x} f32={fl:.9g}")
    return ("   ; " + " | ".join(notes)) if notes else ""


def func_bounds(addr):
    addrs, texts, raws, starts = load()
    i = bisect.bisect_right(starts, addr) - 1
    start = starts[max(i, 0)]
    end = starts[i + 1] if i + 1 < len(starts) else addrs[-1] + 1
    return start, end


def print_range(img, lo, hi, maxlines=100000, mark=None):
    addrs, texts, raws, starts = load()
    i = bisect.bisect_left(addrs, lo)
    n = 0
    sset = None
    while i < len(addrs) and addrs[i] < hi and n < maxlines:
        t = texts[i]
        if t == "int         3":
            i += 1
            continue
        flag = ">>" if mark is not None and addrs[i] == mark else "  "
        print(f"{flag}{addrs[i]:08X}: {t}{annotate(img, t)}")
        n += 1
        i += 1
    if i < len(addrs) and addrs[i] < hi:
        print(f"  ... truncated at {addrs[i]:08X}")


def cmd_xref(img, targets):
    addrs, texts, raws, starts = load()
    for tgt in targets:
        v = int(tgt, 16)
        pat = re.compile(r"\b0*%Xh?\b" % v)
        print(f"== xrefs to {v:08X} ({img.sec(v)}) {img.cstr(v)!r}")
        for a, t in zip(addrs, texts):
            if pat.search(t):
                fs, fe = func_bounds(a)
                print(f"  {a:08X} (fn {fs:08X}): {t}")


def cmd_str(img, regex):
    pat = re.compile(regex.encode("latin-1"), re.I)
    hits = []
    for name, sva, vsize, roff, rsize in img.secs:
        if name not in (".rdata", ".data"):
            continue
        blob = img.data[roff:roff + rsize]
        for m in re.finditer(rb"[\x20-\x7e\x80-\xff]{3,}", blob):
            if pat.search(m.group()):
                hits.append((sva + m.start(), m.group().decode("latin-1")))
    addrs, texts, raws, starts = load()
    for va, s in hits:
        print(f"== {va:08X} {s!r}")
        pat2 = re.compile(r"\b0*%Xh\b" % va)
        for a, t in zip(addrs, texts):
            if pat2.search(t):
                fs, fe = func_bounds(a)
                print(f"     {a:08X} (fn {fs:08X}): {t}")


def main():
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    cmd = sys.argv[1]
    if cmd == "index":
        build_index()
        return
    img = Image(EXE)
    if cmd == "xref":
        cmd_xref(img, sys.argv[2:])
    elif cmd == "func":
        a = int(sys.argv[2], 16)
        maxlines = int(sys.argv[3]) if len(sys.argv) > 3 else 400
        lo, hi = func_bounds(a)
        print(f"== function {lo:08X}..{hi:08X}")
        print_range(img, lo, hi, maxlines, mark=a)
    elif cmd == "range":
        print_range(img, int(sys.argv[2], 16), int(sys.argv[3], 16))
    elif cmd == "raw":
        # raw <before> <after> <addr> [addr...]  -> like ctx but with instruction bytes
        addrs, texts, raws, starts = load()
        nb, na = int(sys.argv[2]), int(sys.argv[3])
        for s in sys.argv[4:]:
            a = int(s, 16)
            i = bisect.bisect_left(addrs, a)
            print(f"== raw {a:08X}")
            for j in range(max(i - nb, 0), min(i + na + 1, len(addrs))):
                flag = ">>" if addrs[j] == a else "  "
                print(f"{flag}{addrs[j]:08X}: {raws[j]:<24} {texts[j]}{annotate(img, texts[j])}")
    elif cmd == "ctx":
        # ctx <before> <after> <addr> [addr...]
        addrs, texts, raws, starts = load()
        nb, na = int(sys.argv[2]), int(sys.argv[3])
        for s in sys.argv[4:]:
            a = int(s, 16)
            i = bisect.bisect_left(addrs, a)
            lo = addrs[max(i - nb, 0)]
            hi = addrs[min(i + na, len(addrs) - 1)] + 1
            fs, fe = func_bounds(a)
            print(f"== ctx {a:08X} (fn {fs:08X})")
            print_range(img, lo, hi, mark=a)
    elif cmd == "callers":
        addrs, texts, raws, starts = load()
        v = int(sys.argv[2], 16)
        pat = re.compile(r"^(call|jmp)\s+%08X$" % v)
        for a, t in zip(addrs, texts):
            if pat.match(t):
                fs, fe = func_bounds(a)
                print(f"  {a:08X} (fn {fs:08X}): {t}")
    elif cmd == "str":
        cmd_str(img, sys.argv[2])
    elif cmd == "grep":
        addrs, texts, raws, starts = load()
        pat = re.compile(sys.argv[2], re.I)
        maxhits = int(sys.argv[3]) if len(sys.argv) > 3 else 200
        n = 0
        for a, t in zip(addrs, texts):
            if pat.search(t):
                fs, fe = func_bounds(a)
                print(f"  {a:08X} (fn {fs:08X}): {t}{annotate(img, t)}")
                n += 1
                if n >= maxhits:
                    print("  ... more")
                    break


if __name__ == "__main__":
    main()
