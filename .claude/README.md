# .claude – notes, sandbox and working tools

Everything Claude learned or built for this project outside the patcher itself. It is kept
here, next to the project, instead of in Claude's private memory folder and in temp folders.
[CLAUDE.md](../CLAUDE.md) in the repository root links to it.

## memory/

A mirror of Claude's memory for this project. `MEMORY.md` is the index, one line per note.

| Note | Content |
| --- | --- |
| [mhk2-user-context.md](memory/mhk2-user-context.md) | Who the user is in this project |
| [mhk2-windowed-test-recipe.md](memory/mhk2-windowed-test-recipe.md) | Running the real game in a window, unattended |
| [mhk2-fps-physics-root-cause.md](memory/mhk2-fps-physics-root-cause.md) | Why 200 FPS drives differently, and the fix |
| [mhk2-phantom-and-manager-internals.md](memory/mhk2-phantom-and-manager-internals.md) | Phantom files, the game's ghost handling, mhk2_manager's formats, patch 1.2 |
| [mhk2-powerups-and-class-factors.md](memory/mhk2-powerups-and-class-factors.md) | Siren and power can, measured speeds, matching class factors |
| [mhk2-kart-parameters.md](memory/mhk2-kart-parameters.md) | Kart values from karts.txt and their offsets, differences between the characters, what a class changes, the downforce and drag code, standing starts |
| [mhk2-engine-classes.md](memory/mhk2-engine-classes.md) | How 200 cc, 250 cc and the tuning class are wired in: class-dependent code, table slots, text ids, unlock chain |
| [mhk2-tuning-class.md](memory/mhk2-tuning-class.md) | The tuning class: what its seven values do, the downforce rules, races at the limits, the presets (Vorlage row, own presets) |
| [mhk2-tracks-and-championships.md](memory/mhk2-tracks-and-championships.md) | How the game finds tracks and championships, the track files, reversed tracks, the plan for an own track |
| [mhk2-computer-kart-ai.md](memory/mhk2-computer-kart-ai.md) | How the computer karts are held back, and the catch-up of the new classes |
| [mhk2-public-release.md](memory/mhk2-public-release.md) | How the project became public, what never goes into this repository, the release zips |
| [mhk2-showcase-video.md](memory/mhk2-showcase-video.md) | The ~1 min clip of the patch: filming, scene times, cutting |
| [mhk2-notes-live-in-repo.md](memory/mhk2-notes-live-in-repo.md) | Why this folder exists |

The files keep the front matter of Claude's memory files (name, description, type). Claude's
private memory folder for the project may hold copies; when a note changes, both copies should
change.

## notes/

Other write-ups that were lying in scratch folders.

| Note | Content |
| --- | --- |
| [exe-physics-constants.md](notes/exe-physics-constants.md) | Gravity, time step, frame limit from the exe (July 2026, with corrections on top) |

## sandbox/

Where the exe is taken apart and the patch is tested. Nothing in it is needed to build or use
the patch. Git keeps the scripts and the test fixtures; the rest is ignored (`.gitignore`)
because it can be rebuilt or is the output of test runs.

| Folder | In git | Content |
| --- | --- | --- |
| `tools/` | yes | The scripts, see the table at the end |
| `fixtures/` | yes | `Phantom\` and `settings.dat` every test scenario starts from: the game's 24 original phantoms and the user's `settings.dat` as it was on 2026-11-18 (highscores; muted and set to 640x480). The times and ranks the tests expect belong to these files |
| `work/` | no | `MHK2-XXL.orig.exe`, its disassembly (`disasm.txt`, `disasm.pickle`), texts taken out of the game data (`cfg\karts.txt`, …), listings of single functions |
| `game/`, `game2/`, … | no | Game folders to run (the extra ones for test games side by side, made by `gameslot.py`): `data\mhk2-00.dat`, the test builds (`ghost_new.exe`, `ghost_mouse.exe`, `c5_new60.exe`, `ghost_orig.exe`), `settings.dat`, `data\Phantom` |
| `builds/` | no | Outputs of the patcher that were checked or tested, with their listings |
| `runs/` | no | Recordings and logs of test runs; `runs23` is the verification of patch 1.4 |
| `shots/` | no | Screenshots the tests take |

### Rebuilding it

```powershell
py .claude\sandbox\tools\setup_sandbox.py
```

The game files are not in git. `.claude\sandbox\local.json` (ignored by git) says where they
are on this PC; `tools\paths.py` reads it and describes the format:

```json
{
  "original_exe": "D:/Games/Moorhuhn Kart 2/MHK2-XXL.exe",
  "game_data": "D:/Games/Moorhuhn Kart 2/data/mhk2-00.dat",
  "v11_data": "D:/Games/Moorhuhn Kart 2/data/source/mhk2-01.dat"
}
```

Only `original_exe` is required (the unpatched German V1.0). The files are only read.

The script builds `output\` with the patcher (ignored by git), copies the original exe to `work\` (SHA-256 starts with `272bfad50336ec4c`,
2 244 608 bytes), disassembles it with Visual Studio's `dumpbin.exe` (31 MB of text, 556 010
instructions) and indexes that for `dis.py`, takes `karts.txt`, `config.txt` and `text.csv` out
of `mhk2-00.dat`, copies that file to `game\data` (144 MB), restores the fixtures and makes the
test builds from `output\MHK2-XXL.exe` and the original. Run it again whenever the patcher
changed; `--no-disasm` skips the disassembly. `builds\`, `runs\` and `shots\` hold
results only and fill up again as tests run.

A test build (`prep_class5.py <exe> game\<name>.exe [frame cap] [--mouse]`, or `prep_ghost.py`,
`prep_opt.py`, `prep_fps.py`) is a windowed copy of the game that runs without focus and takes
its inputs from memory. Without a frame cap it runs at the game's own 200 FPS.

### Several test games at once

Every test game starts through `gameslot.spawn` (`optest.launch` and `optest.start` call it).
The game itself is single-instance: a second copy pulls the first one's window to the front
and exits. The test builds skip that lock (`pu_noinst.py`, applied by `prep_fps.build`), so
up to three of them can run side by side. `gameslot.py` keeps these rules:

- One game per game folder, because a game writes `settings.dat`, `log.txt` and `data\Phantom`
  there. A test claims its folder with a lock file (`.claim.lock`) that Windows frees when the
  test process ends. `ghosttest.py` and `classtest.py` take the first free one of `game`,
  `game2`, `game3` (`MHK2_GAME=game2` picks one). An extra folder is filled from `game\` on first
  use (Phantom and `settings.dat` from the fixtures). `setup_sandbox.py` updates the extra folders too.
- Nothing starts while the user's real game runs.
- At most `MHK2_MAX_GAMES` test games (default 3) on the whole PC, all sandboxes and worktrees
  together. Each one keeps one CPU core busy.
- A build that still has the single-instance lock (an old build, the original exe) runs alone,
  after 40 s without any game.
- One start at a time on the whole PC, until the game reaches its menu.

`py .claude\sandbox\tools\gameslot.py` lists the running games;
`py .claude\sandbox\tools\parallel_check.py` checks all of this with two live games. The pid
of a started game is in `<game folder>\game.pid`.

### Running the tests

`jobs.py` runs the checks as small jobs, three at a time, each in its own game folder. A job is
one classtest or ghosttest scenario, one race set or one straight run. Each worker takes the
longest job left, using the times of earlier runs (`runs\jobtimes.json`).

```powershell
py .claude\sandbox\tools\jobs.py <name>
```

That runs everything: test builds from `output\`, then 62 jobs, in about 16 minutes (47 when run
one after another). Results go to `runs\<name>`: `summary.txt`, `progress.log`, one log per job
in `jobs\`, and the joined logs (`classtest.log`, `ghosttest.log`, `corners.log`, `singles.log`,
`tune.log`, `classes.log`, `lift.log`, `ai.log`). After a change, run only the part it touches:

```powershell
py .claude\sandbox\tools\jobs.py <name> classtest --no-setup
```

Selectors are groups (`classtest`, `ghosttest`, `races` = `corners` + `singles`, `straight` =
`tune` + `classes` + `lift` + `ai`), single jobs (`classtest:tt250`) or prefixes
(`classtest:tune`). `py .claude\sandbox\tools\jobs.py --list [selector ...]` shows the jobs
and the expected time. classtest alone takes 4 minutes instead of 12. `--no-setup` skips the
test builds when `output\` has not changed. `sh .claude/sandbox/tools/run_checks.sh <name>`
(Git Bash) does the same as `jobs.py <name>`.

The scripts also run on their own, one game at a time:

```powershell
py .claude\sandbox\tools\classtest.py tuning tunemouse tuneown ownmouse tunekart tttune menu tt250 tt200 champ oldsave browser
```

```powershell
py .claude\sandbox\tools\ghosttest.py main cc200 options
```

`ghosttest.py` also has `stock version cliname import`. Every scenario first puts the fixtures
back into its game folder, so the scenarios do not depend on each other.

### Checking new patcher code

```powershell
py tools\patch_200cc.py "<original exe>" .claude\sandbox\builds\new --listing .claude\sandbox\builds\new\listing.txt
```

```powershell
& "<dumpbin.exe>" /disasm /section:.mod200 .claude\sandbox\builds\new\MHK2-XXL.exe > .claude\sandbox\builds\new\mod200.dis.txt
```

```powershell
py .claude\sandbox\tools\verify_listing.py .claude\sandbox\builds\new\listing.txt .claude\sandbox\builds\new\mod200.dis.txt
```

The last command must report 0 mismatches. `dumpbin.exe` is in Visual Studio's folder
`VC\Tools\MSVC\<version>\bin\Hostx64\x86`.

### The scripts

| Group | Scripts |
| --- | --- |
| Setup | `paths.py` (where the game files are: `local.json`), `setup_sandbox.py` (rebuilds `output\`, `work\` and `game\`), `jobs.py` (all checks or a part, as small jobs on three game folders at once), `run_checks.sh` (the same for Git Bash) |
| Disassembly | `dis.py` (navigation over the dumpbin listing), `pestrings.py`, `iat.py`, `gpuse.py` (who uses which GameParameters field), `fnlist.py`, `vt.py`, `decall.py`, `dispscan.py`, `findptr.py`, `showsites.py` |
| mhk2_manager | `build_manager_jar.py` (compiles ..\mhk2_manager for Java 8 and builds its jar in the 2020 layout, into `manager\`), `ManagerCheck.java` (headless check of the manager's phantom code with the new classes, in a scratch folder) |
| Game data | `datlist.py`, `datextract.py` (the `mhk2-NN.dat` archives), `mhk2crypt.py` (cipher of the `.txt` files inside), `settings_dump.py`, `settings_diff.py`, `phantom_slots.py` |
| Test builds | `prep_fps.py` (windowed, frame caps, unattended; the test builds' command slot also has a copy routine and an add routine that adds float deltas to a list of addresses in one frame, `COPY_VA` / `ADD_VA`), `prep_opt.py` (menu page command, injected menu keys and mouse; `prep_class5.py` adds "menu up" / "menu down" for every page, `NAV_INJ`), `prep_ghost.py` (name entry), `prep_class5.py` (the same plus "select" on the engine class menu and the championship trophy page, left / right in the highscore browsers, the inputs of the tuning page; `--mouse` for a simulated mouse), `pu_noinst.py` (drops the single-instance lock; every build above gets it), `prep_test.py` (first version) |
| Driving the game | `gameslot.py` (starts every test game: own game folder, limit, never next to the user's game), `harness.py` (process, memory, screenshots), `optest.py` (start without focus, menu), `focusguard.py` (safety net: asks the game to hand the focus back, should it ever have it), `remote_test.py` (has the game call its own functions through the test build's command slot; nothing is injected), `ghostlib.py` (time trials, forced finish, result pages, name entry) |
| Test runs | `jobs.py` (see Running the tests), `parallel_check.py` (two test games side by side: start rules, focus, own pid, CPU), `ghosttest.py` (phantom karts), `classtest.py` (200 cc, 250 cc, tuning class: class menu, records, phantom files, unlock chain, championship highscores, highscore browsers, the tuning page with keys and with a simulated mouse, kart values), `focus_probe.py` (how long a test build holds the foreground while it starts), `class_runs.py` (standing start and top speed of a class), `tune_runs.py` (straight-line runs of the tuning class with given values), `tune_shot.py` (picture of the tuning page with given values and a selected row), `page_look.py` (opens any menu page and prints its items), `pause_look.py` (pauses a sandbox race and takes a picture of the pause page, with given tuning values and switch), `topspeed.py` (top speed on an endless straight: the kart jumps back along Ägypten's start straight; single runs or resumable sets on three games, any character), `topspeed_fit.py` (fits the patcher's top speed model to those runs), `topspeed_check.py` (drives a preset on the endless straight and compares with the shown top speed; jobs group `topspeed`), `hud_look.py` (drives a race and takes a picture of the HUD with the speed), `release_check.py` (builds the release zips with the public repo's `make_release.py` and this repo's patcher into a sandbox folder and checks them, then checks the public repo: a CHANGELOG section for the release, its patcher copy; jobs group `release`), `tune_pages_look.py` (pictures of the four tuning pages with given values and a selected item), `tune_races.py` (races of the tuning class with computer karts for sets of values, at any frame rate; flags karts whose speed runs away), `tune_sweep.py` (many races of random or given value sets, three games side by side, resumable; badness numbers per race), `tune_sweep_fit.py` (fits the *Am Limit* risk points to those races and prints the patcher's `LIMIT_POINTS`), `tune_limit_check.py` (races grouped by what the *Am Limit* line shows), `preset_search.py` (searches preset values per idea with the *Am Limit* computation), `preset_report.py` (raced preset candidates side by side), `pu_run.py` (straight-line run with a speed power-up switched on and off from outside, or with the throttle lifted at a given speed), `pu_survey.py` (length of every start straight), `regress_drive.py` (speed per class from a standing start), `explore2.py` (trace of race phase and car state around a forced finish), `browser_shot.py` (picture of the highscore browser), `savetest.py`, `mousetest.py`, `optrace.py`, `text_test.py` (options switch), `physruns.py`, `drive.py`, `run_variant.py` (physics measurements), `ai_race.py` (records every kart of a race with computer karts; `--ai-flat F` sets their throttle table, `--tune` takes seven or eight values), `gravity_probe.py` (changes the physics world's gravity during a race and prints the kart's height), `race_recorder.py` (records the user's own races read-only, next to the running game: every kart, every frame, AI controller outputs; into `runs\user`; `--video` also films the game window with ffmpeg into `runs\user\video`, races synced to the millisecond; `--audio` records only the game's sound into a separate .m4a there, via `procaudio.py`; `merge_av.py` puts it under the video without re-encoding, `--fix` makes an .m4a of a killed recorder seekable), `ai_offtrack.py` (where computer karts were reset onto the track), `race_compare.py` (the player against the computer karts along the lap), `ai_batch_summary.py` (resets, speed and standing time per setting of a batch), `item_rate.py` (how often the computer karts fire power-ups, and how long they stand frozen after hits), `geo_build.py` (geometric driver: `geo_driver.asm` -> `asm2py.py` -> patcher -> dumpbin check -> geo60.exe / geo200.exe), `geo_params.py`, `geo_batch.py` (races value sets of the driver against each other and stock), `geo_summary.py`, `geo_resets.py`, `track_line.py` (a track's centre line, width and curvature from its road edge splines), `speed_profile.py` (speed profile from curves and physics, fitted against the resets of driver batches), `speed_signs.py` (crash spots of driver batches and the entry speed that separates clean passes from resets), `user_laps.py` (the player's laps in `race_recorder.py` recordings: lap times, resets, hits, where the kart left the road), `start_box.py` (every pass of a kart through the plane of the track's start box in a `race_recorder.py` recording: inside or beside / above it; a lap counts only inside), `learn_tables.py` (speed and line tables per track from the player's recorded time trials, written as `geo_tables.inc` for `geo_driver.asm`; `geo_free.json` lists the stretches where the learned speed overrules a speed limit box of the game, `geo_adjust.json` the changes of `table_repair.py`), `geo_duel.py` (races two table sets, or several driver settings, against each other in the same races: three karts each, 120 s, recordings kept; distance, time lost to incidents, resets, time per sixth of the lap), `geo_incidents.py` (resets and hits of the computer karts in recordings, by place of the lap, with the seconds before each), `hang_spots.py` (where computer karts stand for a second or more, joined by position, and how each hang ended; also reads the user's own races from `race_recorder.py`), `no_progress.py` (how long karts go without getting beyond their farthest place), `watch_report.py` (compares the even and the odd races of a `geo_duel.py --odd "..."` batch, for example the watch on and off), `opp_races.py` (races with the two values of the page *Gegner* in any class: how far the improved karts and the game's get, how often they are set back; `--more` hands driver values per kart to `ai_race.py`), `race_result.py` (who finished when in a recording of `race_recorder.py`; a kart that finished before the player must be found by its finishing time, not by its distance at the end), `pack_report.py` (how the computer karts get in each other's way: stops, pile-ups, gaps between them; `--against` compares sets with z values), `geo_boxes.py` (the game's speed limit boxes in a `geo_duel.py` batch and the time through each with the box and with it overruled), `table_repair.py` (the search: finds the places where the karts with the learned tables get into trouble and races changes of speed and line there, four challengers against the champion table per race) |
| Evaluation | `hold_speed.py` (top speed from `pu_run.py` runs), `top_from_plain.py` (top speed from a plain standing start, through the force model), `class_model.py` (the force model: top speed and standing start for any gearing and pull), `ai_progress.py` (distance and speed per kart from an `ai_race.py` recording), `runaway_look.py` (the frames before a kart's speed runs away), `load_by_speed.py` (wheel load against speed: what the downforce does), `lift_check.py` (deceleration after the throttle is lifted), `analyze.py`, `rest.py`, `contact.py`, `corner.py`, `timeshift.py`, `ai_stats.py`, `ai_grip.py`, `gears.py`, `carinfo.py`, `carscan.py` |
| Patcher check | `verify_listing.py` |
| Video | `cut_video.py` (cuts a gameplay recording into a short clip with ffmpeg: scenes and labels from a text file, crops to the game picture, CAS sharpening, two-pass encode under GitHub's 10 MB; work files in `video\`; example scene list `cut_video_example.txt`), `video_scenes.py` (the race recorder's races at their times in an OBS recording; 1-second contact sheets for picking scene limits) |

They are working tools: small, made for one job, some superseded by later ones. The scripts
find the sandbox through their own location (`tools\..`).

`harness.py keys|hold`, `race_finish.py`, `champ_race.py`, `finish.py` and `watchstart.py` are
from before the "no keyboard, no focus" rule: they send real key presses and need the game
window in the foreground. Do not use them while the user is working on the PC.
