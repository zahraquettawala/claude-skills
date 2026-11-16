---
name: tiktok-edit
description: Edit raw footage into a finished, ready-to-post TikTok: talking-head, B-roll/montage cut to music, screen-recording tutorials, or faceless voiceover. Layers TikTok-specific decisions (hook timing, length, safe zones, loudness, export, post copy, in-app sound strategy) on top of the i-hate-editing skill, which does the cutting, captions, sound and compositing. Also exports the edit as an editable CapCut project. Use when someone drops footage in a folder and wants a TikTok, Reel or Short out of it.
---

# TikTok Edit

A TikTok-specific layer on [i-hate-editing](https://github.com/ranahaani/i-hate-editing)
(MIT). i-hate-editing is the studio: it cuts from the transcript, verifies the
seams, builds captions and cards, places sound and composites. This skill adds
three things it does not have:

1. **Routing for four kinds of footage.** i-hate-editing is built for
   talking-head. Montage, screen recordings and faceless voiceover each need a
   different first half of the pipeline. Pick the workflow, then hand the
   result to i-hate-editing's enrich steps.
2. **TikTok decisions.** Safe zones, length targets, hook timing, loudness, the
   export spec, post copy, and when to leave the music out so the sound gets
   added in the app. All in `rules/tiktok.md`.
3. **Fallbacks for i-hate-editing's author-specific steps.** Its voice
   enhancement, generated stills and AI B-roll depend on its author's own
   setup. Each has a local replacement here, so an edit never stalls.

`$IHE` below means the i-hate-editing checkout and `$TT` means this skill's
directory. `python3 $TT/scripts/doctor.py` prints both.

## Before anything

```bash
python3 $TT/scripts/doctor.py
```

If i-hate-editing is missing, follow `install.md` in this skill. Then read, in
this order:

1. `$IHE/SKILL.md`: the studio's principles, process and gates. They all apply.
2. `$IHE/HARD-RULES.md`: silent-failure rules. Not negotiable.
3. `$TT/rules/tiktok.md`: where TikTok overrides or adds to the above.
4. The workflow file for this footage (below).
5. The style: `styles/shivani.md` for talking-head and voiceover (the
   default; see "Style" below).
5. `<footage>/studio/taste.md` if it exists (`$IHE/scripts/taste.py brief`).
   The person's own past corrections beat every default here.

## Pick the workflow

Look at the footage before choosing: `ffprobe` every file, and run
`contact_sheet.py` on **every** clip and photo, then read the sheets.

**Upright check, every time.** On each sheet, check the picture is upright:
people standing, text reading left to right, sky at the top. Vloggers often
hold the camera sideways, and that footage carries no rotation tag, so no
probe catches it; only looking does. For anything sideways or upside down,
make an upright copy and use it from then on instead of the original:

```bash
python3 $TT/scripts/fit_vertical.py <clip> -o <studio>/fitted/<name>.mp4 --rotate 90
python3 $TT/scripts/contact_sheet.py <studio>/fitted/<name>.mp4 --out-dir <studio>/sheets
```

`--rotate` is clockwise: 90 when the top of the picture points left, 270
when it points right, 180 when upside down. Re-sheet the fixed copy and look
again before going on. Photos get the same check (`screenshot_card.py
--rotate`). Tell the person which files were turned. Never present a cut
built on a sideways clip.

| Footage | Workflow | What drives the cut |
|---|---|---|
| Someone talking to camera, scripted or in short takes | `workflows/talking-head.md` | The transcript (i-hate-editing as is) |
| One long unscripted take (a sit-down ramble) | `workflows/ramble.md` | An outline of what was said, then the transcript |
| Clips with no talking, cut to a song or sound | `workflows/montage.md` | The beat grid (`music_beats.py`) |
| A screen recording, narrated or silent | `workflows/screen-recording.md` | Dead-time detection + transcript |
| A voiceover over stock, B-roll or images | `workflows/voiceover.md` | The voiceover's transcript |

Mixed footage is normal (a talking head with screen inserts, a montage with a
spoken intro). Pick the workflow for whatever drives the timing and borrow
steps from the others. Ask the person only if you really cannot tell what the
video is for. Never ask about fonts, transitions or levels.

## Style

The default look for talking-to-camera and voiceover videos is **Shivani's
style** (`styles/shivani.md`): tight jump cuts with no dead air, one word on
screen at a time in the centre in white ChunkFive, and a two-line title held
for the whole video in the upper third. It replaces i-hate-editing's own house
style (green accent, hook band card, 27%-from-bottom captions) for those
videos. Its montage/promo rules are in `workflows/montage.md`.

Use another look only when the person asks for one or their `taste.md` says
so. Their corrections to this style go in `taste.md` like any other.

## What changes from i-hate-editing's defaults

Read `rules/tiktok.md` for the full set. The ones that bite most often:

- **The first second is the hook, not the first three.** Text on screen from
  frame 0, the payoff promised by about 1.5 s. i-hate-editing's 3.4 s hook
  plan still applies, compressed.
- **Burned-in text stays inside the safe area**: 160 px from the top, 480 px
  from the bottom, 140 px from the right, 60 px from the left (1080x1920).
  i-hate-editing's 27%-from-bottom caption line already clears it. Check
  every card and proof beat against it with the `tiktok_export.py` frames.
- **Its house palette is not yours.** i-hate-editing defaults to green
  `#76B900`, its author's brand. Set `brand.accent` and `brand.font` in
  `profile.yml` from the person's existing videos or what they say; if they
  have no brand, pick one bold accent and keep it across their videos.
- **Voice enhancement:** use `$IHE/scripts/enhance.py` only if `doctor.py`
  shows ego-browser. Otherwise `voice_clean.py` (same output level, so the
  sound rules still hold).
- **Generated stills / AI B-roll:** `gen_image.py` only if the Gemini proxy is
  listening; `broll-gen` only if installed. Otherwise use real footage, a
  designed Remotion scene, or a card. Never fake a screenshot either way.
- **Export:** finish with `tiktok_export.py`, not `deliver.py` alone. It
  conforms the spec, normalises to -14 LUFS, writes a no-music copy when
  asked, and produces the safe-zone proof frames.

## The gates still hold

i-hate-editing has two stop points: show the approved cut before building
anything on it, and verify the render before delivering. Montage and
screen-recording cuts get the same first gate: show `cut.mp4` (`$IHE/scripts/review.py`)
and wait for a yes before captions, cards or sound.

Never present something you have not looked at. For TikTok that includes:
reading every `safe_*.png` from the export, and watching the first two seconds
on their own, because that is all most viewers see.

## Deliver

Everything lands in `<footage>/studio/out/`:

- `tiktok/tiktok.mp4`: the upload
- `tiktok/tiktok_nomusic.mp4`: when the sound will be added in the app
- `tiktok/safe_*.png`, `tiktok/report.json`: the checks you read
- the other platform crops from `deliver.py`, if `profile.yml` asks for them
- `post.md`: write it yourself, using the template in `rules/tiktok.md`
  (caption, 3–5 hashtags, the on-screen keyword, cover frame time, and the
  sound plan)
- **a CapCut project** of the same edit, when the person wants to tweak it by
  hand (see "CapCut export" below)

Then step 13 of i-hate-editing: record every correction with `taste.py add`
and pass `--said` with the person's own words. A TikTok-specific note (hook
length, caption density, sound choice) is filed under the matching area like
any other.

## CapCut export

After the MP4 is approved, also write the edit as an editable CapCut project:

```bash
python3 $TT/scripts/capcut_export.py --studio <studio> --name "<short title>" \
    --style shivani --title "line one\nline two"
# talking-head with a cleaned voice: keep that voice instead of the raw clips' sound
python3 $TT/scripts/capcut_export.py --studio <studio> --name "..." --voice-from-cut
# a music bed laid with music.py: pass it so it gets its own track
python3 $TT/scripts/capcut_export.py --studio <studio> --name "..." --music <bed> --music-level 0.15
```

It must run on the computer with CapCut desktop, with CapCut **closed**.
Every cut becomes a clip on the main track (trimming a clip trims its sound),
captions and cards become editable text, and B-roll, sound effects and music
get their own tracks. All media is copied into the project. The colour grade,
card designs, animations and proof zooms are not carried over; they exist only
in the MP4. Say so when you hand it over.

`--style shivani` gives one-word centred captions in ChunkFive, the held
title, and screenshot cards (`floats.json`) at the style's size and place.

It depends on pyCapCut, which writes CapCut's undocumented project format and
is verified against CapCut for Windows. On a Mac (detected automatically, or
`--mac`) it also writes `draft_info.json` and its `.bak`, the file names Mac
CapCut reads, and points the text at a ChunkFive font file that exists on the
Mac. Shivani's skill confirms Mac CapCut 8.x opens projects written into its
folder this way. Mac specifics:

- The App Store CapCut is sandboxed: media outside `~/Movies` shows as "File
  not accessible". The export copies all media into the project folder,
  which is inside `~/Movies/CapCut`, so that cannot happen.
- If the text shows in the wrong font, the person adds one text clip in
  ChunkFive in CapCut once (CapCut downloads it), then re-run the export.
- Never overwrite a project the person has edited by hand. Each revision gets
  a new name (`… v2`, `… v3`), so their hand edits survive.

If CapCut shows the project as broken, tell the person plainly and fall back
to the MP4. If the export fails, the MP4 is still the deliverable: never hold
the MP4 back for it.

To finish on a phone: open the project once in CapCut desktop, upload it to
CapCut's cloud space (same account), then open it in the phone app.

## Scripts in this skill

| Script | Does |
|---|---|
| `doctor.py` | Finds i-hate-editing, checks tools, names the fallbacks |
| `contact_sheet.py` | Frame grids for footage with no transcript |
| `fit_vertical.py` | Any source to 1080x1920: crop, blur, panel, region |
| `music_beats.py` | Beat grid, montage EDL, frame-exact render with the track |
| `dead_time.py` | Cuts frozen and silent stretches out of screen recordings |
| `voice_clean.py` | Local voice cleanup and levelling (replaces Adobe Enhance) |
| `tiktok_export.py` | Final encode, loudness, no-music copy, safe-zone frames |
| `capcut_export.py` | The same edit as an editable CapCut desktop project |
| `apply_style.py` | Restyles the composition to a style preset, then renders |
| `ramble.py` | Ramble cuts: fillers, untranscribed ums and dead air out; paper edit; must-keep check |
| `screenshot_card.py` | Screenshot to floating card clip, with its pop/whoosh |

All need only ffmpeg and Python 3.10+. `music_beats.py analyze` also needs
numpy, and `capcut_export.py` needs `pycapcut==0.0.4`.
