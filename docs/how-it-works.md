[← Overview](../README.md) · [All documents](README.md)

# How it works

- 91 small patches in the original code plus about 8300 bytes of new code (and 2400 of data) in an added section (`.mod200`).
- The save file has fixed tables for 3 classes × 64 tracks and 3 × 20 championships, of which only
  8 tracks and 4 championships are ever used. The new records are stored in unused slots
  (tracks 33–64 and championships 11–20): those of the 150 cc rows for 200 cc, of the 100 cc
  rows for 250 cc and of the 50 cc rows for the tuning class. So the file layout is unchanged,
  and a `settings.dat` from an earlier version of the patch keeps its records.
- Class names are texts 332 + class, and the unlock messages are numbered by class too. Some
  of the numbers the new classes need are taken by other stock texts (336, the hint in the
  class menu, and 584), so the patch moves the hint to 342 and gives 250 cc and the tuning
  class their own message numbers (588, 589). The tuning row of the class menu is a label with
  an empty text until the class is unlocked, so the rows keep their numbers.
- Computer karts: each kart's throttle is the game's factor for the class, its rubber band
  and its random strength multiplied together (200 cc, 250 cc and Tuning use the 150 cc
  values). A hook right behind that multiplication turns the throttle *t* into
  *t* + (1 − *t*) · *g*, with *g* = 0.5 in 200 cc, 1 in 250 cc and *Tempo* / 100 in the tuning
  class (below 0 it is *t* · (1 + *g*)). Above 100 % the pull hook (see *Pull*) multiplies
  their pull by *Tempo* / 100 for every vehicle that is not a human player's: the race object
  keeps the players' cars, and each car points to its vehicle. Steering, braking and the racing line are the game's own in every class.
- Pull: the game multiplies the engine's torque and the traction limit by a factor that only
  its power-ups set. The patch multiplies both by the class's pull as well.
- Tuning class: the game applies a class at the end of loading a kart's values and then builds
  the kart's physics from them. The tuning class scales seven of those values at that point.
  The gravity: the game builds a new physics world at every race start with the gravity
  (0, −19.62, 0); in the tuning class a hook right behind that scales it.
  The pages are new menu pages (numbers 1Dh, 1Fh, 20h and 21h; the game's own end at 1Ch) with their
  own builder and input handling. The nine values live in a highscore entry the game never
  reaches (50 cc, track 63: `settings.dat` offset 0x2E48, the marker `TUNE` at 0x2E78). The
  presets are a table behind the patch's code, their names texts 250–265 in `text-20.csv`.
  The own presets are page 1Eh, their eight slots two more unused highscore entries (50 cc,
  tracks 61 and 62: `settings.dat` offset 0x2C60, 32 bytes each: eight values – the gravity,
  never 0, marks a filled slot – and the name), with the marker `OWNP` at 0x2D60. Behind them
  are the marker `WELT` (0x2D6C, "this save has eight values"), the number of the preset
  copied last (0x2D70; up to 1.6 it was where the gravity is now) and the marker `GEGN`
  (0x2D74, "this save has *Tempo*", added in 1.9). The own slots' *Tempo* does not fit into their
  32 bytes; it is a table of eight words at 0x2D7C with the marker `OPPS` at 0x2D8C. Renaming uses the
  game's name page: a hook in front of the result pages' input handler takes *Weiter* and
  Esc while a slot is being renamed, the game does the typing.
- Downforce rules of the tuning class: the force function computes the downforce as
  coefficient × (velocity · forward axis)² along the chassis' up axis. One hook in front of
  it limits that speed to 120 × √(Gewicht / Anpressdruck), to 75 × √(…) while none of the four
  wheels reported ground contact in this step, and to zero while the vertical part of the up
  axis is below 0.5 (a tilt of 60°). In every other class the hook changes nothing.
- `text-20.csv` uses the game's built-in override mechanism (`text-NN.csv` is merged over `text.csv`).
- Suspension: for every wheel and physics step the game turns "wheels stiffness" *k* and "wheels
  damping" *c* into the solver's contact parameters `1 / (dt·(c + k·dt))` and `k·dt / (c + k·dt)`.
  The solver's effective spring is then `k·dt` and its damper `dt·(c + k·dt)` – both shrink with the
  step `dt`. With the switch on, the patch computes `1 / (h·(c + k·h))` and `k·dt / (c + k·h)` with a
  fixed `h` = 1/60 s, which gives the 60 FPS spring and damper for any `dt`.
- The switch lives in three unused padding bytes of the settings object (`settings.dat` offset
  0x49, the bytes `36 30 46` = on). The stock game saves and loads them but never looks at them.
- Phantom karts: three small patches remove the "is this file from my own PC" check (race start,
  race restart, import). At the finish the header of the new phantom is cleaned first – the
  stock game leaves bytes 5–31 of the phantom it loaded in there – and after the file is
  closed it is copied over the track's phantom file if its time is lower. The data version is
  found at startup from the size of `data\mk2\level01\objects\collision_border.dff` (29 772
  bytes in V1.1), looked up the way the game does, newest `mhk2-NN.dat` first.
- The player name is stored in a highscore entry the game never reaches (50 cc, track 64,
  rank 5: `settings.dat` offset 0x2F0C, with the marker `NAME` at 0x2F2C).
