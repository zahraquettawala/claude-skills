#!/usr/bin/env python3
"""Clean and level a voice with ffmpeg alone: the stand-in for Adobe Enhance.

i-hate-editing's step 9 runs Adobe Podcast Enhance through its author's
signed-in ego-browser session. Most machines do not have that. This is the
local fallback: not as strong on a bad room, but it never leaves the machine,
needs no account, and lands the voice at the same level step 9 expects, so
every sound rule downstream still holds.

    voice_clean.py studio/cut.mp4 --remux               # writes cut_clean.mp4
    voice_clean.py voiceover.wav -o vo_clean.wav
    voice_clean.py studio/cut.mp4 --remux --denoise strong

Chain: high-pass at 80 Hz (rumble, desk bumps) -> FFT denoise -> de-ess ->
gentle compression -> two-pass linear loudnorm to -18.4 LUFS, true peak -1.5
(i-hate-editing's enhanced-voice target, so stings measured against it sit
where rules/sound.md says).

--remux copies the video stream untouched and swaps the audio, so no
timestamp moves. Duration is checked against the input; it fails over 50ms
drift, as enhance.py does.
"""

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _common import die, level_audio, loudness, probe, sh  # noqa: E402

DENOISE = {"off": None, "light": "afftdn=nr=8:nf=-30:tn=1",
           "normal": "afftdn=nr=12:nf=-28:tn=1",
           "strong": "afftdn=nr=20:nf=-25:tn=1"}
TARGET_I, TARGET_TP = -18.4, -1.5


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("source")
    ap.add_argument("-o", "--out")
    ap.add_argument("--remux", action="store_true",
                    help="source is a video: keep its picture, swap the audio")
    ap.add_argument("--denoise", default="normal", choices=list(DENOISE))
    ap.add_argument("--target", type=float, default=TARGET_I)
    args = ap.parse_args()

    src = Path(args.source)
    info = probe(src)
    if not info["audio"]:
        die(f"{src} has no audio")
    pre = ["highpass=f=80", DENOISE[args.denoise], "deesser=i=0.4",
           "acompressor=threshold=0.05:ratio=3:attack=8:release=120:makeup=1.5"]
    pre = ",".join(p for p in pre if p)

    stage = src.with_name(src.stem + "_stage.wav")
    sh(["ffmpeg", "-y", "-loglevel", "error", "-i", str(src), "-vn",
        "-af", pre, "-ar", "48000", "-ac", "2", str(stage)], check=True)
    leveled = src.with_name(src.stem + "_level.wav")
    level_audio(stage, leveled, args.target, TARGET_TP)
    stage.unlink(missing_ok=True)

    if args.remux:
        out = Path(args.out) if args.out else src.with_name(src.stem + "_clean.mp4")
        sh(["ffmpeg", "-y", "-loglevel", "error", "-i", str(src), "-i", str(leveled),
            "-map", "0:v:0", "-map", "1:a:0", "-c:v", "copy", "-c:a", "aac",
            "-b:a", "192k", "-movflags", "+faststart", str(out)], check=True)
        leveled.unlink(missing_ok=True)
    else:
        out = Path(args.out) if args.out else src.with_name(src.stem + "_clean.wav")
        leveled.replace(out)

    drift = abs(probe(out)["duration"] - info["duration"])
    lufs, tp, _ = loudness(out)
    print(f"{src.name} -> {out}  {lufs:.1f} LUFS, TP {tp:.1f} dBTP, "
          f"drift {drift * 1000:.0f}ms")
    if drift > 0.05:
        die("duration drifted over 50ms; every timestamp downstream is now off")


if __name__ == "__main__":
    main()
