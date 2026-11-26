"""Test builds only: skip the game's single-instance lock.

A second instance normally finds the lock (a named mutex made by 0x4A4950), raises the first
instance's window (ShowWindow/BringWindowToTop/SetForegroundWindow) and exits. With this
change a test build neither creates the mutex nor looks for other windows, so it can run next
to other test games without touching them, and the user's real game, which still takes the
lock, always starts as the first instance.

  0046F3AC  call 004A4950 (thiscall, ret 4)  ->  add esp,4 ; nop ; nop   (drop its argument)
  0046F3B3  jne 0046F481 (first instance)    ->  nop ; jmp 0046F481

The lock object stays as its constructor (0x4A4900) left it, handle 0; its destructor
(0x4A4920) only releases a handle that is not 0. prep_fps.build applies this to every test
build since 2026-11-22; gameslot.py tells the two kinds apart by the bytes at 0x46F3AC.

usage: pu_noinst.py <in exe> <out exe>
"""
import sys

BASE = 0x400000
SITES = (
    (0x0046F3AC, "E8 9F 55 03 00", "83 C4 04 90 90"),              # call InstanceLock -> drop its argument
    (0x0046F3B3, "0F 85 C8 00 00 00", "90 E9 C8 00 00 00"),        # jne first-instance path -> jmp
)


def apply(d):
    """Patch bytearray d in place; a build that already has the change is left as it is."""
    for va, old, new in SITES:
        o = va - BASE          # .text: file offset == rva for this image
        old, new = bytes.fromhex(old), bytes.fromhex(new)
        cur = bytes(d[o:o + len(old)])
        if cur == new:
            continue
        assert cur == old, (hex(va), cur.hex(" "))
        d[o:o + len(new)] = new


def main():
    src, dst = sys.argv[1], sys.argv[2]
    d = bytearray(open(src, "rb").read())
    apply(d)
    open(dst, "wb").write(d)
    print("built", dst)


if __name__ == "__main__":
    main()
