#!/usr/bin/env python3
"""Final TikTok export, spec check, and safe-zone proof frames.

    tiktok_export.py studio/out/final.mp4 --studio studio
    tiktok_export.py final.mp4 --studio studio --no-music studio/out/master.mp4
    tiktok_export.py final.mp4 --studio studio --frames 3.2 7.9 12.0

Writes into <studio>/out/tiktok/:

  tiktok.mp4           1080x1920, H.264 High, yuv420p, AAC 48k, +faststart,
                       loudness normalised (default -14 LUFS, TP -1)
  tiktok_nomusic.mp4   same, from --no-music: post this one when the music
                       will be added in the TikTok app instead (see
                       rules/tiktok.md, "Trending sounds")
  safe_*.png           frames with TikTok's UI zones shaded red. Read them:
                       nothing that matters may sit in the red.
  report.json          what was checked and what to fix

Frame rate is kept at 30 or 60 when the master is already one of those,
otherwise conformed to 30. A master that is not 9:16 is blur-padded and
flagged, because that means something upstream went wrong.
"""

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _common import H, SAFE, W, die, level_audio, loudness, probe, sh  # noqa: E402


def encode(src, dst, target_lufs, fps):
    info = probe(src)
    if (info["w"], info["h"]) == (W, H):
        vf, graph = f"fps={fps},setsar=1,format=yuv420p", False
    elif abs(info["w"] / max(1, info["h"]) - W / H) < 0.01:
        vf, graph = f"scale={W}:{H}:flags=lanczos,fps={fps},setsar=1,format=yuv420p", False
    else:
        vf, graph = (f"[0:v]split=2[bg][fg];[bg]scale={W}:{H}:force_original_aspect_ratio="
                     f"increase,crop={W}:{H},boxblur=40:2[b];[fg]scale={W}:{H}:"
                     f"force_original_aspect_ratio=decrease[f];[b][f]overlay=(W-w)/2:"
                     f"(H-h)/2,fps={fps},setsar=1,format=yuv420p[v]"), True
    cmd = ["ffmpeg", "-y", "-loglevel", "error", "-i", str(src)]
    wav = Path(dst).with_suffix(".audio.wav")
    if info["audio"]:
        level_audio(src, wav, target_lufs, -1.0)
        cmd += ["-i", str(wav)]
    cmd += ["-filter_complex", vf, "-map", "[v]"] if graph else ["-vf", vf, "-map", "0:v:0"]
    if info["audio"]:
        cmd += ["-map", "1:a:0", "-c:a", "aac", "-b:a", "192k", "-ar", "48000",
                "-ac", "2"]
    cmd += ["-c:v", "libx264", "-profile:v", "high", "-preset", "slow",
            "-crf", "18", "-maxrate", "20M", "-bufsize", "40M",
            "-g", str(fps * 2), "-movflags", "+faststart", str(dst)]
    sh(cmd, check=True)
    wav.unlink(missing_ok=True)
    return info


def safe_frames(video, out_dir, times):
    t, b, l, r = SAFE["top"], SAFE["bottom"], SAFE["left"], SAFE["right"]
    shade = "color=red@0.35:t=fill"
    boxes = ",".join([
        f"drawbox=x=0:y=0:w={W}:h={t}:{shade}",
        f"drawbox=x=0:y={H - b}:w={W}:h={b}:{shade}",
        f"drawbox=x=0:y={t}:w={l}:h={H - t - b}:{shade}",
        f"drawbox=x={W - r}:y={t}:w={r}:h={H - t - b}:{shade}",
        f"drawbox=x={l}:y={t}:w={W - l - r}:h={H - t - b}:color=white@0.9:t=4",
    ])
    paths = []
    for i, ts in enumerate(times):
        p = Path(out_dir) / f"safe_{i:02d}_{ts:.1f}s.png"
        sh(["ffmpeg", "-y", "-loglevel", "error", "-ss", f"{ts:.3f}", "-i", str(video),
            "-frames:v", "1", "-vf", f"{boxes},scale=540:960", str(p)], check=True)
        paths.append(str(p))
    return paths


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("master")
    ap.add_argument("--studio", default="studio")
    ap.add_argument("--no-music", dest="no_music",
                    help="the same edit without the music bed")
    ap.add_argument("--lufs", type=float, default=-14.0)
    ap.add_argument("--frames", type=float, nargs="*",
                    help="times to proof against the safe zones "
                         "(default: 6 spread across the video)")
    args = ap.parse_args()

    src = Path(args.master)
    if not src.is_file():
        die(f"no master at {src}")
    out_dir = Path(args.studio) / "out" / "tiktok"
    out_dir.mkdir(parents=True, exist_ok=True)
    for old in out_dir.glob("safe_*.png"):
        old.unlink()

    info = probe(src)
    fps = int(round(info["fps"])) if int(round(info["fps"])) in (30, 60) else 30
    warn = []
    if (info["w"], info["h"]) != (W, H):
        warn.append(f"master is {info['w']}x{info['h']}, not {W}x{H}; "
                    "fix upstream rather than shipping a padded frame")
    if not info["audio"]:
        warn.append("no audio track: TikTok will treat it as silent; add the "
                    "sound in-app or lay a bed with music.py")

    main_out = out_dir / "tiktok.mp4"
    encode(src, main_out, args.lufs, fps)
    outs = {"tiktok": str(main_out)}
    if args.no_music:
        nm = out_dir / "tiktok_nomusic.mp4"
        encode(Path(args.no_music), nm, args.lufs, fps)
        outs["tiktok_nomusic"] = str(nm)
        if abs(probe(nm)["duration"] - probe(main_out)["duration"]) > 0.1:
            warn.append("the no-music export is a different length from the "
                        "main one; they should be the same edit")

    final = probe(main_out)
    dur = final["duration"]
    lufs, tp, _ = loudness(main_out) if final["audio"] else (None, None, None)
    if dur < 3:
        warn.append(f"{dur:.1f}s is too short to register a view")
    if dur > 600:
        warn.append(f"{dur / 60:.1f} min is over the in-app upload limit; "
                    "upload from desktop web")
    size_mb = main_out.stat().st_size / 1e6

    times = args.frames or [round(dur * f, 2) for f in (0.03, 0.2, 0.4, 0.6, 0.8, 0.96)]
    frames = safe_frames(main_out, out_dir, times)

    report = {"outputs": outs, "duration": round(dur, 2),
              "size": f"{final['w']}x{final['h']}", "fps": fps,
              "video": final["vcodec"], "audio": final["acodec"],
              "lufs": lufs, "true_peak": tp, "megabytes": round(size_mb, 1),
              "safe_zone_frames": frames, "safe_zone_px": SAFE,
              "warnings": warn}
    (out_dir / "report.json").write_text(json.dumps(report, indent=2))

    print(f"tiktok.mp4  {final['w']}x{final['h']}@{fps} · {dur:.1f}s · "
          f"{size_mb:.1f} MB" + (f" · {lufs:.1f} LUFS, TP {tp:.1f}" if lufs is not None else ""))
    for k, v in outs.items():
        print(f"  {k:<15} {v}")
    print(f"  safe-zone frames: {len(frames)} in {out_dir} (read them)")
    for w in warn:
        print(f"  warning: {w}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
