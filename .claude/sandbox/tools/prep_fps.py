"""Build windowed test copies of the ORIGINAL exe with different timing behaviour.

usage: prep_fps.py <original exe> <gamedir> <settings source> [fps ...]

Creates in <gamedir>:
  win_stock.exe      stock timing (frame >= 5 ms, i.e. up to 200 FPS; physics step = frame time)
  win_capNN.exe      frame loop waits for >= 1/NN s (what an external NN FPS limiter does)
  win_physNN.exe     frames stay at up to 200 FPS, but the physics accumulates time and
                     only steps once >= 1/NN s have passed
plus a muted 640x480 settings.dat.
"""
import os
import struct
import sys

BASE = 0x400000
CONST_VA = 0x005938A0      # unused bytes behind the code (inside .text's raw data)


def patch(d, va, old_hex, new_bytes):
    o = va - BASE
    old = bytes.fromhex(old_hex)
    assert d[o:o + len(old)] == old, (hex(va), d[o:o + len(old)].hex())
    d[o:o + len(new_bytes)] = new_bytes


def windowed(d):
    patch(d, 0x0046F8B4, "C6 40 0C 01", bytes.fromhex("C6 40 0C 00"))   # framed window instead of fullscreen
    patch(d, 0x0046F94A, "6A 20", bytes.fromhex("6A 0B"))
    patch(d, 0x0046F94E, "6A 21", bytes.fromhex("6A 0C"))


def autonomous(d):
    """Test-only: let the game run unattended in the background (no keyboard focus needed)."""
    patch(d, 0x00403652, "74 76", bytes.fromhex("EB 76"))                    # never pause on focus loss
    patch(d, 0x00407081, "0F 8B 17 07 00 00", b"\x90" * 6)                   # skip the pre-race intro camera
    patch(d, 0x0046F91D, "6A 05", bytes.fromhex("6A 04"))                    # ShowWindow(SW_SHOWNOACTIVATE)
    patch(d, 0x0046F975, "6A 02", bytes.fromhex("6A 12"))                    # SetWindowPos(.., NOMOVE|NOACTIVATE)
    # player kart inputs come from three floats the harness writes (steer, brake, throttle)
    # instead of the keyboard:  stub = fld dword ptr [INJECT + n] ; ret 4
    for n, call_va in enumerate((0x0043AE11, 0x0043AEA0, 0x0043AF29)):
        stub_va = STUB_VA + 0x10 * n
        stub = b"\xD9\x05" + struct.pack("<I", INJECT_VA + 4 * n) + b"\xC2\x04\x00"
        o = stub_va - BASE
        assert not any(d[o:o + len(stub)])
        d[o:o + len(stub)] = stub
        old = b"\xE8" + struct.pack("<i", 0x0045C890 - (call_va + 5))
        patch(d, call_va, old.hex(" "), b"\xE8" + struct.pack("<i", stub_va - (call_va + 5)))
    no_activation(d)
    command_slot(d)


def no_activation(d):
    """Test-only: the window never activates itself, so it does not take the keyboard focus.

    The graphics library sizes and restores the game window with calls that also activate it.
    """
    for va, old, new in ((0x0053302A, "6A 06", "6A 16"),      # SetWindowPos(NOMOVE|NOZORDER) + NOACTIVATE
                         (0x00533DEA, "6A 06", "6A 16"),
                         (0x00533E85, "6A 26", "6A 36"),      # ... with FRAMECHANGED
                         (0x00534B50, "6A 06", "6A 16"),
                         (0x0053140E, "6A 09", "6A 04")):     # ShowWindow(SW_RESTORE) -> SW_SHOWNOACTIVATE
        patch(d, va, old, bytes.fromhex(new))
    # The frame window is created disabled (WS_DISABLED): Windows does not activate a disabled
    # window, whoever asks. The tests need no real input in it.
    patch(d, 0x0046F8F2, "68 00 80 CF 00", bytes.fromhex("68 00 80 CF 08"))
    # The game's first windows are invisible developer dialogs ("Messages", "Watches",
    # "Control Panel", "Create Game Element", ...). A new process may take the foreground once,
    # and creating such a dialog did: the keyboard focus then sat on an invisible window until
    # the game gave it back. The test build creates none of them: the library's
    # CDialog::Create(template, parent) returns FALSE at once, the dialog objects stay
    # without a window ...
    patch(d, 0x0057D3F6, "53 8B 5C 24 08", bytes.fromhex("33 C0 C2 08 00"))   # xor eax,eax ; ret 8
    # ... and every dialog template gets WS_DISABLED as well, for any created another way.
    n = 0
    for off in dialog_style_offsets(d):
        style = struct.unpack_from("<I", d, off)[0]
        struct.pack_into("<I", d, off, style | 0x08000000)
        n += 1
    assert n == 17, "expected 17 dialog templates, found %d" % n


def no_instance_lock(d):
    """Test builds never take the game's single-instance lock (see pu_noinst.py): they create
    no mutex and look for no other game window, so they can run next to other test games, and
    the user's real game always starts as the first instance, even while tests run."""
    import pu_noinst
    pu_noinst.apply(d)


def dialog_style_offsets(d):
    """File offsets of the style field of every dialog template in the resources."""
    def entries(off):
        named, ids = struct.unpack_from("<HH", d, off + 12)
        return [struct.unpack_from("<II", d, off + 16 + 8 * i) for i in range(named + ids)]

    for type_id, type_dir in entries(RSRC_OFF):
        if type_id != 5:                                   # RT_DIALOG
            continue
        for _, name_dir in entries(RSRC_OFF + (type_dir & 0x7FFFFFFF)):
            for _, data in entries(RSRC_OFF + (name_dir & 0x7FFFFFFF)):
                rva = struct.unpack_from("<I", d, RSRC_OFF + data)[0]
                off = rva - RSRC_RVA + RSRC_OFF
                extended = struct.unpack_from("<HH", d, off) == (1, 0xFFFF)   # DLGTEMPLATEEX
                yield off + 12 if extended else off


def command_slot(d):
    """Test-only: the game runs test commands itself, once per frame, on its own thread.

    Nothing is injected from outside; a test only writes plain values into the slots:
      HANDBACK_VA  a window handle: the game gives the foreground to that window and clears the slot
      CALL_VA      function address, ecx, number of stack arguments, six arguments, result.
                   The game calls the function and clears the address when it is done.
    Also a copy routine at COPY_VA, copy(dst, src, n), and at ADD_VA add(list): list = count,
    then count pairs (address of a float, float to add). Both for writes that must land in one
    frame (the endless straight of topspeed.py moves the kart's body and frame with add).
    """
    def dw(v):
        return struct.pack("<I", v)

    handback = b"\xC7\x05" + dw(HANDBACK_VA) + dw(0)         # mov dword ptr [HANDBACK],0
    handback += b"\x50"                                       # push eax
    handback += b"\xFF\x15" + dw(0x0059545C)                  # call dword ptr [SetForegroundWindow]
    push_loop = b"\x49"                                       # dec ecx
    push_loop += b"\xFF\x34\x8D" + dw(CALL_VA + 0x0C)         # push dword ptr [ecx*4 + args]
    loop = b"\x85\xC9" + b"\x74" + bytes([len(push_loop) + 2]) + push_loop   # test ecx,ecx ; jz go
    loop += b"\xEB" + struct.pack("<b", -(len(loop) + 2))                     # jmp loop
    call = b"\x8B\xEC"                                        # mov ebp,esp
    call += b"\x8B\x0D" + dw(CALL_VA + 8)                     # mov ecx,[nargs]
    call += loop
    call += b"\x8B\x0D" + dw(CALL_VA + 4)                     # mov ecx,[ecx value]
    call += b"\xFF\xD0"                                       # call eax
    call += b"\x8B\xE5"                                       # mov esp,ebp  (callee- or caller-cleaned alike)
    call += b"\xA3" + dw(CALL_VA + 0x24)                      # mov [result],eax
    call += b"\xC7\x05" + dw(CALL_VA) + dw(0)                 # mov dword ptr [function],0
    code = b"\x9C\x60"                                        # pushfd ; pushad
    code += b"\xA1" + dw(HANDBACK_VA) + b"\x85\xC0" + b"\x74" + bytes([len(handback)]) + handback
    code += b"\xA1" + dw(CALL_VA) + b"\x85\xC0" + b"\x74" + bytes([len(call)]) + call
    code += b"\x61\x9D"                                       # popad ; popfd
    code += b"\xE9" + struct.pack("<i", FRAME_CALL_TARGET - (DISPATCH_VA + len(code) + 5))
    copy = bytes.fromhex("56 57 8B 7C 24 0C 8B 74 24 10 8B 4C 24 14 F3 A4 5F 5E C3")   # rep movsb, ret
    add = bytes.fromhex("56 53 8B 5C 24 0C 8B 13 83 C3 04"          # ebx = list, edx = count
                        "85 D2 74 0F 8B 33 D9 06 D8 43 04 D9 1E 83 C3 08 4A EB ED"   # [addr] += delta
                        "5B 5E C3")
    for va, code_ in ((COPY_VA, copy), (ADD_VA, add)):
        o = va - BASE
        assert not any(d[o:o + len(code_)]), "test routine space is not free"
        d[o:o + len(code_)] = code_
    o = DISPATCH_VA - BASE
    assert not any(d[o:o + len(code)]), "dispatcher space is not free"
    d[o:o + len(code)] = code
    old = b"\xE8" + struct.pack("<i", FRAME_CALL_TARGET - (FRAME_CALL_VA + 5))
    patch(d, FRAME_CALL_VA, old.hex(" "), b"\xE8" + struct.pack("<i", DISPATCH_VA - (FRAME_CALL_VA + 5)))


STUB_VA = 0x00593900       # unused bytes behind the code
INJECT_VA = 0x00884F00     # unused, zero-initialised, writable bytes at the end of .data
DISPATCH_VA = 0x00593B00   # unused bytes behind the code
COPY_VA = 0x00593A80       # copy(dst, src, n), cdecl-like (the slot restores esp); unused bytes
ADD_VA = 0x00593AA0        # add(list): floats += deltas, all in one frame
FRAME_CALL_VA = 0x00472ED7     # a call the frame loop makes once per frame ...
FRAME_CALL_TARGET = 0x0043ACC0  # ... to this function
RSRC_RVA, RSRC_OFF = 0x00486000, 0x001EA000   # the resource section: rva and file offset
CALL_VA = 0x00884F60       # function, ecx, nargs, 6 args, result (zero-initialised, writable)
HANDBACK_VA = 0x00884F90   # window that should get the foreground back


H0_VA = 0x005938B0         # float: reference physics step the suspension was tuned for
INV_H0_VA = 0x005938B4     # float: 1 / reference step
CAVE_VA = 0x005938C0


def suspension_fix(d, h0=1.0 / 60.0):
    """Make the wheel spring/damper independent of the physics step.

    Stock: P0 = 1/(dt*(c + k*dt)), P1 = k*dt/(c + k*dt)  -> effective stiffness k*dt, damping dt*(c + k*dt).
    Fixed: P0 = 1/(h0*(c + k*h0)), P1 = k*dt/(c + k*h0)  -> what the stock game does at dt == h0, at any dt.
    """
    o = H0_VA - BASE
    assert not any(d[o:o + 0x40])
    d[o:o + 8] = struct.pack("<ff", h0, 1.0 / h0)
    # (A) k*dt -> k*h0 ; (B) dt*(c + k*h0) -> h0*(c + k*h0)
    patch(d, 0x0043FB88, "D8 8C 24 E8 00 00 00", b"\xD8\x0D" + struct.pack("<I", H0_VA) + b"\x90")
    patch(d, 0x0043FB9B, "D9 84 24 E8 00 00 00", b"\xD9\x05" + struct.pack("<I", H0_VA) + b"\x90")
    # P1 = (k*h0/(c + k*h0)) * dt / h0
    cave = bytes.fromhex("D9 44 24 10" "D8 F1" "D8 8C 24 E8 00 00 00") + b"\xD8\x0D" + struct.pack("<I", INV_H0_VA)
    back = 0x0043FBB2
    cave += b"\xE9" + struct.pack("<i", back - (CAVE_VA + len(cave) + 5))
    c = CAVE_VA - BASE
    d[c:c + len(cave)] = cave
    patch(d, 0x0043FBAC, "D9 44 24 10 D8 F1", b"\xE9" + struct.pack("<i", CAVE_VA - (0x0043FBAC + 5)) + b"\x90")


def build(orig, mode, step, fix=False, auto=False):
    d = bytearray(orig)
    windowed(d)
    no_instance_lock(d)
    if auto:
        autonomous(d)
    if fix:
        suspension_fix(d)
    o = CONST_VA - BASE
    assert not any(d[o:o + 8])
    d[o:o + 8] = struct.pack("<d", step)
    addr = struct.pack("<I", CONST_VA)
    if mode == "frame":
        # 00472E0F: fcomp qword ptr [005992A8] (0.005) -> our constant
        patch(d, 0x00472E0F, "DC 1D A8 92 59 00", b"\xDC\x1D" + addr)
    elif mode == "physics":
        # 00469071: fcom qword ptr [005992A8] (0.005) -> our constant
        patch(d, 0x00469071, "DC 15 A8 92 59 00", b"\xDC\x15" + addr)
    return d


def main():
    exe, game, settings = sys.argv[1:4]
    rates = [int(x) for x in sys.argv[4:]] or [60]
    orig = open(exe, "rb").read()
    assert len(orig) == 0x224000, "need the original exe"
    open(os.path.join(game, "win_stock.exe"), "wb").write(build(orig, None, 0.005))
    open(os.path.join(game, "win_fix.exe"), "wb").write(build(orig, None, 0.005, fix=True))
    # unattended variants (no keyboard, no focus): stock 200 FPS, capped, and with the suspension fix
    open(os.path.join(game, "auto_stock.exe"), "wb").write(build(orig, None, 0.005, auto=True))
    open(os.path.join(game, "auto_fix.exe"), "wb").write(build(orig, None, 0.005, fix=True, auto=True))
    for fps in rates:
        step = 1.0 / fps - 1e-5
        open(os.path.join(game, f"auto_cap{fps}.exe"), "wb").write(build(orig, "frame", step, auto=True))
        open(os.path.join(game, f"auto_fixcap{fps}.exe"), "wb").write(build(orig, "frame", step, fix=True, auto=True))
    for fps in rates:
        step = 1.0 / fps - 1e-5
        open(os.path.join(game, f"win_cap{fps}.exe"), "wb").write(build(orig, "frame", step))
        open(os.path.join(game, f"win_phys{fps}.exe"), "wb").write(build(orig, "physics", step))
        open(os.path.join(game, f"win_fixcap{fps}.exe"), "wb").write(build(orig, "frame", step, fix=True))
    print("built stock +", rates)
    s = bytearray(open(settings, "rb").read())
    struct.pack_into("<ii", s, 4, 0, 0)        # music / sfx volume
    struct.pack_into("<i", s, 0x14, 0)         # 640x480
    open(os.path.join(game, "settings.dat"), "wb").write(s)


if __name__ == "__main__":
    main()
