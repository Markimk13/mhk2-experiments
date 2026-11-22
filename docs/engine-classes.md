[← Overview](../README.md) · [All documents](README.md)

# 200 cc, 250 cc and Tuning: unlocking and what changes

## Unlocking 200 cc, 250 cc and Tuning

All three follow the game's own chain: win **Meisterschaft 2 in 150 cc** to open 200 cc,
**Meisterschaft 2 in 200 cc** to open 250 cc, and **Meisterschaft 2 in 250 cc** to open the
tuning class (*Du hast die Tuning-Klasse freigeschaltet!*). Until then the tuning row of the
class menu stays empty. The win has to happen with a patched exe that knows the class above:
the stock game never recorded a win in 150 cc, versions up to 1.2 never recorded one in
200 cc, and versions up to 1.8 none in 250 cc. Inside 200 cc and 250 cc, Meisterschaft 2 and
tracks 5–8 open up after winning Meisterschaft 1, as in the other classes; the tuning class
has all eight tracks and both championships from the start.

![tuning class unlocked](../screenshots/14-unlock-tuning.png)

To open them straight away use `--unlock` or `--unlock-tuning`, see
[Commands](../README.md#commands-unlock-the-classes-build-the-exe).

## 200 cc and 250 cc: what changes

![engine class menu](../screenshots/01-engine-menu.png)

- **Menu:** *Leistungsklasse wählen* has six rows now: 200 cc and 250 cc, each greyed out
  while locked, and Tuning, which is not shown until it is unlocked. The rows sit closer
  together than in the stock game to make room.
- **Speed:** the three stock classes differ in one number, the class factor (0.9 / 1.1 / 1.3).
  It lengthens the gearing; the push at the wheels is the same in all three at the same
  engine speed. So 50, 100 and 150 cc leave the line equally fast and only part once each
  reaches its gear changes.

  200 cc and 250 cc continue the gearing with **1.468** and **1.545**, and they also **pull
  harder**: 1.5 and 2 times the thrust (the siren pulls 2.5 times, the power can 5 times).
  Gearing and pull together give the top speed that a 150 cc kart has with the two speed
  power-ups: 200 cc is as fast as 150 cc with the siren, 250 cc as fast as 150 cc with the
  power can. Rebuild with `--factor`, `--pull`, `--factor-250` and `--pull-250` to change them.

  Measured with Moorhuhn on a flat straight at 60 FPS, in game units per second:

  | | Top speed | After 1 s | After 2 s | Time to 40 |
  | --- | --- | --- | --- | --- |
  | 50 cc | 36.2 (calculated) | 18.6 | 27.9 | – |
  | 100 cc | 43.5 (calculated) | 20.1 | 30.8 | – |
  | 150 cc | 50.5 | 21.2 | 32.9 | 2.91 s |
  | 150 cc with siren | 57.59 | | | |
  | **200 cc** | 57.58 | 30.0 | 44.2 | 1.65 s |
  | 150 cc with power can | 61.25 | | | |
  | **250 cc** | 61.21 | 31.8 | 49.7 | 1.37 s |

  The speeds after 1 and 2 seconds are from a standing start. No start straight in the game
  is long enough to reach top speed that way; the top speeds were measured on the longest
  flat one (fourth track) by pushing the kart with a power-up and watching where it settles
  afterwards.
- **Power-ups** multiply on top of the class: the siren in 250 cc pulls 2 × 2.5 = 5 times as
  hard as a plain 150 cc kart, and it lengthens the gearing by 10 % as in every class.
- **Lifting the throttle** brakes harder in the new classes: the pull also scales the
  engine's braking, the same way the game's power-ups do it. In the half second after
  lifting at the same engine speed (about 4450 rpm) a 150 cc kart slows down by 6.4 units/s
  per second, a 250 cc kart by 10.5.
- **Off the line** 250 cc gains nothing over 200 cc: twice the thrust is more than the tyres
  hold on the first metres. After half a second it is at 16.9 against 18.0, after one second
  it is ahead.
- **Opponents:** computer karts get the same gearing and pull and drive with each track's
  150 cc AI settings, but the game holds them back less. In every class it gives them only
  part throttle while they are near you (in 150 cc 0.9 of full throttle, times a random
  strength per kart from 1.0 down to 0.6, and less when they are ahead). In 200 cc they lose
  half of that handicap, in 250 cc all of it: full throttle all the time, like you. Their
  driving itself (line, braking, steering) is the game's own in every class.
  Races on the first track (75 s, mean speed of the six computer karts, game units per
  second): 150 cc 36.5, 200 cc 45.1, 250 cc 48.7 (with version 1.8: 43.2); 250 cc with every
  limit of the game's table set to full throttle: 50.2, the same within the scatter of a race.
- **Records:** time trial and championship highscores, phantom karts, the highscore browser
  and the unlock messages work for both classes.
- **Sound:** both reuse the 150 cc engine sample.

Earlier versions of this patch had other values: up to 1.2, 200 cc had the factor 1.5; in 1.3
the factors were 1.52 and 1.64; neither had extra pull. Times and phantoms driven with them
stay in the lists. They come from karts with the same or a slightly lower top speed and a
much weaker pull, so they are easier to beat now.
