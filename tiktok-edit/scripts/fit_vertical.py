#!/usr/bin/env python3
"""Reformat any source to a 1080x1920 TikTok frame before it enters the cut.

i-hate-editing's render.py sizes every segment to the FIRST source and
letterboxes the rest with black bars. That is fine for one phone camera, and
wrong the moment a montage mixes landscape B-roll, a screen recording and
vertical phone clips. Fit each source here first, then point the EDL at the
fitted copies.

    fit_vertical.py clip.mp4 -o fitted/clip.mp4                    # auto
    fit_vertical.py land.mp4 -o f.mp4 --mode crop --focus-x 0.62
    fit_vertical.py screen.mov -o f.mp4 --mode panel --panel-y 0.14
    fit_vertical.py screen.mov -o f.mp4 --mode region --region 0.55,0.1,0.4,0.5
    fit_vertical.py *.mp4 --out-dir fitted/                         # batch

Modes:
  auto    vertical stays as is; landscape and square go to `blur`.
  crop    fill the frame and crop the sides. --focus-x picks which part
          survives (0 = left edge, 1 = right edge). For B-roll with one subject.
  blur    whole frame visible, centred over a blurred copy of itself.
  panel   whole frame at full width near the top, dark ground below. For screen
          recordings that need room for a face, captions or a card underneath.
  region  crop to one area of the source (x,y,w,h as fractions), then fill. For
          zooming into the part of a screen recording that matters.

Every output carries an audio track (silent if the source had none), because
render.py fades audio on every segment and fails on a video-only file.
"""

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _common import FPS, H, W, die, probe, sh  # noqa: E402


def vfilter(info, mode, focus_x, focus_y, panel_y, region, ground):
    sw, sh_ = info["w"], info["h"]
    if mode == "auto":
        mode = "crop" if abs(sw / sh_ - W / H) < 0.02 else (
            "crop" if sw / sh_ < W / H else "blur")
    if mode == "crop":
        return (f"scale={W}:{H}:force_original_aspect_ratio=increase:flags=lanczos,"
                f"crop={W}:{H}:(iw-{W})*{focus_x:.3f}:(ih-{H})*{focus_y:.3f}"), mode
    if mode == "region":
        x, y, w, h = region
        return (f"crop=iw*{w:.4f}:ih*{h:.4f}:iw*{x:.4f}:ih*{y:.4f},"
                f"scale={W}:{H}:force_original_aspect_ratio=increase:flags=lanczos,"
                f"crop={W}:{H}"), mode
    if mode == "blur":
        return (f"split=2[bg][fg];"
                f"[bg]scale={W}:{H}:force_original_aspect_ratio=increase,"
                f"crop={W}:{H},boxblur=40:2,eq=brightness=-0.08[bgb];"
                f"[fg]scale={W}:{H}:force_original_aspect_ratio=decrease:flags=lanczos[fgs];"
                f"[bgb][fgs]overlay=(W-w)/2:(H-h)/2"), mode
    if mode == "panel":
        y = int(H * panel_y)
        return (f"scale={W}:-2:flags=lanczos,"
                f"pad={W}:{H}:0:min({y}\\,{H}-ih):color={ground}"), mode
    die(f"unknown mode {mode}")


def fit(src, dst, args):
    info = probe(src)
    if not info["w"]:
        die(f"could not probe {src}")
    vf, used = vfilter(info, args.mode, args.focus_x, args.focus_y,
                       args.panel_y, args.region, args.ground)
    vf += f",fps={args.fps},setsar=1,format=yuv420p"
    cmd = ["ffmpeg", "-y", "-loglevel", "error", "-i", str(src)]
    if not info["audio"]:
        cmd += ["-f", "lavfi", "-i", "anullsrc=r=48000:cl=stereo"]
    cmd += ["-filter_complex" if ";" in vf else "-vf", vf if ";" not in vf
            else f"[0:v]{vf}[v]"]
    cmd += ["-map", "[v]" if ";" in vf else "0:v:0",
            "-map", "0:a:0" if info["audio"] else "1:a:0", "-shortest",
            "-c:v", "libx264", "-preset", "medium", "-crf", str(args.crf),
            "-c:a", "aac", "-b:a", "192k", "-ar", "48000", "-ac", "2",
            "-movflags", "+faststart", str(dst)]
    Path(dst).parent.mkdir(parents=True, exist_ok=True)
    sh(cmd, check=True)
    print(f"{Path(src).name}: {info['w']}x{info['h']} -> {W}x{H} [{used}]"
          f"{'' if info['audio'] else ' +silent audio'}  -> {dst}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("sources", nargs="+")
    ap.add_argument("-o", "--out")
    ap.add_argument("--out-dir")
    ap.add_argument("--mode", default="auto",
                    choices=["auto", "crop", "blur", "panel", "region"])
    ap.add_argument("--focus-x", type=float, default=0.5)
    ap.add_argument("--focus-y", type=float, default=0.5)
    ap.add_argument("--panel-y", type=float, default=0.14,
                    help="top of the panel as a share of frame height; 0.14 "
                         "clears TikTok's header")
    ap.add_argument("--region", default="0,0,1,1",
                    help="x,y,w,h as fractions of the source frame")
    ap.add_argument("--ground", default="0x0d0d10")
    ap.add_argument("--fps", type=int, default=FPS)
    ap.add_argument("--crf", type=int, default=18)
    args = ap.parse_args()
    try:
        args.region = [float(v) for v in args.region.split(",")]
        assert len(args.region) == 4
    except (ValueError, AssertionError):
        die("--region wants x,y,w,h")

    if len(args.sources) > 1 or args.out_dir:
        if not args.out_dir:
            die("several sources need --out-dir")
        for s in args.sources:
            fit(s, Path(args.out_dir) / (Path(s).stem + ".mp4"), args)
    else:
        if not args.out:
            die("give -o or --out-dir")
        fit(args.sources[0], args.out, args)


if __name__ == "__main__":
    main()
