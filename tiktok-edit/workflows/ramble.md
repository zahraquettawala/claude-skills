# Sit-down ramble

One long take of someone talking it through: no script, false starts, ums,
tangents, the good line arriving at minute four. The job is to find the story
in it and cut everything else, without losing a single fact the video needs.

This is talking-head (`workflows/talking-head.md` and i-hate-editing's steps
all apply) with three things added: an outline before any cut, a paper edit
the person approves, and a must-keep check after the cut. The look is
Shivani's style (`styles/shivani.md`) unless they say otherwise.

Run every script with `~/Developer/i-hate-editing/.venv/bin/python` (it has
numpy).

## 1. Upright, transcribe, scan

Upright check first (SKILL.md). Then i-hate-editing steps 1–4: inventory,
`transcribe.py` (word-level), `pack.py` → `takes.md`. Then:

```bash
python $TT/scripts/ramble.py scan --studio <studio> --source <ramble.mp4>
```

`scan.md` counts the fillers, the untranscribed ums (Whisper tidies speech, so
many ums are missing from the transcript; the scan finds them as sound between
words), the dead air, and the soft fillers ("like", "so", "you know"). If the
speech threshold it prints looks wrong for the room (lots of "sounds" that are
really background noise), pass `--thr-db` a few dB higher everywhere below.

## 2. Outline: everything that was said

Read all of `takes.md`. Write `<studio>/outline.md`: every distinct point, in
the order said, with its time range and one label:

| Label | Meaning | Default |
|---|---|---|
| HOOK | A line that would stop a scroll: a claim, a surprise, the result, a question | Candidate for the opening |
| STORY | Setup, problem, turn, payoff: the spine | Keep |
| INFO | A fact, number, name, date, price, step, recommendation, warning | **Keep, always** |
| COLOUR | A joke, a feeling, a vivid detail | Keep if it is short and good |
| REPEAT | Said again elsewhere | Keep the clearest version only |
| ASIDE | A tangent that does not serve the point | Cut |
| RESTART | A false start or abandoned sentence | Cut (keep the complete retry) |
| CHATTER | "Is this recording", "hold on", talking to someone off camera | Cut |

Then list every INFO item's exact words in `<studio>/mustkeep.json`:

```json
{"items": ["the best beans come from Ethiopia", "it costs twelve dollars"]}
```

Use the speaker's exact words from the transcript, short enough to be one
phrase.

## 3. Story: choose and order

- **One video, one point.** Name it in a sentence in outline.md before
  choosing anything. If the ramble has two separate points, say so and offer
  two videos rather than cramming both into one.
- **Structure:** hook → context → the beats in a logical order → payoff → a
  short ending line. The hook can be moved to the front even if it was said
  last; say "(moved)" in the outline.
- **Keep every INFO item**, unless it is a REPEAT (keep the clearest version)
  or the person says it can go.
- **Orphans:** after choosing, read the kept lines in order as if you had never
  heard the rest. A "that", "she", "the second one" or "like I said" whose
  meaning was cut must either get its reference back or go.
- **Clauses stay whole.** Never cut a negation, a "but" or a number off a
  sentence (i-hate-editing's cutting rules).
- **Length:** let the story set it. A ramble usually lands at 40–90 s. Over 90
  s, offer a short version (the hook and the core point) alongside the full one.
- **Intro:** in Shivani's style a "hi, I'm…" opening stays whole, with the
  hook straight after it.

Write the chosen blocks, in video order, to `<studio>/story.json` (format in
`ramble.py`'s header): one range per block, broad, from the start of its first
sentence to the end of its last. Don't trim fillers or pauses inside a block
by hand; that is the next step's job.

## 4. Paper edit: the person approves in words  (STOP)

```bash
python $TT/scripts/ramble.py tighten --studio <studio>
python $TT/scripts/ramble.py paper   --studio <studio>
```

Show the person, in plain words:

1. The one-sentence point, and the hook you chose.
2. The story beats in order, a line each.
3. **What you cut**, every block, with a few words on why ("tangent about
   parking", "said again better at 3:10"). Flag anything you were unsure of.
4. The must-keep list.
5. The length, before and after.

`paper_edit.md` has the full line-by-line view for them to check. **Wait for
their OK.** Rendering a cut they have not agreed to wastes the slowest step,
and a story change after captions invalidates every timestamp.

## 5. Cut, then check nothing important went

```bash
python $TT/scripts/ramble.py tighten --studio <studio>     # again, if story.json changed
python $IHE/scripts/render.py --studio <studio>
python $TT/scripts/ramble.py check --studio <studio>
```

`check` must pass. Then i-hate-editing's verify gate: re-transcribe short
windows at the seams (repeated or clipped words), and watch it. A ramble cut
has many seams, so also listen for:

- **Breath and pace:** if it sounds breathless, re-run `tighten` with
  `--max-pause 0.25`.
- **Clipped word endings:** pass `--thr-db` 2–3 dB lower and re-tighten.
- **Jumpy picture:** many jump cuts on one framing can feel twitchy. Offer
  `tighten --punch 1.1` (every other piece slightly zoomed), which reads as a
  camera change. Shivani's style doesn't use it by default; ask.

Show the cut (`review.py`). **STOP for approval** before captions.

## 6. Finish

Captions (one word, `captions.py --max-words 1`), title, sound, export, CapCut
export: as in `styles/shivani.md` and SKILL.md "Deliver". Record every
correction in `taste.md` (`taste.py add … --said "<their words>"`), especially
story ones ("keep my tangents about food, they're my thing"), so the next
ramble is cut the way they like.

## Advice for the person, when they ask how to film a ramble

- Talk to the lens, sit near a window, use a mic if you have one.
- If you fumble, pause for a second and say the whole sentence again. The
  pause makes the restart easy to find, and the later take is kept.
- Say the most important thing more than once in different ways; the clearest
  version is kept.
- Don't worry about ums or long pauses. Those get cut.
