[← Overview](../README.md) · [All documents](README.md)

# Good to know

- **Phantoms of the new classes** are `data\Phantom\phantom-4-NN.mhk2` (200 cc),
  `phantom-5-NN.mhk2` (250 cc) and `phantom-6-NN.mhk2` (tuning), NN = track 01–08. The first
  finished time trial on a track creates the file; until then the highscore list shows a
  placeholder phantom (10:39:99).
- **mhk2_manager** knows 200 ccm, 250 ccm and Tuning from V1.1 on (V1.0 stops at the first
  run in a new class). V1.1 has been used side by side with the patched game.
- The player name only changes when the game asks for one (a time trial result in the top
  five) or with `--player-name`. Names longer than 12 characters are cut in phantom files.
- The options menu rows sit a little higher than in the stock game to make room for the switch.
- The new texts are German, like the rest of this version's texts. `--lang en` writes them in
  English instead; the game's own texts (*Weiter*, *Zurück*, the menu titles, …) stay German.
- The switch only corrects the suspension. Two smaller frame-rate effects stay as they are: the
  computer karts' steering logic runs every other frame, and a wheel in the air loses 0.5 % of its
  spin per physics step. How often the computer karts fire their power-ups no longer depends on
  the frame rate (see [60 FPS physics switch](60fps-physics.md)).
- Not tried yet: two-player modes in the new classes or with the switch on, and driving on
  the V1.1 data (with `mhk2-01.dat` only the version label of new phantom files was checked).
- The patch has been played by hand in fullscreen, in the new classes and against own
  phantoms; the measurements come from test copies in a window with simulated input. Reports
  from real races are welcome.
