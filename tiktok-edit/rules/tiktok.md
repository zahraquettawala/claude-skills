# TikTok rules

These override or extend i-hate-editing's `rules/` for TikTok. Where this file
says nothing, i-hate-editing's rule stands. Where the person's `taste.md` says
something, that wins over both.

Platform numbers move. Anything below marked *(check)* is a platform fact
worth re-checking against TikTok's own docs if a result looks off. The rest
are editing decisions.

---

## The frame

- **1080x1920, 9:16, 30 fps** (keep 60 only when the source is 60 and the
  motion needs it: sport, gaming, fast screen scrolls).
- **Every source gets fitted before the cut** (`fit_vertical.py`).
  i-hate-editing's render sizes everything to the first source and
  letterboxes the rest with black. Black bars on TikTok read as a repost.

### Safe zones

TikTok's interface covers parts of the frame *(check)*:

| Edge | Reserved (px at 1080x1920) | What sits there |
|---|---|---|
| Top | 160 | Following / For You tabs, search, LIVE |
| Bottom | 480 | Username, caption, sound ticker, progress bar |
| Right | 140 | Avatar, like, comment, save, share, the spinning sound disc |
| Left | 60 | Margin; text touching the edge reads as cropped |

So **burned-in text lives between y=160 and y=1440, x=60 to x=940**.
i-hate-editing's caption line (27% from the bottom, about y=1400) already
sits just inside that. Its cards and proof beats need checking:

- A card's headline in the top band (above y=160) is hidden. Push it down.
- A right-aligned note in a list card can run under the button column.
- A full-frame proof zoom whose highlight lands near the bottom is covered by
  the caption. Re-target it higher.

`tiktok_export.py` shades these zones on six frames. Read every one. If
something you placed is in the red, fix it upstream and re-render.

**Faces:** eyes on the upper third (about y=640) as i-hate-editing says. That
also keeps the face clear of the right-hand button column on a centred shot.

---

## Length

Decide the length from the content, not a target. These are starting points:

| Kind | Aim | Why |
|---|---|---|
| Talking-head take / opinion | 20–40 s | One idea, said once, ends on the point |
| Montage to a sound | Length of the sound's hook, usually 7–15 s | It loops; a clean loop rewatches |
| Tutorial / screen recording | 30–75 s | Long enough to finish the task shown |
| Faceless explainer / story | 30–60 s | The voiceover sets it; cut padding, not content |

- **Cut to the end of the thought, then stop.** No sign-off, no "follow for
  more" unless the person asks for one. The last frame should make the loop
  back to frame 0 feel natural.
- *(check)* TikTok's Creator Rewards program has required videos over one
  minute. If the person is in it and a piece lands at 50–60 s, say so; do not
  pad to cross the line on your own.

---

## The hook (first 1–2 seconds)

i-hate-editing's hook rules (`$IHE/rules/hooks.md`) all apply. TikTok makes
them tighter:

- **Text on screen from frame 0.** Many people watch with the sound off for the
  first second. In Shivani's style that is the held title; otherwise the hook
  headline (`style: "band"` card) starts at 0.0, not after the first word.
- **The promise lands by ~1.5 s.** The first spoken line states what they get
  or the problem, not "so" or "hey guys". Cut the throat-clear even if it is
  the best take otherwise. Exception: in Shivani's style a "hi, my name is…"
  intro stays whole, with the held title carrying the hook text from frame 0
  and the hook line straight after the intro.
- **Motion in the first second.** A cut, a zoom punch, or a panel change at
  about 1.0–1.3 s (i-hate-editing's split-proof hook already does this).
- **Montage:** open on the strongest clip, and if the track has a drop, either
  open on it or build to it inside 3 s. Never a slow fade-in.
- **Screen recording:** open on the end result (the finished thing, the
  number, the "after"), then go back to the start.

---

## Captions

i-hate-editing's caption rules stand (late by 0.08 s, 1–4 words, proofread
gate). TikTok-specific:

- **Burned-in captions are the default** for talking-head and voiceover. Tell
  the person to leave TikTok's auto-captions off for the video, or the two
  stack on top of each other.
- **Montage:** no running captions. One or two text beats at most, inside the
  safe area, timed to the beat.
- **Screen recording:** captions go in the band below the panel when the
  recording is in `panel` layout, and move up over the dark ground, never over
  the UI being demonstrated.

---

## Sound

### Loudness

- Master the finished mix **at -14 LUFS integrated, true peak ≤ -1 dBTP**.
  `tiktok_export.py` does this. *(check)* TikTok does not publish a loudness
  target; -14 is the common streaming level and plays at a comparable volume
  next to other videos in the feed. i-hate-editing's -15 LUFS master is fine
  as an intermediate step; the export lifts it.
- Voice levels and sting levels follow i-hate-editing (`rules/sound.md`),
  measured against the cleaned voice (`voice_clean.py` lands it at the same
  -18.4 LUFS that its Adobe step does).

### Trending sounds: the in-app rule

A video that uses a TikTok sound from the app's library is linked to that
sound's page and can show up there. A song baked into the file is not linked
(and can be muted for copyright).

So when the person wants a trending or library sound:

1. Get a local copy of the sound only to cut against (the person's own
   download or recording). Never ship it inside the file.
2. Build the edit to it (`music_beats.py`) so the cuts land on its beats.
3. Export **both**: `tiktok.mp4` (with the track, for review) and
   `tiktok_nomusic.mp4` (voice and SFX only, or silent for a montage).
4. In `post.md`, tell them: upload `tiktok_nomusic.mp4`, add the sound in the
   app, and set its start to the same point (`music.start` in `edl.json`).
   Original audio at about 0–10% for a montage; for talking-head keep the
   original audio up and the sound low.

When the music is the person's own, licensed or royalty-free, bake it in and
skip the no-music copy.

### SFX

i-hate-editing's SFX library and placement rules apply. On TikTok, less: one
sting per real event (a cut to proof, a reveal, a number). A whoosh on every
caption is noise.

---

## Post copy (`post.md`)

Written by you, from what was actually said or shown, never generated
filler. Template:

```markdown
**Caption** (first line is all most people read; ≤ 150 chars total works best)
<a hook line that adds to the video, not a repeat of the on-screen text>

**Hashtags** (3–5, specific > broad)
#<topic> #<niche> #<format, e.g. tutorial>

**Search keyword**: <the phrase someone would type to find this>
Make sure it is spoken in the first seconds AND appears in the on-screen text
AND in the caption. TikTok search reads all three.

**Cover**: <timestamp> from the thumbnail candidates; face clear, text readable
in the 3:4 crop the profile grid shows

**Sound plan**: baked in | add "<sound name>" in-app, start at <s>, original
audio at <n>%

**Auto-captions**: off (captions are burned in) | on
```

The profile grid crops covers to about 3:4 from the centre *(check)*. Pick a
cover whose subject and text sit in the middle.

---

## Export checklist

`tiktok_export.py` covers the mechanical part. You still check:

- [ ] First 2 s watched on their own, with sound and without
- [ ] Every `safe_*.png` read; nothing important in the red
- [ ] `report.json` has no warnings, or each one is explained to the person
- [ ] Loops cleanly: last frame → first frame does not jar
- [ ] `post.md` written, sound plan stated
- [ ] CapCut project exported if the person edits in CapCut, and they were
      told what it does not include (grade, card designs, zooms)
- [ ] Corrections recorded in `taste.md`
