import sys, pickle, bisect
sys.path.insert(0, sys.argv[1])
import dis as D
addrs, texts, raws, starts = D.load()
lo, hi = int(sys.argv[2], 16), int(sys.argv[3], 16)
i = bisect.bisect_left(starts, lo)
out = []
while i < len(starts) and starts[i] < hi:
    s = starts[i]
    e = starts[i+1] if i+1 < len(starts) else s
    out.append(f"{s:08X} size={e-s:#x}")
    i += 1
print("\n".join(out))
