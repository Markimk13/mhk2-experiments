import sys
sys.path.insert(0, sys.argv[1])
from dis import Image, EXE
img = Image(EXE)
vt = int(sys.argv[2], 16)
n = int(sys.argv[3]) if len(sys.argv) > 3 else 16
for i in range(n):
    v = img.u32(vt + 4 * i)
    print(f"  [{4*i:#04x}] {v:08X}  ({img.sec(v)})")
