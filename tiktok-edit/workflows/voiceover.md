# Faceless / voiceover

The voiceover is the timeline; the visuals cover it. i-hate-editing's
pipeline needs a video to cut, so give the voiceover a placeholder picture,
cut it like a talking-head, then cover every second with B-roll.

## 1. Clean the voice first

```bash
python3 $TT/scripts/voice_clean.py voiceover.wav -o <studio>/vo_clean.wav
```

## 2. A placeholder video to cut

```bash
ffmpeg -f lavfi -i color=c=0x0d0d10:s=1080x1920:r=30 -i <studio>/vo_clean.wav \
    -shortest -c:v libx264 -crf 30 -c:a aac -b:a 192k <studio>/vo_base.mp4
```

## 3. Cut it (i-hate-editing steps 3–8)

Transcribe `vo_base.mp4`, pack, plan the cut from `takes.md` (drop retakes,
breaths, a slow intro; the payoff line by ~1.5 s), `edl.json`, `render.py`,
`verify.py`. **Gate:** approve the cut by listening; there is nothing to see
yet.

## 4. Plan the visuals: one per beat

Read `takes.md` against the cut's `timeline.json`. Every 1.5–3 s gets a new
visual (i-hate-editing's "something new every three seconds", tighter for
TikTok). For each beat, in this order of preference:

1. The person's own footage that shows the thing said
2. A real page or product (`$IHE/scripts/capture.py` proof beat)
3. A designed scene for anything with structure: a number, a comparison, a
   list (`scenes.json` → Remotion, `$IHE/rules/scenes.md`)
4. Licensed stock the person supplied
5. A generated still (`gen_image.py`) only if `doctor.py` shows the proxy,
   and never one that implies a real screenshot

Run `contact_sheet.py` over the B-roll and fit it (`fit_vertical.py`).

## 5. Cover the timeline

Write `broll.json` with **full-frame** overlays end to end. No gaps, or the
dark placeholder shows:

```json
{"overlays": [
  {"file": "fitted/city.mp4",  "start": 0.00, "end": 2.10, "full": true},
  {"file": "fitted/phone.mp4", "start": 2.10, "end": 4.40, "full": true, "focus_x": 0.6}
]}
```

Cut visuals on word onsets from the transcript, not mid-word. A visual
change on a stressed word lands like a beat.

Overlays composite muted (i-hate-editing hard rules), so B-roll audio never
reaches the mix. If a clip's own sound matters (a door slam), add it as an SFX.

## 6. Enrich and export

Captions (`captions.py`, `proofread.py`): burned in, the only on-screen
voice there is. A music bed with `music.py` (ducked under the voice), then
`tiktok_export.py`. With a TikTok library sound planned, export `--no-music`
from `master.mp4` and set the sound low in the app; the voice carries a
faceless video.
