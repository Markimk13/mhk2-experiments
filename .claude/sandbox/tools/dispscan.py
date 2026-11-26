import sys, re
sys.path.insert(0, sys.argv[1])
import dis as D
addrs, texts, raws, starts = D.load()
pat = re.compile(r"[+-]0*([0-9A-F]{3,8})h\]")
lo, hi = int(sys.argv[2], 16), int(sys.argv[3], 16)
n = 0
for a, t in zip(addrs, texts):
    for m in pat.finditer(t):
        v = int(m.group(1), 16)
        if lo <= v < hi:
            fs, fe = D.func_bounds(a)
            print(f"  {a:08X} (fn {fs:08X}) {v:#07x}: {t}")
            n += 1
print(n, "sites")
