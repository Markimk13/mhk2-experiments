import sys, struct
sys.path.insert(0, sys.argv[1])
from dis import Image, EXE
img = Image(EXE)
d = img.data
for target in [int(x, 16) for x in sys.argv[2:]]:
    pat = struct.pack("<I", target)
    pos = 0
    while True:
        i = d.find(pat, pos)
        if i < 0: break
        # file offset -> va
        for name, sva, vsize, roff, rsize in img.secs:
            if roff <= i < roff + rsize:
                print(f"{target:08X} referenced at {sva + i - roff:08X} ({name})")
        pos = i + 1
