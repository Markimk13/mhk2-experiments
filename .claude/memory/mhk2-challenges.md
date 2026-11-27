---
name: mhk2-challenges
description: "The idea of async challenges (a seed gives a ~20 s stretch of a track, tuning values and character; players send each other the seed and their phantom; a daily seed from the date) and what the exe offers for it (a moved start tested, works without exe change): where the race-start grid is placed, how a finish on path progress could replace the lap count, why segment phantoms need no change; tools datpack.py and startpos_test.py"
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
- **A challenge finish writes the normal record and phantom**: the 4.4 s run became the 150 cc
  record of track 1, and the patch made it `phantom-3-01.mhk2` (590 bytes). The next run showed that
  ghost as a red, see-through band on the road. Must be fixed before a release: challenge times and
  phantoms in their own place. Restore after such tests: `fixtures\settings.dat`,
  `fixtures\Phantom\` (done for game, game2, game3).
- Pictures with three games open catch whatever window is on top (the capture takes the screen
  area); take pictures with one game at a time.
- Short stretches are only a few path points on the minimap: 0.03 of track 1 is about 4 points.

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
