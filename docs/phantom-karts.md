[← Overview](../README.md) · [All documents](README.md)

# Phantom karts

The stock game saves every finished time trial as `data\Phantom\new-phantom.mhk2` and races
against `data\Phantom\phantom-C-TT.mhk2` (C = class 1–5, TT = track 01–08). But it skips every
phantom file that was recorded on the same PC – it compares an id stored in the file with its
own – so it never shows your own run. `mhk2_manager` works around that from outside.

With the patch the game does it itself:

- **Own ghosts.** Phantom files from this PC are loaded like any other.
- **The best run becomes the phantom.** A finished time trial that is faster than the phantom
  of its track and class replaces it at the finish. The first run on a track without phantom
  file creates one (that is every 200 cc and 250 cc track at first). Slower runs change nothing.
- **Version.** New phantom files start with `V1.1` when the V1.1 data (`mhk2-01.dat`) is
  loaded and with `V1.0` otherwise. The stock game always writes `V1.0`.
- **Name.** The name typed at *Neue Highscore* (time trial or championship) is kept in
  `settings.dat` and written into every new phantom file, in bytes 8–19, where `mhk2_manager`
  keeps its player name. The run it was typed for gets it too. The highscore lists show the name
  instead of "PHANTOM KART". The next time the name page comes up, the field already holds it
  (the cursor behind it); confirming an empty field takes the kept name as well.

![result list with the phantom's name](../screenshots/07-phantom-name.png)

The name can be set without waiting for a highscore (at most 12 characters):

```powershell
py tools\patch_200cc.py --player-name "Name" "<game folder>\settings.dat"
```

`MHK2-XXL.exe some-file.mhk2`, the stock game's way of installing a downloaded phantom, now
also accepts files from this PC.

Things to keep in mind:

- A replaced phantom file is gone, also an imported one or one of the original phantoms. Keep
  copies of the ones you want to race again (`mhk2_manager` keeps the originals in
  `data\Phantom\source`).
- Phantom files written by the game have no `mhk2_manager` checksum, so the manager does not
  accept them as custom phantoms. Going by its code, a manager that runs alongside keeps
  archiving the runs and puts its own stamped copy in place; that combination is untested.
- The files keep this PC's id. The unpatched game on the same PC still skips them.
