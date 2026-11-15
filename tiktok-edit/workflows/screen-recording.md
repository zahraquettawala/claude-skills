# Screen recordings (tutorials, demos, walkthroughs)

Two problems i-hate-editing does not cover: a landscape screen in a vertical
frame, and dead time where nobody talks and nothing moves.

## 1. Inventory and look

`ffprobe` it. Screen recordings are often variable frame rate, which drifts
every cut. If `avg_frame_rate` looks odd, conform first:

```bash
ffmpeg -i screen.mov -vf fps=30 -c:v libx264 -crf 16 -c:a aac screen_cfr.mp4
```

Then `contact_sheet.py` it, to see where the action is on screen.

## 2. Cut the dead time

**Narrated** (they talk over it): run i-hate-editing's transcript pipeline
first (transcribe → pack → plan the cut from `takes.md` → `edl.json`), cutting
the talk like a talking-head. Then, for long stretches inside kept blocks where
the screen sits frozen and they are silent:

```bash
python3 $TT/scripts/dead_time.py screen.mp4 --studio <studio> --narrated -o <studio>/dead.json
```

and fold its drops into your EDL by hand. You decide; it only points.

**Silent** (no narration):

```bash
python3 $TT/scripts/dead_time.py screen.mp4 --studio <studio>
```

Writes `edl.json` that keeps everything except frozen stretches, each cut
down to a 0.45 s hold. Read its table; if a blinking cursor or clock keeps
"moving" a frame that is really idle, raise `--freeze-noise`.

Open on the result (`rules/tiktok.md`, hook): move the range that shows the
finished thing to the front of the EDL as the cold open.

## 3. Reframe for 9:16

Pick per segment, from the contact sheet:

| What matters on screen | Layout | Command |
|---|---|---|
| The whole window, plus a face or captions below | `panel` | `fit_vertical.py screen.mp4 -o fitted/panel.mp4 --mode panel` |
| One area (a form, a terminal, a button) | `region` | `fit_vertical.py screen.mp4 -o fitted/form.mp4 --mode region --region 0.55,0.10,0.40,0.55` |
| A wide UI that must stay whole, nothing below | `blur` | `fit_vertical.py screen.mp4 -o fitted/wide.mp4 --mode blur` |

`--region x,y,w,h` is fractions of the source frame. Keep regions at least
~35% of the source width, or text goes soft. Several fitted versions of the
same recording are normal: point each EDL range at the version it needs
(same timestamps, different `source`). That is how you get a "zoom in" cut.

Write the EDL against the fitted files, then:

```bash
python3 $IHE/scripts/render.py --studio <studio>
```

**Gate:** review and wait for approval.

## 4. With a face cam

If there is a separate face-cam recording, it is i-hate-editing's split
layout: the screen panel on top as a `broll.json` overlay (not `full`), the
face below. Cut the face-cam take as the base (it carries the voice), and
add screen segments as overlays timed to what is being described.

## 5. Enrich

- Captions from narration (`captions.py`, `proofread.py`). In panel layout
  they go below the panel, never over the UI being shown.
- **Proof beats** (`capture.py`) are for real web pages; for an app UI the
  recording itself is the proof. Use zoomed `region` cuts instead.
- One click or pop sting per meaningful action (a submit, a result
  appearing), per i-hate-editing's sound rules.
- Voice: `voice_clean.py --remux` (or `enhance.py` if available).

## 6. Export

`tiktok_export.py` as in SKILL.md. Read the safe-zone frames carefully: a
UI's own toolbar at the very top or bottom of a panel lands under TikTok's.
