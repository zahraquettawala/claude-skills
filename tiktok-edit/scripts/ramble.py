#!/usr/bin/env python3
"""Cut a sit-down ramble: fillers out, dead air out, story kept.

The story decision (which parts of the ramble make the video, in what order)
is yours, written by hand as studio/story.json after the paper edit is
approved. This script does the mechanical part inside those blocks, the part
that is tedious and error-prone by hand:

    ramble.py scan    --studio studio         # fillers, repeats, pauses -> scan.md
    ramble.py tighten --studio studio         # story.json -> edl.json
    ramble.py paper   --studio studio         # what was kept/cut -> paper_edit.md
    ramble.py check   --studio studio         # must-keep facts survived?

story.json is an i-hate-editing EDL at the block level: one range per story
beat, in VIDEO order (a hook can come first even if it was said last):

    {"sources": {"take": "/abs/ramble.mp4"},
     "ranges": [{"source": "take", "start": 212.4, "end": 219.8, "beat": "HOOK"},
                {"source": "take", "start": 3.1, "end": 41.0, "beat": "SETUP"}]}

`tighten` splits every block at:
  - pauses longer than --max-pause (0.15 s), down to a short natural gap
  - filler words (um, uh, erm, hmm...) and stutters ("I I", "the the")
  - stretches between words where the audio has sound but no words: that is
    where Whisper hid an "um" it did not transcribe (it tidies speech by
    default, so fillers are often missing from the transcript entirely)
and snaps every edge to the audio, so a word ending is never clipped even
when Whisper's timestamp is early. Cuts only ever land between words.

`paper` writes the whole ramble as numbered lines marked KEPT or cut, with
the removed fillers and the time saved, for the person to read before
rendering. `check` reads studio/mustkeep.json ({"items": ["exact phrase",
...]}) and fails if any phrase is not in the kept audio's transcript.

Needs numpy (the i-hate-editing venv has it) and i-hate-editing's
transcript of each source (transcribe.py, word-level).
"""

import argparse
import json
import re
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _common import die, probe  # noqa: E402

FILLERS = {"um", "umm", "uh", "uhh", "uhm", "erm", "er", "ah", "ahh", "hmm",
           "hm", "mm", "mmm", "eh"}
# Said as filler often, as meaning just as often: listed for a judgement call,
# never cut automatically.
SOFT = {"like", "basically", "literally", "actually", "so", "right",
        "you know", "i mean", "kind of", "sort of"}
SR = 16000
FRAME = 0.010
LEAD, TAIL = 0.04, 0.08          # audio kept before/after speech at each edge
KEEP_GAP = 0.08                  # natural gap left where a pause was removed
SENTENCE_GAP = 0.12              # a little more at a full stop
MIN_RUN = 0.25                   # shorter speech runs merge into a neighbour
GHOST_MIN = 0.18                 # voiced, unworded stretch that counts as filler


def norm(text):
    return re.sub(r"[^\w']", "", text.lower())


def load_words(studio, src):
    """Word-level transcript for `src` from i-hate-editing's cache."""
    src = str(Path(src).resolve())
    best = None
    for f in sorted((Path(studio) / "transcripts").glob("*.json")):
        try:
            d = json.loads(f.read_text())
        except (OSError, json.JSONDecodeError):
            continue
        if d.get("source") != src or d.get("mode", "").startswith("translate"):
            continue
        if best is None or d.get("granularity") == "word":
            best = d
    if not best:
        die(f"no transcript for {Path(src).name}: run "
            f"$IHE/scripts/transcribe.py on it first")
    if best.get("granularity") != "word":
        print(f"note: {Path(src).name} has only a phrase-level transcript; "
              "filler detection relies on the audio alone", file=sys.stderr)
    return [w for w in best["words"] if w["end"] > w["start"]]


class Envelope:
    """10 ms loudness envelope of a source, and a speech threshold for it."""

    def __init__(self, src, thr_db=None):
        import numpy as np
        raw = subprocess.run(["ffmpeg", "-v", "error", "-i", str(src), "-vn",
                              "-ac", "1", "-ar", str(SR), "-f", "f32le", "-"],
                             capture_output=True).stdout
        y = np.frombuffer(raw, dtype=np.float32)
        hop = int(SR * FRAME)
        n = len(y) // hop
        rms = np.sqrt((y[:n * hop].reshape(n, hop) ** 2).mean(axis=1) + 1e-12)
        self.db = 20 * np.log10(rms)
        floor = float(np.percentile(self.db, 10))
        # Speech sits well above the room; 12 dB over the quiet floor is the
        # same margin Shivani's cuts used.
        self.thr = thr_db if thr_db is not None else floor + 12
        self.floor = floor

    def idx(self, t):
        return max(0, min(len(self.db) - 1, int(t / FRAME)))

    def voiced(self, a, b):
        """Seconds of sound above the speech threshold between a and b."""
        i, j = self.idx(a), self.idx(b)
        return float((self.db[i:j] > self.thr).sum()) * FRAME if j > i else 0.0

    def snap_end(self, t, limit):
        """Push an edge later while the word is still sounding (max `limit`)."""
        i, stop = self.idx(t), self.idx(t + limit)
        while i < stop and self.db[i] > self.thr:
            i += 1
        return i * FRAME

    def snap_start(self, t, limit):
        i, stop = self.idx(t), self.idx(max(0.0, t - limit))
        while i > stop and self.db[i - 1] > self.thr:
            i -= 1
        return i * FRAME

    def next_sound(self, t, limit):
        """Time of the next sound after a silence that starts at t, or t+limit."""
        i, stop = self.idx(t), self.idx(t + limit)
        while i < stop and self.db[i] <= self.thr:
            i += 1
        return i * FRAME

    def prev_sound(self, t, limit):
        i, stop = self.idx(t), self.idx(max(0.0, t - limit))
        while i > stop and self.db[i - 1] <= self.thr:
            i -= 1
        return i * FRAME


def mark(words, env):
    """Label each word: keep, filler, stutter, soft (judgement), and the gap
    after it: pause or ghost (sound with no words: an untranscribed um)."""
    out = []
    for i, w in enumerate(words):
        t = norm(w["text"])
        nxt = norm(words[i + 1]["text"]) if i + 1 < len(words) else ""
        kind = "keep"
        if t in FILLERS:
            kind = "filler"
        elif t and t == nxt and len(t) <= 6:
            kind = "stutter"                      # "I I", "the the": drop the first
        elif w["text"].strip().endswith("-"):
            kind = "stutter"                      # a cut-off fragment
        elif t in SOFT or (t + " " + nxt) in SOFT:
            kind = "soft"
        gap, gap_kind = 0.0, None
        if i + 1 < len(words):
            gap = words[i + 1]["start"] - w["end"]
            if gap > 0.12:
                gap_kind = ("ghost" if env.voiced(w["end"], words[i + 1]["start"]) >= GHOST_MIN
                            else "pause")
        out.append({**w, "kind": kind, "gap": round(gap, 3), "gap_kind": gap_kind})
    return out


def runs_in_block(marked, a, b, env, max_pause):
    """Speech runs inside [a, b] after dropping fillers, stutters, long pauses
    and ghosts. Returns [(start, end, n_words, ends_sentence)]."""
    inside = [w for w in marked if w["start"] >= a - 0.05 and w["end"] <= b + 0.05]
    runs, cur = [], []
    for w in inside:
        if w["kind"] in ("filler", "stutter"):
            if cur:
                runs.append(cur)
            cur = []
            continue
        cur.append(w)
        breaks = w["gap_kind"] == "ghost" or w["gap"] > max_pause
        if breaks:
            runs.append(cur)
            cur = []
    if cur:
        runs.append(cur)
    out = []
    # The margins around each edge must stop short of the next sound: that
    # sound is a dropped filler, a stutter or an untranscribed um, and even
    # 30 ms of it (plus render.py's own 30 ms edge pad) is an audible blip.
    clear = 0.035
    for r in runs:
        s0 = env.snap_start(max(a, r[0]["start"]), 0.10)
        e0 = env.snap_end(min(b, r[-1]["end"]), 0.15)
        s = max(s0 - LEAD, env.prev_sound(s0, LEAD + clear) + clear) \
            if s0 - LEAD > 0 else s0
        e = min(e0 + TAIL, env.next_sound(e0, TAIL + clear) - clear)
        s, e = min(s, s0), max(e, e0)
        out.append([max(a, s), min(b, e), len(r),
                    r[-1]["text"].strip()[-1:] in ".?!"])
    # Merge slivers into the neighbour they are closest to; a run this short
    # on its own reads as a glitch, not a cut.
    merged = []
    for r in out:
        if merged and (r[1] - r[0] < MIN_RUN or merged[-1][1] - merged[-1][0] < MIN_RUN) \
                and r[0] - merged[-1][1] < 0.35:
            merged[-1][1], merged[-1][2] = r[1], merged[-1][2] + r[2]
            merged[-1][3] = r[3]
        else:
            merged.append(r)
    # Leave a short natural gap where a pause was removed, a little longer at
    # a full stop, by extending each run's tail into the removed silence.
    for k in range(len(merged) - 1):
        room = merged[k + 1][0] - merged[k][1]
        want = SENTENCE_GAP if merged[k][3] else KEEP_GAP
        merged[k][1] += max(0.0, min(want, room) - TAIL)
    return merged


def load_story(studio):
    p = Path(studio) / "story.json"
    if not p.is_file():
        die(f"no {p}: write the story blocks first (see workflows/ramble.md)")
    return json.loads(p.read_text())


def cmd_scan(args):
    studio = Path(args.studio)
    story = load_story(studio) if (studio / "story.json").is_file() else None
    srcs = (story or {}).get("sources") or {}
    if args.source:
        srcs = {"take": str(Path(args.source).resolve())}
    if not srcs:
        die("give --source or write story.json first")
    lines = ["# Ramble scan", ""]
    for key, src in srcs.items():
        env = Envelope(src)
        m = mark(load_words(studio, src), env)
        fill = [w for w in m if w["kind"] in ("filler", "stutter")]
        ghosts = [w for w in m if w["gap_kind"] == "ghost"]
        pauses = [w for w in m if w["gap_kind"] == "pause" and w["gap"] > args.max_pause]
        soft = [w for w in m if w["kind"] == "soft"]
        dead = sum(w["gap"] for w in pauses)
        lines += [f"## {Path(src).name}", "",
                  f"- {probe(src)['duration']:.0f} s long, {len(m)} words",
                  f"- {len(fill)} transcribed fillers/stutters (cut automatically)",
                  f"- {len(ghosts)} untranscribed sounds between words, most "
                  f"likely um/uh (cut automatically)",
                  f"- {len(pauses)} pauses over {args.max_pause}s, "
                  f"{dead:.0f} s of dead air (cut automatically)",
                  f"- {len(soft)} soft fillers (like, so, you know...): your "
                  f"call, never cut automatically",
                  f"- room floor {env.floor:.0f} dB, speech threshold "
                  f"{env.thr:.0f} dB", ""]
        for w in fill[:40]:
            lines.append(f"  - {w['start']:7.2f}s  {w['kind']:<8} \"{w['text'].strip()}\"")
        for w in ghosts[:40]:
            lines.append(f"  - {w['end']:7.2f}s  sound    ({w['gap']:.2f}s, no words) "
                         f"after \"{w['text'].strip()}\"")
        lines.append("")
    out = studio / "scan.md"
    out.write_text("\n".join(lines))
    print("\n".join(lines[:14]))
    print(f"-> {out}")


def cmd_tighten(args):
    studio = Path(args.studio)
    story = load_story(studio)
    cache = {}
    ranges, before, after = [], 0.0, 0.0
    for blk in story["ranges"]:
        src = story["sources"].get(blk["source"], blk["source"])
        if src not in cache:
            env = Envelope(src, args.thr_db)
            cache[src] = (env, mark(load_words(studio, src), env))
        env, m = cache[src]
        a, b = float(blk["start"]), float(blk["end"])
        runs = runs_in_block(m, a, b, env, args.max_pause)
        before += b - a
        for i, (s, e, n, _) in enumerate(runs):
            ranges.append({"source": blk["source"], "start": round(s, 3),
                           "end": round(e, 3), "beat": blk.get("beat"),
                           "reason": f"{blk.get('beat') or 'block'} part {i + 1}/{len(runs)}"})
            after += e - s
    if args.punch:
        # Alternate a slight punch-in on every other piece: the jump cut
        # reads as a deliberate camera change instead of a skip.
        for i, r in enumerate(ranges):
            if i % 2:
                r["zoom"], r["zoom_y"] = args.punch, 0.35
    edl = {k: v for k, v in story.items() if k not in ("ranges",)}
    edl["ranges"] = ranges
    edl["pad"] = {"in": 0.03, "out": 0.03}
    (studio / "edl.json").write_text(json.dumps(edl, indent=1))
    speed = float(edl.get("speed", 1.0))
    print(f"{len(story['ranges'])} story block(s) -> {len(ranges)} pieces · "
          f"{before:.1f}s -> {after:.1f}s ({before - after:.1f}s of fillers and "
          f"dead air out)" + (f" · {after / speed:.1f}s at {speed}x" if speed != 1 else ""))
    print(f"-> {studio / 'edl.json'}")


def kept_words(studio, edl):
    """Transcript words that fall inside the EDL's ranges, in video order."""
    words = []
    for r in edl["ranges"]:
        src = edl["sources"].get(r["source"], r["source"])
        for w in load_words(studio, src):
            mid = (w["start"] + w["end"]) / 2
            if r["start"] <= mid <= r["end"]:
                words.append(w)
    return words


def cmd_paper(args):
    studio = Path(args.studio)
    story = load_story(studio)
    edl_p = studio / "edl.json"
    edl = json.loads(edl_p.read_text()) if edl_p.is_file() else story
    lines = ["# Paper edit", "",
             "Everything you said, line by line. **Bold** lines are in the "
             "video; ~~struck~~ lines are cut. Inside kept lines, struck words "
             "are fillers and stutters that are cut. Pauses and untranscribed "
             "ums are cut too but not shown.", ""]
    for key, src in story["sources"].items():
        words = mark(load_words(studio, src), Envelope(src, args.thr_db))
        blocks = [r for r in story["ranges"] if story["sources"].get(r["source"], r["source"]) == src]
        # Phrase lines: break on sentence ends and long pauses.
        cur, phrases = [], []
        for i, w in enumerate(words):
            cur.append(w)
            gap = words[i + 1]["start"] - w["end"] if i + 1 < len(words) else 9
            if w["text"].strip()[-1:] in ".?!" or gap > 0.7 or len(cur) >= 18:
                phrases.append(cur)
                cur = []
        if cur:
            phrases.append(cur)
        lines.append(f"## {Path(src).name}\n")
        for n, p in enumerate(phrases, 1):
            mid = (p[0]["start"] + p[-1]["end"]) / 2
            text = " ".join(f"~~{w['text'].strip()}~~" if w["kind"] in ("filler", "stutter")
                            else w["text"].strip() for w in p)
            hit = next((r for r in blocks if r["start"] <= mid <= r["end"]), None)
            stamp = f"`{p[0]['start']:6.1f}s`"
            if hit:
                order = story["ranges"].index(hit) + 1
                lines.append(f"{n}. {stamp} **{text}**  ← block {order}"
                             f"{' (' + hit['beat'] + ')' if hit.get('beat') else ''}")
            else:
                lines.append(f"{n}. {stamp} ~~{text}~~")
        lines.append("")
    total = sum(r["end"] - r["start"] for r in edl["ranges"])
    lines.append(f"\nVideo length before any speed-up: about {total:.0f} s.\n")
    out = studio / "paper_edit.md"
    out.write_text("\n".join(lines))
    print(f"-> {out}")


def cmd_check(args):
    studio = Path(args.studio)
    mk = studio / "mustkeep.json"
    if not mk.is_file():
        die(f"no {mk}: list the facts that must survive the cut")
    items = json.loads(mk.read_text())["items"]
    edl = json.loads((studio / "edl.json").read_text())
    said = " " + " ".join(norm(w["text"]) for w in kept_words(studio, edl)) + " "
    said = re.sub(r"\s+", " ", said)
    missing = []
    for it in items:
        phrase = " " + " ".join(norm(t) for t in it.split() if norm(t)) + " "
        ok = phrase in said
        print(f"  {'ok  ' if ok else 'MISS'} {it}")
        if not ok:
            missing.append(it)
    if missing:
        print(f"\n{len(missing)} must-keep item(s) not in the cut. Put them back "
              "(or confirm with the person that they can go).", file=sys.stderr)
        return 1
    print(f"\nall {len(items)} must-keep items are in the cut")
    return 0


def main():
    try:
        import numpy  # noqa: F401
    except ImportError:
        die("numpy is required: run with ~/Developer/i-hate-editing/.venv/bin/python")
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    for name in ("scan", "tighten", "paper", "check"):
        p = sub.add_parser(name)
        p.add_argument("--studio", default="studio")
        p.add_argument("--max-pause", type=float, default=0.15,
                       help="pauses longer than this are cut (s)")
        p.add_argument("--thr-db", type=float, default=None,
                       help="speech threshold in dB; default 12 dB over the room")
        if name == "scan":
            p.add_argument("--source", default=None)
        if name == "tighten":
            p.add_argument("--punch", type=float, default=None,
                           help="zoom every other piece, e.g. 1.1, to hide jump cuts")
    args = ap.parse_args()
    return {"scan": cmd_scan, "tighten": cmd_tighten, "paper": cmd_paper,
            "check": cmd_check}[args.cmd](args) or 0


if __name__ == "__main__":
    sys.exit(main())
