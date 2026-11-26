> **Corrections (2026-11-18).** This note is from the first reverse-engineering pass (July 2026) and
> is kept as it was written. Three things in it turned out differently:
>
> - The frame cap is not applied by `mhk2_manager.jar`. The game only limits itself to 200 FPS; a
>   60 FPS cap comes from outside the game (driver, limiter tool, monitor sync).
> - The physics does take a `1/60` reference: `RwPhysics::Update` (0x469060) runs
>   `round(dt * 60)` sub-steps (at least one), so frames longer than 1/60 s are subdivided and
>   shorter ones step with the short `dt`. That is the root of the 200 FPS behaviour, see
>   [mhk2-fps-physics-root-cause.md](../memory/mhk2-fps-physics-root-cause.md).
> - The game files are not in this repository; the sandbox reads them from the paths in
>   `.claude/sandbox/local.json` (see `.claude/sandbox/tools/paths.py`).

# Exe-bound physics constants — TRACED from MHK2-XXL.exe

World gravity, the fixed timestep and the FPS coupling
live in `MHK2-XXL.exe`, not the text configs. This file records them, recovered by static analysis of the retail
`MHK2-XXL.exe` (x86-32 PE, ImageBase 0x400000, RenderWare 3.3.6 + RenderWare
Physics; disassembled with capstone/pefile). Only the numeric facts are
transcribed — the binary itself is copyrighted and stays out of the repo.

## Method note: the two "FPS" builds are the SAME binary

The install ships as `Moorhuhn Kart 2 FPS 60` and `... FPS 200` (on the user's PC), but the two
`MHK2-XXL.exe` files are **byte-identical** (same MD5). The install trees
differ only in save data (championship/phantom ghosts, highscores,
`settings.dat`). So the frame-rate is **not** a compiled-in difference — the
`mhk2_manager.jar` launcher applies an external cap. The timestep behaviour is
therefore entirely inside the shared exe.

## World gravity = 19.62 (along −Y, Y-up)

`RwPhysics::Init` (fn @ `0x468e30`, bracketed by the log strings
`"RwPhysics::Init"` → `"RwPhysics::Init ok"`) sets up the physics world with a
hardcoded gravity vector and world AABB, as immediate stores:

```
mov dword [.. +0x10], 0            ; gravity.x = 0
mov dword [.. +0x14], 0xC19CF5C3   ; gravity.y = -19.62   <-- WORLD GRAVITY
mov dword [.. +0x18], 0            ; gravity.z = 0
mov dword [.. +0x1c], 0x461C4000   ; +10000.0  ) world
mov dword [.. +0x20], 0x461C4000   ; +10000.0  ) AABB
mov dword [.. +0x24], 0x461C4000   ; +10000.0  ) max
mov dword [.. +0x2c], 0xC61C4000   ; -10000.0  ) world
mov dword [.. +0x30], 0xC61C4000   ; -10000.0  ) AABB
mov dword [.. +0x34], 0xC61C4000   ; -10000.0  ) min
```

`0xC19CF5C3` as float32 = **−19.6200008** (exactly 2 × 9.81). RenderWare is
Y-up, so gravity points down the −Y axis. Magnitude **19.62** in the physics
world's own units (the same units the `karts.txt` masses 17–23 and wheel
friction coefficients are expressed in). The physics world spans ±10000 units.

## Timestep = real seconds, clamped to [0.005, 0.3] → a native 200 fps cap

The main loop (RenderWindow, fn around `0x472d40`) computes the frame time from
the high-resolution timer, not a fixed constant:

```
QueryPerformanceCounter(&now)              ; edi = QPC import
delta = now - prev                         ; 64-bit tick delta
fild delta ; fild [freq] ; fdivp          ; dt = delta / QueryPerformanceFrequency  (SECONDS)
fst  [esp+0x10]                            ; dt stored (float32 s)

fcomp qword [0x5992a8]  ; = 0.005          ; if dt < 0.005 (fps > 200) ...
test ah,5 ; jnp 0x4730b5                   ;   ... jump to a bare "return" -> SKIP the frame
fcomp qword [0x598048]  ; = 0.3            ; if dt > 0.3 (fps < 3.33) ...
... mov [esp+0x10], 0x3E99999A ; = 0.3     ;   ... clamp dt to 0.3
mov [0x87a458], dt                         ; publish dt to the game
push dt ; call <game update>               ; update(dt)  — real elapsed seconds
```

So the game **does** feed real elapsed seconds to its update, but:

- **dt < 0.005 s (faster than 200 fps): the frame is dropped** — this is the
  game's built-in **200 fps ceiling** (the "FPS 200" build simply runs into
  it; the "FPS 60" build is the launcher forcing 60).
- **dt > 0.3 s (slower than ~3.3 fps): dt is clamped to 0.3** — a hitch guard.
- `1.0 / dt` is written to the on-screen `fps` stat; a separate accumulator
  averages it (the `Statistics` / `delta time ms` debug block @ `0x472bf0`).

Why the game is still "framerate-coupled" in practice: the vehicle/physics
integration is not fully dt-normalised, so its authentic feel is the one at
**60 fps → dt = 1/60 s (0.016667)**. There is no `1/60` constant in the binary
(confirmed by a float-immediate scan); 60 fps is just where the real-time dt
lands when the launcher caps it there.

