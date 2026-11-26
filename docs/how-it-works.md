[← Overview](../README.md) · [All documents](README.md)

# How it works

This page is for developers. Players find everything they need on the other pages.

The patch makes 91 small patches in the original code. It adds about 8300 bytes of new code and
2400 bytes of data in a new section, `.mod200`.

## 200 cc, 250 cc and unlocking

- **Pull.** The game multiplies the engine's torque and the traction limit by a factor. Only its
  power-ups set this factor. The patch also multiplies both by the pull of the class.
- **Texts.** The class names are the texts 332 + class. The unlock messages are also numbered
  by class. Other original texts use some of the numbers that the new classes need: 336 (the
  hint in the class menu) and 584. So the patch moves the hint to 342. 250 cc and the tuning
  class get their own message numbers, 588 and 589.
- **Class menu.** The tuning row is a label with an empty text until the class is unlocked. So
  the rows keep their numbers.
- **Alles freigeschaltet** (1.10) is the marker `FREI` at `settings.dat` offset 0x2D98, behind
  `STDG`. Any other value means off. The progress stays where the original game keeps it: the
  highest unlocked class at 0xFD04, and one bit for each class for Meisterschaft 2 at 0xFD08.
  Only the places that read the progress check the switch:
  - the class menu: the 100 cc and 150 cc rows of the game, the 200 cc, 250 cc and Tuning rows
    of the patch,
  - the track lock, which also locks Meisterschaft 2,
  - the *Gegner* button of the championship page.

  The code that records a won championship reads the real progress.

## Tuning class

- **Kart values.** The game applies a class at the end of loading a kart's values. Then it
  builds the kart's physics from them. The tuning class scales seven of these values at that
  point.
- **Gravity.** The game builds a new physics world at every race start with the gravity
  (0, −19.62, 0). In the tuning class, a hook right behind that scales it.
- **Pages.** The tuning pages are new menu pages with their own builder and input handling:
  1Dh, 1Fh, 20h and 21h. The game's own pages end at 1Ch. The own presets are page 1Eh.
- **Presets.** The presets are a table behind the patch's code. Their names are the texts 250
  to 265 in `text-20.csv`.
- **Renaming.** Renaming a slot uses the game's name page. A hook in front of the input handler
  of the result pages takes *Weiter* and Esc while a slot is renamed. The game does the typing.
- **Downforce rules.** The force function computes the downforce as coefficient ×
  (velocity · forward axis)² along the chassis' up axis. A hook in front of it limits that
  speed to 120 × √(Gewicht / Anpressdruck). While none of the four wheels reported ground
  contact in this step, the limit is 75 × √(…). While the vertical part of the up axis is below
  0.5 (a tilt of 60°), the limit is zero. In every other class, the hook changes nothing.

## Gegner: the computer karts

- **Throttle.** The throttle of each computer kart is the game's factor for the class × its
  rubber band × its random strength. 200 cc, 250 cc and Tuning use the values of 150 cc. A hook
  right behind that multiplication turns the throttle *t* into *t* + (1 − *t*) · *g*, with
  *g* = *Tempo* / 100. Below 0, it is *t* · (1 + *g*). At *Standard*, *g* is 0 up to 150 cc, 0.5
  in 200 cc, and 1 in 250 cc and the tuning class.
- **Pull above 100 %.** The pull hook (see *Pull* above) multiplies the pull by *Tempo* / 100
  for every vehicle that is not a human player's. The race object keeps the players' cars, and
  each car points to its vehicle.
- **Driver.** Steering, braking and the racing line are the game's own in every class. The
  exception is the karts that *Verbesserte Gegner* switches to the learned driver.
- **Championship page.** The game builds the championship page (0Ch) again in every frame. A
  hook behind its builder moves the championship row and the four track rows, and adds the
  button and its line of values. A hook in the menu's drawing moves the picture. The game steps
  through the items of a page by their number. So a hook in front of the page's input handler
  puts the button, the tenth item, between the tracks and *Starte Meisterschaft* for ↑ and ↓.

## 60 FPS physics switch

- **Suspension.** The game has a "wheels stiffness" *k* and a "wheels damping" *c*. For every
  wheel and physics step, it turns them into the solver's contact parameters
  `1 / (dt·(c + k·dt))` and `k·dt / (c + k·dt)`. The solver's effective spring is then `k·dt`, and its damper
  `dt·(c + k·dt)`. Both shrink with the step `dt`. With the switch on, the patch computes
  `1 / (h·(c + k·h))` and `k·dt / (c + k·h)` with a fixed `h` = 1/60 s. This gives the spring
  and the damper of 60 FPS for any `dt`.

## Phantom karts

- **Own phantoms.** Three small patches remove the check "is this file from my own PC": at race
  start, at race restart and at import.
- **Best run.** At the finish, the patch first cleans the header of the new phantom. The
  original game leaves bytes 5 to 31 of the phantom that it loaded in there. After the file is
  closed, the patch copies it over the track's phantom file if its time is lower.
- **Name.** The name goes into bytes 8 to 19 of every new phantom file. `mhk2_manager` keeps its
  player name there too.
- **Data version.** At startup, the patch finds the data version from the size of
  `data\mk2\level01\objects\collision_border.dff` (29 772 bytes in V1.1). It looks the file up
  the way the game does, the newest `mhk2-NN.dat` first.

## Texts

`text-20.csv` uses the game's own override mechanism: the game merges `text-NN.csv` over
`text.csv`.

## Save file

The patch keeps the file layout of `settings.dat`. So a save from an earlier version of the
patch keeps its records.

- **Records.** The save file has fixed tables for 3 classes × 64 tracks and 3 × 20
  championships. The game uses only 8 tracks and 4 championships. The new records are in unused
  slots (tracks 33 to 64 and championships 11 to 20): the 150 cc rows for 200 cc, the 100 cc
  rows for 250 cc, and the 50 cc rows for the tuning class.
- **60 FPS switch.** Three unused padding bytes of the settings object, offset 0x49. The bytes
  `36 30 46` mean on. The original game saves and loads these bytes but never reads them.
- **Tuning values.** The eight values, and behind them the two values of *Gegner*, are in a
  highscore entry that the game never reaches: 50 cc, track 63, offset 0x2E48, with the marker
  `TUNE` at 0x2E78.
- **Own presets.** Two more unused highscore entries: 50 cc, tracks 61 and 62, offset 0x2C60,
  32 bytes for each slot. A slot holds eight values and the name. The gravity is never 0, so it
  marks a filled slot. The marker `OWNP` is at 0x2D60.
- **Markers behind the own presets:**

  | Offset | Content |
  | --- | --- |
  | 0x2D6C | `WELT`: this save has eight values |
  | 0x2D70 | The number of the preset copied last. Up to 1.6, the gravity was here. |
  | 0x2D74 | `GEGN` (1.9): this save has *Tempo*, the ninth value at 0x2E68 |
  | 0x2D7C | 1.9 only: *Tempo* of the own slots, eight words, with the marker `OPPS` at 0x2D8C. 1.10 does not read it. |
  | 0x2D90 | `NEWG` (1.10): *Verbesserte Gegner* is the dword at 0x2E6C, behind the nine values |
  | 0x2D94 | `STDG` (1.10): the two values of *Gegner* hold for every class. Without it, the game takes *Standard* and 0, and the first page that shows them saves these. |
  | 0x2D98 | `FREI` (1.10): *Alles freigeschaltet* is on |

  *Standard* is saved as −125, one step below −100 %.
- **Player name.** A highscore entry that the game never reaches: 50 cc, track 64, rank 5,
  offset 0x2F0C, with the marker `NAME` at 0x2F2C.
