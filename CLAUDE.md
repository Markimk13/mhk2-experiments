# Moorhuhn Kart 2 – patch project

Loaded at the start of every Claude session in this repository. Details are in the linked
notes; read the ones the task touches. This repository is **public**.

## What is where

| Path | Content |
| --- | --- |
| `tools/patch_200cc.py` | The patcher. Builds a patched `MHK2-XXL.exe` and `text-20.csv` from the original exe: 200 cc and 250 cc classes (with faster computer karts), a tuning class, 60 FPS physics switch, own phantom karts. Pure Python, no dependencies. |
| `tools/make_release.py` | Builds the release zips (German and English texts) into `dist/`. |
| `README.md`, `docs/`, `CHANGELOG.md` | Documentation of the patch: `README.md` is the overview, `docs/` the details for players and developers, `CHANGELOG.md` one section per release. Structure and style: skill [public-docs](.claude/skills/public-docs/SKILL.md). |
| `TODO.md` | Technical details of the open points; the points themselves are GitHub issues of this repository (see [Public release](.claude/memory/mhk2-public-release.md)). |
| `screenshots/` | Pictures used by the README. |
| `.claude/` | Claude's notes (`memory/`, `notes/`) and the sandbox (`sandbox/`: test tools and fixtures in git; the game copy, disassembly, builds and test results there are ignored by git), see [.claude/README.md](.claude/README.md). |
| `output/`, `dist/` | Generated (patcher output, release zips); ignored by git. |

No game files are in this repository. `.claude/sandbox/local.json` (ignored by git) names the
original exe and the game data on this PC; `.claude/sandbox/tools/paths.py` reads it. On the
user's PC those files sit in `mhk2-originals/` (ignored by git), a copy taken from their game
folders; the game folders themselves hold real records and phantoms.

The manager program (`mhk2_manager`, github.com/Markimk13/mhk2_manager) is the user's own tool.

## Rules

- Never change the user's game folders or `mhk2-originals/`: the game folders are real installs
  with real records. Test in the sandbox, `.claude/sandbox/game` (a copy that git ignores;
  `py .claude\sandbox\tools\setup_sandbox.py` rebuilds it).
- Commit and push only when the user says so.
- A commit that worked on a GitHub issue names it in the message (user, 2026-11-26), on its
  own line at the end of the body, before the `Co-Authored-By` line: `Refs #12`. Several
  issues: `Refs #12, #15`. Use a closing keyword (`Fixes #12`) only when the user says the
  commit finishes the issue, because GitHub closes it when the commit reaches `main`.
- Version (user, 2026-11-22, suffix 2026-11-23): a release has two digits and raises the second
  (1.9 -> 1.10); every commit in between carries the next release with a `-preN` suffix
  (1.10-pre2), counted by the patcher itself (`patch_version()`: commits since tag
  `v<PATCH_RELEASE>` + 1).
- Docs during the work (user, 2026-11-26), in the structure and style of the skill
  [public-docs](.claude/skills/public-docs/SKILL.md):
  - `CHANGELOG.md`: every commit with a player-visible change adds its bullet to the section of
    the next release (`## 1.11`; create it with the first bullet), in the same commit.
  - `README.md` and `docs/*.md`: update them in the commit that finishes a feature or an issue,
    not in the steps before it, because names and settings still change during the work.
- At a release: run the checklist of the skill [public-docs](.claude/skills/public-docs/SKILL.md)
  over `README.md`, `docs/*.md` and `CHANGELOG.md` and fill every gap since the last release
  (user, 2026-11-24; the 1.9 sync missed parts). `make_release.py` refuses without a CHANGELOG
  section for the release, and it builds the two-digit number. Then set `PATCH_RELEASE` to it
  and tag the release commit `v<release>`. The release notes for the GitHub release page
  (`dist\release-<release>.md`, ignored by git) only link to the release's section in
  `CHANGELOG.md` at the tag (user, 2026-11-26), for example
  `https://github.com/Markimk13/mhk2-experiments/blob/v1.10/CHANGELOG.md#110`.
- Public repository: never commit game files (exe, `.dat`, extracted texts, disassembly), the
  user's records or phantoms, absolute paths with the user's name, or other personal data. The
  only game-derived files in git are the test fixtures (the game's original phantoms and a
  save). Check screenshots for player names. See [Public release](.claude/memory/mhk2-public-release.md).
- The user works on this PC while tests run. A test may not take the keyboard focus, send keys
  or move the mouse. Start test games only through the sandbox tools (`gameslot.spawn`): up to
  three test games at once, each in its own game folder, never while the user's real game runs.
  Stop only processes you started.
- The game is the German version: texts are German, text files are cp1252.
- Patcher conventions: every patch site checks the original bytes; new code is position
  independent and may not overlap a relocation; every new instruction is compared with
  dumpbin's disassembly before the exe is used (how: [.claude/README.md](.claude/README.md)).
- Knowledge about this project belongs in `.claude/memory/` (plus a line below), not only in
  Claude's private memory, and reusable helper scripts in `.claude/sandbox/tools/`. Working
  files (builds to check, test results, pictures) go into `.claude/sandbox/` too, not into a
  temp folder; what can be rebuilt is ignored by git. The user asked for this on 2026-11-18
  and 2026-11-19.
- Write GitHub issues, PR descriptions and docs in the style of
  [.claude/writing-style.md](.claude/writing-style.md) (user, 2026-11-23). Read it before you
  write one. For `README.md`, `CHANGELOG.md` and `docs/*.md`, use the skill
  [public-docs](.claude/skills/public-docs/SKILL.md): which reader each text is for, where it
  goes, the structure of each file.

## Notes

- [User context](.claude/memory/mhk2-user-context.md) – who the user is in this project: author of mhk2_manager, serious time trial player; new features go into the patch, never into the manager.
- [Unattended test recipe](.claude/memory/mhk2-windowed-test-recipe.md) – how to run the real game in a window without keyboard, focus or mouse, and the addresses that makes possible.
- [FPS physics root cause](.claude/memory/mhk2-fps-physics-root-cause.md) – why the game drives differently at 200 FPS (suspension stiffness follows the physics step) and how the switch fixes it.
- [Phantom karts and the manager](.claude/memory/mhk2-phantom-and-manager-internals.md) – phantom file format, how the game loads, blocks and imports ghosts, mhk2_manager's file formats and checksum, hook addresses.
- [Power-ups and class factors](.claude/memory/mhk2-powerups-and-class-factors.md) – how the siren and the power can work, measured top speeds, class factors that match them, the single-instance lock and how test builds skip it.
- [Kart parameters](.claude/memory/mhk2-kart-parameters.md) – the values in karts.txt and where they sit in the Car object, how the characters differ, what a class changes, the downforce and drag code, measured standing starts.
- [Engine classes](.claude/memory/mhk2-engine-classes.md) – every place in the exe that depends on the number of classes, the slots and text ids the added classes use, the unlock chain (the tuning class after Meisterschaft 2 in 250 cc), the switch *Alles freigeschaltet* (1.10), how to test it.
- [Tuning class](.claude/memory/mhk2-tuning-class.md) – the sixth class: what its nine values do (seven kart values on the page *Kart*, the gravity on *Welt*, the pace of the computer karts on *Gegner*), why much downforce blew the physics up and the three rules against it, races at the limits, the presets (the *Vorlage* row with built-in presets, the page *Eigene Vorlagen* with eight own slots and renaming), the 1.6 → 1.7 save conversion, the green *Am Limit* line (a fit to about 1250 races of the computer karts), the *Top speed* line (a fit to about 420 runs on an endless straight; the "wall" at 61 units/s) and how the 1.9 presets were found; since the 1.10 work *Gegner* is no part of the class: its two values hold for every class, with *Tempo* *Standard*, behind a button on the championship page, which got two columns for it (markers, hooks, key order, tests).
- [Computer kart AI](.claude/memory/mhk2-computer-kart-ai.md) – how the opponents are held back: throttle cap per class, random strength per kart, rubber band; table addresses; the catch-up of 200 cc / 250 cc / *Gegner* (1.9); the learned driver of *Verbesserte Gegner* (1.10): tables from the player's time trials, its values, the speed limit boxes, the search that repairs the tables by racing variations and what it found; *Tempo* and *Verbesserte Gegner* in every class (1.10).
- [Tracks and championships](.claude/memory/mhk2-tracks-and-championships.md) – tracks and championships come from text ids, the limits for a 9th track, the track files and the archive format, how laps are counted (start box plus path progress; a missed start box, e.g. flying over it in the tuning class, stops the lap count for the rest of the race), why a reversed track needs no 3D work, the ground materials and their drag per track, the bridges of Insel and their low bamboo posts, what the driver's animation car+29Ch says about crashes (#32), the plan for a first own track (a TODO).
- [Challenges](.claude/memory/mhk2-challenges.md) – the idea of async challenges (a seed gives a ~20 s stretch of a track with random tuning values; daily seed) and what the exe offers: the race-start grid from one float, a finish on path progress instead of laps, segment phantoms without change.
- [Public release](.claude/memory/mhk2-public-release.md) – how the project became public (2026-11-22 to 2026-11-26), what never goes in, the game paths in `local.json`, the fixtures, the release zips (German / English texts), privacy checks before a commit.
- [Showcase video](.claude/memory/mhk2-showcase-video.md) – the ~1 min clip of the patch: filming with `race_recorder.py --video` (game window via ffmpeg, fullscreen too, races synced; `--audio`: the game's sound only, separate .m4a), OBS settings (the 2026-11-25 recording had the game in a 300x224 corner), scene times from the race recorder (`video_scenes.py`), cutting with `cut_video.py` (deterministic, under GitHub's 10 MB).
- [Notes live in the repo](.claude/memory/mhk2-notes-live-in-repo.md) – why this folder exists and how to keep it current.
- [Exe physics constants](.claude/notes/exe-physics-constants.md) – gravity, time step and frame limit traced from the exe (older note, with corrections).
- [Sandbox and working tools](.claude/README.md) – what is in `.claude/sandbox/`, how to rebuild it, the scripts, how to check new patcher code.
