---
name: mhk2-phantom-and-manager-internals
description: "How Moorhuhn Kart 2 handles phantom (ghost) files, what mhk2_manager adds on top, and what patch 1.2 changed - addresses, file formats, test approach"
metadata:
  node_type: memory
  type: project
  modified: 2026-11-18T13:08:23.385Z
---

Worked out on 2026-11-18 by decompiling `mhk2_manager.jar` (its source is in `..\mhk2_manager`, identical to the jar V1.0) and reading MHK2-XXL.exe V1.0. Decompiler without downloads: `java -cp "<IntelliJ>\plugins\java-decompiler\lib\java-decompiler.jar" org.jetbrains.java.decompiler.main.decompiler.ConsoleDecompiler <classes dir> <out dir>` (JDK 17 in `C:\Program Files\Java\jdk-17`).

**Game (stock)**
- Phantom file = 0x6C header + recording. Header: +0x00 char[0x20] version (game always writes "V1.0" from 0x5C38B8, writable .data, never checked on load), +0x20 edition ([0x5C38D8], 2 = full), +0x24 language id, +0x28 char[0x20] machine id, +0x4C track (1-based), +0x50 class, +0x54 character, +0x58 total time, +0x5C/+0x60/+0x64 lap times.
- Recording (read 2026-11-23 for the AI work): at 0x6C a chunk header of 24 bytes (dword 1, dword 3, "car\0", sample size 22, data size, ...), then samples of 22 bytes from 0x84: x, y, z floats (world position, same frame as car+10h) and packed rotation; samples are evenly spaced, total time / count = about 0.21 s. Positions only, no inputs; speed and line along the lap follow from them (`.claude\sandbox\tools\track_line.py` maps x, z to the centre line).
- Machine id: 32 random hex chars, registry HKCU\Software\mhk2 value "machine-id", kept at 0x5C38DC (fn 0x46EFF0). Sandbox copies use the same registry value as the real installs.
- Time-trial finish writes `data\Phantom\new-phantom.mhk2` (0x406B67..0x406C96); the header is built at GameParameters+0xFB04. The stock game never promotes that file.
- At race start the game reads the loaded ghost's header INTO GameParameters+0xFB04, and the finish code only fills some fields: in the stock game bytes 5..31 of a new phantom are leftovers of the opponent's header (with the manager: its name and checksum).
- Ghost load at race start (0x409B0A..) and at "Rennen wiederholen" (0x4072D1..) opens `phantom-%d-%02d.mhk2` and skips it when its machine id equals the own one (je at 0x409BAF / 0x40736E): the stock game never shows your own ghost. gp+0x54 (byte) = 1 when a ghost was loaded.
- `CopyPhantomKart(path)` 0x40C360 copies a phantom file to its `phantom-C-TT.mhk2` slot with CopyFileA (import slot 0x5951CC), also refusing the own id (je at 0x40C406). Called with command-line argument 1 at startup (0x46F787) and from a WM_USER message (0x4726C6), so `MHK2-XXL.exe file.mhk2` installs a phantom.
- Header table GameParameters+0xAA04 [3][64]*0x6C, index class*64 + track-1, is refilled at every menu init (fn 0x412F20); a missing file leaves track 0 and 639.99 s but does not clear bytes 5..31. The patch scans phantom-4-NN (200 cc) into slots 160..191 and phantom-5-NN (250 cc) into slots 96..127.
- Race end: the race update (fn 0x4067B0, virtual) checks every frame: race phase [state+0x118] == 2, car state [car+0x2D0] == 2, laps [car+0x264] >= 3. Then phase 4, then 5 with the result pages drawn over the race by the menu object at [race state+0x144] (active flag byte +0x148). Current state object = [[0x5E851C]+4].
- Result pages = fn 0x421970, menu states 0x0E (overlay "Ergebnis", item 0 "Weiter"), 0x0F (result list: item 0 "Rennen wiederholen", 1 "Phantom Kart übertragen", 2 "Hauptmenü"), 0x13/0x14/0x15 (name entry single / player 1 / player 2). "Weiter" goes to 0x13 when 0x412A90 says the time is a top-five result, else to 0x0F. The typed name is the std::string at menu+0x17C, emptied when the page opens; confirming calls 0x412AE0(menu, kart) at 0x422340 for time trial and duel, 0x412D60 for championships. gp+0x74 (float) is the finish time and is bit-identical to header+0x58.
- Highscore entry (0xB4 at gp+0x234 + (class*64 + track index)*0xB4): 5 times, laps at +0x14 (5*3), names 16 bytes each at +0x50, characters at +0xA0. The rows of the result list and of the highscore browser are built by fn 0x4207D0 (edi = table index; callers 0x4236A9 and 0x41C3CB); text 382 "PHANTOM KART" is pushed only at 0x420B39.
- Menu states: 0..0x0D main menu pages (1 options, 3 quit question, 4 race mode, 5 resolution list, 6 character, 7 track, 8 class, 0x0A/0x0B pause, 0x0C/0x0D championship), 0x0E..0x15 result pages, 0x16 "Highscore" (choose), 0x17/0x18 time trial lists (browser), 0x19/0x1A championship lists.
- Dead online buttons: text 377 "Phantom Kart übertragen" (result list) and 531 "Lade Phantom Kart" (highscore browser, AddButton call 0x41C17A, y 500); upload fn 0x497EE0.
- Data files: loop 0x46F791..0x46F845 mounts `data\mhk2-00..99.dat` BEFORE settings.dat is loaded (0x46F84B). FileManager = 0x401550; Open 0x451850(name, mode, flag) searches the archives newest first; archive vector at fm+8 (0x54 bytes each, count via 0x410F70 with ecx = fm+4); Find 0x451360(archive, name) returns an entry with offset at +0x68 and size at +0x6C. V1.1 = `mhk2-01.dat` (new collision borders / drop zones / objects for levels 1-4 and 6-8 plus config.txt); `data\mk2\level01\objects\collision_border.dff` is 42004 bytes in V1.0 and 29772 in V1.1. The exe does not read "dataversion".
- Imports present: CopyFileA, MoveFileA, CreateFileA, ReadFile, WriteFile, SetFilePointer, CloseHandle, lstrcpynA, wsprintfA, FindFirstFileA/FindNextFileA/FindClose, GetProcAddress, LoadLibraryA, GetModuleHandleA, ShellExecuteA. Not imported: CreateDirectoryA.
- settings.dat bytes 0..223 are the "last race" block the manager reads: 12 class, 24 mode (0 time trial, 1 championship, 2 duel, 3 championship 2P), 28 track, 36+4r championship tracks, 68 race index, 84+4i characters, 112+4i finish times, 140+12i+4j lap times. The 60-FPS switch bytes (73..75) lie inside this block (the manager copies but ignores them).

**Manager (V1.0, 2020)**
- Only works while the game was started with its button: watches settings.dat and new-phantom.mhk2, archives runs as `data\Phantom\phantom-C-TT\trial-NNNNN.mhk2`, championships as `data\Championship\championship-C-a-b-c-d\championship-NNNNN.dat` (32 front + 12 hash + 4 + 4*224 bytes) and duels as `data\Duel\duel-C-TT\duel-NNNNN.dat` (48 + 224).
- Stamps phantoms: bytes 0..3 "V1.0"/"V1.1" (by presence of `data\mhk2-01.dat`), 8..19 player name, 20..31 hash, 40..71 copied from the source phantom of that track in `data\Phantom\source\` (32 dashes or a developer id) - that is what makes the game accept the own run as ghost.
- Hash ("CRC96", reproduced in Python against the user's files): 4 bytes `b[3-i] = (crc32(part1) >>> 4*i) & 0xFF` (sic, nibble steps), then CRC-64/XZ (poly 0xC96C5795D7870F42 reflected) of part1+part2, big-endian. Phantom: part1 = bytes 0..19, part2 = bytes 32..end. Files without it are "not valid" for the manager.
- Copies the best run to `phantom-C-TT.mhk2`; options: best times / source phantoms, only current version / character, imported custom phantoms with per-file rules.
- V1.0's `Engine` enum had 3 values, so a 200 cc or 250 cc phantom (class 3 or 4) broke it (ArrayIndexOutOfBounds at the first run). Its TODO.txt proposes the collision_border size as version test.

**Manager V1.1 (2026-11-22, commit "V1.1: classes 200 ccm, 250 ccm and Tuning" in ..\mhk2_manager)**
- `Engine` has ENGINE_200, ENGINE_250, ENGINE_TUNING (`hasSourcePhantoms()` is true for the stock three); names in the three MessagesBundle files.
- No source phantoms for classes 3..5: `Phantom.savePhantom` writes 32 dashes as id (bytes 40..71) when `data\Phantom\source\phantom-C-TT.mhk2` is missing; `CustomPhantom.getAllPhantoms` skips such tracks (best-times mode: no run yet; source mode: new class); `SettingsUpdateChecker.savePhantom` treats a missing phantom as "none yet" and saves the run as main phantom only when it is not slower than the file in place (the patched game may already have put a faster run, or this run, there).
- Build: `py .claude\sandbox\tools\build_manager_jar.py` (javac --release 8, Cp1252, keeps the 2020 jar's layout; out: `.claude\sandbox\manager\mhk2_manager.jar`). Check: `ManagerCheck.java` in the same folder, run headless in a scratch folder with `data\mhk2-00.dat` (hard link to the sandbox copy); 23 checks pass on V1.1, V1.0 crashes at the first 200 cc run. The window was not started (it would take the focus).
- The repo's git `user.email` is set to the noreply address (the global one is a private address).

**Patch 1.2 (built 2026-11-18, `tools/patch_200cc.py`)**
- Own-id checks removed (0x409BAF, 0x40736E, 0x40C406 -> NOPs).
- `phantom_stamp` (jump from 0x406C69): clears header bytes 4..31, copies the stored name to +8. `phantom_promote` (replaces the close call at 0x406C91): closes, then copies new-phantom over the track's phantom file and its header into the table when the time is strictly lower.
- `name_confirm` (replaces the call at 0x422340; time trial, kart 0 only): stores the name (max 12 chars) at gp+0x2F10 with marker "NAME" (0x454D414E) at gp+0x2F30 - the unused highscore entry [50 cc][track 64][rank 5]; writes it into new-phantom.mhk2 and, when the table entry is this run and its bytes 20..23 are zero, into the track's phantom file (CreateFileA/SetFilePointer/WriteFile at offset 8).
- `phantom_row_name` (replaces the assign at 0x420B70): lists show header bytes 8..19 instead of "PHANTOM KART" when the entry has a track and a name.
- `version_detect` (replaces the load call at 0x46F857): writes '1' to 0x5C38BB when the mounted collision_border.dff has 29772 bytes.
- `--player-name NAME settings.dat` writes name and marker (file offsets 0x2F0C / 0x2F2C).
- Tested with `ghosttest.py` in the sandbox (see .claude/sandbox/tools in the repo): a forced finish only works once the car is in state 2; the result pages need a one-shot "menu select" stub at the six input reads of fn 0x421970 (0x4219E3, 0x421A8B, 0x421BDB, 0x421C4F, 0x421CA5, 0x4222CA), and the selection [menu+0x148] has to be written right before each press.

- Championship and duel archives (issue #5): the game keeps only the last race; the manager's `.dat` format would need the four 224-byte race blocks plus its checksum.

**Why:** on 2026-11-18 the user asked which manager features could move into the game and then had the first three built (own ghost, version tag, player name). Open rows are GitHub issues #1-10 in the public repo.
**How to apply:** start from these addresses for the next rows (ghost choice, run archive with checksum, championship/duel archives), and check bytes before patching the way `tools/patch_200cc.py` does. See [[mhk2-user-context]] and [[mhk2-windowed-test-recipe]].
