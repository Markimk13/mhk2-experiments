import os, sys
sys.path.insert(0, sys.argv[1])
from mhk2crypt import decrypt, encrypt
root = sys.argv[2]
for dp, dn, fn in os.walk(root):
    for f in fn:
        if f.lower().endswith('.txt') and not f.endswith('.dec.txt'):
            p = os.path.join(dp, f)
            raw = open(p, 'rb').read()
            dec = decrypt(raw)
            assert encrypt(dec) == raw
            open(p[:-4] + '.dec.txt', 'wb').write(dec)
            print(len(raw), os.path.relpath(p, root))
