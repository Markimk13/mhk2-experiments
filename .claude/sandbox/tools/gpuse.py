"""Find accesses to fields of the GameParameters singleton.

Tracks the result of `call 00403790` (GameParameters::Instance) through simple
register copies and reports every memory operand based on a tracked register.

usage: gpuse.py hist                 histogram of accessed offsets
       gpuse.py <hexoff> [...]       list sites that touch the given offset(s)
       gpuse.py range <lo> <hi>      list sites touching offsets in [lo, hi)
"""
import os
import re
import sys
from collections import Counter, defaultdict

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import dis as D

GETTER = "call        00403790"
REGS = ["eax", "ecx", "edx", "ebx", "esi", "edi", "ebp"]
MEM = re.compile(r"\[([a-z]{3})(?:\+([a-z]{3})(?:\*([248]))?)?(?:([+-])([0-9A-F]+)h?)?\]")
MOVRR = re.compile(r"^mov\s+([a-z]{3}),([a-z]{3})$")
LEA = re.compile(r"^lea\s+([a-z]{3}),\[([a-z]{3})([+-])([0-9A-F]+)h?\]$")
WRITES = re.compile(r"^(mov|lea|xor|sub|add|and|or|pop|movzx|movsx|imul|inc|dec|neg|not|shl|shr|sar|sbb|adc|xchg|setl|fnstsw)\s+([a-z]{2,3})\b")
SUBREG = {"al": "eax", "ah": "eax", "ax": "eax", "cl": "ecx", "ch": "ecx", "cx": "ecx",
          "dl": "edx", "dh": "edx", "dx": "edx", "bl": "ebx", "bh": "ebx", "bx": "ebx",
          "si": "esi", "di": "edi", "bp": "ebp"}


def scan():
    addrs, texts, raws, starts = D.load()
    startset = set(starts)
    hits = []  # (addr, off, text, fn)
    track = {}  # reg -> base offset delta
    fn = 0
    for i, (a, t) in enumerate(zip(addrs, texts)):
        if a in startset:
            track = {}
            fn = a
        if t == GETTER:
            track = {k: v for k, v in track.items() if k not in ("eax", "ecx", "edx")}
            track["eax"] = 0
            continue
        if track:
            for m in MEM.finditer(t):
                base, idx, scale, sign, disp = m.groups()
                if base in track:
                    d = int(disp, 16) if disp else 0
                    if sign == "-":
                        d = -d
                    hits.append((a, track[base] + d, t, fn, idx, scale))
        # propagate
        m = MOVRR.match(t)
        if m and m.group(2) in track:
            track[m.group(1)] = track[m.group(2)]
            continue
        m = LEA.match(t)
        if m and m.group(2) in track:
            d = int(m.group(4), 16)
            if m.group(3) == "-":
                d = -d
            track[m.group(1)] = track[m.group(2)] + d
            continue
        if t.startswith("call"):
            for r in ("eax", "ecx", "edx"):
                track.pop(r, None)
            continue
        m = WRITES.match(t)
        if m:
            r = SUBREG.get(m.group(2), m.group(2))
            if m.group(1) in ("add", "sub") and r in track:
                mm = re.match(r"^(add|sub)\s+[a-z]{3},([0-9A-F]+)h?$", t)
                if mm:
                    d = int(mm.group(2), 16)
                    track[r] += d if mm.group(1) == "add" else -d
                    continue
            track.pop(r, None)
        if t.startswith("ret") or t.startswith("jmp"):
            # linear flow ends; keep callee-saved copies (they usually stay valid in the function)
            for r in ("eax", "ecx", "edx"):
                track.pop(r, None)
    return hits


def main():
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    hits = scan()
    if sys.argv[1] == "hist":
        c = Counter(h[1] for h in hits)
        for off in sorted(c):
            print(f"  +{off:#06x}: {c[off]}")
        return
    if sys.argv[1] == "range":
        lo, hi = int(sys.argv[2], 16), int(sys.argv[3], 16)
        sel = [h for h in hits if lo <= h[1] < hi]
    else:
        offs = {int(x, 16) for x in sys.argv[1:]}
        sel = [h for h in hits if h[1] in offs]
    for a, off, t, fn, idx, scale in sel:
        print(f"  {a:08X} (fn {fn:08X}) +{off:#x}: {t}")
    print(f"{len(sel)} sites")


if __name__ == "__main__":
    main()
