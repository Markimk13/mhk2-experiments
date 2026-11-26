"""Unattended test build for the engine class tests (sandbox only).

usage: prep_class5.py <exe (original or patched)> <out exe> [fps cap] [--mouse]

--mouse adds prep_opt's simulated mouse (MOUSE_INJ: moved flag, x, y; the real cursor is neither
read nor moved).

prep_ghost's build (windowed, no focus needed, menu page command, injected options keys,
one-shot "menu select" for the result pages) with the same one-shot "menu select" on two
more pages: the engine class menu (state 8) and the championship trophy page (state 1Bh).
Write 1.0f to NAME_INJ to press it. The highscore browsers (states 17h..1Ah) take "menu left"
and "menu right" from prep_opt's one-shot floats (MENU_INJ + 8 and + 12).

The tuning page of the patch (state 1Dh) reads its four actions through one call; that call
goes to a stub which serves them from prep_opt's one-shot floats (MENU_INJ: back, select,
left, right).

"menu up" and "menu down" (NAV_INJ, two one-shot floats): Menu::Navigate, which every page calls,
takes them from there. The patch's own look at them (the championship page, in front of the
game's handler) sees them through the same stub as the four actions, without taking them.
Both must see a key in the same frame, but a test writes it at any moment: so Menu::Navigate
takes a key only once the patch's look has seen it (a byte per key at NAV_SEEN), or one frame
after it first saw the key itself (on pages where the patch does not look).
"""
import os
import struct
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import prep_fps as P
import prep_opt as PO
import prep_ghost as PG

# "menu select" reads: engine class menu, championship trophy page
EXTRA_SELECT_SITES = (0x0041E1C9, 0x00414FE2)
# highscore browsers, time trial lists and championship lists: "menu left" / "menu right" reads
BROWSER_LEFT = (0x0041EE67, 0x0041F18A)
BROWSER_RIGHT = (0x0041EF20, 0x0041F243)
TUNE_STUB = 0x00593BA0          # unused bytes behind the code
INPUT_READ = 0x0045C890
ACTIONS = (0x00597570, 0x00595F1C, 0x00596D4C, 0x00596D40)   # "menu back", "menu select", "menu left", "menu right"
MOD_RVA, MOD_OFF = 0x004C0000, 0x00224000                    # the patch's own section
NAV_INJ = 0x00884FC0            # floats "menu up", "menu down" (unused, zero-initialised, writable; slack behind .data)
NAV_ACTIONS = (0x00596B44, 0x00596B38)                       # "menu up", "menu down"
NAV_SITES = (0x00411835, 0x004118E8)                         # Menu::Navigate reads them there
NAV_SEEN = NAV_INJ + 8          # bytes: the key was seen (by the patch's look, or by Menu::Navigate a frame ago)
NAV_STUBS = 0x00593C20          # unused bytes behind the code (0x40 apart)


def extra_select(d):
    for site in EXTRA_SELECT_SITES:
        P.patch(d, site, (bytes([0xE8]) + struct.pack("<i", INPUT_READ - (site + 5))).hex(" "),
                bytes([0xE8]) + struct.pack("<i", PG.NAME_STUB - (site + 5)))
    for sites, key in ((BROWSER_LEFT, 2), (BROWSER_RIGHT, 3)):       # prep_opt's stubs: 2 = left, 3 = right
        stub = PO.MENU_STUBS + 0x20 * key
        for site in sites:
            P.patch(d, site, (bytes([0xE8]) + struct.pack("<i", INPUT_READ - (site + 5))).hex(" "),
                    bytes([0xE8]) + struct.pack("<i", stub - (site + 5)))


def nav_inputs(d):
    """Menu::Navigate takes "menu up" / "menu down" from the one-shot floats at NAV_INJ."""
    for n, site in enumerate(NAV_SITES):
        va = NAV_STUBS + 0x40 * n
        a = struct.pack("<I", NAV_INJ + 4 * n)
        s = struct.pack("<I", NAV_SEEN + n)
        code = (bytes([0xA1]) + a                         # mov eax,[key]
                + bytes([0x85, 0xC0, 0x74, 16])           # test eax,eax ; jz none
                + bytes([0x80, 0x3D]) + s + bytes([0])    # cmp byte ptr [seen],0
                + bytes([0x75, 12])                       # jne take
                + bytes([0xC6, 0x05]) + s + bytes([1])    # mov byte ptr [seen],1   (take it in the next frame)
                + bytes([0xD9, 0xEE, 0xC2, 0x04, 0x00])   # none: fldz ; ret 4
                + bytes([0xD9, 0x05]) + a                 # take: fld dword ptr [key]
                + bytes([0xC7, 0x05]) + a + bytes(4)      # mov dword ptr [key],0
                + bytes([0xC6, 0x05]) + s + bytes([0])    # mov byte ptr [seen],0
                + bytes([0xC2, 0x04, 0x00]))              # ret 4
        assert len(code) == 56
        PO.put(d, va, code)
        P.patch(d, site, (bytes([0xE8]) + struct.pack("<i", INPUT_READ - (site + 5))).hex(" "),
                bytes([0xE8]) + struct.pack("<i", va - (site + 5)))


def tuning_inputs(d):
    """The tuning page's `tune_pressed` routine: its input read comes from MENU_INJ instead."""
    if len(d) <= MOD_OFF:
        return False                                  # the original exe: no tuning page
    # tune_pressed: push eax ; call Instance ; mov ecx,eax ; call Read ; fldz ; fucompp ; fnstsw ax ; test ah,40h ; ret
    tail = bytes.fromhex("D9 EE DA E9 DF E0 F6 C4 40 C3")
    at = d.find(tail, MOD_OFF)
    if at < 0:
        return False                                  # a patch version without the tuning page
    call_off = at - 5
    assert d[call_off] == 0xE8 and d[call_off - 2:call_off] == b"\x8B\xC8", "tune_pressed looks different"
    call_va = P.BASE + MOD_RVA + (call_off - MOD_OFF)
    assert struct.unpack_from("<i", d, call_off + 1)[0] == INPUT_READ - (call_va + 5)
    # stub(this, name): the one-shot float of the action (NAV_INJ's are read only: Menu::Navigate
    # takes them later in the frame), 0 for any other name
    code = bytearray(b"\x8B\x44\x24\x04" + b"\x33\xD2")           # mov eax,[esp+4] ; xor edx,edx
    jumps = []
    for i, name in enumerate(ACTIONS + NAV_ACTIONS):
        if i:
            code += b"\x42"                                        # inc edx
        code += b"\x3D" + struct.pack("<I", name)                  # cmp eax,name
        jumps.append(len(code))
        code += b"\x74\x00"                                       # je got / peek (filled in below)
    code += b"\xD9\xEE\xC2\x04\x00"                                # fldz ; ret 4
    got = len(code)
    code += b"\xD9\x04\x95" + struct.pack("<I", PO.MENU_INJ)       # fld dword ptr [edx*4+MENU_INJ]
    code += b"\xC7\x04\x95" + struct.pack("<I", PO.MENU_INJ) + bytes(4)   # mov dword ptr [edx*4+MENU_INJ],0
    code += b"\xC2\x04\x00"                                        # ret 4
    peek = len(code)
    nav = struct.pack("<I", NAV_INJ - 4 * len(ACTIONS))
    code += bytes([0x8B, 0x04, 0x95]) + nav + bytes([0x85, 0xC0, 0x74, 0x07])    # mov eax,[edx*4+NAV_INJ-10h] ; test eax,eax ; jz +7
    code += bytes([0xC6, 0x82]) + struct.pack("<I", NAV_SEEN - len(ACTIONS)) + bytes([1])   # mov byte ptr [edx+NAV_SEEN-4],1
    code += bytes([0xD9, 0x04, 0x95]) + nav                         # fld dword ptr [edx*4+NAV_INJ-10h]
    code += bytes([0xC2, 0x04, 0x00])                               # ret 4
    for i, pos in enumerate(jumps):
        code[pos + 1] = (got if i < len(ACTIONS) else peek) - (pos + 2)
    assert len(code) <= NAV_STUBS - TUNE_STUB
    PO.put(d, TUNE_STUB, bytes(code))
    d[call_off + 1:call_off + 5] = struct.pack("<i", TUNE_STUB - (call_va + 5))
    return True


def main():
    args = [a for a in sys.argv[1:] if a != "--mouse"]
    src, out = args[:2]
    fps = int(args[2]) if len(args) > 2 else None
    data = open(src, "rb").read()
    if fps:
        d = P.build(data, "frame", 1.0 / fps - 1e-5, auto=True)
    else:
        d = P.build(data, None, 0.005, auto=True)
    PO.menu_hooks(d)
    PG.name_hook(d)
    extra_select(d)
    nav_inputs(d)
    tuned = tuning_inputs(d)
    if "--mouse" in sys.argv:
        PO.mouse_hooks(d)
    open(out, "wb").write(d)
    print("built", out, "cap", fps or "stock (200)", "| tuning page inputs hooked" if tuned else "")


if __name__ == "__main__":
    main()
