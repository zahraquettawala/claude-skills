"""Shared helpers for tiktok-edit scripts. Standard library only."""

import json
import os
import subprocess
import sys
from pathlib import Path

W, H, FPS = 1080, 1920, 30

# TikTok's interface sits on top of the video. These are conservative margins
# in the 1080x1920 frame, measured off the For You feed. They are approximate
# and the app moves them now and then, so leave slack instead of designing to
# the pixel.
SAFE = {"top": 160, "bottom": 480, "left": 60, "right": 140}


def sh(cmd, check=False):
    p = subprocess.run(cmd, capture_output=True, text=True, errors="replace")
    if check and p.returncode != 0:
        die(f"{cmd[0]} failed:\n{p.stderr[-1200:]}")
    return p


def die(msg):
    print(f"error: {msg}", file=sys.stderr)
    sys.exit(1)


def _rotation(path):
    out = sh(["ffprobe", "-v", "error", "-select_streams", "v:0",
              "-show_entries", "stream_side_data=rotation",
              "-show_entries", "stream_tags=rotate", "-of", "json", str(path)]).stdout
    try:
        st = (json.loads(out or "{}").get("streams") or [{}])[0]
    except json.JSONDecodeError:
        return 0
    val = next((sd["rotation"] for sd in st.get("side_data_list") or []
                if "rotation" in sd), (st.get("tags") or {}).get("rotate"))
    try:
        return int(abs(float(val))) % 360 if val is not None else 0
    except (TypeError, ValueError):
        return 0


def probe(path):
    """Rotation-aware probe: dict(w, h, fps, duration, audio, vcodec).

    Phone footage stores a rotation matrix instead of rotated pixels, so the
    raw stream width/height is wrong for vertical clips (i-hate-editing hard
    rule 9d). Always size from here."""
    out = sh(["ffprobe", "-v", "error", "-show_entries",
              "stream=codec_type,codec_name,width,height,avg_frame_rate",
              "-show_entries", "format=duration", "-of", "json", str(path)]).stdout
    try:
        d = json.loads(out or "{}")
    except json.JSONDecodeError:
        d = {}
    streams = d.get("streams") or []
    v = next((s for s in streams if s.get("codec_type") == "video"), {})
    a = next((s for s in streams if s.get("codec_type") == "audio"), None)
    w, h = v.get("width") or 0, v.get("height") or 0
    if v and _rotation(path) in (90, 270):
        w, h = h, w
    try:
        num, den = (v.get("avg_frame_rate") or "0/1").split("/")
        fps = float(num) / float(den) if float(den) else 0.0
    except ValueError:
        fps = 0.0
    try:
        dur = float((d.get("format") or {}).get("duration") or 0)
    except (TypeError, ValueError):
        dur = 0.0
    return {"w": w, "h": h, "fps": fps, "duration": dur,
            "audio": a is not None, "vcodec": v.get("codec_name"),
            "acodec": a.get("codec_name") if a else None}


def ihe_dir():
    """Locate the i-hate-editing checkout this skill layers on."""
    cands = [os.environ.get("IHE_DIR"),
             "~/.claude/skills/i-hate-editing",
             "~/Developer/i-hate-editing",
             "~/.agents/skills/i-hate-editing"]
    for c in cands:
        if c and (Path(c).expanduser() / "SKILL.md").is_file():
            return Path(c).expanduser().resolve()
    return None


def loudness(path):
    """Integrated LUFS and true peak via a loudnorm measurement pass."""
    p = sh(["ffmpeg", "-hide_banner", "-nostats", "-i", str(path), "-vn",
            "-af", "loudnorm=print_format=json", "-f", "null", "-"])
    txt = p.stderr
    i = txt.rfind("{")
    try:
        m = json.loads(txt[i:txt.rfind("}") + 1])
        return float(m["input_i"]), float(m["input_tp"]), m
    except (ValueError, KeyError):
        return None, None, None


def loudnorm_filter(path, target_i, target_tp=-1.0, lra=11):
    """Two-pass linear loudnorm filter string, measured against `path`."""
    _, _, m = loudness(path)
    if not m or m.get("input_i") in (None, "-inf"):
        return f"loudnorm=I={target_i}:TP={target_tp}:LRA={lra}"
    return (f"loudnorm=I={target_i}:TP={target_tp}:LRA={lra}"
            f":measured_I={m['input_i']}:measured_TP={m['input_tp']}"
            f":measured_LRA={m['input_lra']}:measured_thresh={m['input_thresh']}"
            f":offset={m['target_offset']}:linear=true")


def level_audio(src, dst, target_i, target_tp=-1.0, tol=0.5):
    """Bring `src`'s audio to target_i LUFS with peaks under target_tp; write
    a 48k stereo WAV to `dst`. Returns the measured (LUFS, TP) of the result.

    loudnorm alone cannot do this for a peaky mix: when the gain needed would
    push the true peak over the ceiling, linear mode is impossible and its
    dynamic fallback undershoots by several LU on a short clip. So it is gain
    into a limiter, re-measured and corrected until it lands within `tol`.
    The limiter ceiling sits 1.5 dB under target_tp because the AAC encode
    that follows adds intersample overs of about that much."""
    i, _, _ = loudness(src)
    if i is None or i == float("-inf"):
        die(f"could not measure loudness of {src}")
    ceiling = 10 ** ((target_tp - 1.5) / 20)
    gain, out_i, out_tp = target_i - i, None, None
    for _ in range(4):
        sh(["ffmpeg", "-y", "-loglevel", "error", "-i", str(src), "-vn",
            "-af", f"volume={gain:.2f}dB,alimiter=limit={ceiling:.4f}:attack=5:"
                   f"release=60:level=disabled,aresample=48000",
            "-ar", "48000", "-ac", "2", str(dst)], check=True)
        out_i, out_tp, _ = loudness(dst)
        if out_i is None or abs(target_i - out_i) <= tol:
            break
        gain += target_i - out_i
    return out_i, out_tp
