[← Overview](../README.md) · [All documents](README.md)

# Challenges

A challenge is a short time trial over one stretch of a track. The game draws the track, the
stretch, your driver and the tuning values. The daily challenge is the same for all players on
the same day, and the game keeps your best run of the day as a phantom.

## Where to find it

Open *Hauptmenü → Rennmodus → Herausforderung* (challenge). It is the third button under
*Ein Spieler* (one player). You need nothing to unlock it.

![challenge page](../screenshots/18-challenge-page.png)

## How to use it

1. Press *Zufall* (random) for a new challenge, or *Täglich* (daily) for the challenge of the day.
2. Read the challenge on the page: the track, the length of the stretch, where it starts, your
   driver and the tuning values.
3. Press *Weiter* (next) to start the race.

Press *Zufall* again to draw a new challenge. *Zurück* (back) leaves the page. Your own class,
track, driver and tuning values are back when you leave.

| Button | What it does |
| --- | --- |
| *Zufall* | Draws a new random challenge. Every press gives another one. |
| *Täglich* | Draws the challenge of the day. All players get the same one on the same day. It changes at midnight UTC (1:00 in Germany in winter, 2:00 in summer). |
| *Weiter* | Starts the race. It works after a press of *Zufall* or *Täglich*. |
| *Zurück* | Goes back to the page *Rennmodus*. |

## The race

- **The stretch.** You start somewhere on the track, not on the start line. The stretch is
  1000 to 1600 m long, which is 30 % to 70 % of the track. At 200 to 250 km/h, it takes 15 to
  30 seconds.
- **Metres to go.** The top left shows *Noch 340 m* (340 m to go) instead of the lap.
- **The minimap.** It shows the stretch in magenta and the finish in white. The rest of the
  track is grey.
- **The pause page.** It shows the challenge: *Tägliche Herausforderung* (daily challenge) with
  the date and your best time of the day, or *Zufällige Herausforderung* (random challenge)
  with its seed. Below are the tuning values, the top speed, the track, the stretch and your
  driver.
- **The kart.** A challenge always uses the tuning class, with values that are hard but drivable.
  The tuning page would call them *Am Limit* or *Hart am Limit*
  ([Tuning class](tuning-class.md)). The switch *60-FPS-Fahrphysik* is on for the race.
- **The finish.** The race ends after the stretch. The result page shows *Deine Zeit* (your
  time). In a daily challenge, the line below shows your best time of the day, or *Neue
  Bestzeit!* (new best time) in green.
  *Rennen wiederholen* (repeat the race) starts the same stretch again.

![challenge race](../screenshots/19-challenge-race.png)

## Records and phantoms

- **Täglich.** The page shows your best time of the day. Your best run of the day becomes the
  phantom, and the next race of the day shows it with the driver of the day. The phantom file is
  `data\Phantom\daily-<day>.mhk2`. A new day starts without a time and without a phantom.
- **Zufall.** The game keeps no time and no phantom.
- **Normal records.** A challenge never changes your records, your highscore lists or the
  phantoms of your time trials.

## Good to know

- The phantom files of earlier days stay in `data\Phantom`. You can delete them.
- A challenge is not part of the highscore lists of the game. Rankings with other players and
  challenges between friends are planned in the issues.

How the patch does it: [How it works](how-it-works.md#challenges).
