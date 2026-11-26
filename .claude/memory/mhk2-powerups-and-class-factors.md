---
name: mhk2-powerups-and-class-factors
description: How the two speed power-ups (Sirene = blue light, Powerdose = turbo can) work in Moorhuhn Kart 2, the force model behind top speed and standing start, measured speeds, the gearing and pull chosen for 200 cc and 250 cc, how to measure a top speed, and the single-instance trap for test builds
metadata:
  type: project
---

Measured on the original MHK2-XXL.exe V1.0 and the patched one, at 60 FPS, with moorhuhn (character 0).

**The user's decisions**
- 2026-11-18: 200 cc = top speed of 150 cc with the siren, new 250 cc class = with the power can ("200 ccm 1.52 and 250 ccm 1.64"; patch 1.3, class factors only).
- 2026-11-18/19: "250 ccm should have a faster acceleration, maybe also 200 ccm. not as fast as their power-ups though". Patch 1.4: pull 1.5 (200 cc) and 2.0 (250 cc), class factors lowered to 1.468 and 1.545 so the top speeds still match. The amounts were my choice (the user left them open); they can try others in the tuning class, see [[mhk2-engine-classes]].

**Mechanism (from code and karts.txt)**
- `karts.txt`, GameSettings / PowerUpInfo: "blue light" (Sirene) time 8 s, accel factor 2.5, max. speed factor 1.10; "turbo can" (Powerdose) time 5 s, accel factor 5.0, max. speed factor 1.15. In memory: GameSettings accessor 0x40B7B0, blue light at +0x48/+0x4C/+0x50, turbo can at +0x64/+0x68/+0x6C.
- Car: active power-up [car+0x274] (-1 none, 2 blue light, 3 shield, 7 turbo can), remaining time [car+0x278]. `Car::ActivatePowerUp(type)` 0x42D320 (thiscall) must be used to switch one on (it creates the sound objects the per-frame code dereferences); writing 1e6 to the timer keeps it alive, writing 0.001 ends it cleanly.
- Every frame Car::Update (0x4332A1..) writes two factors into the vehicle object v = [car+0x44]: [v+0x268] accel factor and [v+0x26C] max. speed factor. Defaults 1.0/1.0; 1.5/1.1 while [car+0x29C] == 11; blue light 2.5/1.1; turbo can 5.0/1.15 but only once the kart is faster than 15 units/s.
- Force function 0x43F700: engine torque = lookup(rpm / speed factor) (0x440110: throttle*T(rpm) - (1-throttle)*ebrake(rpm); exactly zero at and above 6000 rpm at full throttle). The drive torque (0x43F7F4) and the traction limit (0x43FAFF) are multiplied by the accel factor. So the speed factor is exactly equivalent to multiplying the class factor, and the accel factor multiplies thrust, engine braking and the traction limit. Since patch 1.4 both places also multiply by the class's pull.
- Class factor = diff ratio / f and torque curve * f (0x437724): thrust at a given engine speed is the same in every class, the engine just turns slower. Engine speed = 143.27 * v * (gear / 0.5) / class factor; gears 1.0 / 1.0 / 0.75 / 0.5, change up at 4000 rpm.

**Force model** (`class_model.py`; fits plain runs and power-up runs to 0.01 .. 0.03 units/s²)
- a(v) = pull * min(C * (gear / 0.5) * T(rpm), 22.2) - R(v), with T the torque curve (0,1.4) (2000,1.0) (4000,0.6) (6000,0), C = 16.15 units/s² and R(v) = 2.81 * (v / 57.57)² units/s²: the drag grows with the square of the speed. (The first estimate, a linear 0.049 * v, was wrong and gave 49.8 for 150 cc.)
- 22.2 units/s² is the launch acceleration of every stock class: in the low gears the engine offers more than the tyres transmit, which is why the classes are identical for the first half second.
- With a pull above about 1.6 the real launch stays behind the model: the tyres slip. 250 cc (pull 2.0) is at 16.9 units/s after 0.5 s, 200 cc (pull 1.5) at 18.0, the model says 21.9 and 16.6.
- Near top speed the kart closes the gap at about 0.5 per second in the plain classes, 0.8 with pull 1.5, 1.0 with pull 2, 1.3 with the siren, 2.6 with the power can.

**Top speeds on the flat, game units per second**
| | measured | model |
| --- | --- | --- |
| 50 cc (0.9) | | 36.2 |
| 100 cc (1.1) | | 43.5 |
| 150 cc (1.3) | 50.46 and 50.49 (two runs, decay fitted from above) | 50.4 |
| 150 cc + Sirene | 57.59 (two runs) | 57.57 |
| 150 cc + Powerdose | 61.25 | 61.24 |
| 200 cc in patch 1.4 (1.468, pull 1.5) | 57.58 (three runs, the last on the final build) | 57.5 |
| 250 cc in patch 1.4 (1.545, pull 2.0) | 61.21 (two clean runs, the second on the final build; a noisier one read 60.8) | 61.2 |
| 200 cc in patch 1.3 (1.52) | 57.57 (constant over 0.7 s) | 57.51 |
| 250 cc in patch 1.3 (1.64) | 61.15 (constant over 0.7 s) | 61.18 |
| 200 cc up to patch 1.2 (1.5) | | 56.9 |

**Standing start** (track index 3, time from the moment the throttle opens)
| | 50 cc | 100 cc | 150 cc | 200 cc (1.4) | 250 cc (1.4) | 200 cc (1.3) | 250 cc (1.3) |
| --- | --- | --- | --- | --- | --- | --- | --- |
| after 0.5 s | 11.0 | 11.0 | 11.0 | 18.0 | 16.9 | 11.0 | 11.0 |
| after 1 s | 18.6 | 20.1 | 21.2 | 30.0 | 31.8 | 22.1 | 22.7 |
| after 2 s | 27.9 | 30.8 | 32.9 | 44.2 | 49.7 | 35.1 | 36.2 |
| time to 30 | 2.37 s | 1.92 s | 1.72 s | 1.00 s | 0.95 s | 1.55 s | 1.47 s |
| time to 40 | | | 2.91 s | 1.65 s | 1.37 s | 2.52 s | 2.38 s |
For comparison the model for 150 cc with the siren: 40 after 1.00 s; with the power can: 0.48 s.

**How to measure a top speed**
- Since 2026-11-23 the better way is `topspeed.py` (an endless straight: the kart is put back 39 units at the end of Ägypten's start straight, see [[mhk2-tuning-class]], top speed bullet). It also showed that the quadratic resistance above only holds up to about 61 units/s; beyond that a wall (the chassis on the road) takes over.
- Track index 3 ("Ägypten") has the longest flat start straight (x from 150.7 down to about 52; other start straights are 32..66 units, the castle's 174 units drop by 12 %). No class reaches top speed there from a standing start.
- So: `pu_run.py <60 FPS test build> out.csv --track 3 --cls C --boost 7 --cut V` pushes the kart with the power can from 16 units/s on and ends the power-up at speed V; `--boost 2` pushes with the siren, `--then 2` switches the siren on after the cut. The speed overshoots V (the cut takes two or three frames), then a dip in the road at x 95..103 takes 1 to 3 units/s off. Behind it (x 94..52, 0.7 s) the kart either holds its speed or creeps towards its top speed; `hold_speed.py` prints start, end, slope and the speed the run is heading for (exponential fit; trust it when the rms error is about 0.001). `class_runs.py` does standing start and pushes for a list of classes.
- Classes with a pull above 1 must be pushed with the siren: with the power can the stacked pull overshoots by 10 units/s and more. Cuts that worked: 200 cc siren 52 and 55, 250 cc siren 56 (59 gave a noisy fit); plain classes with the can: class 2 at 46.5 and 48.5, class 3 (1.3) at 53.0 and 55.5, class 4 (1.3) at 56.5 and 59.0; siren itself 52.0 and 54.5 with `--then 2`.
- `top_from_plain.py` estimates a top speed from a plain standing start through the model; it reads about 0.15 low for pull 1.

**Test tooling trap**
- The game has a single-instance lock: 0x4A4950 (thiscall, ret 4, called at 0x46F3AC with ecx = app+0xA0) makes a named mutex; if it exists already, it looks for the window "Moorhuhn Kart 2", calls ShowWindow(SW_RESTORE), BringWindowToTop and SetForegroundWindow on it and the game exits with code 0 before writing a log. So a second instance that takes the lock fails silently AND pulls the first one's window to the front. The only other shared state is HKCU\Software\mhk2 `machine-id` (read; written once if missing).
- Test builds skip it (since 2026-11-22 `prep_fps.build` applies `pu_noinst.apply` to every build): 0x46F3AC `E8 9F 55 03 00` -> `83 C4 04 90 90` (drop the argument) and 0x46F3B3 `0F 85 C8 00 00 00` -> `90 E9 C8 00 00 00` (always the first-instance path); checked against dumpbin. The lock object keeps handle 0 from its constructor 0x4A4900, and the destructor 0x4A4920 releases only a non-zero handle. Such builds create no mutex and look for no window, so they run side by side, and the user's real game (which keeps the lock; the shipped patch is unchanged) always starts as the first instance even while tests run. Rules for starting them: `gameslot.py`, see [[mhk2-windowed-test-recipe]].
- A path-following "robot" driver was tried for reaching top speed on a whole lap and abandoned (it scraped walls).

**Why:** the user wanted the new classes tied to the power-ups' speeds, then a stronger pull.
**How to apply:** gearing and pull are the patcher's defaults (`--factor`, `--pull`, `--factor-250`, `--pull-250`). To change a pull and keep a top speed, `class_model.py match <top speed> <pull>` gives the gearing; then measure as above. See [[mhk2-windowed-test-recipe]], [[mhk2-kart-parameters]] and [[mhk2-fps-physics-root-cause]].
