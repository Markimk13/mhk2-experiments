"""Call functions of the running sandbox game, without putting any code into its process.

The unattended test builds (prep_fps.py, command_slot) look at a small slot once per frame, on
the game's own thread: function address, ecx, number of stack arguments, up to six arguments.
`Remote.call` fills that slot with plain memory writes and waits until the game has cleared it.
A build without the slot (an older test build, the real game) never answers; the call then
stops with a message.
"""
import ctypes
import os
import struct
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import harness as H

k32 = H.kernel32
CALL_VA = 0x00884F60        # function, ecx, nargs, six arguments, result
START_RACE = 0x004122E0     # the menu's own "start the race" (this = menu object)


class Remote:
    def __init__(self):
        self.h = H.open_proc()
        self.gp = H.u32(self.h, 0x5E84EC)

    def write(self, addr, data):
        n = ctypes.c_size_t()
        assert k32.WriteProcessMemory(self.h, ctypes.c_void_p(addr), data, len(data), ctypes.byref(n))

    def gp_i32(self, off, v):
        self.write(self.gp + off, struct.pack("<i", v))

    def gp_f32(self, off, v):
        self.write(self.gp + off, struct.pack("<f", v))

    def call(self, func, ecx=0, args=(), timeout=15.0):
        """Have the game call func(args...) with this = ecx on its own thread; returns eax."""
        assert len(args) <= 6
        packed = b"".join(struct.pack("<f", a) if isinstance(a, float) else struct.pack("<I", a & 0xFFFFFFFF) for a in args)
        self.write(CALL_VA + 4, struct.pack("<II", ecx & 0xFFFFFFFF, len(args)) + packed)
        self.write(CALL_VA, struct.pack("<I", func))          # the address last: it is the "go"
        t0 = time.time()
        while H.u32(self.h, CALL_VA):
            if time.time() - t0 > timeout:
                self.write(CALL_VA, struct.pack("<I", 0))
                raise SystemExit("the game did not pick up the call to %08X (no command slot in this build, "
                                 "or its frame loop stands still)" % func)
            time.sleep(0.003)
        return H.u32(self.h, CALL_VA + 0x24)

    def menu(self):
        return H.u32(self.h, H.u32(self.h, 0x5E851C) + 4)

    def start_race(self):
        """Start the race that the GameParameters describe (mode, class, track), like the menu does."""
        return self.call(START_RACE, ecx=self.menu())


def slot_hs(r, slot):
    e = H.read(r.h, r.gp + 0x234 + slot * 0xB4, 0xB4)
    t = [round(x, 2) for x in struct.unpack_from("<5f", e, 0)]
    nm = [e[0x50 + 16 * i:0x60 + 16 * i].split(b"\0")[0].decode("latin-1") for i in range(5)]
    laps = [round(x, 2) for x in struct.unpack_from("<3f", e, 0x14)]
    ch = struct.unpack_from("<5i", e, 0xA0)
    return t, nm, laps, ch


def slot_ch(r, slot):
    e = H.read(r.h, r.gp + 0x8934 + slot * 0x8C, 0x8C)
    t = [round(x, 2) for x in struct.unpack_from("<5f", e, 0)]
    p = struct.unpack_from("<5i", e, 0x14)
    nm = [e[0x28 + 16 * i:0x38 + 16 * i].split(b"\0")[0].decode("latin-1") for i in range(5)]
    return t, p, nm
