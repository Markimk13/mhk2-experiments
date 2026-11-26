[← Overview](../README.md) · [All documents](README.md)

# 60 FPS physics switch

At high frame rates, the original game makes the kart slower and slippery, and it hops at
random. The switch *60-FPS-Fahrphysik* (60 FPS driving physics) makes the kart drive at every
frame rate as it does at 60 FPS.

## Where to find it

1. Open *Hauptmenü → Einstellungen* (main menu → settings).
2. Select *60-FPS-Fahrphysik*.
3. Press Enter, ← or →, or click an arrow, to set it to *An* (on) or *Aus* (off).

![options menu](../screenshots/06-options-60fps-physics.png)

The game saves the switch in `settings.dat` with its other settings. The default is *Aus*.

## The settings

| Setting | What it does |
| --- | --- |
| *Aus* (off) | The original game. At high frame rates, the kart drives worse. |
| *An* (on) | The kart drives at every frame rate as it does at 60 FPS |

**When to switch it on.** Switch it on when your game runs faster than about 100 FPS. The game
runs at up to 200 FPS. At 60 FPS, the switch changes nothing.

**Why the game drives differently.** The springs of the wheels get softer when the frame rate
gets higher. At 200 FPS, the kart sits lower. At speed, the downforce presses the body of the
kart onto the road. Then the tyres carry less weight and have less grip. You feel this as slow,
slippery driving, "like ice", and as random hops.

You can also set the switch with the game closed:

```powershell
py tools\patch_200cc.py --physics60 on settings.dat
```

## Good to know

- **Power-ups of the computer karts.** Without the patch, the computer karts fire their
  power-ups almost two times as often at 200 FPS as at 60 FPS. The patch corrects this at every
  frame rate, also with the switch off.
- **What the switch does not change.** At 200 FPS, the game reads your controls more often than
  at 60 FPS. Two small effects also stay: the computer karts steer only in every second frame,
  and a wheel in the air slows its turning by 0.5 % in each frame.
- **Tuning class:** switch it on at high frame rates. Much downforce makes the problem stronger.

## Details

This section is for players who want the numbers.

The game runs one physics step in each frame when a frame is shorter than 1/60 s. The springs
depend on the length of that step. At 200 FPS, they are 3.3 times softer and about 6 times less
damped than at 60 FPS. The problem starts at about 100 to 120 FPS. At 200 FPS, the body of the
kart touches the road from about 60 % of the top speed.

Tests in the patched game: 150 cc time trial, first track, the same scripted inputs, game units.

| | 60 FPS | 200 FPS, *Aus* | 200 FPS, *An* |
| --- | --- | --- | --- |
| Height of the kart on the grid | 3.450 | 3.416 | 3.449 |
| Speed 2.5 s after a standing start | 37.5 | 32.8 | 37.8 |
| Weight not carried by the wheels, on the straight | ≈ 0 % | 20 % | 2 % |
| Sideways acceleration in a full turn | 54 | 36 | 55 |

With the switch on at 200 FPS, the speed curve is the curve of 60 FPS, about 0.05 s earlier.
After a shift of 0.05 s, the two curves agree within 0.1 %.

**Power-ups.** The original game lets a computer kart fire its power-up with a chance of 1 in
800 in each frame. At 60 FPS, this is after 13 s on average. At 200 FPS, it is after 4 s. On
the first track, the karts fired 21 to 23 power-ups per minute at 200 FPS, against 12 at
60 FPS. They hit each other much more often, stood frozen after hits, and the game put them
back on the track. The patch counts the chance for each second, not for each frame.

How the patch does it: [How it works](how-it-works.md#60-fps-physics-switch).
