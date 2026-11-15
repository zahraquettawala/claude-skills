#!/usr/bin/env python3
"""Find dead time in a screen recording and write an EDL that drops it.

A screen recording's dead time is the screen sitting still while nobody
talks: waiting for a build, hunting for a tab, the long pause before the
click. Talking-head cutting finds it from the transcript; with no speech, or
speech over a static screen, the pixels have to be read too.

    dead_time.py screen.mov --studio studio                 # silent recording
    dead_time.py screen.mov --studio studio --narrated      # voice over it

Silent recording: every stretch where the frame is frozen for longer than
--min-freeze is cut down to --hold seconds of stillness (enough for the eye
to land on the result).

Narrated: a stretch is only dead when the frame is frozen AND nobody is
talking, so explanations over a still screen are kept. For narrated takes,
prefer i-hate-editing's transcript-driven cut first and run this as a second
pass on what remains.

Writes <studio>/edl.json in i-hate-editing's format, so render.py renders it
and verify.py checks it. Prints a table of what it dropped so the call can be
checked before rendering. Does not touch the source.
"""

import argparse
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _common import die, probe, sh  # noqa: E402


def intervals(stderr, start_key, end_key):
    starts = [float(x) for x in re.findall(rf"{start_key}: ?([\d.]+)", stderr)]
    ends = [float(x) for x in re.findall(rf"{end_key}: ?([\d.]+)", stderr)]
    return starts, ends


def freezes(src, noise, min_dur, total):
    p = sh(["ffmpeg", "-hide_banner", "-nostats", "-i", str(src), "-an",
            "-vf", f"freezedetect=n={noise}:d={min_dur}", "-f", "null", "-"])
    s, e = intervals(p.stderr, "lavfi.freezedetect.freeze_start",
                     "lavfi.freezedetect.freeze_end")
    e += [total] * (len(s) - len(e))      # frozen through to the end
    return list(zip(s, e))


def silences(src, noise, min_dur, total):
    p = sh(["ffmpeg", "-hide_banner", "-nostats", "-i", str(src), "-vn",
            "-af", f"silencedetect=noise={noise}:d={min_dur}", "-f", "null", "-"])
    s, e = intervals(p.stderr, "silence_start", "silence_end")
    e += [total] * (len(s) - len(e))
    return list(zip(s, e))


def intersect(a, b):
    out, i, j = [], 0, 0
    while i < len(a) and j < len(b):
        lo, hi = max(a[i][0], b[j][0]), min(a[i][1], b[j][1])
        if hi > lo:
            out.append((lo, hi))
        if a[i][1] < b[j][1]:
            i += 1
        else:
            j += 1
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("source")
    ap.add_argument("--studio", default="studio")
    ap.add_argument("--narrated", action="store_true")
    ap.add_argument("--min-freeze", type=float, default=1.2,
                    help="stillness shorter than this is left alone")
    ap.add_argument("--hold", type=float, default=0.45,
                    help="stillness kept from each dead stretch")
    ap.add_argument("--freeze-noise", default="0.003",
                    help="freezedetect threshold; raise it if a blinking "
                         "cursor or clock keeps a frame 'moving'")
    ap.add_argument("--silence-noise", default="-35dB")
    ap.add_argument("-o", "--out")
    args = ap.parse_args()

    src = Path(args.source).expanduser().resolve()
    info = probe(src)
    if not info["w"]:
        die(f"could not probe {src}")
    total = info["duration"]

    dead = freezes(src, args.freeze_noise, args.min_freeze, total)
    if args.narrated:
        if not info["audio"]:
            die("--narrated but the source has no audio track")
        dead = intersect(dead, silences(src, args.silence_noise,
                                        args.min_freeze, total))
    dead = [(a, b) for a, b in dead if b - a >= args.min_freeze]

    # Keep the first `hold` seconds of each dead stretch, drop the rest.
    keep, cursor, dropped = [], 0.0, []
    for a, b in dead:
        cut_from = a + args.hold
        if cut_from > cursor:
            keep.append((cursor, cut_from))
        dropped.append((cut_from, b))
        cursor = b
    if total - cursor > 0.05:
        keep.append((cursor, total))

    studio = Path(args.studio)
    studio.mkdir(parents=True, exist_ok=True)
    edl = {"sources": {"screen": str(src)},
           "ranges": [{"source": "screen", "start": round(a, 3),
                       "end": round(b, 3), "beat": f"k{i}",
                       "reason": "between dead stretches"}
                      for i, (a, b) in enumerate(keep)],
           "pad": {"in": 0.03, "out": 0.03}, "grade": None}
    out = Path(args.out) if args.out else studio / "edl.json"
    out.write_text(json.dumps(edl, indent=1))

    cut = sum(b - a for a, b in dropped)
    for a, b in dropped:
        print(f"  drop {a:7.2f}-{b:7.2f}  ({b - a:5.2f}s still"
              f"{', silent' if args.narrated else ''})")
    print(f"{len(dropped)} dead stretch(es) · {total:.1f}s -> "
          f"{total - cut:.1f}s ({cut / total * 100 if total else 0:.0f}% cut)"
          f"\n-> {out}")
    if info["w"] / max(1, info["h"]) > 0.6:
        print("note: landscape source; reframe with fit_vertical.py "
              "(--mode panel or region) before render.py, or render.py "
              "letterboxes it")


if __name__ == "__main__":
    main()
