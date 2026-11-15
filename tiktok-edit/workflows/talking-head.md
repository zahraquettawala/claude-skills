# Talking-head

i-hate-editing was built for this. Run its process (`$IHE/SKILL.md`, steps
1–13) with these changes.

## Setup

```bash
python3 $IHE/scripts/scan.py --footage <footage>
```

Then make sure `<footage>/studio/profile.yml` has:

```yaml
aspects: ["9:16"]            # add "1:1", "16:9" only if they post elsewhere too
pacing: punchy
brand: {accent: "<their colour>", font: "<their font>", caption_style: big-keyword}
names: ["<product names they say>"]
```

For the default style (`styles/shivani.md`) set `brand.font: "ChunkFive"`;
the style keeps everything white, so the accent colour is unused. For any
other look, replace i-hate-editing's green default with the person's own
colour (see SKILL.md).

## Steps that change

| i-hate-editing step | Change |
|---|---|
| 1–4 Read, inventory, transcribe, pack | As is. Fit any non-vertical source with `fit_vertical.py --mode crop` first, choosing `--focus-x` from a contact sheet so the face survives. |
| 5 Plan the cut | Apply the cut rules in `styles/shivani.md` (no dead air, intro kept whole, a beat after the hook, 30 s default, end on the punchiest line). Look for the line that states the payoff and make sure it is spoken by ~1.5 s. If it comes later in the take, move it to the front (a cold-open line followed by the build-up is a normal TikTok structure). If they open with "hi, my name is…", keep it whole as Shivani's style says, and make sure the hook follows straight after it. |
| 6 Assemble | `edl.json` may set `"speed": 1.1`–`1.2` for punchy pacing (i-hate-editing applies it in the render; hard rule 9c). |
| 7–8 Verify, present | As is. **Stop and wait for approval.** |
| 9 Enhance voice | `enhance.py` only if `doctor.py` shows ego-browser. Otherwise: `python3 $TT/scripts/voice_clean.py <studio>/cut.mp4 --remux`, then use `cut_clean.mp4` as the cut from here on (rename it over `cut.mp4` once checked, so the rest of the scripts find it). |
| 10 Enrich | Follow `styles/shivani.md` "Producing it": `captions.py --max-words 1`, screenshot cards with `screenshot_card.py`, `compose.py` without `--render`, then `apply_style.py --title "..." --render`. No hook band card (the held title is the hook text). Check positions against the safe area (`rules/tiktok.md`). Skip `gen_image.py` / `broll-gen` unless `doctor.py` shows them. |
| 11 Verify render | As is. |
| 12 Deliver | `music.py` for a bed (if any) → `deliver.py` → **`tiktok_export.py`** (see below) → read the frames → write `post.md` with the TikTok template. |
| 13 Learn | As is. |

## Export

```bash
python3 $TT/scripts/tiktok_export.py <studio>/out/final.mp4 --studio <studio>
# with an in-app sound planned:
python3 $TT/scripts/tiktok_export.py <studio>/out/final.mp4 --studio <studio> \
    --no-music <studio>/out/master.mp4
```

`master.mp4` is the composite before `music.py` added the bed, so it is
the same edit without the music.
