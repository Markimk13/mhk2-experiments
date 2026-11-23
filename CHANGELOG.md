# Changelog

Saves (`settings.dat`) keep their format through all versions; records and phantoms of earlier
versions stay.

## 1.9

- The tuning class is unlocked by winning Meisterschaft 2 in 250 cc; until then it is not shown
  in the class menu. (Up to 1.8 it was always open; on such a save it is hidden again until that
  win, or use `--unlock-tuning`.)
- Faster computer karts: in 200 cc they lose half of the game's handicap, in 250 cc all of it
  (full throttle all the time, like you).
- Tuning class: a third page *Gegner* with *Tempo* (−100 to 200 %): how fast the computer karts
  drive, from walking pace through 150 cc (0 %) to full throttle (100 %); above that they get
  more engine power than you. Part of the presets: the class copies have their class's pace,
  own slots keep it.
- Computer karts fire their power-ups as often at 200 FPS as at 60 FPS (the stock game counted
  the chance per frame, so at 200 FPS they fired nearly twice as many and stood frozen after
  hits far more often).
- Tuning page: each group's values (*Kart*, *Welt*, *Gegner*) now sit under its button.
- The detail pages explain the selected row; warnings only show on the pages that hold one of
  their values.
- `--unlock` also opens Meisterschaft 2 and tracks 5–8 in 50 cc to 250 cc; new
  `--unlock-tuning` opens the tuning class as well.
- The name page shows the name typed last (also after a championship); an empty name takes it.
- The main menu shows the patch version. Releases have two digits; builds in between a third one
  that counts the changes since the last release.
- The release zips contain `tools\patch_200cc.py`, so the commands work straight from the
  game folder.
- Tuning class: the *Am Limit* line replaces the three yellow warnings. Every value gives
  challenge and risk points; the line says whether the values are extreme but still race well
  (green), close to the limit (bright green), too risky (orange) or neither (grey). The risk
  points are a fit to about 1250 races of the computer karts.
- Tuning class: a *Top speed* line on every tuning page and on the pause page, in km/h, for the
  character chosen last (fitted to about 420 runs on an endless straight; most sets within 5 %).
- Presets: *Rakete*, *Formel 1*, *Rallye*, *Glatteis*, *Schwergewicht* and *Wahnsinn* have new
  values that race better; *Dragster* is gone; new are *Bremsversagen*, *Federleicht*,
  *Hetzjagd* and *Mondrakete*. Own slots stay, and a saved "last preset" is moved along.
- The pause page shows what the race runs with: class, the 60 FPS switch, in the tuning class
  the preset and all values, and the top speed.
- The race shows the kart's speed in km/h below lap and position (for each player in the
  two-player game).

## 1.8 – first public release

- The tuning page lists all values under the *Vorlage* row, grouped *Kart* and *Welt*; the page
  of own presets shows a slot's values the same way.
- English menu texts as a second download (`--lang en` in the patcher). The exe is the same.

## 1.7

- The tuning page leads to two pages: *Kart* (the seven kart values) and *Welt* (gravity,
  25–300 %).
- New presets *Mondfahrt* (25 % gravity) and *Jupiter* (250 %); own presets store the gravity too.
  Saves from 1.6 are converted once.
- A yellow warning on the tuning pages for three combinations that leave the computer karts
  stuck.

## 1.6

- Own presets for the tuning class: eight slots with *Laden*, *Speichern*, *Umbenennen*,
  *Löschen*; filled slots also appear in the *Vorlage* row.

## 1.5

- *Vorlage* row on the tuning page: copies one of the five classes or nine ready-made presets
  into the values.

## 1.4

- 200 cc and 250 cc pull harder (thrust and traction 1.5 and 2 times); gearing 1.468 / 1.545
  keeps the top speeds of 150 cc with the siren and with the power can.
- Sixth class *Tuning* with seven kart values, its own records and phantoms, always open.
- Downforce limits for the tuning class, so extreme values no longer throw karts off the track.

## 1.3

- 200 cc at factor 1.52 and a new class 250 cc at 1.64, unlocked by winning championship 2 in
  200 cc.

## 1.2

- Own phantom karts without a helper program: the game races against runs from the same PC,
  replaces the phantom when it is beaten, and writes the data version and the player name into
  new phantom files.

## 1.0 – 1.1

- 200 cc class (factor 1.5), unlocked by winning championship 2 in 150 cc.
- Switch *60-FPS-Fahrphysik* in the options: the kart drives at any frame rate as it does at
  60 FPS.
