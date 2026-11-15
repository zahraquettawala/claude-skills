# B-roll / montage cut to music

No speech, so no transcript: the music is the clock. Audio is still the
authority on time (i-hate-editing principle 3), just different audio.

## 1. Get the track and the footage

- The track: the person's own file, or a local copy of the TikTok sound they
  want to cut to (see "Trending sounds" in `rules/tiktok.md`: a library
  sound gets added in the app, not baked in).
- The clips: everything in the folder. `ffprobe` each one (rotation, fps,
  duration).

## 2. Look at the footage

```bash
python3 $TT/scripts/contact_sheet.py <footage>/*.mp4 --out-dir <studio>/sheets
```

Read every sheet. First, the upright check (SKILL.md): anything sideways or
upside down gets `--rotate` in the next step. For each clip note: what it shows, where the best 1–4 s
are (by cell time), whether the subject is left, centre or right, and
whether it has motion (motion on a beat hits harder than a static shot).

## 3. Fit everything to 9:16

```bash
python3 $TT/scripts/fit_vertical.py <footage>/*.mp4 --out-dir <studio>/fitted
# re-do one with a better crop:
python3 $TT/scripts/fit_vertical.py <footage>/beach.mp4 -o <studio>/fitted/beach.mp4 \
    --mode crop --focus-x 0.7
```

`auto` blur-pads landscape. For B-roll with one clear subject, `crop` with
the right `--focus-x` fills the frame and looks better. Use `blur` when the
whole width matters (a wide landscape, a group).

## 4. Find the beats

```bash
python3 $TT/scripts/music_beats.py analyze <track> -o <studio>/beats.json
```

It prints tempo, beat count and the first downbeat. Sanity-check the tempo
against what you hear; if it reads half or double, the grid is still usable
(cut every 2 or every ½ beats). `strong_onsets` are the drops and hits.

## Promo / event reels (Shivani's style 2)

For an event or brand promo: vertical, about 10–20 s, either a fast montage
of 20–25 cuts at 0.3–0.5 s each (1 beat per clip at most tempos) or one main
clip with a few overlays. Titles in sequence, about 1.2–1.8 s each, white
ChunkFive with fades: "<brand> presents" → event name → date or key detail.
Ask for the brand, event name, date and details; never invent them. Pick
lively frames from the contact sheets (faces, crowd, motion) and skip blurry
or blank ones. If no song is given, keep the clips' own audio and say a song
can be added in CapCut.

## 5. Plan the cut: `clips.json`

This is the edit. Decide it like an editor:

- **Start on a downbeat** (`start_beat` = the index of one of the
  `downbeats` in `beats`). If the track has a drop, either start on it or
  make sure it arrives within 3 s.
- **Pacing follows energy**: 4 beats per clip in a quiet intro, 2 in the
  body, 1 (or a run of 1s) into and on the drop.
- **Strongest clip first.** Weakest clips in the middle, never at either end.
- **Motion on the cut**: pick `in` points so something moves right after the
  cut, not before it.
- **End so it loops**: the last clip should flow back into the first.

```json
{"start_beat": 8, "clips": [
  {"source": "<studio>/fitted/drone.mp4", "in": 2.1, "beats": 4, "beat": "OPEN"},
  {"source": "<studio>/fitted/walk.mp4",  "in": 0.6, "beats": 2},
  {"source": "<studio>/fitted/jump.mp4",  "in": 1.4, "beats": 1, "beat": "DROP"}
]}
```

```bash
python3 $TT/scripts/music_beats.py edl --beats <studio>/beats.json \
    --clips <studio>/clips.json -o <studio>/edl.json
```

It fails if a clip's `in` + duration runs past its end. Move `in` earlier or
give it fewer beats.

## 6. Render: not with render.py

```bash
python3 $TT/scripts/music_beats.py render --studio <studio>
```

Frame-exact video segments with the track laid under them, plus
`timeline.json` in i-hate-editing's format. Do not use `$IHE/scripts/render.py`
for a montage: its per-segment AAC padding drifts ~17 ms per cut, which is
off the beat by the twentieth cut.

**Gate:** open it with `$IHE/scripts/review.py --studio <studio>` and wait
for approval. Check that cuts land on the beat by ear, and step through the
seams.

## 7. Enrich (light)

- **Grade:** `$IHE/scripts/grade.py` on `cut.mp4` to make mixed sources look
  like one shoot. Look at the comparison frame.
- **Text:** at most one or two `cards.json` beats (a `band` hook at 0.0, a
  closing line), timed to beats. No running captions.
- **SFX:** usually none; the track is the sound. A riser or impact only on
  a drop the track does not already hit.
- **Compose** only if there are cards. i-hate-editing's `captions.py` has
  nothing to transcribe here, but `compose.py` refuses to run without a
  captions file, so write an empty one:
  `echo '{"chunks": []}' > <studio>/captions.json`, then
  `$IHE/scripts/compose.py --studio <studio> --render`. With no cards, copy
  `cut.mp4` (or `cut_graded.mp4`) to `<studio>/out/master.mp4` instead.

## 8. Export

Track baked in (own or licensed music):

```bash
python3 $TT/scripts/tiktok_export.py <studio>/out/master.mp4 --studio <studio>
```

TikTok library sound (added in the app): export the same edit without its
audio as the upload, and the version with the track for review:

```bash
ffmpeg -i <studio>/out/master.mp4 -c:v copy -an <studio>/out/master_silent.mp4
python3 $TT/scripts/tiktok_export.py <studio>/out/master.mp4 --studio <studio> \
    --no-music <studio>/out/master_silent.mp4
```

In `post.md`, give the sound name and its start point (`music.start` from
`edl.json`) so they line it up in the app.
