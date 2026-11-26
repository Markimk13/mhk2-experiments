import re, sys
lines = open(sys.argv[1], encoding="latin-1").read().splitlines()
want = set(sys.argv[2:])
dll = None; iat = None; idx = 0
for i, l in enumerate(lines):
    m = re.match(r"^\s{4}(\S+\.(?:dll|DLL|ocx))\s*$", l)
    if m:
        dll = m.group(1); iat = None; idx = 0; continue
    m = re.match(r"^\s+([0-9A-F]+) Import Address Table", l)
    if m:
        iat = int(m.group(1), 16); idx = 0; continue
    m = re.match(r"^\s+([0-9A-F]+)\s+(\w+)\s*$", l)
    if m and iat is not None and dll:
        name = m.group(2)
        if name in want:
            print(f"{dll} {name} IAT={iat + 4*idx:08X}")
        idx += 1
