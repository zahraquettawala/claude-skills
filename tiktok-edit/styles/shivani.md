# Style: Shivani (the default for talking-to-camera)

Taken from Shivani's `capcut-video-styles` skill: the look of the TikToks she
makes. It is the default for talking-head and voiceover edits unless the
person's `taste.md` or their own words say otherwise. Machine-readable
values are in `shivani.json`; the scripts read them from there.

Her skill had CapCut do the listening (Auto captions) and the voice cleanup
(Isolate voice) inside the app, because it ran in the cloud with no
speech-to-text. This skill transcribes locally with whisper.cpp, so none of
that round trip is needed. Her editing decisions carry over unchanged.

## The look

- **One word on screen at a time, dead centre.** White ChunkFive, heavy
  black outline, no box. Very short words ("a", "the", "your") ride with the
  next word, so nothing flashes for one frame.
- **A two-line title held for the whole video**, centred in the upper third:
  between about 380 and 620 px from the top of the 1920 frame, above the
  caption. White ChunkFive, no fade. It is what shows in the TikTok profile
  grid, so it names the video's topic in two short lines ("how I got / my
  first client"). Write it from what is said; never clickbait it.
- **No running colour accent** on captions. Everything white.

## The cut

- **Tight jump cuts, no dead air.** Remove every pause over about 0.15 s,
  edge pads at the 0.03 s minimum. Snap edges to words, then confirm against
  silence detection (i-hate-editing hard rules 6 and 7).
- **Default length 30 s.** "Under 30" means about 28–29.5 s. If trimming
  leaves it short, put back a strong line rather than slowing the cut.
- **Keep the intro whole.** "Hi, my name is…" stays as one unbroken take,
  no jump cuts inside it.
- **Give the hook a beat.** The hook line's last word rings out fully before
  the cut. Same for any line ending on a key word that would get clipped.
- **Cut off-camera chatter** ("hold on", "is it still recording"), repeats
  and rambling. Drop "um", "uh", "hmm".
- **Keep shout-outs** to friends, and get their names right in the captions
  (`profile.yml` `names`, `proofread.py --name`).
- **End on the strongest punchy line**, with about 0.7 s of hold after the
  last word so it does not feel chopped.
- With several takes: the cleanest take for most of it, and a standout line
  pulled from another.

## Screenshot cards (when the video talks about something on a screen)

- Crop to just the relevant part (one message bubble, one number), one per
  card, 968 px wide with a 4 px border. Never include sidebars, emails or
  unrelated personal content.
- Floated over the speaker, lower middle: 70% size, nudged left, so the card
  sits around x 120–880, y 1000–1450, clear of TikTok's buttons and caption.
- One in the first 10 seconds, a few through the middle, each where they
  describe what it shows. About 3–4 cards, 2–4 s each. The face stays on
  screen for the hook, the shout-out and the ending.
- A pop/whoosh on every card, starting 0.17 s before the card so the peak
  lands as it appears.
- Ask before opening their browser to capture something. Otherwise ask them
  to screenshot it and attach it.

`screenshot_card.py` makes the card clip and the sound and writes both into
the studio; `apply_style.py` and `capcut_export.py` place them.

## Producing it

1. i-hate-editing steps 1–8 as usual, with the cut rules above. Stop for
   approval of the cut.
2. Voice: `voice_clean.py --remux` (or `enhance.py` if available). In the
   CapCut project, the person can also switch on CapCut's own
   **Audio → Isolate voice** on the main-track clips.
3. Captions, one word each:
   `python3 $IHE/scripts/captions.py --studio <studio> --max-words 1`, then
   `proofread.py` as usual.
4. Cards (if any): `screenshot_card.py`.
5. Compose WITHOUT rendering, then apply the style and render:
   ```bash
   python3 $IHE/scripts/compose.py --studio <studio>
   python3 $TT/scripts/apply_style.py --studio <studio> \
       --title "how I got\nmy first client" --render
   ```
   Skip i-hate-editing's hook band card and running caption accent for this
   style: the held title is the hook text.
6. `tiktok_export.py`, then
   `capcut_export.py --style shivani --title "how I got\nmy first client"`.
