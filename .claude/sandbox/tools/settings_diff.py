import sys, struct
a = open(sys.argv[1], "rb").read(); b = open(sys.argv[2], "rb").read()
assert len(a) == len(b) == 0xFD0C
# file offset -> object offset (+4); report differing regions by table
regions = {}
for i in range(len(a)):
    if a[i] != b[i]:
        o = i + 4
        if o < 0x234: key = f"header field +{o & ~3:#x}"
        elif o < 0x8934: key = f"highscore slot {(o - 0x234) // 0xB4}"
        elif o < 0xAA04: key = f"championship slot {(o - 0x8934) // 0x8C}"
        elif o < 0xFB04: key = f"phantom slot {(o - 0xAA04) // 0x6C}"
        else: key = f"tail +{o & ~3:#x}"
        regions[key] = regions.get(key, 0) + 1
for k, v in regions.items():
    print(f"  changed: {k} ({v} bytes)")
