---
name: mhk2-kart-parameters
description: "The kart parameters Moorhuhn Kart 2 reads from karts.txt, where they sit in the Car object, how the seven characters differ, what an engine class changes (two numbers), and the measured standing start of all five classes"
metadata:
  type: project
---

Worked out on 2026-11-18 from MHK2-XXL.exe V1.0 and the game's `karts.txt` (inside `mhk2-00.dat`, encrypted; `mhk2crypt.py` decodes it).

**Loading**
- `karts.txt` has one `[Car] "<character>"` object per character: moorhuhn, lesshuhn, moorfrosch, pumpkin, snowman, turtle, hank. Function 0x437080 (a Car method; car in edi, the reader object in esi) reads every value by name into the Car object.
- At its end (0x437719, only when the reader is loading: `call [vtbl+8]`) it applies the engine class, then throws the kart's physics objects away and builds them again from the values (0x42BFF0, then 0x4343E0). So a value changed at that point takes full effect. Every kart in a race goes through this, computer karts included.

**What an engine class changes: two things, by one factor f** (0.9 / 1.1 / 1.3 stock; the patch adds 1.468 and 1.545, up to patch 1.3 they were 1.52 and 1.64)
- `diff ratio` (car+0x13C) is divided by f.
- The four `torque` values (car+0x154..0x160) are multiplied by f.
- Nothing else. Wheel thrust at a given engine speed is therefore the same in every class; the kart just covers f times more ground per engine turn. Engine speed = 47.75 * v * gear * diff ratio (wheel radius 0.2), gear change at `change up rpm` 4000.
- Since patch 1.4 the added classes have a second number, the pull (1.5 for 200 cc, 2.0 for 250 cc): it multiplies the drive torque and the traction limit where the game's power-ups do it, see [[mhk2-powerups-and-class-factors]]. The tuning class scales seven values, see [[mhk2-tuning-class]].

**Where the values sit in the Car object**
| Offset | Value (karts.txt name) | moorhuhn |
| --- | --- | --- |
| +0x60 | mass | 20 |
| +0x64, +0x70 | chassis size, center of mass (3 floats each) | |
| +0x7C, +0x80 | chassis bounce, chassis slide | 0.1, 0.5 |
| +0x90, +0x94 | wheels radius front / rear | 0.2 |
| +0x98..+0xA4 | steer base front / rear, steer track front / rear | 4.135, 0, 0, 1.6 |
| +0xA8..+0xB4 | wheels stiffness front / rear, wheels damping front / rear | 20000, 200 |
| +0xB8, +0xBC | lateral friction coeff front / rear | 2.2 |
| +0xC0, +0xC4 | roll friction coeff front / rear | 4.4, 2.2 |
| +0xC8, +0xCC | roll friction coeff locked front / rear | 1.0, 0.5 |
| +0xD0..+0xDC | wheels bounce, wheels slide front / rear | 0.1, 0 |
| +0x110, +0x114 | brake coefficient front / rear | 1.0 |
| +0x118, +0x11C | max. brake front / rear | 1.0 |
| +0x120, +0x124 | torque coefficient front / rear (which axle drives) | 0, 1 |
| +0x128..+0x134 | gear 1..4 | 1.0, 1.0, 0.75, 0.5 |
| +0x138, +0x13C | gear reverse, diff ratio | 3.0, 6.0 |
| +0x140 | change up rpm | 4000 |
| +0x144..+0x150 | rpm position 1..4 | 0, 2000, 4000, 6000 |
| +0x154..+0x160 | torque 1..4 | 1.4, 1.0, 0.6, 0 |
| +0x164..+0x170 | e braking 1..4 | 0, 0, 0.2, 2.0 |
| +0x174, +0x178 | steering washout, steering washout power | 0.03, 1.6 |
| +0x17C, +0x180 | drag coefficient, downforce coefficient | 0, 0.5 |
| +0x184, +0x188 | steering speed, steering rest speed | 170, 600 |
| +0x18C | max steering angle | 40 |
| +0x190, +0x194 | brake speed, acceleration speed | 100, 10 |
| +0x198 | friction equalizer | 0.8 |
| +0x19C..+0x1A4 | angular vel. damping, collision limit, collision damping | 2, 2, 12 |
| +0x1A8, +0x1AC | extra steering torque, extra steering torque impulse | 3, 0 |
| +0x1B0 | upright torque factor | 100 |

**How the characters differ** (everything else is the same for all seven)
| | moorhuhn | lesshuhn | moorfrosch | pumpkin | snowman | turtle | hank |
| --- | --- | --- | --- | --- | --- | --- | --- |
| mass | 20 | 20 | 17 | 18 | 23 | 17 | 21 |
| lateral friction | 2.2 | 2.0 | 2.0 | 2.0 | 2.0 | 2.0 | 2.0 |
| roll friction front / rear | 4.4 / 2.2 | 4 / 2 | 4 / 2 | 4 / 2 | 4 / 2 | 4 / 2 | 4 / 2 |
| brake coefficient | 1.0 | 1.3 | 1.0 | 1.0 | 0.7 | 1.0 | 2.0 |
| max. brake | 1.0 | 1.2 | 1.0 | 1.0 | 0.7 | 1.0 | 2.0 |
| gear 1 / 3 / 4 | 1 / 0.75 / 0.5 | same | 1.5 / 0.75 / 0.55 | 1 / 0.7 / 0.45 | 1 / 0.75 / 0.55 | 1 / 0.75 / 0.52 | 0.5 / 0.75 / 0.5 |
| diff ratio | 6.0 | 6.0 | 6.0 | 7.0 | 5.5 | 6.7 | 6.2 |
| steering speed / rest speed | 170 / 600 | 100 / 300 | 150 / 500 | 100 / 400 | 80 / 300 | 150 / 400 | 150 / 500 |
Also the centre of mass (x 0.043..0.08) and, for the turtle, steering washout power 1.57. All top speeds measured so far are for moorhuhn (character 0).

**Standing start by gearing alone** (moorhuhn, track index 3, 60 FPS, full throttle; times from the moment the throttle opens; 200 cc and 250 cc as they were in patch 1.3, class factors 1.52 and 1.64 without pull. The numbers of patch 1.4 are in [[mhk2-powerups-and-class-factors]])
| | 50 cc | 100 cc | 150 cc | 200 cc | 250 cc |
| --- | --- | --- | --- | --- | --- |
| speed after 0.5 s | 11.0 | 11.0 | 11.0 | 11.0 | 11.0 |
| after 1 s | 18.6 | 20.1 | 21.2 | 22.1 | 22.7 |
| after 2 s | 27.9 | 30.8 | 32.9 | 35.1 | 36.2 |
| after 3 s | 32.4 | 36.9 | 40.6 | 43.9 | 45.4 |
| time to 30 units/s | 2.37 s | 1.92 s | 1.72 s | 1.55 s | 1.47 s |
| gear 2 -> 3 at | 13.0 | 16.3 | 18.7 | 21.6 | 23.3 |
| gear 3 -> 4 at | 16.8 | 20.6 | 24.4 | 28.3 | 30.7 |
| top speed | 36.2 (model) | 43.5 (model) | 50.5 | 57.6 | 61.15 |
The first 0.5 s are identical (22.2 units/s² in every class); the classes part as each one reaches its gear changes. Top speed model in [[mhk2-powerups-and-class-factors]].

**Aerodynamics** (force function 0x43F700, after the wheel loop, 0x43FC42..0x43FDA3; traced on 2026-11-19. edi = vehicle object = [car+0x44], [edi+4] = the vehicle's parameter object, ebx = its rigid body)
- At its start the function turns two local axes into world vectors with the body's matrix: the forward axis (parameter object +0x54, kept at [esp+4Ch]) and the up axis (+0x6C, at [esp+34h]). In the recordings of `ai_race.py` the columns fx, fy, fz are the forward axis and sx, sy, sz the side axis; the up axis is not recorded.
- Downforce (0x43FCB4..0x43FD32): `[v+0x264] * [params+0x1E0] * (velocity · forward)²`, applied at the body's position against the up axis. [v+0x264] is one of five factors that start as the same value (0x43EE47..0x43EE5F; +0x268 and +0x26C are the power-ups' accel and speed factor). Read in a running 250 cc race: factor 1.0 and coefficient 0.5 (the kart file's `downforce coefficient`; `ai_race.py` prints them). So the acceleration is 0.5 * s² / mass: for mass 20, 94 units/s² at 61 units/s, 4.6 times gravity (20.4, from the wheel loads of a standing kart). A kart in the air with tuning values confirmed the size (about 0.026 * s²).
- It is a plain force along the kart's own down axis, whatever the kart is doing: in the air it pulls a level kart down faster, a kart on its back is lifted, and a kart standing on its tail is shoved forward. With stock values that hardly shows. The tuning class has rules for it, see [[mhk2-tuning-class]].
- Drag (0x43FD37..0x43FD9E): `([v+0x260] * [params+0x1DC] + X) * |velocity|²` against the velocity. X is the largest [surface+0x34] among the surfaces the wheels stand on (wheel loop 0x43FA29..0x43FA50; surface table from the object 0x401470 returns, at its +0x44, 0x7C bytes per surface). In the race the factor read 1.0 and the coefficient 0: `drag coefficient` is 0 for every kart.
- The resistance a kart meets on the road (2.81 * (v / 57.57)² units/s² for a 250 cc kart) follows the downforce: with "Anpressdruck" 800 % a 250 cc kart tops out at 31 units/s, with 0 % it is still gaining after 3 s. It also is a force: a kart of a quarter of the mass tops out at 34. How much of it is the surface's X and how much the downforce pressing the kart onto the road was not separated. The summed wheel load stops growing at five to seven times the kart's weight while the downforce goes on growing, so beyond that the chassis must be carrying it (the same thing the 60 FPS switch is about, [[mhk2-fps-physics-root-cause]]); that is an inference from the recordings, not traced in code.
- Per wheel (struct of 0x84 bytes, the first at v+0x34): +0x18 "touched the ground in the last step" (copied from +0x1C and cleared at the end of the wheel loop), +0x40 load.

**Why:** the user asked on 2026-11-18 how the classes differ in acceleration and other properties, and floated a sixth class "not to take too serious for highscores" whose properties can be changed in the game.
**How to apply:** the tuning class (patch 1.4, [[mhk2-tuning-class]]) scales fields of this table right before the rebuild; more rows work the same way. A changed value only takes effect through the rebuild (0x42BFF0, then 0x4343E0) at the end of the loader. See [[mhk2-engine-classes]].
