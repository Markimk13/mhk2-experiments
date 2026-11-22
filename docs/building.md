[← Overview](../README.md) · [All documents](README.md)

# Building the patch yourself

## Building it yourself

Instead of the release zip, the patch can be applied to your own original exe with Python 3
(no other dependencies). The [commands](../README.md#commands-unlock-the-classes-build-the-exe) that change `settings.dat` (`--physics60`,
`--player-name`, `--unlock`, `--unlock-tuning`) use the same script.

```powershell
py tools\patch_200cc.py "<game folder>\MHK2-XXL.exe" out
```

This writes `out\MHK2-XXL.exe` and `out\data\MK2\text-20.csv`; add `--lang en` for the English
menu texts (the exe is the same). The script only accepts the original exe (SHA-256 starting
with `272bfad50336ec4c`; an already patched one is refused), checks every byte it replaces, and
never writes next to its input. `--listing FILE` dumps the added code and all patch sites.
If it refuses your exe, see [Other versions of the exe](#other-versions-of-the-exe).

`py tools\make_release.py "<game folder>\MHK2-XXL.exe"` builds both release zips into `dist\`.

## Other versions of the exe

The patch is made for one exe: **German V1.0**, file version 1.0, build Mar 23 2004,
2,244,608 bytes, SHA-256 starting with `272bfad50336ec4c`. It comes from the *10 Jahre
Moorhuhn* CD. To check yours, in PowerShell in the game folder:

```powershell
Get-FileHash MHK2-XXL.exe
```

```powershell
(Get-Item MHK2-XXL.exe).Length
```

The patcher prints both values too when it refuses an exe.

Other releases may well have a different exe: the first German release (if it differs from the
CD), the V1.1 update, and certainly the English version. Only this one exe was available, so
none of them has been looked at. If yours differs:

- **Try the patched exe from the zip.** The exe holds no game data; tracks, karts and texts come
  from `data\mhk2-00.dat` (and `mhk2-01.dat` with V1.1). On a German install the release exe
  may run fine; it has not been tried on anything but the CD version. Keep your own exe and put
  it back if something is wrong. If the V1.1 update brought its own exe, its changes in the exe
  are missing then; its changes in `mhk2-01.dat` stay.
- **English version:** untested. Its data and text files probably differ from the German ones,
  so the release exe may not find its texts or may not run at all.
- **Moving the patch to another exe** is possible but not a switch. Every patch site checks the
  bytes it replaces, so the patcher never writes into an exe it does not know. In an exe built
  from slightly different source code, the same code sits at other addresses: each of the 80
  sites, and the game addresses the new code uses, would have to be found again and the patcher
  given a second set of addresses. This has not been done for any other build.
- **Tell me about it:** open an issue with the file size, the SHA-256, the file version
  (Properties → Details) and where the game comes from (CD or box, edition, update, language).
  Please do not upload the exe itself.
