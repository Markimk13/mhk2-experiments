import re, sys, bisect
LINE = re.compile(r"^  ([0-9A-F]{8}): ((?:[0-9A-F]{2} )+)\s*(.*)$")
addrs, texts = [], []
for line in open(sys.argv[1], encoding="latin-1"):
    m = LINE.match(line.rstrip("\n"))
    if m:
        addrs.append(int(m.group(1), 16)); texts.append(m.group(3).strip())
sites = [0x004099A4,0x00412A9E,0x00412B0B,0x0041C788,0x0041C816,0x0041C976,0x00420817,0x00423B2F,0x00423BCE,0x00423D2C,0x00412D0F,0x00412D9B,0x00420DDA,0x0043A504,0x0043A5BB,0x0042FC14,0x0043771E,0x0041304E,0x0041306B,0x0041B3F4,0x0041E1EF,0x00414571,0x0041ED48,0x0041ED8E,0x0041EEB5,0x0041EF70,0x0041F0A4,0x0041F0DA,0x0041F1D8,0x0041F293]
for s in sites:
    i = bisect.bisect_left(addrs, s)
    ok = addrs[i] == s
    print(f"--- {s:08X} {'' if ok else '(NOT AN INSTRUCTION START!)'}")
    for j in range(i-2, i+5):
        print(f"   {'>' if addrs[j]==s else ' '} {addrs[j]:08X}: {texts[j]}")
