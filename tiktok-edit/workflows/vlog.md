# Vlog

Many clips from a day or an outing: talking to the camera on the move,
things happening, places, food, friends. The story is the day (or the trip,
the event, the errand), told in order with the boring parts gone. It looks
and moves differently from a sit-down talking head:

| | Talking head (`ramble.md`) | Vlog (this file) |
|---|---|---|
| Footage | One or a few long takes, sitting still | Many short clips, camera moving |
| Story | One point, built from what was said | The day in order, a hook up front |
| Picture | The face, jump cuts, screenshot cards | Talking bits cut with B-roll and moments |
| Title | Held the whole video (`shivani`) | Hook text for the first ~3 s (`vlog` style) |
| Captions | One word, centre | 1–3 words, lower, only while someone talks |
| Sound | Voice only, maybe a pop | Natural sound kept, a music bed under it |

Style preset: `styles/vlog.json`. The person's `taste.md` overrides it.
Run every script with `~/Developer/i-hate-editing/.venv/bin/python`.

## 1. Look at everything

1. Upright check and contact sheets for every clip (SKILL.md). Vlog footage
   is the most likely to be sideways.
2. Fit every clip to 1080x1920 (`fit_vertical.py`, `--rotate` where needed,
   `crop` with a sensible `--focus-x` for landscape clips, `blur` when the
   whole width matters). The fitted copies are the sources from here on.
3. Sort every clip into one of three kinds, in `<studio>/clips.md`, in the
   order they were filmed (file names and times give the order):
   - **TALK**: talking to the camera. Transcribe the fitted copies of these
     (`transcribe.py`), since those are the sources the cut uses.
   - **MOMENT**: something happens with its own sound worth hearing (a
     laugh, a reaction, a door opening onto a view, someone else talking).
   - **BROLL**: scenery, food, walking, details. Sound not needed.

## 2. Find the story

- **Hook first:** the best moment or line of the whole day goes in the first
  2 seconds, even if it happened at the end (then the day plays in order).
- **One arc:** start → what happened → how it ended or what you thought.
  Name it in one sentence in clips.md before cutting.
- **Talking bits** carry the story. Cut them like a ramble: run `ramble.py
  scan` on each TALK clip, and keep only the lines that move the story on.
- **Between talking bits,** 2–4 B-roll shots of 0.8–2.5 s each show where
  you are and what's happening. Faster when it's busy, slower for a view.
- **Length:** let the day set it; 30–60 s usually. Cut repeats of the same
  place or activity down to the best shot.
- Anything private in frame (other people's faces up close, screens, house
  numbers) gets left out unless the person says it's fine.

## 3. Plan and approve  (STOP)

Write `<studio>/story.json` (format in `ramble.py`): TALK blocks as usual,
and BROLL/MOMENT blocks with `"whole": true` so they're kept exactly as
chosen. Then:

```bash
python $TT/scripts/ramble.py tighten --studio <studio> --max-pause 0.25
python $TT/scripts/ramble.py paper   --studio <studio>
```

Show the person, in plain words: the hook, the arc in a few lines, the clips
used in order (with what each shows), what was left out, and the length.
Wait for their OK.

A slightly longer `--max-pause` (0.25 s) suits a vlog: talking while walking
has natural breaths, and cutting every one makes it feel frantic.

## 4. Cut

```bash
python $IHE/scripts/render.py --studio <studio>
```

Optionally lay B-roll over the end of a talking bit (`broll.json`, full-frame
overlays) so the voice carries over the picture: it makes a vlog flow instead
of hopping. i-hate-editing's verify gate applies, then review and **STOP**
for approval.

## 5. Sound

- Voice clean-up on TALK clips only (`voice_clean.py`).
- MOMENT clips keep their own sound.
- A music bed under everything with `$IHE/scripts/music.py` (it ducks under
  the voice automatically). If they want a TikTok sound instead, follow
  "Trending sounds" in `rules/tiktok.md` and export `--no-music` too.

## 6. Text, export

```bash
python $IHE/scripts/captions.py --studio <studio> --max-words 3
python $IHE/scripts/compose.py  --studio <studio>
python $TT/scripts/apply_style.py --studio <studio> --style vlog \
    --title "line one\nline two" --render
```

Captions only appear where there is speech, so B-roll stays clean. Then
`tiktok_export.py`, and `capcut_export.py --style vlog --title "..."`.
Record corrections in `taste.md` as always.
