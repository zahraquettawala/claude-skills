#!/usr/bin/env python3
"""Guess what kind of video a footage folder is, so the right path is offered.

    detect_mode.py <footage folder>
    detect_mode.py <footage folder> --json

Measures every video: length, how much of it has someone talking, and how
much the picture moves. Then suggests a mode with its reasons:

  talking-head  one or a few long takes, mostly speech, a steady camera
  vlog          many clips through a day or an outing, a moving camera,
                talking mixed with moments and scenery
  montage       clips with little or no talking (cut to music)
  screen        a screen recording (steady picture, landscape, often silent)

It is a suggestion, never the decision: say what it found in one line and let
the person confirm or pick another mode. Needs numpy.
"""

import argparse
import json
import re
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _common import die, probe, sh  # noqa: E402

VIDEO = {".mp4", ".mov", ".m4v", ".mkv"}


def speech_share(path, dur):
    """Share of the clip that is not silence (a stand-in for talking)."""
    if dur <= 0:
        return 0.0
    p = sh(["ffmpeg", "-hide_banner", "-nostats", "-i", str(path), "-vn",
            "-af", "silencedetect=noise=-35dB:d=0.6", "-f", "null", "-"])
    starts = [float(x) for x in re.findall(r"silence_start: ([\d.]+)", p.stderr)]
    ends = [float(x) for x in re.findall(r"silence_end: ([\d.]+)", p.stderr)]
    ends += [dur] * (len(starts) - len(ends))
    silent = sum(max(0.0, e - s) for s, e in zip(starts, ends))
    return max(0.0, min(1.0, 1 - silent / dur))


def motion(path, dur):
    """Mean change between frames sampled every second, 0 (still) to ~1."""
    import numpy as np
    w, h = 64, 36
    step = max(1.0, dur / 120)          # at most ~120 samples per clip
    raw = subprocess.run(["ffmpeg", "-v", "error", "-i", str(path), "-vf",
                          f"fps=1/{step:.2f},scale={w}:{h},format=gray",
                          "-f", "rawvideo", "-"], capture_output=True).stdout
    n = len(raw) // (w * h)
    if n < 2:
        return 0.0
    f = np.frombuffer(raw[:n * w * h], dtype=np.uint8).reshape(n, h, w).astype(float)
    return float(np.abs(np.diff(f, axis=0)).mean() / 255 * 4)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("folder")
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args()
    try:
        import numpy  # noqa: F401
    except ImportError:
        die("numpy is required: run with ~/Developer/i-hate-editing/.venv/bin/python")

    clips = sorted(p for p in Path(args.folder).expanduser().iterdir()
                   if p.suffix.lower() in VIDEO and not p.name.startswith("."))
    if not clips:
        die(f"no videos in {args.folder}")
    rows = []
    for c in clips:
        info = probe(c)
        d = info["duration"]
        rows.append({"file": c.name, "seconds": round(d, 1),
                     "landscape": info["w"] > info["h"],
                     "talking": round(speech_share(c, d) if info["audio"] else 0.0, 2),
                     "motion": round(motion(c, d), 3)})

    total = sum(r["seconds"] for r in rows) or 1
    talk = sum(r["talking"] * r["seconds"] for r in rows) / total
    move = sum(r["motion"] * r["seconds"] for r in rows) / total
    longest = max(r["seconds"] for r in rows)
    n = len(rows)
    why = [f"{n} clip(s), {total / 60:.1f} min in all, longest {longest:.0f} s",
           f"talking in about {talk:.0%} of it",
           f"camera movement {'low' if move < 0.05 else 'medium' if move < 0.12 else 'high'} "
           f"({move:.3f})"]
    if talk < 0.25:
        mode = "montage"
    elif n <= 3 and longest >= 45 and talk >= 0.5 and move < 0.08:
        mode = "talking-head"
    elif all(r["landscape"] for r in rows) and move < 0.03 and talk < 0.5:
        mode = "screen"
    elif n >= 4 or move >= 0.08:
        mode = "vlog"
    else:
        mode = "talking-head"
    sure = (mode == "talking-head" and n <= 2 and move < 0.05) or \
           (mode == "vlog" and n >= 6) or (mode == "montage" and talk < 0.1)

    out = {"suggested": mode, "confident": sure, "why": why, "clips": rows}
    if args.json:
        print(json.dumps(out, indent=2))
    else:
        print(f"suggested mode: {mode}{'' if sure else ' (not sure)'}")
        for w in why:
            print(f"  - {w}")
        for r in rows:
            print(f"    {r['file']:<28} {r['seconds']:7.1f}s  talking {r['talking']:.0%}"
                  f"  motion {r['motion']:.3f}{'  landscape' if r['landscape'] else ''}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
