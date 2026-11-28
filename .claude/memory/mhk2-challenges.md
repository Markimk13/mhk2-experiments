---
name: mhk2-challenges
description: "Challenges (issue #35, built 2026-11-27): the menu page, the draw, the daily best and phantom, the settings swap and its traps; the idea of async challenges (a seed gives a ~20 s stretch of a track, tuning values and character; players send each other the seed and their phantom; a daily seed from the date) and what the exe offers for it (a moved start tested, works without exe change): where the race-start grid is placed, how a finish on path progress could replace the lap count, why segment phantoms need no change; tools datpack.py and startpos_test.py"
metadata:
  type: project
---

## The idea (user, 2026-11-26/27; GitHub issue #35 "Daily challenge")

Online races came up first. The user prefers **async races** (like the BikeRace multiplayer) to live
ghosts: a **seed** picks a time trial track, a random start, an end 30..70 % of the track later
(about 20 s), random but challenging tuning values and a random character. A player sends the seed
and their phantom to another player as a challenge. A **daily seed** from the date gives a daily
challenge (#35, the offline part); only a global ranking of it needs online storage (a free serverless tier would do; the
server cannot replay a phantom, so a ranking rests on trust). Everything goes into the patch, nothing
into mhk2_manager (see [[mhk2-user-context]]).

My suggestions so far, not decided: measure the length in expected seconds, not in share of the track;
draw tuning values below the *Am Limit* line and inside the downforce rules ([[mhk2-tuning-class]]);
force the 60 FPS physics switch ([[mhk2-fps-physics-root-cause]]) and store patch and data version
(V1.0 / V1.1 collision borders differ) in the challenge; give the seed generator a version.

## What the exe offers (traced 2026-11-27 from the original exe)

- **Path progress** car+224h is a fraction 0..1 of the track's path; the lap logic is in
  [[mhk2-tracks-and-championships]] (wraps car+230h, start box). Path length: fn 0x4437F0 with
  ecx = TrackPath = [[0x5E8520]+1Ch].
- **The grid** (race-state init, fn 0x4061E0): at 0x40647C it reads `start spline offset` from
  LevelSettings+50h (singleton [0x5E852C], getter 0x401940; objects.txt's serializer writes it at
  0x41A058). For every kart i (cars in [0x5E8520]+10h, in championships in their grid order) it sets
  car+224h = offset - 3 * i / path length (0x4065B6..0x4065D6) and sends the car the message
  `"start left"` (even i) or `"start right"` (odd i), which places it on the path. So **one float
  moves the whole grid anywhere on the track**, facing along the path. Patch options: replace
  `mov eax,[eax+50h]` at 0x406481 with the challenge's start, or write LevelSettings+50h after the
  level is loaded and before this init.
- **A reset to any path position**: 0x406EA0..0x406F15, behind a check of `"lap"` (fn 0x45F350, likely
  a debug key or console command; not traced), sets car+230h = laps + 1, car+224h = offset - 0.01
  and sends `"reset car"`. The same message works for any progress value.
- **Race end**: 0x406B5A `cmp dword ptr [esi+264h],3` / `jl 0x406DD8` (13 bytes) in the race update
  fn 0x4067B0, inside the loop over all cars with car state [car+2D0h] == 2. A finish on progress
  would replace this test: done = car+230h + frac(car+224h + s) - frac(start + s) >= length
  (s = 0.5 on Sumpf, see the lap note). The finish code after it (phantom save, times, result
  pages) then runs as for a lap finish. Not built; records and phantom slots of a challenge must
  stay apart from the normal time trial ones.
- **Phantoms**: the recording ("phantom record", sample "car" every 0.2 s, 0x432AB3) runs while the
  car state is 2, from race start, in world positions ([[mhk2-phantom-and-manager-internals]]). A
  segment phantom therefore needs no change; the header would carry the seed so that a ghost plays
  only in its own challenge.

## Showing the finish (user, 2026-11-27: the lap text and the minimap together, metres not percent)

Plan: "Runde 1/3" becomes "Noch 340 m"; the minimap shows the challenge stretch bright, the rest
dim, plus a mark at the finish. No world marker for now (the start line is painted into the ground
texture `Boden_Start_UV` of level.bsp; there is no object to move).

- **Lap text**: Hud::Draw (fn 0x418EF0) 0x419073..0x41909C: text 100 ("Runde %d/3") via 0x401710 /
  0x490C70, lap number = [Hud+20h+4*[Hud+4]] + 1, formatted by 0x4946D0 / 0x494EB0, drawn at
  0x4190EF (x 100, y 20, scaled). The patch's speed line hooks 0x41920D (`HUD_SPEED_HOOK` in the
  patcher) and draws with `HUD_DRAW_TEXT` 0x490820; a challenge branch swaps text id and number at
  the lap text the same way. Text 102 at 0x419212 is the next line (not looked at).
- **Metres**: path length = (length of the left + right edge spline) / 2, fn 0x4437F0 (ecx =
  TrackPath [[0x5E8520]+1Ch], spline length 0x493EC0). Progress is not exactly arc length, but in
  the three test runs the kart covered 1950..2250 units per unit of progress where it drove clean
  (track 1, path about 2220 units by the edge polylines). So metres left = (finish - progress) *
  path length, 1 unit = 1 m (the HUD's km/h is units/s * 3.6). Off by about +-10 % locally, fine
  for a countdown.
- **Minimap** = Hud::DisplayTrack fn 0x418790. Built once (flag Hud+ECh): the road edges of the path
  (left [path+6Ch], right [path+7Ch], 12-byte points), each pair pulled towards the middle, scaled to
  the bounding box (0x5C3C88..0x5C3C94), into Hud+90h; Hud+A0h (vector begin Hud+A4h) holds 2n+2
  screen vertices of 28 bytes (RwIm2DVertex: x, y, z, rhw, colour, u, v). Every frame
  (0x418B90..0x418C35) vertex k gets x, y, u = k & 1, v = (k / 2) / n and **colour 0xFFC0C0C0
  (ARGB) at 0x418C28** (`mov dword ptr [ecx+eax-0Ch],0FFC0C0C0h`, 8 bytes; ebx = k + 1 there,
  [esp+10h] = k / 2, edi = 2n); texture trackline.png (Hud+C0h); render states 0x0A = 5, 0x0B = 6
  (alpha blending on); drawn as a triangle strip (type 4) by [[0x87CB40]+30h]. A challenge hook at
  0x418C28 colours path point k / 2 by whether (k / 2) / n lies in the stretch (assumes progress ~
  point index / n; check on screen).
- **Kart dots**: list Hud+B4h..B8h, 16 bytes per entry (position at +0, icon index at +0Ch); icon
  cell = trackIcons.png (Hud+C4h, 64x64, a 4x4 atlas of 16 px cells: 0 red, 1 blue, 2 green, the
  rest empty), drawn 12 px wide (scaled) at 0x418E45..0x418EA4 with the RGBA tint pushed at
  0x418E4A..0x418E59 (all 1.0). A finish mark = one more icon at the finish point's path position,
  tinted (for example white or yellow), with no new picture; a checkered flag would need a changed
  trackIcons.png in an archive, which the release does not ship yet.

## First build (2026-11-27, patcher `CH_*`, test tool `challenge_test.py`)

- Runtime block `CH_DATA` = 0x885100 (the free, writable rest of the `_rwdseg` page; .data ends at
  0x884D04 and its free tail 0x884D04..0x884FFF is used by the test builds' slots): active, start,
  length, done, last progress, finish band low / high. For now a test tool writes active, start and
  length before the race; no menu, no seed yet. Off (0) = the stock game.
- Five hooks: grid (0x406481, the start instead of `start spline offset`; resets done / last and
  computes the band), finish (0x406B5A: car 0 sums its progress steps, each wrapped into
  -0.5..0.5, and finishes at `length`; other cars never finish), lap text id (0x419078, text 105
  "Noch %d m" / "%d m to go"), lap number (0x419094, (length - done) * path length via 0x4437F0),
  minimap vertex colour (0x418C28: rest 0x60C0C0C0, stretch 0xFFFFD040, finish band +-0.008 white;
  not red or green, because the kart dots are red, blue and green).
- dumpbin check: 0 mismatches. Under Git Bash dumpbin exits 157; run it from PowerShell.
- Results on track 1, 150 cc, full throttle without steering: start 0.985 length 0.05 (across the
  wrap at 0) finished at 4.38 s with done 0.0499; start 0.25 length 0.03 at 3.46 s. The HUD counted
  down ("Noch 102 m" ... "Noch 0 m"), then the game showed its finish camera. Start 0.5 length 0.4
  showed "Noch 866 m" (path about 2200 units) and the stretch in colour on the minimap.
- **A challenge finish wrote the normal record and phantom** (first build): the 4.4 s run became
  the 150 cc record of track 1 and the patch made it `phantom-3-01.mhk2`; the next run showed that
  ghost as a red, see-through band on the road. **Fixed** (second commit): `ch_top5` answers "no"
  for both calls of the top-five check 0x412A90 (0x421A2F, 0x422398), so "Weiter" leads to the
  result list (0Fh), not to the name entry; `phantom_promote` copies nothing in a challenge; both
  ghost loads (race start 0x409B44, restart 0x407304) format the file name again as an empty
  string, so no phantom loads (gp+54h stays 0). Tested: record and phantom file unchanged.
  Restore after tests that finish: `fixtures\settings.dat`, `fixtures\Phantom\`.
- Pictures with three games open catch whatever window is on top (the capture takes the screen
  area); take pictures with one game at a time.
- Short stretches are only a few path points on the minimap: 0.03 of track 1 is about 4 points.

## The menu and the daily challenge (2026-11-27, third commit; player page docs/challenges.md)

User's spec: a third button under *Ein Spieler*; on its page *Zufall* and *Täglich* show the draw
and (only *Täglich*) the best time of the day; *Weiter* races against the best-time ghost (only
*Täglich*); a phantom only for *Täglich*, one per day. Built as follows (patcher `CH_*`,
`mode_*`, `ch_*`):
- **Page 4** is built by the game from a table (texts 281..287, kinds 0 label / 1 button, y 160,
  220, 260, 340, 400, 440, 520). `mode_build` (page_build dispatch) turns item 3, the label "Zwei
  Spieler" (never selected), into a button (kind 1, y 300, text 150) and appends the label again
  (y 350). The game's item numbers stay; `mode_update` catches "select" on item 3, all else goes
  to the game's handler 0x41D400. Up / down steps by item number, so 1 -> 2 -> 3 -> 4 is right.
- **Page 22h** (`ch_build` / `ch_update`): items 0 Zufall, 1 Täglich, 2 Weiter, 3 Zurück, then the
  labels (track + metres + start + driver; the tuning values with `values_text_id` /
  `top_text` like the pause page; daily: best time via 0x411FA0 "mm:ss:hh" or "noch keine Zeit").
  Test builds route `tune_pressed` to MENU_INJ, so tests press keys on both pages.
- **The draw** (`ch_draw`, Python mirror `challenge_draw()`): xorshift32; track % 8, start % 1000
  per mille, metres 1000 + % 601 -> share of `CH_PATHS` (measured: 2222, 1799, 2860, 3401, 1260,
  2641, 2906, 2435), kept in 0.3..0.7; character % 7; set % 64 of `challenge_sets()` (random grid
  values, gravity 50..200, kept when `tune_limit` level >= 1). Seeds: GetTickCount (IAT
  0x59514C); daily: day = FILETIME / 864e9 (GetSystemTimeAsFileTime, IAT 0x59511C, UTC) * 9E3779B1h
  xor 5EED35h.
- **Settings swap** (`CH_SWAP`: gp+10h class, 1Ch mode, 20h track, 4Ch switch dword, 58h
  character, the eight TUNE_VALUES; saved at CH_DATA+40h). `ch_arm` runs `tune_defaults` first
  (a save without the tuning marker would otherwise get the defaults over the challenge's
  values at race start) and swaps; `ch_disarm` swaps back on page 4 / the main menu (main menu
  object only, not the race overlay). Both writes of settings.dat (`File::Write` at 0x4122BB in
  the menu end fn 0x412100 = every race start, and 0x403B72 in GameMK2::Exit) are wrapped with a
  swap, so the file never holds a challenge.
- **Trap: gp+4Ch low byte.** It is the game's own bool. When it is 0, the race start (0x408777)
  takes a debug path: track from the config's "level", 150 cc, Moorhuhn. The first draw left it 0
  (the swap had put the empty save area there); `ch_draw` now keeps the player's byte.
- **Time:** the game's total time is the sum of the three lap times (fn 0x4378D0); a challenge
  counts no lap, so `ch_finish` writes the lap timer car+250h as lap 1.
- **Daily:** `ch_promote` (in `phantom_promote`) copies new-phantom.mhk2 to
  `data\Phantom\daily-<day>.mhk2` when faster than the day's best, and keeps marker `DAYC`, day,
  time at gp+`DAILY_ENTRY` (0x2BB0; file 0x2BAC; 50 cc "track 60", never reached). The ghost
  hooks load that file (random: an empty name). Old days' files stay.
- **Restart** ("Rennen wiederholen") runs the grid hook again: same start, done 0. Tested.
- Section `.mod200` grew to 0x7000.
- Test: `challenge_flow.py builds\ch <out> [--random] [--tuned]` (27 / 18 / 24 checks, all pass
  on 2026-11-27): page 4, page 22h, draw = Python mirror, settings.dat at race start, race,
  shortened stretch finish, no name entry, daily file and best time, restart, main menu swap
  back, best time line and ghost on the second daily race.

## Tools and test (2026-11-27)

- `datpack.py` writes an archive; `data\mhk2-02.dat` in a sandbox game replaces entries of
  mhk2-00/01. Round trip checked with datlist / datextract / mhk2crypt. Keep CRLF in edited
  objects.txt (Git Bash `sed` strips it; edit in Python).
- `startpos_test.py <game folder> <out.csv> --dat <archive>`: time trial (150 cc, track 1) with full
  throttle and no steering, records position, progress, wraps and laps per frame; removes the
  archive after the game has exited. Archives (ignored by git): `work\startpos\mhk2-02_50.dat` /
  `_25.dat` = track 1 with offset 0.5 / 0.25 (stock 0.982). Results in `runs\startpos\`.
- **Result: a moved start works without any exe change.** The kart stood at exactly the offset
  (progress 0.4999 at (-223.9, 3.05, 37.5); 0.2500 at (-11.0, 13.1, 114.0), on a raised part),
  standing still, facing along the path: progress rose from the first metre, and it drove off
  normally (23 units/s after 2 s, as from the stock grid). Without steering it then hit walls,
  as expected.
- Lap logic with a grid outside the start box: car+234h stays -1 and car+230h stays 0 until the kart
  first enters the box, laps stay 0. Harmless for a challenge, whose finish replaces the lap test.
  On the stock grid car+234h becomes 1 at once and car+230h counts the wrap at progress 0.
- Not yet checked: starts in a sharp bend, on a jump or a slope (only two places tried, one track);
  races with computer karts and the HUD (track line, lap display) from a moved start.

## The user's first look (2026-11-27) and the fixes (fourth commit)

- **Result overlay (page 0Eh)** listed laps 1..3 and *Gesamt* (texts 361..364, blocks from
  0x422643; duel / 2P use a second set from 0x422C1F). In a challenge `ch_result` replaces them
  (see "Result lines" below).
- **Total 4:32 for a 2.6 s run:** at the race end fn 0x437920 gives every kart with car+264h < 3
  estimated lap times (average of its laps, else 90 s, times a random factor) and sets car state
  4. `ch_finish` now also sets car+264h = 3. The phantom header (written at the finish) had been
  right all along.
- **Phantom driver:** the race start creates the phantom car (Car ctor 0x42F430, byte +2ACh = 1,
  in the car list) with the character [gp + slot * 6Ch + 0A9ECh] at 0x4099B1 = +54h of the
  header table (gp+0AA04h) entry of the normal phantom of that class and track, not of the file
  it loads. Character of a car: +330h (set by 0x4343E0). `ch_ghostchar`: player 1's character
  (gp+58h) in a challenge.
- **Minimap:** the stretch is magenta 0xFFE040FF now (yellow looked too much like the green dot).
- **Pause page:** `pause_ch` (from `pause_info`, frame grown to 380h): *Tägliche
  Herausforderung: dd.mm.yyyy, Bestzeit: …* or *Zufällige Herausforderung: Seed n* (CH_SEED0,
  the former CH_UNUSED, keeps the seed), then values, top speed and ", Strecke: …, n m ab p %,
  Fahrer: …" in one label. Date: `ch_date` (Hinnant's civil_from_days; mirror
  `challenge_date`, checked against datetime). Texts 157..159, 167. The 4 lines fit above the
  stock items (picture `runs\challenge\flow2\7_pause.png`).
- `challenge_flow.py` checks all of it (daily 33, random 26, tuned 33 checks).
- Not changed: the HUD's *Bestzeit* (top right) stays "--:--:--" in a daily race, and the result
  list (0Fh) after *Weiter* shows the tuning class's normal highscore list of the track.
- **Result lines (user, 2026-11-27):** "Deine Zeit: …" (header time gp+FB04h+58h), and in a daily
  challenge "Bestzeit: …" or the green "Neue Bestzeit!" (texts 168..170, y 270 / 320; random: the
  first line only). `ch_result` builds them and jumps to 0x4233B5, where all stock line blocks
  end. `ch_promote` sets CH_NEWBEST (CH_DATA+34h) when it copied a faster daily run (0 else), so
  a tie shows "Bestzeit".
- **Result list and HUD (user, 2026-11-27, sixth commit):** page 0Fh builds its buttons
  (0x413C00, items 0..2, y 440 / 490 / 550), a line (0x413980), then the table (string array
  0x560470 / 0x560410, rows 0x4207D0, labels 0x413B10) and the title "Highscore" (0x413CE0),
  ending at 0x424658 (selection = ebx, [menu+144h] = ebp = -1). `ch_list` (0x42351F) skips from
  the buttons to that end and adds `ch_result_lines` and the title *Herausforderung*. HUD best
  time: Hud::Draw formats [Hud + player*4 + 18h] (best lap) with 0x418090 at 0x41965C;
  `ch_hudbest` puts the day's best there (daily, marker and day match). Hud+10h / +14h are the
  other two times. Flow tests: daily 36, random 28 checks.

## A power can in every challenge (user, 2026-11-27; built, see below)

The user wants it simple: every challenge gives one *Powerdose* (power can), no rule draw.
Traced so far (read only):
- **The held power-up** is car+270h (-1 none; 7 = turbo can, the values of car+274h). The car
  fires it in Car::Update (0x4330FA..0x433129): controller [car+1F4h] with byte +22h set (fire
  key), car state 2, car+270h >= 0 -> `ActivatePowerUp(car+270h)` 0x42D320, then car+270h = -1.
  Nothing there checks the race mode, so a time trial should fire it too.
- **The phantom replay** (0x433203..0x43325D) writes a word of each sample into car+270h and
  fires it the same way: a phantom shows where its run fired the can. Check that the recording
  stores it for the player too.

Steps:
1. Give the can: in `ch_finish` (it runs every frame for car 0 in car state 2), set car+270h = 7
   once, with a flag that `ch_grid` clears (race start and *Rennen wiederholen*). Writing it in
   the grid hook may be too early if the car reset clears car+270h after it; check where 0x42FAC4
   / 0x436EF0 (the lap resets) clear the power-up.
2. HUD: check that the icon top left shows the can (in a time trial it shows the crossed-out
   circle; find whether that is "no power-up" or "time trial").
3. Physics: fire the can on all 64 challenge sets on a straight (`pu_run.py`-like). The can's
   accel factor 5.0 stacks with the set's pull; with pull > 1 the stock classes overshot by 10
   units/s. No set may blow up (runaway check as in the races). Drop or change sets that do;
   that changes `challenge_sets()` and so every draw: give the draw a version then.
4. Texts: the challenge page and the pause page say that the race has a *Powerdose*; docs.
5. Tests: `challenge_flow.py` checks car+270h = 7 after the start and fires it (find a test
   input for the fire key, or call 0x42D320 remotely), then car+274h = 7 and car+270h = -1.

## Medals (bronze, silver, gold; plan below, built 2026-11-27, see the end)

Goal: a target time for every draw, also for random seeds (2^32 of them, so nothing can be
measured per seed). The patcher ships pace tables measured in the sandbox; the game adds up the
stretch from them at the draw.

1. **Pace tool** (`stretch_pace.py`): a computer kart with the learned driver (*Verbesserte
   Gegner*) drives with one challenge set on one track, alone, two laps. It records the race
   time at path progress k/64 on the flying lap. 64 sets x 8 tracks = 512 runs, about 3 h on
   three game folders.
2. **Standing start**: the stretch starts from standing. Measure per set the time lost against
   a flying pass (start at 3 places per track, compare with the table). One value per set.
3. **Table size**: full curves are 512 x 64 x 2 bytes = 64 KB. Smaller: one curve shape per
   track (64 points) and one lap time per track and set, about 2.2 KB. Use the small form if
   step 4 shows under 2 % error; else one shape per group of sets (by top speed).
4. **Check**: the computer kart drives 30 real challenges from their start (the challenge code,
   with the kart of player 1 given to the AI); compare with the estimate.
5. **The can**: the reference kart drives without it. Measure per set what one well-placed can
   saves (fire at the start of the longest straight of the stretch, or at the start), and make
   gold need it.
6. **Medal times**: gold / silver / bronze = factors on the reference (start: 0.97 / 1.0 / 1.1),
   set after the user drove some daily challenges. Python mirror `challenge_medals(seed)` for
   the tests.
7. **Display**: the challenge page and the pause page show the three times; the result shows the
   medal won; the daily best keeps its medal. Maybe a medal icon later (needs a picture in an
   archive).
- **Built (2026-11-27): the power can.** `ch_finish` sets car+270h = 7 on the first frame in car
  state 2 (flag CH_CAN = CH_DATA+38h, cleared by `ch_grid`, so the restart gives a new one). Not
  on the challenge page or the pause page (user: a static feature of the mode). Test: the flow
  writes the controller's fire byte [car+1F4h]+22h in a loop until car+274h = 7. Physics check:
  `ch_can_check.py` races the 64 sets (8 per track, 60 s, six computer karts that get a new can
  whenever they hold none; `ai_race.py --cans`, `tune_races.py --cans`). Results below.
- **Can races (2026-11-27, `runs\ch_can`):** 64 sets x 60 s, 833 cans fired: no blow-up on the
  ground (fastest 133 units/s, about 480 km/h, with can and slope). Two "runaways", both on Sumpf
  (sets 55 and 63), were karts falling out of the world, not physics: reruns of these two sets
  gave a fall in 3 of 5 races with cans, in 0 of 6 without. Set 63 crested a rise at x 30 z 240
  at 107..116 units/s and flew over the course's edge; set 55 (Motorkraft 525 %, Gewicht 25 %)
  flipped and drove off a ledge at x -275 z 135 at 40 units/s. The computer karts came back after
  7..9 s through the patch's watch (computer karts only). **A player who leaves the world falls
  until *Neustart*** (pause page): no reset for the player outside the drop boxes. Not changed;
  the tuning class has the same risk without a can. Options if it matters: a challenge reset when
  y drops 30 units below the road, or drop such sets.
- HUD: the icon top left shows the can while held (picture `runs\challenge\flow6_random\4_race.png`).
  Flow tests: daily 39, random 31, tuned 39 checks (the test fires the can in both runs: it does
  not steer, and a draw in a bend finished only with the can).

## Medals as built (2026-11-27, sixth commit)

- **Model** (`challenge_medals()` in the patcher, asm `ch_medals`, called at the end of
  `ch_draw`): ref = ((C_t(start+share) - C_t(start)) x CH_PACE_LAP[t] x CH_PACE_SET[s] +
  CH_PACE_LOSS[s]) x CH_PACE_CHAR[c]; C_t = cumulative share of CH_PACE_SHAPE[t] at 65 points
  (`ch_cum` builds float32 tables at build time), linear between, C(e-1)+1 behind the wrap. Medals
  = round(ref x (0.66, 0.74, 0.85) x 100) / 100 into CH_MEDALS = CH_DATA+80h (3 floats). CH_SET =
  CH_DATA+3Ch holds the drawn set (`_draw_set()` = the fifth xorshift number % 64).
  `CH_MEDAL_FACTORS` (first 0.97 / 1.0 / 1.1, "far too easy") are set from the user's first
  daily challenge (2026-11-27, Insel 1185 m, reference 29.0 s): 20.60 s without the can (0.71),
  18.12 s with it (0.62); the user chose gold 0.66 (needs the can), silver 0.74, bronze 0.85.
  One player, one draw: check again with more runs. The earlier Insel recordings gave 0.70.
- **Display**: page 22h, a line at CH_Y_LINES[2] (text 171, the best line moved to [3]); the
  pause page, a fourth line (text 172) behind track and driver; the result (texts 173..175 for
  gold..bronze, 176 "Keine Medaille (Bronze: %s)"), compared with fcom: time <= medal wins.
  Colours CH_MEDAL_COLORS (gold, silver grey, bronze).
- **Pause page compacted for room**: texts 131/133 (volume headings) empty, 132/134 carry the name
  ("Lautstärke Musik: %d %%"); PAUSE_Y_NEW moves all seven items (data patches at 0x413E92 +
  8 x row, buttons at 0x413FE1, 0x41405B, 0x4140D2). Empty texts are fine: the game shows
  nothing, no fallback. `classtest.py pause` expects the new stock list.
- **Measurement** (`stretch_pace.py` -> `pace_sNN_tN.json` in `runs\medals\pace`):
  `ai_race.py` championship race, class 5 with the set's values, `--tempo 100 --improved 6
  --physics60 --char (s+t)%7`, `--seconds auto` = max(75, path/2222 x 100). Per kart the
  crossings of each 1/64 of progress (car+224h unwrapped). `pace_table.py`: the q30 quantile per
  segment over all karts and laps, 8 segments after the grid skipped; loss = time at the 8th
  crossing - flying time from p0 (the race clock starts at "go"), the minimum over the karts.
  Several crossings in one frame (a reset jump) give no segment time.
  `pace_fit.py <dir> --check`: alternating least squares on log lap = log T[t] + log F[s];
  partial runs (slow sets that cover no full lap) estimated from their segments against the
  track's mean shape; shape per track = mean of the runs' shares; loss per set = median;
  character = geometric mean of the karts' median ratio to the table. Prints the CH_PACE_ lines.
- **Runs**: tracks 0 and 4 with all 64 sets, tracks 1-3 and 5-7 with sets 0..7 (plus whatever the
  first pilots covered), about 160 runs on three game folders (about 4 min per run).
- **Results** (157 runs, `runs\medalsit.txt`): leave-one-out over tracks 1-3, 5-7 (45 runs):
  lap error mean +0.4 %, abs median 3.5 %, max 29 %; random stretches abs median 4.5 %, 90 % below
  16 %. Worst: set 2 (Lenkung 50 %, Schwerkraft 200 %, Anpressdruck 775 %: karts stuck, +-30 %)
  and set 4 on track 2. Set factors 0.67..2.18; lap times 33.7 s (Insel) .. 70.3 s; standing loss
  0..2.8 s; characters 0.986..1.022. Partial runs need 32 of 64 segments
  (set 7 on track 7 covered 16 with stuck karts and gave a 436 s lap that spoiled track 7).
  Shapes have spikes (up to 5x a segment) where the computer karts crash or slow in a bend.
- **Display rounding**: a medal of n hundredths is stored as (n + 0.99) / 100 (`CH_MEDAL_UP`);
  TIME_TEXT cuts hundredths, so 23.94 as float32 (23.93999) showed 23:93 before.
- **Flow test stretch**: 0.006 of the path (was 0.02): the test does not steer and a bend 22 m
  after the start of two random draws ended in a wall.
- **Not done**: step 4 (the computer kart driving real challenges from their start), step 5 (what
  the can saves; gold does not need the can yet), a medal kept with the daily best, an icon.
- **150 cc floor (2026-11-27, user: "the top speed should be not slower than 150 ccm (would be too
  boring otherwise)")**: `challenge_sets()` keeps a set only when `top_speed()` >= the preset
  *150 cc* for every character (`CH_MIN_TOP_PRESET`; 150 cc = 50.5 units/s, about 180 km/h for
  character 0, 160 for the slowest; the user had thought 130). 18 sets went (down to 45 km/h on
  the page; set 18 = 320/100/225/25/275/150/450/200 showed 45 km/h, the user drove about 80, so
  `top_speed` is wrong that far down). The kept sets keep their order (indices 0..45), the new
  ones are 46..63; every draw changed, including the daily of 2026-11-27 (the user's seed
  41853500 had set 18 and medals no one could reach: its lap on Moorhuhn X came from a partial run
  of stuck computer karts). Old runs in `runs\medals\pace_v1`, kept runs renamed into `pace`.
- **Refit with the new sets (2026-11-28)**: 36 runs of sets 46..63 on tracks 0 and 4; 160 runs:
  lap check abs median 2.6 %, stretches 4.2 %, 90 % below 14.9 %; set factors 0.75..1.76.
- **Top speed cap (CH_MEDAL_CAPS 0.93 / 0.82 / 0.72, 2026-11-28)**: the computer karts' average
  speed against `top_kmh` (character 0) per track, median: Moorhuhn X 0.91, Ägypten 0.98 (up to
  1.23), Insel 0.59, the rest 0.75..0.81. A human averaged 0.82 (no can) / 0.93 (can) on Insel.
  With the new tables the dailies of 11-28 and 11-29 had gold at 1.02 / 1.03 of the top speed, so
  each medal is now max(AI time x factor, metres / (km/h / 3.6) / cap) before the rounding;
  `ch_medals` calls `tune_top` (edx = the values, the character from gp+58h) first. Suspects for
  the fast computer karts: the item boxes of their championship races (power-ups), resets that
  move a kart forward. Not checked. A recording of the user's challenge runs (`race_recorder.py`
  stores the challenge since then: seed, set, start, length, medals) shows the human side.
- **The cap decides most draws**: in 1000 random seeds, 87 % (gold) to 88 % (silver, bronze) of
  the medal times are the cap's, not the computer karts'. So the medals are mostly "the stretch at
  93 / 82 / 72 % of the top speed", blind to bends and hills; the pace tables matter only where
  the computer karts are slow (Insel, slow sets). Next: the user's daily runs with the recorder;
  if bends make 82 % too hard on twisty stretches, a share per track or from the shape table.
- **The cap was wrong; factors from the user's runs (2026-11-28)**: the user recorded 13 challenges
  (`runs\user\20261128_0037..0100`, 1 to 18 tries each, all best runs with the can;
  `challenge_runs.py` lists them). Their average speed was 57..115 % of the top speed (fast sets
  57..78 %: the bends limit; slow sets 87..115 %: downhill and the can), so the cap set every
  silver and missed by x0.71..x1.63. Against the computer karts' time (no cap), per track index:
  0.87, 0.91 (1), 1.03, 1.05, 1.08, 1.29 (2 = Insel), 1.06, 1.20 (0 = Moorhuhn X), 1.09, 0.93,
  1.37 (3, 6, 7), 1.77 (5, a crashed run). The daily of 11-27 (Insel, set 24 now, Anpressdruck
  775 %) against the new tables: 0.65 with the can, 0.74 without; an outlier of set and track,
  not Insel (track 4 is Fabrik, not Insel: I mixed them up once and put a 0.65 factor on track 4,
  removed before the commit). The cap is gone; CH_MEDAL_FACTORS = 0.95 / 1.05 / 1.2. With them
  the 12 best runs give 3 gold, 2 silver, 3 bronze, 4 none (one 0.1 s off bronze). So "a good
  player is 30 % faster" came from that one outlier.
- **Day change fixed (2026-11-28)**: `ch_today` divided FILETIME by the day in x87; the game runs
  the FPU in 24-bit precision, so near midnight UTC the day was one off (a flow at 00:05 UTC got
  the day before). Now integers: shrd by 14, two `div` by 52734375 (DAY_100NS = 2^14 x that).
