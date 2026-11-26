# Open points

The open points are GitHub issues of this repository:
https://github.com/Markimk13/mhk2-experiments/issues (milestone 1.10: better computer karts,
more opponents, new and changed tracks). Their technical background is in the notes in
[.claude/memory/](.claude/memory/), e.g. the computer karts in
[mhk2-computer-kart-ai.md](.claude/memory/mhk2-computer-kart-ai.md), tracks in
[mhk2-tracks-and-championships.md](.claude/memory/mhk2-tracks-and-championships.md), the tuning
class with its presets and measurements in [mhk2-tuning-class.md](.claude/memory/mhk2-tuning-class.md).

This file keeps only what has no issue.

## Not tested

Done by the user by 2026-11-22: playing by hand in fullscreen, racing a full-length own ghost,
full laps by hand in 200 cc / 250 cc / tuning, the patched game and `mhk2_manager` side by side.

- Two-player modes (duel, championship for two) with the new classes, the physics switch and the new phantom code.
- Races on the V1.1 data. Only the version label was tested with `mhk2-01.dat`.

## Known limitations (no plan to change them)

- Winning Meisterschaft 2 in 200 cc with a patch up to 1.2 was not recorded, so 250 cc starts locked on such a save (the switch *Alles freigeschaltet* or `--unlock` opens it).
- A save that used the tuning class with 1.8 or older has it hidden again until Meisterschaft 2 in 250 cc is won (or the switch *Alles freigeschaltet*, or `--unlock-tuning`).
- The green *Am Limit* line of the tuning class (`LIMIT_POINTS`) is a fit to 45 s races of the computer karts at 60 FPS (about 850 races, all eight tracks, one race per set and track). A single race scatters a lot (the same values: from a clean race to a broken one on another track), so the line says what works on average, not on every track. It judges the computer karts only, not the player's own driving feel; its "challenge" points are set by hand.
- The three downforce rules (limit, lower limit in the air, none when tilted by more than 60°) only exist in the tuning class, so a kart on its side or back behaves differently from a 250 cc kart even with the default values. The limits (120 and 75 units/s) were chosen with a margin of three to where the physics broke, not tuned for feel.
- At 200 FPS without *60-FPS-Fahrphysik*, the wheels of a kart with much downforce carry only a third of what they carry at 60 FPS (the stock frame-rate effect, stronger here). The class runs stable either way; it is meant to be driven with the switch on.
