[← Overview](../README.md) · [All documents](README.md)

# Building the patch yourself

## Other versions of the exe

The patch is made for one game file: the **German V1.0** from the *10 Jahre Moorhuhn* CD. Other
versions can have a different `MHK2-XXL.exe`, for example the first German release, the V1.1
update or the English version. Nobody has tested the patch with them.

To check your exe:

1. Open PowerShell in the game folder.
2. Run this command:

   ```powershell
   Get-FileHash MHK2-XXL.exe
   ```

3. Run this command:

   ```powershell
   (Get-Item MHK2-XXL.exe).Length
   ```

The patch is made for the size 2,244,608 bytes and a SHA-256 that starts with
`272bfad50336ec4c`. The patcher also shows both values when it refuses an exe.

If your exe is different:

- **Try the exe from the zip.** The exe has no game data. The tracks, karts and texts come
  from `data\mhk2-00.dat`, and from `mhk2-01.dat` with the V1.1 update. On a German game, the
  exe from the zip can work. Keep your own exe, and copy it back if something is wrong. If the
  V1.1 update came with its own exe, its changes to the exe are missing then. Its changes in
  `mhk2-01.dat` stay.
- **English version:** not tested. Its data and text files are probably different from the
  German ones. The exe from the zip may not find its texts, or may not start.
- **Tell us about it.** Open an [issue](https://github.com/Markimk13/mhk2-experiments/issues).
  Give the file size, the SHA-256 and the file version (Properties → Details). Also tell us
  where the game comes from: CD or box, edition, update, language. Do not upload the exe.

**For developers: the patch on another exe.** This is possible, but there is no switch for it.
Every patch site checks the bytes that it replaces. So the patcher never writes into an exe
that it does not know. An exe built from slightly different source code has the same code at
other addresses. Somebody must find each patch site again, and each game address that the new
code uses, and give the patcher a second set of addresses. Nobody has done this for another
build.

## Building it yourself

You can apply the patch to your own original exe instead of using the zip. You need Python 3
and no other packages.

```powershell
py tools\patch_200cc.py "<game folder>\MHK2-XXL.exe" out
```

- This writes `out\MHK2-XXL.exe` and `out\data\MK2\text-20.csv`.
- Add `--lang en` for the English menu texts. The exe is the same.
- The script accepts only the original exe. It refuses an exe that is already patched.
- It checks every byte that it replaces, and it never writes next to its input file.
- `--listing FILE` writes the added code and all patch sites into a file.
- `--factor`, `--pull`, `--factor-250` and `--pull-250` change the gearing and the pull of
  200 cc and 250 cc.

The [commands](../README.md#commands-build-the-exe-unlock-the-classes) that change
`settings.dat` use the same script: `--unlock`, `--unlock-tuning`, `--lock`, `--physics60` and
`--player-name`.

## Release zips

```powershell
py tools\make_release.py "<game folder>\MHK2-XXL.exe"
```

This builds both release zips (German and English texts) into `dist\`. It refuses to build when
`CHANGELOG.md` has no section for the release.
