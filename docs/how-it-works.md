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

## Challenges

- **Menu.** The page *Rennmodus* (menu page 4) is built by the game from a table. After that, the
  patch turns its item 3, the label *Zwei Spieler*, into the button *Herausforderung* and adds
  the label again behind the items. So the item numbers of the game's buttons stay the same. The
  button opens the new menu page 22h. Its texts are 150 to 176 in `text-20.csv`.
- **The draw.** A seed starts an xorshift32 generator: `x ^= x << 13; x ^= x >> 17;
  x ^= x << 5`. Five numbers follow, in this order: the track (% 8), the start (% 1000, per
  mille of the track's path), the length (1000 + % 601 metres, as a share of the path, kept in
  0.3 to 0.7), the character (% 7) and one of 64 sets of tuning values. `challenge_draw()` in
  the patcher does the same in Python.
- **Seeds.** *Zufall* takes `GetTickCount`. *Täglich* takes the day: the days since 1601 from
  `GetSystemTimeAsFileTime` (UTC), times 9E3779B1h, xor 5EED35h. The patch divides the
  FILETIME with integers (a shift by 14, then two 32-bit divisions by 52734375): the game runs
  the x87 in single precision, and a float division moved the day change by up to 20 minutes.
- **Tuning sets.** The patcher draws the 64 sets when it builds the exe, with a fixed seed. It
  keeps a set when `tune_limit()` gives it the line *Am Limit* or *Hart am Limit* and when
  `top_speed()` is at least that of the preset *150 cc* for every character. The gravity stays in
  50 % to 200 %.
- **Path lengths.** The page shows the length in metres before the track is loaded. So the
  patcher holds the path length of each track, measured in the game with the path length
  function (0x4437F0): 2222, 1799, 2860, 3401, 1260, 2641, 2906 and 2435 units. 1 unit is 1 m.
- **Settings.** A draw puts class 5, time trial, the track, player 1's character, the eight
  tuning values and the 60 FPS switch into the settings object. The player's own values go to
  a block in the free rest of the `_rwdseg` page (0x885100). They come back when the page
  *Rennmodus* or the main menu is built. Both writes of `settings.dat` (0x4122BB, 0x403B72) swap
  the player's values in for the write, so the file never holds a challenge.
- **Start.** The race start reads the track's `start spline offset` at 0x406481. A challenge
  gives its own start there. The game places the grid along the path from this one value.
- **Finish.** The race update tests "3 laps" at 0x406B5A. In a challenge, it adds up the path
  progress of player 1 instead (each step taken into −0.5 to 0.5, so the wrap at 0 counts
  right). The race ends at the challenge's length. The lap timer becomes lap 1, because the
  game takes the time from the sum of the three lap times. The lap counter becomes 3: at the
  race end, fn 0x437920 gives every kart with fewer laps estimated lap times of about 90 s.
- **Result.** The result overlay (page 0Eh) adds the lines *Runde 1* to *Runde 3* and *Gesamt*
  from 0x422643 on. In a challenge, the patch adds its own lines instead (texts 168 to 170) and
  continues at 0x4233B5: the run's time and, in a daily challenge, the best time of the day or
  *Neue Bestzeit!*. The copy of a faster daily run sets a flag for that. The result list (page
  0Fh) adds its three buttons, then the highscore table from 0x42351F on. In a challenge, it
  adds the same lines and the title *Herausforderung* instead, and jumps to the page's end
  (0x424658).
- **Power can.** The held power-up of a car is car+270h (-1 = none, 7 = power can). In a
  challenge, the finish hook sets it to 7 on the first frame of the race, once per race. The car
  fires it on the power-up key (0x4330FA). The car reset at the start and the restart clears it
  (0x436F21). The phantom recording stores the held power-up, so a phantom fires it too.
- **HUD best time.** The HUD reads the best lap at 0x41965C (Hud + player × 4 + 18h). In a daily
  challenge with a time of the day, it reads the best time of the day instead.
- **HUD.** The lap line (text 100 at 0x419078) becomes text 105 with the metres:
  (length − progress) × path length. The minimap gives each vertex of its track line its colour
  at 0x418C28. A challenge colours the stretch magenta, the finish white and the rest dim.
- **Pause page.** In a challenge, the pause page gets other lines than in the tuning class:
  *Tägliche Herausforderung* with the date and the best time of the day, or *Zufällige
  Herausforderung* with the seed. Then the values, the top speed, the track and the driver. The
  date comes from the day number with H. Hinnant's `civil_from_days` (`challenge_date()` in the
  patcher).
- **Records and phantoms.** In a challenge, the result pages' "top five" test (0x412A90) says no,
  and the best-run copy skips the track's phantom. Both phantom loads (race start, restart) get
  an empty file name for *Zufall* and `data\Phantom\daily-<day>.mhk2` for *Täglich*. A faster
  daily run is copied to that file. The race start takes the phantom's character from the
  header of the track's phantom file (0x4099B1). In a challenge, it takes player 1's character
  instead: the daily draw always gives the same driver.
- **Medals.** The draw also computes the three medal times and keeps them at 0x885180. The
  reference time is ((C_t(start + share) − C_t(start)) × LAP[t] × SET[s] + LOSS[s]) × CHAR[c].
  C_t is the cumulative share of the lap time at 65 points of the path (`CH_PACE_SHAPE`), linear
  between them, with C(e − 1) + 1 behind the wrap. Each medal is the reference × 0.95, 1.05 and
  1.2, rounded to hundredths n. The patch stores (n + 0.99) / 100, because the game's time text
  cuts the hundredths: a float a hair below n would show n − 1. A run wins a medal exactly when
  its own time shows n or less. `challenge_medals()` in the patcher does the same in Python. The
  result compares the run's time with each medal (time ≤ medal wins) and shows text 173 to 175,
  or text 176 with the bronze time.
- **Cheering.** At the finish, the game sets a flag when the player's place is under 3 (0x406B55).
  With the flag, the car gets state 3 (`winner.anm`, sound `RACE_finish`), else state 4 (sound
  `RACE_failure`). In a challenge, the finish hook sets the flag when the run's time reaches
  bronze.
- **Best time in colour.** The texts of the best time of the day (155, 157, 169) take three
  strings: an opening colour tag, the time, a closing tag. `ch_tags` picks the tags of the best
  medal that the time reaches, or two empty strings.
- **Medal tables.** The tables come from races of computer karts: class 5 with the set's values,
  *Tempo* 100 %, 6 improved karts, the 60 FPS switch, each kart's path progress per 1/64 lap. A
  set's lap time on a track is the sum of the 30 % quantile of every 1/64 over all karts and
  laps. log L = log LAP[t] + log SET[s], fitted by least squares; the geometric mean of SET is 1.
  LOSS is the cleanest start of each run: the time at 8/64 behind the grid minus the flying time
  over the same part.

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

The pause page shows the volumes as one line each (1.11): the headings (texts 131 and 133) are
empty, and the value texts 132 and 134 carry the names, as in *Lautstärke Musik: 50 %*. The patch
moves the pause items to the new rows (the y values at 0x413E92 and the three buttons).

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
- **Best time of the day.** A highscore entry that the game never reaches: 50 cc, track 60,
  offset 0x2BAC. It holds the marker `DAYC`, the day (days since 1601, UTC) and the best time
  of that day (float, seconds).
